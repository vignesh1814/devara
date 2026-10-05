#!/usr/bin/env python3
"""One-command health check of a Devara install on this machine (Windows or Linux).

Checks the toolchain, then builds and runs the full corpus at -O0 and -O1 and the
leak check (DEVARA_RT_STATS=1 must report live=0 on every normally-exiting program).
Prints a summary and writes build/machine_report.txt.

Usage:  python scripts/check_machine.py [-j N]
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVARA = [sys.executable, "-c", "from compiler.cli import run_main; run_main()"]
lines: list[str] = []


def say(msg: str = "") -> None:
    print(msg, flush=True)
    lines.append(msg)


def toolchain() -> bool:
    ok = True
    say(f"OS        : {platform.platform()} ({platform.machine()})")
    say(f"Python    : {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 11):
        say("  FAIL: Python >= 3.11 is required")
        ok = False
    cc = os.environ.get("DEVARA_CC", "gcc")
    path = shutil.which(cc)
    if not path:
        say(f"C compiler: '{cc}' NOT FOUND on PATH")
        if os.name == "nt":
            say("  fix: winget install BrechtSanders.WinLibs.POSIX.UCRT  (then open a new terminal)")
        return False
    try:
        machine = subprocess.run([cc, "-dumpmachine"], capture_output=True, text=True).stdout.strip()
        version = subprocess.run([cc, "-dumpversion"], capture_output=True, text=True).stdout.strip()
    except OSError as e:
        say(f"C compiler: {path} cannot run: {e}")
        return False
    say(f"C compiler: {path} ({machine}, gcc {version})")
    if not machine.startswith("x86_64"):
        say("  FAIL: an x86-64 gcc is required (on Windows: MinGW-w64 x86_64, not 32-bit MinGW)")
        ok = False
    return ok


def run_corpus(opt: str, jobs: int) -> bool:
    report = ROOT / "build" / f"machine_corpus{opt}.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_corpus.py"), opt, "-j", str(jobs),
                        "--report", str(report)], capture_output=True, text=True, cwd=ROOT)
    stats = [ln for ln in r.stdout.splitlines() if ln.strip()]
    say(f"Corpus {opt}: " + ", ".join(" ".join(ln.split()) for ln in stats[-8:]))
    if r.returncode != 0:
        for ln in (r.stdout + r.stderr).splitlines()[:40]:
            if "FAIL" in ln or "error" in ln.lower():
                say("  " + ln)
    return r.returncode == 0


def leak_one(src: Path, opt: str, workdir: Path) -> str | None:
    if src.with_suffix(".exit").exists():
        return None                       # runtime-error programs are exempt
    exe = workdir / (src.stem + opt + (".exe" if os.name == "nt" else ""))
    b = subprocess.run(DEVARA + [opt, "build", str(src), "-o", str(exe)], capture_output=True, text=True, cwd=ROOT)
    if b.returncode != 0:
        return f"{src.name} {opt}: build failed: {b.stderr.strip()[:200]}"
    inp = src.with_suffix(".in")
    data = inp.read_bytes() if inp.exists() else b""
    env = dict(os.environ, DEVARA_RT_STATS="1")
    try:
        p = subprocess.run([str(exe)], input=data, capture_output=True, env=env, timeout=30)
    except subprocess.TimeoutExpired:
        return f"{src.name} {opt}: timeout"
    err = p.stderr.decode("latin-1")
    if p.returncode != 0 or "devara-rt: live=0" not in err:
        return f"{src.name} {opt}: rc={p.returncode} stderr={err.strip()[-120:]!r}"
    return None


def leaks(jobs: int) -> bool:
    progs = sorted((ROOT / "tests" / "corpus").rglob("*.tel"))
    with tempfile.TemporaryDirectory(prefix="devara_check_") as d, ThreadPoolExecutor(jobs) as pool:
        futs = [pool.submit(leak_one, s, o, Path(d)) for s in progs for o in ("-O0", "-O1")]
        bad = [f.result() for f in futs]
    bad = [b for b in bad if b]
    checked = sum(1 for s in progs if not s.with_suffix(".exit").exists()) * 2
    say(f"Leak check: {checked - len(bad)}/{checked} program runs report live=0")
    for b in bad[:20]:
        say("  " + b)
    return not bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()
    say("== Devara machine check ==")
    ok = toolchain()
    if ok:
        ok = run_corpus("-O0", args.jobs) & run_corpus("-O1", args.jobs) & leaks(args.jobs)
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    out = ROOT / "build" / "machine_report.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"(report written to {out})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
