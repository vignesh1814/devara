#!/usr/bin/env python3
"""Run the end-to-end corpus and print statistics (plan §G, master prompt §17).

Layout: ``tests/corpus/<category>/NNN_name.tel`` with optional ``.in`` (stdin),
``.out`` (expected stdout, default empty) and ``.exit`` (expected exit status,
default 0). Every program is compiled with ``./devara build`` and executed with
a 10 s timeout. Writes ``build/corpus_report.json``.

Programs are built and run in parallel (``concurrent.futures`` pool, default one worker per CPU).

Usage: scripts/run_corpus.py [--corpus DIR] [-O0|-O1] [--target linux|windows] [-j N | --jobs N]
                             [--timeout S] [--report FILE]

Environment: ``DEVARA_CC`` (C compiler, e.g. x86_64-w64-mingw32-gcc) and ``DEVARA_RUNNER``
(program prefix, e.g. ``wine``) are honoured, so a Windows-target corpus run on Linux is
``DEVARA_CC=x86_64-w64-mingw32-gcc DEVARA_RUNNER=wine scripts/run_corpus.py --target windows``.
When a ``.err`` file exists the program's stderr must equal it.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# the ``devara`` wrapper is a bash script; invoke the module directly so this also works on Windows
DEVARA = [sys.executable, "-c", "from compiler.cli import run_main; run_main()"]


def target_args(target: str | None) -> list[str]:
    return ["--target", target] if target else []


def runner() -> list[str]:
    return shlex.split(os.environ.get("DEVARA_RUNNER", ""), posix=(os.name != "nt"))


def run_one(tel: Path, opt: str, timeout: float, target: str | None = None) -> dict:
    rec = {"program": str(tel.relative_to(ROOT)) if tel.is_relative_to(ROOT) else str(tel),
           "status": None, "detail": ""}
    expected_out = tel.with_suffix(".out")
    expected_out = expected_out.read_bytes() if expected_out.exists() else b""
    exit_file = tel.with_suffix(".exit")
    expected_exit = int(exit_file.read_text().strip()) if exit_file.exists() else 0
    err_file = tel.with_suffix(".err")
    in_file = tel.with_suffix(".in")
    stdin = in_file.read_bytes() if in_file.exists() else b""

    with tempfile.TemporaryDirectory(prefix="corpus_") as tmp:
        exe = Path(tmp) / ("prog.exe" if target == "windows" or (target is None and os.name == "nt")
                           else "prog")
        t0 = time.time()
        try:
            c = subprocess.run(
                [*DEVARA, opt, "build", *target_args(target), str(tel), "-o", str(exe)],
                capture_output=True, timeout=120, cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")},
            )
        except subprocess.TimeoutExpired:
            rec.update(status="compile_failed", detail="compiler timeout")
            return rec
        rec["compile_seconds"] = round(time.time() - t0, 3)
        if c.returncode != 0:
            rec.update(status="compile_failed",
                       detail=f"exit {c.returncode}: {c.stderr.decode(errors='replace')[:500]}")
            return rec
        t0 = time.time()
        try:
            r = subprocess.run([*runner(), str(exe)], input=stdin, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            rec.update(status="timeout", detail=f"> {timeout}s")
            return rec
        rec["run_seconds"] = round(time.time() - t0, 3)
        if r.returncode != expected_exit:
            rec.update(status="runtime_failed",
                       detail=f"exit {r.returncode}, expected {expected_exit}: "
                              f"{r.stderr.decode(errors='replace')[:300]}")
        elif r.stdout != expected_out:
            rec.update(status="incorrect", detail="stdout differs from .out")
        elif err_file.exists() and r.stderr.strip() != err_file.read_bytes().strip():
            rec.update(status="incorrect",
                       detail=f"stderr differs from .err: {r.stderr.decode(errors='replace')[:200]!r}")
        else:
            rec.update(status="correct")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default=str(ROOT / "tests" / "corpus"))
    ap.add_argument("-O0", dest="opt", action="store_const", const="-O0", default="-O1")
    ap.add_argument("-O1", dest="opt", action="store_const", const="-O1")
    ap.add_argument("--target", choices=("linux", "windows"), default=None,
                    help="code-generation target (default: host OS)")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1,
                    help="parallel workers (default: CPU count = %(default)s)")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--report", default=str(ROOT / "build" / "corpus_report.json"),
                    help="where to write the JSON report")
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error("--jobs must be at least 1")

    host_is_windows = os.name == "nt"
    if args.target and (args.target == "windows") != host_is_windows and not runner():
        print(f"error: running {args.target} executables on this host needs DEVARA_RUNNER (e.g. wine)",
              file=sys.stderr)
        return 2
    programs = sorted(Path(args.corpus).rglob("*.tel"))
    if not programs:
        print(f"no corpus programs found under {args.corpus}")
    # warm the runtime-object cache once so parallel builds don't race
    if programs:
        with tempfile.TemporaryDirectory(prefix="corpus_warm_") as warm:
            subprocess.run([*DEVARA, "build", *target_args(args.target), str(programs[0]), "-o",
                            str(Path(warm) / "warm.exe")], capture_output=True, cwd=ROOT,
                           env={**os.environ,
                                "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")})

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        records = list(ex.map(lambda p: run_one(p, args.opt, args.timeout, args.target), programs))

    counts = {k: 0 for k in ("correct", "incorrect", "runtime_failed", "timeout", "compile_failed")}
    for r in records:
        counts[r["status"]] += 1
    total = len(records)
    compiled = total - counts["compile_failed"]
    executed = compiled - counts["timeout"]
    stats = {
        "total": total, "compiled": compiled, "failed_compilation": counts["compile_failed"],
        "executed": executed, "runtime_failed": counts["runtime_failed"],
        "incorrect_output": counts["incorrect"], "timeout": counts["timeout"],
        "correct": counts["correct"], "opt_level": args.opt, "target": args.target or "host",
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"stats": stats, "programs": records}, indent=2))

    print("Corpus statistics")
    print("-----------------")
    for k in ("total", "compiled", "failed_compilation", "executed",
              "runtime_failed", "incorrect_output", "timeout", "correct"):
        print(f"{k:20s} {stats[k]}")
    for r in records:
        if r["status"] != "correct":
            print(f"  {r['status']:15s} {r['program']}: {r['detail'][:200]}")
    return 0 if counts["correct"] == total else 1


if __name__ == "__main__":
    sys.exit(main())
