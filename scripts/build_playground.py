#!/usr/bin/env python3
"""Build the static browser playground into ``build/playground/`` (or --out DIR).

Output (host it anywhere that serves static files, e.g. GitHub Pages):

    index.html             full page with an example picker
    embed.html             minimal page for <iframe> embedding (configured by the URL hash)
    devara-playground.js   the <devara-playground> web component (self-contained)
    devara.zip             the compiler, loaded into Pyodide by the component
    examples.json          the programs in examples/ for the picker

Usage:  python scripts/build_playground.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "playground"
# Only what the browser needs. The native code generator, debugger and CLI need subprocess / gdb / gcc.
EXCLUDE = {"codegen", "cli.py", "debugger.py", "__pycache__"}
# Sample input for examples that read from stdin.
STDIN_FOR = {"truth_machine": "0\n", "fibonacci": "10\n", "factorial": "5\n", "collatz": "27\n", "primes": "30\n",
             "reverse": "Devara\n", "sort": "5\n9 3 7 1 4\n", "squares": "5\n", "fizzbuzz": "15\n"}
FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # reproducible archive


def package_zip(dest: Path) -> int:
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted((ROOT / "compiler").rglob("*.py")):
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE for part in rel.parts):
                continue
            z.writestr(zipfile.ZipInfo(rel.as_posix(), FIXED_TIME), path.read_bytes(), zipfile.ZIP_DEFLATED)
            n += 1
        # keep `import compiler.codegen` importable without shipping the native back end
        z.writestr(zipfile.ZipInfo("compiler/codegen/__init__.py", FIXED_TIME), b"# not shipped to the browser\n")
    return n


def examples() -> dict:
    out = {}
    for path in sorted((ROOT / "examples").glob("*.tel")):
        out[path.stem] = {
            "title": path.stem.replace("_", " ").title(),
            "code": path.read_text(encoding="utf-8"),
            "stdin": STDIN_FOR.get(path.stem, ""),
        }
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "playground")
    out = ap.parse_args(argv).out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in ("index.html", "embed.html", "devara-playground.js"):
        shutil.copy2(SRC / name, out / name)
    count = package_zip(out / "devara.zip")
    (out / "examples.json").write_text(json.dumps(examples(), indent=1), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    size = sum(p.stat().st_size for p in out.iterdir() if p.is_file())
    print(f"playground built in {out}: {count} compiler modules, {size / 1024:.0f} KB total")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
