"""Language behaviour that the line/branch coverage run (Windows, full suite) showed no test reaching:

* constant folding of array dimensions (`compiler/semantic/checker.py` const_eval / convert_const / binary_const):
  float arithmetic, every relational and equality operator on int and float constants, `&&` `||` `!`, unary minus,
  and every cast between int / float / bool / char;
* lexical errors for an empty and a multi-character character literal;
* the parser error for a non-identifier loop variable in `pratisari`.

Constant dimensions are folded at compile time, so a dimension that folds to 0 is a semantic error (plan A-001) and any
other value must give an array whose last element is addressable. Each valid case is also compared with the reference
interpreter at -O0 and -O1.
"""
import pytest

from tests.validation.stress_util import check_against_reference, run

pytestmark = pytest.mark.slow

# (constant dimension expression, value it must fold to; 0 = rejected as INVALID_ARRAY_SIZE)
FOLDS = [
    # float arithmetic
    ("(int)(1.5 + 2.5)", 4), ("(int)(5.5 - 1.5)", 4), ("(int)(1.5 * 2.0)", 3), ("(int)(9.0 / 2.0)", 4), ("(int)(1.0 - 1.0)", 0),
    ("(int)(1.0 / 2.0)", 0), ("(int)(-(-2.5))", 2),
    # float comparisons
    ("(int)(1.0 < 2.0)", 1), ("(int)(2.0 < 1.0)", 0), ("(int)(2.0 > 1.0)", 1), ("(int)(1.0 > 2.0)", 0),
    ("(int)(1.0 <= 1.0)", 1), ("(int)(2.0 <= 1.0)", 0), ("(int)(1.0 >= 1.0)", 1), ("(int)(1.0 >= 2.0)", 0),
    ("(int)(1.0 == 1.0)", 1), ("(int)(1.0 == 2.0)", 0), ("(int)(1.0 != 2.0)", 1), ("(int)(1.0 != 1.0)", 0),
    # int arithmetic and comparisons
    ("3 + 4", 7), ("5 - 4", 1), ("2 * 3", 6), ("7 / 2", 3), ("7 % 4", 3), ("-(-3)", 3),
    ("(int)(3 < 4)", 1), ("(int)(4 < 3)", 0), ("(int)(4 > 3)", 1), ("(int)(3 > 4)", 0),
    ("(int)(3 <= 3)", 1), ("(int)(4 <= 3)", 0), ("(int)(3 >= 3)", 1), ("(int)(3 >= 4)", 0),
    ("(int)(3 == 3)", 1), ("(int)(3 == 4)", 0), ("(int)(3 != 4)", 1), ("(int)(3 != 3)", 0),
    # logical operators
    ("(int)(nijam && nijam)", 1), ("(int)(nijam && abaddham)", 0), ("(int)(abaddham || nijam)", 1),
    ("(int)(abaddham || abaddham)", 0), ("(int)(!abaddham)", 1), ("(int)(!nijam)", 0),
    # casts
    ("(int)(char)300", 44), ("(int)(char)256", 0), ("(int)(char)3.9", 3), ("(int)(bool)5", 1), ("(int)(bool)0", 0),
    ("(int)(bool)0.5", 1), ("(int)(float)3", 3), ("(int)(float)(bool)nijam", 1),
]


@pytest.mark.parametrize("expr,size", FOLDS, ids=[e for e, _ in FOLDS])
def test_constant_dimension_folds(expr, size):
    if size == 0:
        for opt in ("-O0", "-O1"):
            p = run(f"int a[{expr}]\n", opt)
            assert p.rc == 1 and "[INVALID_ARRAY_SIZE]" in p.err and "got 0" in p.err, (opt, p.err)
        return
    src = f"int a[{expr}]\na[{size - 1}] lo 9 pettu\na[{size - 1}] ni chupi\n"
    ref = check_against_reference(src, expect_status=0)
    assert ref.stdout == b"9\n"


def test_empty_character_literal_is_a_lexical_error():
    p = run("char c\nc lo '' pettu\n")
    assert p.rc == 1 and "[INVALID_CHAR_LITERAL]" in p.err and "Empty character literal" in p.err


def test_multi_character_literal_is_a_lexical_error():
    p = run("char c\nc lo 'ab' pettu\n")
    assert p.rc == 1 and "[INVALID_CHAR_LITERAL]" in p.err and "Multi-character character literal" in p.err


def test_pratisari_needs_an_identifier_as_loop_variable():
    p = run("pratisari (int 5; nijam; ) { }\n")
    assert p.rc == 1 and "[INVALID_STATEMENT]" in p.err and "Expected loop variable in pratisari" in p.err
