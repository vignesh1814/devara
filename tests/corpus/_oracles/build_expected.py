#!/usr/bin/env python3
"""Regenerate .out/.exit/.err for every corpus program by running its Python oracle.

The expected output therefore comes ONLY from the independent oracle, never from the compiler.
Usage: python3 tests/corpus/_oracles/build_expected.py [NNN ...]
"""
import os, subprocess, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)


def main():
    want = set(sys.argv[1:])
    n = 0
    for tel in sorted(glob.glob(os.path.join(CORPUS, "*", "*.tel"))):
        stem = os.path.basename(tel)[:-4]
        if want and stem[:3] not in want:
            continue
        base = tel[:-4]
        oracle = os.path.join(HERE, stem + ".py")
        if not os.path.exists(oracle):
            print("MISSING ORACLE", stem)
            continue
        inp = open(base + ".in", "rb").read() if os.path.exists(base + ".in") else b""
        r = subprocess.run([sys.executable, oracle], input=inp, capture_output=True, timeout=60)
        open(base + ".out", "wb").write(r.stdout)
        for ext in (".exit", ".err"):
            if os.path.exists(base + ext):
                os.remove(base + ext)
        if r.returncode != 0:
            open(base + ".exit", "w").write("%d\n" % r.returncode)
            open(base + ".err", "wb").write(r.stderr)
        n += 1
    print("built", n)


if __name__ == "__main__":
    main()
