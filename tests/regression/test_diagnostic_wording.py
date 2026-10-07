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
