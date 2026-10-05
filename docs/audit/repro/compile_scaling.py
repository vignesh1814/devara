"""Compile-time scaling: generate programs of ~N lines and time `devara -O0/-O1 asm`.

usage: python docs/audit/repro/compile_scaling.py [N ...]   (default: 100 1000 5000 20000)
"""
import resource, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def generate(n: int) -> str:
    out = ["int g"]
    for f in range(max(1, n // 10)):
        out += [f"int f{f} charya (int a, int b) {{", "    int s", "    s lo 0 pettu",
                "    prati i 0 nundi a varaku {", f"        s lo s + (i * {f % 7 + 1} + b) % 13 pettu",
                "        s > 100 ayite { aapu }", "    }", "    s ivvu", "}",
                f"g lo g + f{f}(3, {f}) pettu"]
    out.append("g ni chupi")
    return "\n".join(out) + "\n"


sizes = [int(a) for a in sys.argv[1:]] or [100, 1000, 5000, 20000]
with tempfile.TemporaryDirectory() as tmp:
    for n in sizes:
        src = Path(tmp) / f"gen{n}.tel"
        src.write_text(generate(n))
        for lvl in ("-O0", "-O1"):
            t = time.perf_counter()
            p = subprocess.run([sys.executable, "-c", "from compiler.cli import run_main; run_main()", lvl, "asm", str(src)],
                               capture_output=True, cwd=ROOT)
            dt = time.perf_counter() - t
            rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024
            print(f"lines~{n:6} {lvl} rc={p.returncode} {dt:7.2f}s {dt / n * 1000:6.3f} ms/line maxrss(so far)={rss} MB", flush=True)
