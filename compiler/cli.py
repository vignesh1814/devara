"""Devara command line interface (plan §E).

    devara lex|parse|sema|ir|opt|asm|build|run [options] FILE

Exit status: 0 success; 1 user-program error; 2 usage / I/O error;
3 internal compiler error. ``run`` returns the program's own status.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from compiler import driver, serialize
from compiler.codegen.target import TARGETS as _TARGETS, get_target
from compiler.diagnostics import Diagnostic, InternalCompilerError

EXIT_OK, EXIT_USER, EXIT_USAGE, EXIT_ICE = 0, 1, 2, 3

_TARGET_NAMES = tuple(_TARGETS)
_STAGE_ORDER = {name: i for i, name in enumerate(["source", *driver.STAGES])}


class _Fail(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="devara", description="Devara compiler (Romanized-Telugu language)"
    )
    ap.add_argument("-O0", dest="opt_level", action="store_const", const=0,
                    help="disable optimization")
    ap.add_argument("-O1", dest="opt_level", action="store_const", const=1,
                    help="enable optimization (default)")
    ap.add_argument("--target", choices=sorted(_TARGET_NAMES), default=None,
                    help="code-generation target (default: host OS)")
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name: str, help_: str, *, json_flag=False, opt=False, out=False):  # noqa: C901
        p = sub.add_parser(name, help=help_)
        p.add_argument("file", metavar="FILE", help="source file, stage JSON, or '-' for stdin")
        if json_flag:
            p.add_argument("--json", action="store_true", help="emit stage JSON")
        if opt:
            p.add_argument("-O0", dest="opt_level", action="store_const", const=0,
                           default=argparse.SUPPRESS, help="disable optimization")
            p.add_argument("-O1", dest="opt_level", action="store_const", const=1,
                           default=argparse.SUPPRESS, help="enable optimization (default)")
        if opt:
            p.add_argument("--target", choices=sorted(_TARGET_NAMES), default=argparse.SUPPRESS,
                           help="code-generation target (default: host OS)")
        if out:
            p.add_argument("-o", dest="output", metavar="OUT", help="output executable")
        return p

    add("lex", "tokenize", json_flag=True)
    add("parse", "parse to AST", json_flag=True)
    add("sema", "semantic analysis (typed tree)", json_flag=True)
    add("ir", "lower to IR (unoptimized)", json_flag=True)
    add("opt", "optimized IR", json_flag=True)
    add("asm", "x86-64 assembly", opt=True)
    add("build", "build an executable", opt=True, out=True)
    add("run", "build and run", opt=True)
    return ap


def _read_input(file: str) -> tuple[str, bytes]:
    if file == "-":
        return "<stdin>", sys.stdin.buffer.read()
    p = Path(file)
    try:
        return file, p.read_bytes()
    except OSError as e:
        print(f"devara: cannot read {file}: {e.strerror}", file=sys.stderr)
        raise _Fail(EXIT_USAGE)


def _check_output_path(out: Path, filename: str) -> None:
    """Writing the requested output is an I/O matter (exit 2), checked before the toolchain runs."""
    parent = out.parent if str(out.parent) else Path(".")
    reason = None
    if out.is_dir():
        reason = "Is a directory"
    elif not parent.exists():
        reason = "No such file or directory"
    elif not parent.is_dir():
        reason = "Not a directory"
    elif not os.access(parent, os.W_OK) or (out.exists() and not os.access(out, os.W_OK)):
        reason = "Permission denied"
    if reason is not None:
        print(f"{filename}: error: cannot write output '{out}': {reason}", file=sys.stderr)
        raise _Fail(EXIT_USAGE)


def _output_path(args, filename: str, target) -> Path:
    out = Path(args.output) if args.output else Path(Path(filename).stem or "a.out")
    return driver.executable_path(out, target)


def _link(asm_text: str, out: Path, pipe: "_Pipeline", filename: str, target=None) -> None:
    try:
        driver.link_executable(asm_text, out, *(() if target is None else (target,)))
    except driver.AssemblerError as e:
        if pipe.kind != "asm":
            raise                      # generated code rejected: compiler bug (exit 3)
        print(f"{filename}: assembler error: {e.tool_output.strip()}", file=sys.stderr)
        raise _Fail(EXIT_USER)


def _report(diags: list[Diagnostic]) -> None:
    for d in diags:
        print(d.format(), file=sys.stderr)


class _Pipeline:
    """Runs stages from whatever representation the input file holds."""

    def __init__(self, filename: str, data: bytes, opt_level: int) -> None:
        self.filename = filename
        self.opt_level = opt_level
        self.kind = "source"
        self.value: object = None
        self.asm_text: str | None = None
        if filename.endswith(".json"):
            try:
                self.kind, self.value, _ = driver.from_envelope(data.decode("utf-8"))
            except (ValueError, KeyError, TypeError) as e:
                print(f"{filename}: not a valid devara stage JSON: {e}", file=sys.stderr)
                raise _Fail(EXIT_USAGE)
        elif filename.endswith(".s"):
            self.kind = "asm"
            self.asm_text = data.decode("latin-1")
        else:
            self.value = driver.decode_source(data)

    def advance(self, target: str) -> object:
        """Run stages until the artifact of kind ``target`` exists; return it."""
        if _STAGE_ORDER[self.kind] > _STAGE_ORDER[target]:
            print(
                f"{self.filename}: input is already at stage '{self.kind}', "
                f"cannot produce earlier stage '{target}'",
                file=sys.stderr,
            )
            raise _Fail(EXIT_USAGE)
        while self.kind != target:
            self._step()
        return self.value

    def _step(self) -> None:
        k = self.kind
        if k == "source":
            toks, diags = driver.run_lex(self.value, self.filename)
            self._check(diags)
            self.kind, self.value = "tokens", toks
        elif k == "tokens":
            prog, diags = driver.run_parse(self.value, self.filename)
            self._check(diags)
            self.kind, self.value = "ast", prog
        elif k == "ast":
            typed, diags = driver.run_sema(self.value, self.filename)
            self._check(diags)
            self.kind, self.value = "typed", typed
        elif k == "typed":
            self.kind, self.value = "ir", driver.run_lower(self.value)
        else:
            raise AssertionError(f"no stage after {k}")

    def _check(self, diags: list[Diagnostic]) -> None:
        if diags:
            _report(diags)
            raise _Fail(EXIT_USER)

    def optimized_ir(self, level: int):
        ir = self.advance("ir")
        return driver.run_opt(ir, level)


def _emit(kind: str, obj, args, filename: str, text_fn) -> None:
    if getattr(args, "json", False):
        print(driver.envelope_json(kind, obj, filename))
    else:
        print(text_fn(obj))


def _fmt_tokens(tokens) -> str:
    return "\n".join(
        f"{t.line}:{t.column} {t.type} {t.lexeme!r}" for t in tokens
    )


def _dispatch(args) -> int:
    filename, data = _read_input(args.file)
    target = get_target(getattr(args, "target", None))
    if args.command == "build":
        _check_output_path(_output_path(args, filename, target), filename)
    level = args.opt_level if args.opt_level is not None else 1
    pipe = _Pipeline(filename, data, level)
    cmd = args.command

    if cmd == "lex":
        toks = pipe.advance("tokens")
        _emit("tokens", toks, args, filename, _fmt_tokens)
    elif cmd == "parse":
        prog = pipe.advance("ast")
        _emit("ast", prog, args, filename, serialize.format_tree)
    elif cmd == "sema":
        typed = pipe.advance("typed")
        from compiler.semantic import format_typed

        _emit("typed", typed, args, filename, format_typed)
    elif cmd == "ir":
        ir = pipe.advance("ir")
        from compiler.ir.printer import format_module

        _emit("ir", ir, args, filename, format_module)
    elif cmd == "opt":
        ir = pipe.optimized_ir(1)
        from compiler.ir.printer import format_module

        _emit("ir", ir, args, filename, format_module)
    elif cmd in ("asm", "build", "run"):
        if pipe.kind == "asm":
            asm_text = pipe.asm_text
        else:
            ir = pipe.optimized_ir(level) if level > 0 else pipe.advance("ir")
            if level == 0:
                from compiler.ir.verify import verify_module

                verify_module(ir)
            asm_text = driver.run_codegen(ir, target, level)
        if cmd == "asm":
            sys.stdout.write(asm_text)
            return EXIT_OK
        if cmd == "build":
            _link(asm_text, _output_path(args, filename, target), pipe, filename, target)
            return EXIT_OK
        with tempfile.TemporaryDirectory(prefix="devara_run_") as tmp:
            exe = driver.executable_path(Path(tmp) / "prog", target)
            _link(asm_text, exe, pipe, filename, target)
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                proc = driver.run_executable(exe, target)
            except InternalCompilerError as e:
                print(f"devara: {e}", file=sys.stderr)
                return EXIT_USAGE
            rc = proc.returncode
            return rc if rc >= 0 else 128 - rc
    return EXIT_OK


def _robust_text_streams() -> None:
    """Never die on an unencodable character (e.g. a legacy Windows console code page)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _robust_text_streams()
    ap = _build_parser()
    args = ap.parse_args(argv)
    try:
        return _dispatch(args)
    except _Fail as f:
        return f.status
    except NotImplementedError as e:
        print(f"{args.file}: internal compiler error: not implemented: {e}", file=sys.stderr)
        return EXIT_ICE
    except InternalCompilerError as e:
        print(f"{args.file}: internal compiler error: {e}", file=sys.stderr)
        return EXIT_ICE
    except RecursionError:
        print(f"{args.file}: error: nesting too deep (implementation limit)", file=sys.stderr)
        return EXIT_USER
    except BrokenPipeError:
        return EXIT_OK
    except Exception as e:  # any uncaught exception is a compiler bug
        print(f"{args.file}: internal compiler error: {type(e).__name__}: {e}",
              file=sys.stderr)
        return EXIT_ICE


def run_main() -> None:
    """Entry point: run ``main`` on a big-stack thread (deeply nested sources)."""
    sys.setrecursionlimit(200_000)
    for mib in (512, 256, 64, 16):
        try:
            threading.stack_size(mib * 1024 * 1024)
            break
        except (ValueError, RuntimeError):
            continue
    result: list[int] = []

    def target() -> None:
        try:
            result.append(main())
        except SystemExit as e:  # argparse usage errors
            result.append(e.code if isinstance(e.code, int) else EXIT_USAGE)

    t = threading.Thread(target=target)
    t.start()
    t.join()
    sys.stdout.flush()
    sys.exit(result[0] if result else EXIT_ICE)


if __name__ == "__main__":
    run_main()
