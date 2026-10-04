import os
from pathlib import Path
from tests.validation.helpers import ROOT

CORPUS = ROOT / "tests" / "corpus"


def programs():
    return sorted(p for p in CORPUS.glob("*/*.tel"))


def expected(tel: Path):
    base = tel.with_suffix("")
    inp = base.with_suffix(".in").read_bytes() if base.with_suffix(".in").exists() else b""
    out = base.with_suffix(".out").read_bytes()
    ex = int(base.with_suffix(".exit").read_text()) if base.with_suffix(".exit").exists() else 0
    err = base.with_suffix(".err").read_text() if base.with_suffix(".err").exists() else ""
    return inp, out, ex, err


def pid(p: Path):
    return f"{p.parent.name}/{p.stem}"
