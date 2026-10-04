"""Shared helpers for the black-box validation suite.

Everything goes through the public CLI (`./devara`, plan §E) as a subprocess.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEVARA = ROOT / "devara"
WORK = ROOT / "build" / "validation_work"
WORK.mkdir(parents=True, exist_ok=True)

DIAG_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<stage>lexical|syntax|semantic) error "
                     r"\[(?P<cat>[A-Z_]+)\]: (?P<msg>.*)$")

LEX_CATS = {"INVALID_CHARACTER", "UNTERMINATED_STRING", "UNTERMINATED_CHAR", "INVALID_ESCAPE",
            "INVALID_CHAR_LITERAL", "INVALID_NUMBER"}
SYN_CATS = {"UNEXPECTED_TOKEN", "UNEXPECTED_EOF", "MISSING_TOKEN", "INVALID_EXPRESSION",
            "INVALID_STATEMENT", "INVALID_DECLARATION"}
SEM_CATS = {"UNDECLARED", "REDECLARATION", "TYPE_MISMATCH", "INVALID_CONVERSION", "INVALID_OPERAND",
            "NOT_ASSIGNABLE", "NOT_CALLABLE", "NOT_INDEXABLE", "TOO_MANY_INDICES", "ARGUMENT_COUNT",
            "INVALID_RETURN", "MISSING_RETURN", "BREAK_OUTSIDE_LOOP", "CONTINUE_OUTSIDE_LOOP",
            "UNINITIALIZED", "VOID_MISUSE", "INVALID_ARRAY_SIZE", "LITERAL_OUT_OF_RANGE",
            "INVALID_CONDITION"}
# implicit-conversion failures: the plan names INVALID_CONVERSION only for casts (P27) and
# TYPE_MISMATCH generally; both are accepted for implicit failures (see OPEN_QUESTIONS).
IMPLICIT_BAD = {"TYPE_MISMATCH", "INVALID_CONVERSION"}


@dataclass
class Proc:
    rc: int
    out: bytes
    err: str

    @property
    def text(self) -> str:
        return self.out.decode("latin-1")

    def diags(self):
        res = []
        for line in self.err.splitlines():
            m = DIAG_RE.match(line)
            if m:
                res.append((m["stage"], m["cat"], int(m["line"]), int(m["col"]), m["msg"]))
        return res


def run_cli(args: list[str], stdin: bytes = b"", timeout: float = 120) -> Proc:
    p = subprocess.run([str(DEVARA), *args], input=stdin, capture_output=True, timeout=timeout)
    return Proc(p.returncode, p.stdout, p.stderr.decode("utf-8", "replace"))


@lru_cache(maxsize=None)
def _write(src: str) -> str:
    h = hashlib.sha1(src.encode("latin-1", "replace")).hexdigest()[:16]
    p = WORK / f"t_{h}.tel"
    p.write_bytes(src.encode("latin-1"))
    return str(p)


@lru_cache(maxsize=4096)
def cli(cmd: str, src: str, flags: tuple = (), stdin: bytes = b"") -> Proc:
    """Run `devara [flags-before] CMD [flags] FILE` on a source string (cached)."""
    path = _write(src)
    pre = [f for f in flags if f in ("-O0", "-O1")]
    post = [f for f in flags if f not in ("-O0", "-O1")]
    return run_cli([*pre, cmd, *post, path], stdin)


def prog(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def accepts(src: str, upto: str = "sema"):
    """Source must pass every front-end stage up to `upto` (exit 0)."""
    p = cli(upto, src)
    assert p.rc == 0, f"expected acceptance, got rc={p.rc}\n{p.err}\n--- source ---\n{src}"
    return p


def rejects(src: str, stage: str, cats, upto: str = "sema"):
    """Source must be rejected with a diagnostic of the given stage and a category in `cats`."""
    if isinstance(cats, str):
        cats = {cats}
    p = cli(upto, src)
    assert p.rc == 1, f"expected exit 1 (user error), got {p.rc}\nstderr: {p.err}\n--- source ---\n{src}"
    ds = p.diags()
    assert ds, f"no well-formed diagnostic in stderr: {p.err!r}"
    assert any(d[0] == stage and d[1] in cats for d in ds), \
        f"expected {stage} error in {sorted(cats)}, got {[(d[0], d[1]) for d in ds]}\n--- source ---\n{src}"
    for d in ds:
        assert d[2] >= 1 and d[3] >= 1, f"bad position in diagnostic {d}"
        assert d[1] in LEX_CATS | SYN_CATS | SEM_CATS, f"category {d[1]} outside the closed sets"
    return p


def run(src: str, stdin: bytes = b"", opt: str = "-O1") -> Proc:
    """Compile and run through `devara run`; program exit status passes through."""
    return cli("run", src, (opt,), stdin)


def fmt_float(x: float) -> str:
    return "%g" % x


OPTS = ["-O0", "-O1"]


