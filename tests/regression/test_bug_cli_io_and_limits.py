"""Regressions from the validation round: F-001, F-002, Q-012, N-001, N-002 (plan §M)."""

import os
import subprocess
import time
from pathlib import Path

import pytest

from compiler.diagnostics import SemCategory as S
from tests.unit.test_semantic import accept, reject

ROOT = Path(__file__).parent.parent.parent
DEVARA = str(ROOT / "devara")


def dv(*args, cwd=None):
    return subprocess.run([DEVARA, *args], capture_output=True, text=True, cwd=cwd)


@pytest.fixture
def src(tmp_path):
    p = tmp_path / "a.tel"
    p.write_text("1 ni chupi\n")
    return p


def test_bug_f001_build_to_missing_directory_is_io_error(src, tmp_path):
    out = tmp_path / "nope" / "out"
    r = dv("build", str(src), "-o", str(out))
    assert r.returncode == 2
    assert r.stderr.strip() == f"{src}: error: cannot write output '{out}': No such file or directory"
    assert "internal compiler error" not in r.stderr


def test_bug_f001_build_output_is_a_directory(src, tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    r = dv("build", str(src), "-o", str(d))
    assert r.returncode == 2
    assert r.stderr.strip() == f"{src}: error: cannot write output '{d}': Is a directory"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_bug_f001_build_output_in_unwritable_directory(src, tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    try:
        r = dv("build", str(src), "-o", str(d / "x"))
        assert r.returncode == 2 and "Permission denied" in r.stderr
    finally:
        d.chmod(0o700)


def test_bug_q012_user_supplied_bad_assembly_is_a_user_error(tmp_path):
    s = tmp_path / "bad.s"
    s.write_text("this is not assembly\n")
    for cmd in (["build", str(s), "-o", str(tmp_path / "o")], ["run", str(s)]):
        r = dv(*cmd)
        assert r.returncode == 1, r.stderr
        assert r.stderr.startswith(f"{s}: assembler error: ")
        assert "internal compiler error" not in r.stderr


def test_generated_code_rejection_stays_an_ice(monkeypatch):
    from compiler import cli, driver
    from compiler.diagnostics import InternalCompilerError

    def boom(asm, out):
        raise driver.AssemblerError("bad")

    monkeypatch.setattr(driver, "link_executable", boom)
    with pytest.raises(InternalCompilerError):
        pipe = cli._Pipeline("x.tel", b"1 ni chupi", 1)
        cli._link("", Path("o"), pipe, "x.tel")


@pytest.mark.parametrize("n", [20000, 100000])
def test_bug_n001_excess_nesting_is_a_syntax_diagnostic_not_an_ice(tmp_path, n):
    p = tmp_path / "deep.tel"
    p.write_text("(" * n + "1" + ")" * n + " ni chupi\n")
    r = dv("parse", str(p))
    assert r.returncode == 1
    line = r.stderr.splitlines()[0]
    assert "syntax error [INVALID_EXPRESSION]: nesting too deep (implementation limit)" in line
    assert line.startswith(f"{p}:1:")


def test_n001_supported_depth_is_at_least_1000(tmp_path):
    cases = {
        "parens": "(" * 1000 + "1" + ")" * 1000 + " ni chupi\n",
        "blocks": "nijam ayite { " * 1000 + "1 ni chupi" + " }" * 1000 + "\n",
        "calls": "int f charya(int a) { a ivvu }\n" + "f(" * 1000 + "1" + ")" * 1000 + " ni chupi\n",
        "unary": "- " * 1000 + "1 ni chupi\n",
    }
    for name, text in cases.items():
        p = tmp_path / f"{name}.tel"
        p.write_text(text)
        r = dv("sema", str(p))
        assert r.returncode == 0, (name, r.stderr[-200:])


def test_bug_n002_long_left_associative_chain_is_linear(tmp_path):
    def run(n):
        p = tmp_path / f"c{n}.tel"
        p.write_text(" + ".join(["1"] * n) + " ni chupi\n")
        t = time.time()
        r = dv("parse", str(p))
        assert r.returncode == 0
        return time.time() - t

    t4, t16 = run(4000), run(16000)
    assert t16 < 8.0 and t16 < 12 * max(t4, 0.2)      # was ~23 s (quadratic output indentation)


@pytest.mark.parametrize("cond", ["'a'", "(int) 1", "(char) 1", "(bool) 1", "(float) 1", "1.5", "'a' + 0 - 'a'"])
def test_bug_f002_only_bare_int_or_bool_literals_are_constant_true(cond):
    # these loops can complete normally, so the function must be rejected
    reject(f"int f charya() {{ {cond} unnanta varaku {{ 1 ivvu }} }}", S.MISSING_RETURN)


@pytest.mark.parametrize("cond", ["nijam", "1", "7", "-1 + 2", ])
def test_f002_literal_true_conditions_still_work(cond):
    if cond in ("nijam", "1", "7"):
        accept(f"int f charya() {{ {cond} unnanta varaku {{ }} }}")
    else:
        reject(f"int f charya() {{ {cond} unnanta varaku {{ }} }}", S.MISSING_RETURN)


def test_bug_f002_definite_init_after_non_literal_true_loop():
    reject("int f charya() { int x\n'a' unnanta varaku { x lo 1 pettu\naapu } x ivvu }", S.UNINITIALIZED)
    reject("int f charya() { int x\n(int) 1 unnanta varaku { x lo 1 pettu\naapu } x ivvu }", S.UNINITIALIZED)
    accept("int f charya() { int x\n1 unnanta varaku { x lo 1 pettu\naapu } x ivvu }")


@pytest.mark.parametrize("lexeme", ["078", "0189", "089", "0000009", "0789"])
def test_bug_f003_octal_with_8_or_9_is_one_invalid_number(lexeme):
    from compiler.diagnostics import LexCategory
    from compiler.lexer import Lexer

    lx = Lexer(lexeme)
    toks = lx.tokenize()
    assert [e.category for e in lx.errors] == [LexCategory.INVALID_NUMBER]
    assert lx.errors[0].span.end_column - lx.errors[0].span.start_column == len(lexeme)
    assert [t.lexeme for t in toks[:-1]] == []          # no partial prefix token


def test_f003_valid_zero_prefixed_numbers_unchanged():
    from compiler.lexer import Lexer

    for lx_text in ["0", "07", "0777", "0x1F", "0.5", "08.5"]:
        lx = Lexer(lx_text)
        lx.tokenize()
        assert not lx.errors, lx_text


def test_bug_deeply_nested_blocks_optimize_in_linear_time(tmp_path):
    """merge_blocks was quadratic (5 s at 2000 nested blocks, minutes at 9000)."""
    p = tmp_path / "b.tel"
    n = 4000
    p.write_text("nijam ayite { " * n + "}" * n + "\n")
    t = time.time()
    r = dv("asm", str(p))
    assert r.returncode == 0, r.stderr[-200:]
    assert time.time() - t < 20


def test_n001_explicit_nesting_limit_for_blocks_and_unary(tmp_path):
    for name, text in {"blocks": "nijam ayite { " * 30000 + "}" * 30000 + "\n",
                       "unary": "x lo " + "!" * 30000 + "1 pettu\n"}.items():
        p = tmp_path / f"{name}.tel"
        p.write_text(text)
        r = dv("sema", str(p))
        assert r.returncode == 1 and "nesting too deep (implementation limit)" in r.stderr, name
