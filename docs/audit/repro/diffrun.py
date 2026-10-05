"""Differential run: devara -O0, -O1 vs the reference interpreter, per program.

usage: python docs/audit/repro/diffrun.py OUTDIR PROG.tel [PROG.tel ...]
stdin for PROG.tel is read from PROG.in next to it, if present.
Writes OUTDIR/<stem>.{O0,O1,ref}.{out,err,rc} and prints one summary line per program.
"""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.reference.interp import run_file  # noqa: E402

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, DEVARA_RT_STATS="1")
for p in map(Path, sys.argv[2:]):
    stem = p.stem
    stdin = p.with_suffix(".in").read_bytes() if p.with_suffix(".in").exists() else b""
    res = {}
    for lvl in ("O0", "O1"):
        exe = out / f"{stem}.{lvl}.exe"
        b = subprocess.run([sys.executable, "-c", "from compiler.cli import run_main; run_main()", f"-{lvl}", "build",
                            str(p.resolve()), "-o", str(exe.resolve())], capture_output=True, cwd=ROOT)
        if b.returncode != 0:
            res[lvl] = ("COMPILE", b.returncode, b.stderr.decode(errors="replace"))
            continue
        r = subprocess.run([str(exe)], input=stdin, capture_output=True, env=env, timeout=20)
        res[lvl] = (r.stdout, r.returncode, r.stderr.decode(errors="replace"))
    try:
        rr = run_file(p, stdin)
        res["ref"] = (rr.stdout, rr.status, ("devara: runtime error: %s\n" % rr.error) if rr.status else "")
    except Exception as e:  # noqa: BLE001
        res["ref"] = ("REFERR", -1, repr(e))
    for k, (o, rc, e) in res.items():
        (out / f"{stem}.{k}.out").write_bytes(o if isinstance(o, bytes) else o.encode())
        (out / f"{stem}.{k}.err").write_text(e)
        (out / f"{stem}.{k}.rc").write_text(str(rc))
    def norm_err(e):  # drop the leak-stats line before comparing stderr
        return "".join(l for l in e.splitlines(True) if not l.startswith("devara-rt: live="))
    keys = [(res[k][0], res[k][1], norm_err(res[k][2])) for k in ("O0", "O1", "ref")]
    leak = [k for k in ("O0", "O1") if isinstance(res[k][0], bytes) and res[k][1] == 0 and "live=0" not in res[k][2]]
    status = "AGREE" if keys[0] == keys[1] == keys[2] else "DIFF"
    if leak:
        status += " LEAK:" + ",".join(leak)
    print(f"{status:10} rc={res['O1'][1]} {stem}")
