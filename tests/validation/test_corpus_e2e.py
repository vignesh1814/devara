"""End-to-end corpus: compile + execute every program at -O0 and -O1 and compare stdout, exit status, and (for
runtime-error programs) the stderr diagnostic with the expected files that were produced by the independent Python
oracles in tests/corpus/_oracles (never from compiler output)."""
import subprocess
import pytest
from tests.validation.helpers import run_cli, WORK
from tests.validation.corpus_util import programs, pid, expected

PROGS = programs()


def test_corpus_has_at_least_110_programs():
    assert len(PROGS) >= 110


def test_corpus_files_complete_and_headers_present():
    for tel in PROGS:
        text = tel.read_text()
        head = text.split("\n")[:6]
        assert head[0].startswith("# ID: DSA-"), tel
        for key, line in zip(("# Category:", "# Algorithm:", "# Exercises:", "# Difficulty:", "# Expected:"), head[1:]):
            assert line.startswith(key), (tel, line)
        assert tel.with_suffix(".out").exists(), tel
        assert (tel.parent.parent / "_oracles" / (tel.stem + ".py")).exists(), tel


@pytest.mark.slow
@pytest.mark.parametrize("opt", ["-O0", "-O1"])
@pytest.mark.parametrize("tel", PROGS, ids=pid)
def test_corpus_program(tel, opt):
    inp, out, ex, err = expected(tel)
    exe = WORK / f"corpus_{tel.stem}{opt}"
    b = run_cli([opt, "build", str(tel), "-o", str(exe)])
    assert b.rc == 0, f"compile failed rc={b.rc}\n{b.err}"
    r = subprocess.run([str(exe)], input=inp, capture_output=True, timeout=10)
    assert r.stdout == out, "stdout differs from the oracle"
    assert r.returncode == ex, f"exit status {r.returncode} != {ex}"
    if ex != 0:
        assert r.stderr.decode().strip() == err.strip()


@pytest.mark.slow
@pytest.mark.parametrize("tel", PROGS[::5], ids=pid)
def test_devara_run_matches_build_and_execute(tel):
    inp, out, ex, _ = expected(tel)
    r = run_cli(["run", str(tel)], inp)
    assert r.out == out and r.rc == ex


@pytest.mark.slow
@pytest.mark.parametrize("tel", PROGS, ids=pid)
def test_o0_and_o1_agree(tel):
    inp, out, ex, _ = expected(tel)
    a = run_cli(["-O0", "run", str(tel)], inp)
    b = run_cli(["-O1", "run", str(tel)], inp)
    assert (a.rc, a.out) == (b.rc, b.out)
