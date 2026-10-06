#!/usr/bin/env python3
"""Long differential campaign: python3 tests/property/campaign.py START COUNT SIZE [JOBS]
Prints every seed whose compiled output (-O0/-O1) differs from the reference interpreter."""
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.property.proggen import generate  # noqa: E402
from tests.reference.interp import run_ast, StepLimit  # noqa: E402
from tests.helpers.cli import DEVARA_CMD  # noqa: E402
import json  # noqa: E402

work = ROOT / "build" / "campaign"
work.mkdir(parents=True, exist_ok=True)


def norm(b):
    return re.sub(rb"-?nan", b"nan", b)


def one(seed, size):
    src, stdin = generate(seed, size)
    f = work / f"c{seed}.tel"
    f.write_text(src)
    pr = subprocess.run([*DEVARA_CMD, "parse", "--json", str(f)], capture_output=True)
    if pr.returncode != 0:
        return seed, "PARSE-FAIL " + pr.stderr.decode()[:200]
    try:
        ref = run_ast(json.loads(pr.stdout)["data"], stdin, max_steps=30_000_000)
    except StepLimit:
        return seed, None
    if ref.status != 0:
        return seed, f"REF-RUNTIME-ERROR {ref.error}"
    for opt in ("-O0", "-O1"):
        r = subprocess.run([*DEVARA_CMD, opt, "run", str(f)], input=stdin, capture_output=True, timeout=60)
        if r.returncode != 0:
            return seed, f"{opt}: rc={r.returncode} {r.stderr.decode()[:300]}"
        if norm(r.stdout) != norm(ref.stdout):
            return seed, f"{opt}: OUTPUT DIFFERS"
    f.unlink()
    return seed, None


if __name__ == "__main__":
    start, count, size = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    bad = 0
    with ThreadPoolExecutor(jobs) as ex:
        for seed, msg in ex.map(lambda s: one(s, size), range(start, start + count)):
            if msg:
                bad += 1
                print(f"seed {seed}: {msg}", flush=True)
    print(f"done: {count} programs, {bad} problems")
