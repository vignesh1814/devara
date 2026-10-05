"""Regression: statements after ivvu/aapu/saagu in the same block used to crash lowering
(AssertionError -> internal compiler error, exit 3) when the unreachable statement was itself
a terminator or produced no instruction (e.g. a second ``ivvu`` of a constant)."""

import pytest

from tests.helpers.pipeline import run_ir


def prog(*lines):
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("level", [0, 1])
def test_bug_second_return_after_return(level):
    src = prog("int f charya () {", "  1 ivvu", "  2 ivvu", "}", "f() ni chupi")
    assert run_ir(src, b"", level) == (b"1\n", 0, "")


@pytest.mark.parametrize("level", [0, 1])
def test_bug_break_then_continue_and_return_in_loop(level):
    src = prog(
        "int f charya () {",
        "  int i",
        "  i lo 0 pettu",
        "  i < 5 unnanta varaku {",
        "    i lo i + 1 pettu",
        "    i == 3 ayite { aapu saagu 9 ivvu }",
        "  }",
        "  i ivvu",
        "}",
        "f() ni chupi",
    )
    assert run_ir(src, b"", level) == (b"3\n", 0, "")
