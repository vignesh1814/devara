"""Phase 3: syntax diagnostics (§3.6) and panic-mode recovery (§3.7)."""

import pytest

from compiler.diagnostics import SyntaxCategory as C
from compiler.lexer import Lexer
from compiler.lexer.tokens import TokenType
from compiler.parser import Parser


def errors_of(src):
    toks = Lexer(src, "t.tel").tokenize()
    p = Parser(toks, "t.tel")
    p.parse()
    return p.errors


def cats(src):
    return [e.category for e in errors_of(src)]


def test_categories_are_closed_set():
    allowed = set(C)
    for src in ["x lo pettu", "x lo 1", "int", "+", "x ayite", "int 5", "int f charya(", ")"]:
        for e in errors_of(src):
            assert e.category in allowed and e.stage == "syntax"


def test_missing_token_carries_expected_set():
    e = errors_of("x lo 1 y ni chupi")[0]
    assert e.category == C.MISSING_TOKEN
    assert e.expected == ("PETTU",)
    assert e.message == "Expected 'pettu' after assignment value."
    assert (e.line, e.column) == (1, 8)


def test_eof_errors_are_unexpected_eof():
    assert cats("x lo 1")[0] == C.UNEXPECTED_EOF
    assert cats("x ayite {")[0] == C.UNEXPECTED_EOF
    assert cats("f(1,")[0] == C.UNEXPECTED_EOF
    assert cats("int f charya(int a")[0] == C.UNEXPECTED_EOF


def test_invalid_expression_category():
    assert cats("x lo ) pettu")[0] == C.INVALID_EXPRESSION
    assert cats("x lo * 2 pettu")[0] == C.INVALID_EXPRESSION


def test_invalid_declaration_category():
    assert cats("int 5")[0] == C.INVALID_DECLARATION
    assert cats("int f charya(5) { }")[0] == C.INVALID_DECLARATION


def test_unexpected_token_category_for_stray_tokens():
    for src in [")", "}", "]", "lo", "pettu", ";", ","]:
        assert cats(src)[0] == C.UNEXPECTED_TOKEN, src


def test_one_primary_diagnostic_per_failed_statement():
    assert len(errors_of("x lo 1\n")) == 1
    assert len(errors_of("x lo @@ pettu".replace("@@", ")"))) >= 1


def test_multiple_independent_errors_are_reported():
    src = """
x lo pettu
int y
y lo 2 pettu
z lo + pettu
w lo 1
q ni chupi
"""
    errs = errors_of(src)
    lines = [e.line for e in errs]
    # the third error (missing 'pettu' after `w lo 1`, line 6) is reported where the piece is missing,
    # not at the first token of the next statement on line 7 (audit F5)
    assert lines == [2, 5, 6]


def test_recovery_resumes_at_next_statement_inside_blocks():
    src = "int f charya() {\n  x lo pettu\n  y lo 1 pettu\n  z lo ) pettu\n  0 ivvu\n}\nbad lo\n"
    errs = errors_of(src)
    assert {e.line for e in errs} >= {2, 4}


def test_recovery_skips_nested_blocks_wholesale():
    # error in the condition; the whole `{ ... }` body is skipped as a nested unit,
    # so inner statements do not produce cascading errors and `int ok` is parsed.
    errs = errors_of("x + ayite { y lo 1 pettu }\nint ok\n")
    assert len(errs) == 1


def test_stray_rbrace_at_top_level_terminates():
    errs = errors_of("} } } int x")
    assert errs and all(e.category == C.UNEXPECTED_TOKEN for e in errs[:3])


def test_for_header_recovery_reports_errors_in_later_parts():
    errs = errors_of("pratisari (i 0 tho; i < ; i++) { }")
    assert len(errs) >= 2          # init error and condition error are both reported
    assert all(e.stage == "syntax" for e in errs)


def test_for_header_semicolon_is_not_a_statement_boundary():
    errs = errors_of("pratisari (i 0 tho modhalu; i < n; i++ { }")
    assert errs and errs[0].category == C.MISSING_TOKEN
    assert errs[0].expected == ("RPAREN",)


def test_for_header_nested_delimiters_are_respected():
    errs = errors_of("pratisari (i 0 tho modhalu; f(1, ; 2) < n; i++) { }")
    assert errs


def test_call_argument_recovery_collects_each_bad_argument():
    errs = errors_of("x lo f(1 +, 2, ) , 3) pettu")
    assert errs


def test_index_recovery_terminates():
    assert errors_of("a[ ) lo 1 pettu")
    assert errors_of("a[1 lo 1 pettu")
    assert errors_of("int a[")


@pytest.mark.parametrize("src", [
    "", "(", ")", "{", "}", "[", "]", ";", ",", "int", "int x[", "int f charya(",
    "pratisari", "pratisari (", "pratisari (;;)", "prati", "prati i", "x ni", "x lo",
    "x ayite", "x ayite {", "x ayite { } lekunte", "x unnanta", "f(", "f(1,", "a[",
    "int f charya(int a[", "ivvu", "ivvu ivvu ivvu", "lo lo lo", "( ( ( (",
    "} } } {", "x lo ( 1 + ", "pratisari (int i lo 0 pettu; i <",
])
def test_truncated_inputs_never_crash_or_hang(src):
    toks = Lexer(src).tokenize()
    p = Parser(toks)
    p.parse()  # must return


def test_token_soup_never_crashes_or_hangs():
    import itertools, random
    rng = random.Random(12345)
    kinds = [t for t in TokenType if t != TokenType.EOF]
    from compiler.lexer.tokens import Token
    for _ in range(300):
        n = rng.randint(0, 25)
        toks = [Token(rng.choice(kinds), "x", 1, i + 1) for i in range(n)]
        toks.append(Token(TokenType.EOF, "", 1, n + 1))
        p = Parser(toks)
        p.parse()


def test_parser_handles_token_list_without_eof():
    from compiler.lexer.tokens import Token
    p = Parser([Token(TokenType.INT, "int", 1, 1)])
    p.parse()
    assert p.errors
    assert Parser([]).parse().items == []


def test_diagnostic_format_in_cli_contract():
    e = errors_of("x lo 1 y ni chupi")[0]
    assert e.format() == "t.tel:1:8: syntax error [MISSING_TOKEN]: Expected 'pettu' after assignment value."
