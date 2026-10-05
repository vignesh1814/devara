#!/usr/bin/env python3
"""Run the end-to-end corpus and print statistics (plan §G, master prompt §17).

Layout: ``tests/corpus/<category>/NNN_name.tel`` with optional ``.in`` (stdin),
``.out`` (expected stdout, default empty) and ``.exit`` (expected exit status,
default 0). Every program is compiled with ``./devara build`` and executed with
a 10 s timeout. Writes ``build/corpus_report.json``.

Programs are built and run in parallel (``concurrent.futures`` pool, default one worker per CPU).

Usage: scripts/run_corpus.py [--corpus DIR] [-O0|-O1] [-j N | --jobs N] [--timeout S] [--report FILE]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_one(tel: Path, opt: str, timeout: float) -> dict:
    rec = {"program": str(tel.relative_to(ROOT)) if tel.is_relative_to(ROOT) else str(tel),
           "status": None, "detail": ""}
    expected_out = tel.with_suffix(".out")
    expected_out = expected_out.read_bytes() if expected_out.exists() else b""
    exit_file = tel.with_suffix(".exit")
    expected_exit = int(exit_file.read_text().strip()) if exit_file.exists() else 0
    in_file = tel.with_suffix(".in")
    stdin = in_file.read_bytes() if in_file.exists() else b""

    with tempfile.TemporaryDirectory(prefix="corpus_") as tmp:
        exe = Path(tmp) / "prog"
        t0 = time.time()
        try:
            c = subprocess.run(
                [str(ROOT / "devara"), opt, "build", str(tel), "-o", str(exe)],
                capture_output=True, timeout=120,
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
            r = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=timeout)
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
        else:
            rec.update(status="correct")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default=str(ROOT / "tests" / "corpus"))
    ap.add_argument("-O0", dest="opt", action="store_const", const="-O0", default="-O1")
    ap.add_argument("-O1", dest="opt", action="store_const", const="-O1")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1,
                    help="parallel workers (default: CPU count = %(default)s)")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--report", default=str(ROOT / "build" / "corpus_report.json"),
                    help="where to write the JSON report")
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error("--jobs must be at least 1")

    programs = sorted(Path(args.corpus).rglob("*.tel"))
    if not programs:
        print(f"no corpus programs found under {args.corpus}")
    # warm the runtime-object cache once so parallel builds don't race
    if programs:
        subprocess.run([str(ROOT / "devara"), "asm", str(programs[0])], capture_output=True)

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        records = list(ex.map(lambda p: run_one(p, args.opt, args.timeout), programs))

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
        "correct": counts["correct"], "opt_level": args.opt,
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
