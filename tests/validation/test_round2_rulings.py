"""Design-authority rulings of plan §M (round 2): F-001, Q-010, Q-011, Q-012, N-001."""
import pytest
from tests.validation.helpers import cli, run, run_cli, prog, OPTS

# ---- Q-010: strict tokens
@pytest.mark.slow
@pytest.mark.parametrize("t,data", [("int", b"3.5"), ("int", b"12abc"), ("int", b"1x"), ("int", b"0x10"), ("int", b"1e3"), ("int", b"5,"),
                                    ("float", b"1x"), ("float", b"1.5.5"), ("float", b"2.5abc"), ("bool", b"1x"), ("bool", b"nijamx"), ("bool", b"10")])
@pytest.mark.parametrize("opt", OPTS)
def test_Q010_token_with_trailing_junk_is_invalid_input(t, data, opt):
    p = run(prog(f"{t} x", "x ni chaduvu", "x ni chupi"), data, opt)
    assert p.rc == 1 and p.out == b"" and "invalid input" in p.err


@pytest.mark.slow
@pytest.mark.parametrize("opt", OPTS)
def test_Q010_junk_in_the_next_token_does_not_affect_the_first(opt):
    p = run(prog("int a", "a ni chaduvu", "a ni chupi"), b"12 abc", opt)
    assert p.rc == 0 and p.text == "12\n"


def test_Q010_reference_interpreter_is_strict():
    from tests.reference.interp import run_ast
    from tests.validation.astutil import ast
    r = run_ast(ast(prog("int x", "x ni chaduvu", "x ni chupi")), b"3.5")
    assert r.status == 1 and r.error == "invalid input"


# ---- Q-011
@pytest.mark.parametrize("lit", ["09", "078", "0189", "08", "0777778", "00009"])
def test_Q011_leading_zero_with_8_or_9_is_invalid_number(lit):
    p = cli("lex", lit + "\n")
    assert p.rc == 1 and any(d[0] == "lexical" and d[1] == "INVALID_NUMBER" for d in p.diags()), p.err


@pytest.mark.parametrize("src,toks", [("123abc", ["123", "abc"]), ("0x", ["0", "x"]), ("12_3", ["12", "_3"]), ("007x", ["007", "x"])])
def test_Q011_digits_followed_by_letter_or_underscore_are_two_tokens_P15(src, toks):
    import json
    p = cli("lex", src + "\n", ("--json",))
    assert p.rc == 0
    assert [t["lexeme"] for t in json.loads(p.out)["data"][:-1]] == toks


# ---- Q-012
def test_Q012_user_supplied_bad_assembly_is_exit_1_assembler_error(tmp_path):
    s = tmp_path / "bad.s"
    s.write_text("garbage\n")
    p = run_cli(["build", str(s), "-o", str(tmp_path / "out")])
    assert p.rc == 1, (p.rc, p.err)
    assert "assembler error" in p.err and "internal compiler error" not in p.err


# ---- F-001 (design lead wording)
def test_F001_message_format(tmp_path):
    src = tmp_path / "a.tel"
    src.write_text("1 ni chupi\n")
    p = run_cli(["build", str(src), "-o", "/nonexistent/dir/out"])
    assert p.rc == 2 and "cannot write output" in p.err and "internal compiler error" not in p.err


# ---- N-001
@pytest.mark.parametrize("opener,closer", [("(", ")"), ("[", "]")])
def test_N001_nesting_1000_is_supported(opener, closer):
    if opener == "(":
        src = "(" * 1000 + "1" + ")" * 1000 + " ni chupi\n"
    else:
        src = "int a[2]\na" + "[0]" * 1 + " ni chupi\n"
    assert cli("sema", src).rc == 0


def test_N001_block_nesting_1000_is_supported():
    src = "nijam ayite { " * 1000 + "}" * 1000 + "\n"
    assert cli("sema", src).rc == 0


@pytest.mark.parametrize("depth", [30000, 100000])
def test_N001_too_deep_is_user_error_not_ice(depth):
    src = "(" * depth + "1" + ")" * depth + " ni chupi\n"
    p = cli("parse", src)
    assert p.rc == 1, f"expected exit 1, got {p.rc}: {p.err[:200]}"
    assert any(d[0] == "syntax" and d[1] == "INVALID_EXPRESSION" for d in p.diags()), p.err[:300]
    assert "internal compiler error" not in p.err


@pytest.mark.parametrize("depth", [30000])
def test_N001_too_deep_blocks_and_unary(depth):
    for src in ("nijam ayite { " * depth + "}" * depth + "\n", "x lo " + "!" * depth + "1 pettu\n"):
        p = cli("sema", src)
        assert p.rc == 1 and "internal compiler error" not in p.err and p.diags(), p.err[:200]
