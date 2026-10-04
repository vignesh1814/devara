"""Stage orchestration: source -> tokens -> AST -> typed tree -> IR -> asm -> exe.

Each ``run_*`` function takes the previous stage's artifact and returns
``(artifact_or_None, diagnostics)``. A stage that reports diagnostics yields
``None`` so later stages never see a malformed artifact (plan §F).

Artifacts can be stored as JSON *envelopes* (``{"devara": <kind>, ...}``) so
that any stage output can be fed back into the next stage via the CLI.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from compiler import serialize
from compiler.diagnostics import Diagnostic, InternalCompilerError
from compiler.lexer import Lexer
from compiler.lexer import tokens as _tokens_mod

STAGES = ("tokens", "ast", "typed", "ir", "asm")
ENVELOPE_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_SRC = REPO_ROOT / "runtime" / "devara_rt.c"


def _register_serializable() -> None:
    from compiler import ast as _ast_pkg  # noqa: F401
    from compiler.ast import nodes as ast_nodes
    from compiler import diagnostics

    serialize.register(_tokens_mod, ast_nodes, diagnostics)
    for modname in ("compiler.semantic.types", "compiler.semantic.typed", "compiler.ir.ir"):
        try:
            mod = __import__(modname, fromlist=["_"])
        except ImportError:
            continue
        serialize.register(mod)


# ── Source loading ──

def decode_source(data: bytes) -> str:
    """Sources are byte strings; each byte is one character unit (latin-1).

    This matches the language's 8-bit ``char`` model (L40): non-ASCII bytes can
    only appear in comments and string/char literals, and are preserved 1:1.
    """
    return data.decode("latin-1")


# ── Stage functions ──

def run_lex(source: str, filename: str) -> tuple[list | None, list[Diagnostic]]:
    lexer = Lexer(source, filename=filename)
    toks = lexer.tokenize()
    if lexer.has_errors:
        return None, list(lexer.errors)
    return toks, []


def run_parse(tokens: list, filename: str):
    from compiler.parser import Parser

    parser = Parser(tokens, filename=filename)
    program = parser.parse()
    if parser.errors:
        return None, list(parser.errors)
    return program, []


def run_sema(program, filename: str):
    from compiler.semantic import analyze

    return analyze(program, filename)


def run_lower(typed):
    from compiler.ir.lower import lower_program

    return lower_program(typed)


def run_opt(module, level: int):
    from compiler.opt import optimize

    return optimize(module, level)


def run_codegen(module) -> str:
    from compiler.codegen.x86_64 import generate

    return generate(module)


# ── Envelopes ──

def to_envelope(kind: str, obj: Any, filename: str) -> dict:
    body = serialize.to_data(obj)
    return {"devara": kind, "version": ENVELOPE_VERSION, "file": filename, "data": body}


def envelope_json(kind: str, obj: Any, filename: str) -> str:
    return json.dumps(to_envelope(kind, obj, filename), indent=2)


def from_envelope(text: str) -> tuple[str, Any, str]:
    _register_serializable()
    doc = json.loads(text)
    if not isinstance(doc, dict) or "devara" not in doc or "data" not in doc:
        raise ValueError("not a devara stage envelope")
    kind = doc["devara"]
    if kind not in STAGES:
        raise ValueError(f"unknown envelope kind {kind!r}")
    return kind, serialize.from_data(doc["data"]), doc.get("file", "<json>")


_register_serializable()


# ── Toolchain ──

def runtime_object(cache_dir: Path | None = None) -> Path:
    """Compile ``runtime/devara_rt.c`` once per content hash and cache the object."""
    src = RUNTIME_SRC.read_bytes()
    digest = hashlib.sha256(src).hexdigest()[:16]
    cache = cache_dir or (REPO_ROOT / "build" / "rtcache")
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError:
        cache = Path(tempfile.gettempdir()) / "devara_rtcache"
        cache.mkdir(parents=True, exist_ok=True)
    obj = cache / f"devara_rt_{digest}.o"
    if not obj.exists():
        tmp = obj.with_suffix(f".{os.getpid()}.tmp")
        proc = subprocess.run(
            ["gcc", "-O2", "-c", str(RUNTIME_SRC), "-o", str(tmp)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise InternalCompilerError(f"runtime failed to compile:\n{proc.stderr}")
        os.replace(tmp, obj)
    return obj


def link_executable(asm_text: str, out: Path) -> None:
    """Assemble ``asm_text`` and link with the runtime into ``out``."""
    if shutil.which("gcc") is None:
        raise InternalCompilerError("gcc not found: cannot assemble/link")
    rt = runtime_object()
    with tempfile.TemporaryDirectory(prefix="devara_") as tmp:
        asm_path = Path(tmp) / "prog.s"
        asm_path.write_text(asm_text)
        proc = subprocess.run(
            ["gcc", "-no-pie", str(asm_path), str(rt), "-o", str(out), "-lm"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise InternalCompilerError(
                f"assembler/linker rejected generated code:\n{proc.stderr}"
            )
