"""End-to-end corpus: compile every tests/corpus program, run it, compare with the expected
output / exit status, at both -O0 and -O1 (plan §G, master prompt §17/§18)."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from compiler import driver
from compiler.codegen.x86_64 import generate
from tests.helpers.pipeline import to_ir

CORPUS = Path(__file__).parent.parent / "corpus"
PROGRAMS = sorted(CORPUS.rglob("*.tel"))

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("tel", PROGRAMS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_corpus_program(tel: Path, level: int):
    src = tel.read_bytes().decode("latin-1")
    expected = tel.with_suffix(".out").read_bytes() if tel.with_suffix(".out").exists() else b""
    exit_f = tel.with_suffix(".exit")
    expected_exit = int(exit_f.read_text().strip()) if exit_f.exists() else 0
    stdin = tel.with_suffix(".in").read_bytes() if tel.with_suffix(".in").exists() else b""
    asm = generate(to_ir(src, level), regalloc=level > 0)
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "p"
        driver.link_executable(asm, exe)
        p = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=10)
    assert p.returncode == expected_exit, p.stderr.decode(errors="replace")
    assert p.stdout == expected
