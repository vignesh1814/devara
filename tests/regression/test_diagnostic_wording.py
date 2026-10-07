"""Audit F6: operator diagnostics use the source spelling of the operator (not the internal enum names)."""

import pytest

from compiler.diagnostics import SemCategory as S
from tests.unit.test_semantic import reject


@pytest.mark.parametrize("expr, op", [
    ('"a" - "b"', "-"), ('"a" * "b"', "*"), ('"a" / "b"', "/"), ('"a" % "b"', "%"),
    ('"a" < "b"', "<"), ('"a" >= "b"', ">="), ('"a" + 1', "+"), ('1 == "b"', "=="),
])
def test_f6_binary_operator_is_spelled_as_in_the_source(expr, op):
    d = reject(f"{expr} ni chupi\n", S.INVALID_OPERAND)
    assert d[0].message.startswith(f"operator '{op}' cannot be applied to "), d[0].message


@pytest.mark.parametrize("expr, op", [('-"a"', "-"), ('+"a"', "+"), ('!"a"', "!")])
def test_f6_unary_operator_is_named(expr, op):
    d = reject(f"{expr} ni chupi\n", S.INVALID_OPERAND)
    assert d[0].message == f"operator '{op}' cannot be applied to padham", d[0].message


# ── parser diagnostics (audit F4, F5) ──

from compiler.lexer import Lexer  # noqa: E402
from compiler.parser import Parser  # noqa: E402


def syntax_errors(src):
    parser = Parser(Lexer(src).tokenize())
    parser.parse()
    return [(e.category.value, e.span.start_line, e.span.start_column) for e in parser.errors]


def test_f4_misspelled_output_keyword_is_one_error_not_two():
    src = 'int x\nx lo 5 pettu\nx ni chupi2\n"after" ni chupi\n'
    assert syntax_errors(src) == [("MISSING_TOKEN", 3, 6)]


def test_f4_misspelled_input_keyword_is_one_error_not_two():
    assert syntax_errors("int x\nx ni chaduvuu\nx ni chupi\n") == [("MISSING_TOKEN", 2, 6)]


def test_f4_a_later_statement_after_the_typo_is_still_checked():
    src = "int x\nx ni chupi2\nx lo 1\nx ni chupi\n"      # the next statement lacks 'pettu': a genuine second error
    assert [c for c, _, _ in syntax_errors(src)] == ["MISSING_TOKEN", "MISSING_TOKEN"]


def test_f5_missing_pettu_is_reported_after_the_expression():
    assert syntax_errors("int x\nx lo 5\nx ni chupi\n") == [("MISSING_TOKEN", 2, 7)]


def test_f5_expression_without_a_statement_keyword_is_reported_after_it():
    assert syntax_errors("int f charya (int a) {\n    a + 1\n}\n") == [("INVALID_STATEMENT", 2, 10)]


def test_f5_same_line_errors_still_point_at_the_offending_token():
    assert syntax_errors("int x\nx lo pettu\n") == [("INVALID_EXPRESSION", 2, 6)]
