#!/usr/bin/env python3
"""Micro-benchmarks: wall time of compute-heavy Devara programs at -O0 vs -O1.

Each program is compiled once per optimization level (compile time is not measured) and the
produced executable is run ``--runs`` times; the minimum wall time is reported. Outputs of the two
levels must be identical, otherwise the benchmark fails.

Usage: scripts/bench.py [--runs N] [--only NAME[,NAME...]] [--target linux|windows] [--markdown]

``DEVARA_CC`` / ``DEVARA_RUNNER`` are honoured like in scripts/run_corpus.py.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVARA = [sys.executable, "-c", "from compiler.cli import run_main; run_main()"]

PROGRAMS: dict[str, tuple[str, str]] = {
    "sieve 1e7": ("loop + array", """
int n
n lo 10000000 pettu
bool prime[n + 1]
int i
pratisari (i 2 tho modhalu; i <= n; i++) { prime[i] lo nijam pettu }
int p
p lo 2 pettu
int j
p * p <= n unnanta varaku {
    prime[p] ayite {
        pratisari (j p * p tho modhalu; j <= n; j lo j + p pettu) { prime[j] lo abaddham pettu }
    }
    p lo p + 1 pettu
}
int count
count lo 0 pettu
pratisari (i 2 tho modhalu; i <= n; i++) { prime[i] ayite { count lo count + 1 pettu } }
count ni chupi
"""),
    "matmul 200": ("2-D arrays, triple loop", """
int n
n lo 200 pettu
int a[n][n]
int b[n][n]
int c[n][n]
int i
int j
int k
prati i 0 nundi n varaku {
    prati j 0 nundi n varaku {
        a[i][j] lo (i * 7 + j * 3) % 10 pettu
        b[i][j] lo (i * 5 + j * 11) % 10 pettu
    }
}
int s
prati i 0 nundi n varaku {
    prati j 0 nundi n varaku {
        s lo 0 pettu
        prati k 0 nundi n varaku { s lo s + a[i][k] * b[k][j] pettu }
        c[i][j] lo s pettu
    }
}
int check
check lo 0 pettu
prati i 0 nundi n varaku { prati j 0 nundi n varaku { check lo (check * 31 + c[i][j]) % 1000000007 pettu } }
check ni chupi
"""),
    "fib(32)": ("recursion, calls", """
int fib charya (int n) {
    n < 2 ayite { n ivvu }
    fib(n - 1) + fib(n - 2) ivvu
}
fib(32) ni chupi
"""),
    "sort 1e6": ("merge sort, array params", """
int scratch[1000000]

int merge_sort charya (int a[], int left, int right) {
    right - left < 1 ayite { 0 ivvu }
    int mid
    mid lo left + (right - left) / 2 pettu
    merge_sort(a, left, mid)
    merge_sort(a, mid + 1, right)
    int i
    int j
    int k
    i lo left pettu
    j lo mid + 1 pettu
    k lo left pettu
    i <= mid && j <= right unnanta varaku {
        a[i] <= a[j] ayite {
            scratch[k] lo a[i] pettu
            i lo i + 1 pettu
        } lekunte {
            scratch[k] lo a[j] pettu
            j lo j + 1 pettu
        }
        k lo k + 1 pettu
    }
    i <= mid unnanta varaku { scratch[k] lo a[i] pettu  i lo i + 1 pettu  k lo k + 1 pettu }
    j <= right unnanta varaku { scratch[k] lo a[j] pettu  j lo j + 1 pettu  k lo k + 1 pettu }
    prati x left nundi right + 1 varaku { a[x] lo scratch[x] pettu }
    0 ivvu
}

int n
n lo 1000000 pettu
int a[n]
int seed
seed lo 12345 pettu
prati i 0 nundi n varaku {
    seed lo (seed * 1103515245 + 12345) % 2147483648 pettu
    a[i] lo seed % 1000000 pettu
}
merge_sort(a, 0, n - 1)
int ok
ok lo 1 pettu
int check
check lo 0 pettu
prati i 0 nundi n varaku {
    i > 0 && a[i - 1] > a[i] ayite { ok lo 0 pettu }
    check lo (check * 31 + a[i]) % 1000000007 pettu
}
ok ni chupi
check ni chupi
"""),
    "float loop 2e7": ("float arithmetic", """
float integrate charya (int n) {
    float s
    float x
    float h
    h lo 1.0 / n pettu
    s lo 0.0 pettu
    prati i 0 nundi n varaku {
        x lo (i + 0.5) * h pettu
        s lo s + 4.0 / (1.0 + x * x) pettu
    }
    s * h ivvu
}
integrate(20000000) ni chupi
"""),
}


def runner() -> list[str]:
    return shlex.split(os.environ.get("DEVARA_RUNNER", ""), posix=(os.name != "nt"))


def build(src: Path, exe: Path, level: int, target: str | None) -> None:
    cmd = [*DEVARA, f"-O{level}", "build", *(["--target", target] if target else []), str(src), "-o", str(exe)]
    env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=env)
    if p.returncode != 0:
        raise SystemExit(f"build failed (-O{level}): {p.stderr}")


def timed(exe: Path, runs: int) -> tuple[float, bytes]:
    best = float("inf")
    out = b""
    for _ in range(runs):
        t0 = time.perf_counter()
        p = subprocess.run([*runner(), str(exe)], capture_output=True, timeout=600)
        dt = time.perf_counter() - t0
        if p.returncode != 0:
            raise SystemExit(f"{exe} exited {p.returncode}: {p.stderr.decode(errors='replace')}")
        best = min(best, dt)
        out = p.stdout
    return best, out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=int, default=3, help="runs per measurement (minimum is reported)")
    ap.add_argument("--only", default="", help="comma-separated program names")
    ap.add_argument("--target", choices=("linux", "windows"), default=None)
    ap.add_argument("--markdown", action="store_true", help="print a markdown table")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    rows = []
    with tempfile.TemporaryDirectory(prefix="devara_bench_") as tmp:
        for name, (kind, src) in PROGRAMS.items():
            if only and name not in only:
                continue
            tel = Path(tmp) / "bench.tel"
            tel.write_text(src.lstrip())
            suffix = ".exe" if args.target == "windows" or (args.target is None and os.name == "nt") else ""
            times, outs = {}, {}
            for level in (0, 1):
                exe = Path(tmp) / f"bench_O{level}{suffix}"
                build(tel, exe, level, args.target)
                times[level], outs[level] = timed(exe, args.runs)
            if outs[0] != outs[1]:
                raise SystemExit(f"{name}: -O0 and -O1 outputs differ: {outs[0]!r} vs {outs[1]!r}")
            rows.append((name, kind, times[0], times[1], outs[0].decode().split()))
    if args.markdown:
        print("| program | what it stresses | -O0 (s) | -O1 (s) | speedup |")
        print("|---|---|---:|---:|---:|")
        for name, kind, t0, t1, _ in rows:
            print(f"| {name} | {kind} | {t0:.3f} | {t1:.3f} | {t0 / t1:.1f}x |")
    else:
        print(f"{'program':16s} {'-O0 (s)':>9s} {'-O1 (s)':>9s} {'speedup':>8s}  output")
        for name, _kind, t0, t1, out in rows:
            print(f"{name:16s} {t0:9.3f} {t1:9.3f} {t0 / t1:7.1f}x  {' '.join(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
