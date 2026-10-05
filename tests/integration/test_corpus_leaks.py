"""Leak accounting over the whole corpus (plan P22): every corpus program that exits normally
must report ``devara-rt: live=0`` (no live heap array or padham string left) at -O0 and -O1.
Programs that end with a runtime error (non-zero ``.exit``) are exempt: the runtime does not
unwind on error."""

from pathlib import Path

import pytest

from tests.helpers import native

CORPUS = Path(__file__).parent.parent / "corpus"


def _expected_exit(tel: Path) -> int:
    f = tel.with_suffix(".exit")
    return int(f.read_text().strip()) if f.exists() else 0


PROGRAMS = [p for p in sorted(CORPUS.rglob("*.tel")) if _expected_exit(p) == 0]

pytestmark = pytest.mark.slow


def test_corpus_has_non_error_programs():
    assert len(PROGRAMS) >= 100


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("tel", PROGRAMS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_corpus_program_leaks_nothing(tel: Path, level: int):
    src = tel.read_bytes().decode("latin-1")
    expected = tel.with_suffix(".out").read_bytes() if tel.with_suffix(".out").exists() else b""
    stdin = tel.with_suffix(".in").read_bytes() if tel.with_suffix(".in").exists() else b""
    out, rc, err, live = native.run_stats(src, stdin, level, timeout=20)
    assert rc == 0, err
    assert out == expected
    assert live == 0, f"{live} allocation(s) still live at exit"
