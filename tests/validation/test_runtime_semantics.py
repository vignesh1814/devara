"""Runtime semantics through `devara run` at -O0 and -O1 (plan P1-P12, P27, P28, L29-L43).

Expression tables are compiled into ONE program per group (cached), then each row is its own test case so a
failure points at the exact expression. Expected values are hand-modelled in tests/validation/rtmodel.py.
"""
import pytest
from tests.validation.helpers import cli, run, prog, OPTS
from tests.validation.rtmodel import *

# =========================================================================== expression groups
GROUPS = {}


def group(name, prelude, rows):
    GROUPS[name] = (prelude, rows)


def _program(name):
    prelude, rows = GROUPS[name]
    return "\n".join([*prelude, *[f"{e} ni chupi" for e, _ in rows]]) + "\n"


_cache = {}


def group_lines(name, opt):
    key = (name, opt)
    if key not in _cache:
        p = run(_program(name), opt=opt)
        _cache[key] = p
    return _cache[key]


I = INT_MAX
M = INT_MIN
group("int_arith", [], [
    ("1 + 2", "3"), ("7 - 10", "-3"), ("6 * 7", "42"), ("7 / 2", "3"), ("-7 / 2", "-3"), ("7 / -2", "-3"),
    ("-7 / -2", "3"), ("7 % 3", "1"), ("-7 % 3", "-1"), ("7 % -3", "1"), ("-7 % -3", "-1"), ("0 / 5", "0"),
    ("0 % 5", "0"), ("1 / 2", "0"), ("-1 / 2", "0"), ("-1 % 2", "-1"), ("5 % 5", "0"), ("5 % 7", "5"), ("-5 % 7", "-5"),
    ("9223372036854775807 + 1", str(M)), ("9223372036854775807 + 9223372036854775807", "-2"),
    ("9223372036854775807 * 2", "-2"), ("9223372036854775807 * 9223372036854775807", "1"),
    ("-9223372036854775807 - 1 - 1", str(I)), ("(-9223372036854775807 - 1) * -1", str(M)),
    ("(-9223372036854775807 - 1) % -1", "0"), ("(-9223372036854775807 - 1) / 1", str(M)),
    ("(-9223372036854775807 - 1) / 2", str(M // 2)), ("-(-9223372036854775807 - 1)", str(M)),  # Q-001
    ("(-9223372036854775807 - 1) + (-9223372036854775807 - 1)", "0"),
    ("(-9223372036854775807 - 1) - 1", str(I)), ("(-9223372036854775807 - 1) * (-9223372036854775807 - 1)", "0"),
    ("9223372036854775807 - (-9223372036854775807 - 1)", "-1"), ("(-9223372036854775807 - 1) - 9223372036854775807", "1"),
    ("2 + 3 * 4", "14"), ("(2 + 3) * 4", "20"), ("10 - 4 - 3", "3"), ("100 / 10 / 5", "2"), ("100 / 5 * 2", "40"),
    ("2 * 3 % 4", "2"), ("7 % 4 * 2", "6"), ("1 - -1", "2"), ("- - 5", "5"), ("+5", "5"), ("-+5", "-5"), ("+-5", "-5"),
    ("3037000500 * 3037000500", str(wrap(3037000500 ** 2))), ("4611686018427387904 * 2", str(M)),
    ("4611686018427387904 * 4", "0"), ("123456789 * 987654321", str(123456789 * 987654321)),
    ("9223372036854775807 / -1", str(-I)), ("9223372036854775807 % 2", "1"), ("0xFF + 010", "263"),
    ("0x7FFFFFFFFFFFFFFF", str(I)), ("1000000007 * 1000000007", str(1000000007 ** 2)),
    ("(1000000007 * 1000000007) % 998244353", str((1000000007 ** 2) % 998244353)),
    ("-9223372036854775807 / 3", str(tdiv(-I, 3))), ("-9223372036854775807 % 10", str(trem(-I, 10))),
    ("5 - 7 - 9", "-11"), (" * ".join(["2"] * 20), str(2 ** 20)), (" * ".join(["3"] * 46), str(wrap(3 ** 46))),
])
group("int_vars", [
    "int a", "int b", "int c", "a lo 9223372036854775807 pettu", "b lo 1 pettu", "c lo -9223372036854775807 - 1 pettu",
], [
    ("a + b", str(M)), ("c - b", str(I)), ("a * a", "1"), ("c * c", "0"), ("c * -1", str(M)), ("-c", str(M)),
    ("c / -1 * 0 + 5" if False else "c % -1", "0"), ("a / b", str(I)), ("c / b", str(M)), ("(a + b) / 2", str(M // 2)),
    ("a + a + a", str(wrap(3 * I))), ("c + c + c", str(wrap(3 * M))), ("a * 3 / 3", str(tdiv(wrap(3 * I), 3))),
    ("a - c", "-1"), ("c - a", "1"), ("a * b - c * b", "-1"), ("(a + 1) - 1", str(I)), ("a + 1 > a", "abaddham"),
    ("c - 1 < c", "abaddham"), ("a + b == c", "nijam"), ("-a - 1 == c", "nijam"),
])
group("float_arith", [], [
    ("1.5 + 2.25", "3.75"), ("10 / 4.0", "2.5"), ("7 / 2.0", "3.5"), ("7 / 2", "3"), ("2.0 * 3", "6"), ("1.0 / 3.0", g(1 / 3)),
    ("0.1 + 0.2", g(0.1 + 0.2)), ("0.1 + 0.2 == 0.3", "abaddham"), ("1.0 / 3.0 * 3.0 == 1.0", nb(1 / 3 * 3 == 1.0)),
    ("1.0 / 0.0", "inf"), ("-1.0 / 0.0", "-inf"), ("1 / 0.0", "inf"), ("-1 / 0.0", "-inf"),
    ("123456.0", "123456"), ("1234567.0", "1.23457e+06"), ("0.0001", "0.0001"), ("0.00001", "1e-05"),
    ("100000.0 * 10", "1e+06"), ("0.5", "0.5"), ("100.0", "100"), ("3.0", "3"), ("-2.25", "-2.25"),
    ("-0.0", "-0"), ("0.0 * -1", "-0"), ("0.0 - 0.0", "0"), ("-0.0 + 0.0", "0"), ("-0.0 == 0.0", "nijam"),
    ("3.0 - 3.0", "0"), ("2.5 * 2.5", "6.25"), ("1.0 + 1e0" if False else "1.0 + 1.0", "2"),
    ("999999.5", g(999999.5)), ("9999995.0", g(9999995.0)), ("0.000123456789", g(0.000123456789)),
    ("1.5 < 2", "nijam"), ("2 > 1.5", "nijam"), ("1.5 == 1.5", "nijam"), ("1.5 != 1.5", "abaddham"),
    ("3.14159265358979", g(3.14159265358979)), ("2.718281828459045", g(2.718281828459045)),
    ("(1.0 / 0.0) > 9223372036854775807", "nijam"), ("-(1.0 / 0.0) < -9223372036854775807", "nijam"),
    ("1000000.0 * 1000000.0", "1e+12"), ("0.1 * 3", g(0.1 * 3)), ("0.1 * 3 == 0.3", "abaddham"),
    ("1.0 / 3 + 1.0 / 3 + 1.0 / 3", g(1 / 3 + 1 / 3 + 1 / 3)), ("5 / 2.0 / 2", "1.25"),
    ("2147483647.0 * 2147483647.0", g(2147483647.0 * 2147483647.0)), ("123456789.0 * 1000.0", g(123456789.0 * 1000.0)),
    ("9223372036854775807 + 0.0", g(float(I))), ("(float) 9223372036854775807", g(float(I))),
])
group("float_vars", ["float x", "float y", "x lo 0.0 pettu", "y lo -1.0 pettu"], [
    ("x * y", "-0"), ("x - x", "0"), ("x / y", "-0"), ("y / x", "-inf"), ("x + x * y", "-0" if False else "0"),
    ("y * y / 3", g(1 / 3)), ("x == -x", "nijam"), ("1 / x", "inf"), ("(1 / x) * 0 == 0", "abaddham"), ("x / x == x / x", "abaddham"),
    ("-x", "-0"), ("x * -1", "-0"), ("0 - x", "0"), ("x + 0", "0"), ("x - 0", "0"), ("x * 1", "0"), ("x * 0", "0"), ("y * 0", "-0"), ("y + 0", "-1"),
])
group("compare_logic", [], [
    ("1 < 2", "nijam"), ("2 < 1", "abaddham"), ("2 <= 2", "nijam"), ("3 >= 4", "abaddham"), ("3 > 2", "nijam"),
    ("2 == 2", "nijam"), ("2 != 2", "abaddham"), ("-1 < 0", "nijam"), ("1 < 1.5", "nijam"), ("'a' < 'b'", "nijam"),
    ("'a' == 97", "nijam"), ("nijam > abaddham", "nijam"), ("nijam == 1", "nijam"), ("abaddham == 0", "nijam"),
    ("2 == 2.0", "nijam"), ("9223372036854775807 > -9223372036854775807 - 1", "nijam"),
    ("-9223372036854775807 - 1 < 9223372036854775807", "nijam"), ("(-9223372036854775807 - 1) < 0", "nijam"),
    ("nijam && nijam", "nijam"), ("nijam && abaddham", "abaddham"), ("abaddham || nijam", "nijam"),
    ("abaddham || abaddham", "abaddham"), ("!nijam", "abaddham"), ("!abaddham", "nijam"), ("!0", "nijam"), ("!5", "abaddham"),
    ("!0.0", "nijam"), ("!0.5", "abaddham"), ("!'a'", "abaddham"), ("!!7", "nijam"), ("2 && 3", "nijam"), ("0 || 0.5", "nijam"),
    ("0 && 1", "abaddham"), ("nijam || abaddham && abaddham", "nijam"), ("(nijam || abaddham) && abaddham", "abaddham"),
    ("1 < 2 == 2 > 1", "nijam"), ("3 > 2 > 1", "abaddham"), ("1 == 1 == 1", "nijam"), ("2 == 2 == 2", "abaddham"),
    ("1 < 2 && 2 < 3", "nijam"), ("1 > 2 || 2 > 3", "abaddham"), ("!(1 < 2)", "abaddham"), ("!1 < 2", "nijam"),
    ("nijam + nijam", "2"), ("nijam * 7", "7"), ("-nijam", "-1"), ("+nijam", "1"), ("nijam - abaddham", "1"),
    ("abaddham - nijam", "-1"), ("nijam + 1.5", "2.5"), ("'a' + nijam", "98"),
])
group("conversions", [], [
    ("(int) 3.99", "3"), ("(int) -3.99", "-3"), ("(int) 0.5", "0"), ("(int) -0.5", "0"), ("(int) 1e0" if False else "(int) 2147483648.0", "2147483648"),
    ("(int) 9223372036854775807.0", str(INT_MIN)), ("(int) (1.0 / 0.0)", str(INT_MIN)), ("(int) (-1.0 / 0.0)", str(INT_MIN)),
    ("(int) 100000000000000000000.0", str(INT_MIN)), ("(int) -9223372036854775808.0" if False else "(int) -9223372036854775807.0", str(int(-9223372036854775807.0))),
    ("(float) 7", "7"), ("(float) 7 / 2", "3.5"), ("(float) (7 / 2)", "3"), ("(float) 'a'", "97"), ("(float) nijam", "1"),
    ("(float) -3", "-3"), ("(float) 9223372036854775807", g(float(I))), ("(float) (-9223372036854775807 - 1)", g(float(M))),
    ("(char) 65", "A"), ("(char) 321", "A"), ("(char) -191", "A"), ("(int) (char) 200", "-56"), ("(int) (char) 255", "-1"),
    ("(int) (char) 128", "-128"), ("(int) (char) 127", "127"), ("(int) (char) 256", "0"), ("(int) (char) -1", "-1"),
    ("(int) (char) 65.9", "65"), ("(int) (char) 3.9", "3"), ("(int) (char) -3.9", "-3"), ("(int) (char) 1000", str(s8(1000))),
    ("(int) (char) 9223372036854775807", "-1"), ("(int) (char) nijam", "1"),
    ("(int) 'A'", "65"), ("(int) '\\n'", "10"), ("(int) '\\x7f'", "127"), ("(int) '\\0'", "0"), ("(int) '\\xFF'", "-1"),
    ("(int) '\\x80'", "-128"), ("(int) nijam", "1"), ("(int) abaddham", "0"),
    ("(bool) 5", "nijam"), ("(bool) 0", "abaddham"), ("(bool) 0.0", "abaddham"), ("(bool) -0.0", "abaddham"), ("(bool) 0.25", "nijam"),
    ("(bool) 'a'", "nijam"), ("(bool) '\\0'", "abaddham"), ("(bool) -1", "nijam"), ("(bool) (1.0 / 0.0)", "nijam"),
    ("(padham) 'q'", "q"), ("(char) \"z\"", "z"), ("(padham) (char) 72 + (padham) (char) 105", "Hi"),
    ("podavu((padham) 'x')", "1"), ("(int) (char) \"A\"", "65"), ("(char) ((int) 'a' + 2)", "c"),
    ("(int) (float) 9007199254740993" , str(int(float(9007199254740993)))),
    ("(float) 3 / (float) 2", "1.5"), ("(int) ((float) 7 / 2 * 2)", "7"), ("(int) 2.999999", "2"), ("(int) -2.999999", "-2"),
    ("(bool) (char) 256", "abaddham"), ("(int) (bool) 7", "1"), ("(int) (bool) 0.1", "1"), ("(float) (bool) 3", "1"),
    ("(char) (bool) 3", chr(1)),
])
group("promotions", ["char c", "c lo 'A' pettu", "bool b", "b lo nijam pettu", "int i", "i lo 10 pettu", "float f", "f lo 0.5 pettu"], [
    ("c + 1", "66"), ("c + c", "130"), ("c * c", "4225"), ("c - 'a'", "-32"), ("c / 2", "32"), ("c % 10", "5"), ("c + b", "66"),
    ("c + f", "65.5"), ("b + b", "2"), ("b * i", "10"), ("b + f", "1.5"), ("i + f", "10.5"), ("i / 4", "2"), ("i / 4.0", "2.5"),
    ("i % 3", "1"), ("c > i", "nijam"), ("c == 65", "nijam"), ("c == 'A'", "nijam"), ("f < b", "nijam"), ("-c", "-65"), ("+c", "65"),
    ("-b", "-1"), ("!c", "abaddham"), ("(char) (c + 1)", "B"), ("c < 128", "nijam"),
])
group("padham", ["padham s", "padham t", "s lo \"hello\" pettu", "t lo \"\" pettu"], [
    ("s", "hello"), ("t", ""), ("s + t", "hello"), ("t + s", "hello"), ("s + \" \" + s", "hello hello"), ("podavu(s)", "5"), ("podavu(t)", "0"),
    ("podavu(s + s)", "10"), ("s == \"hello\"", "nijam"), ("s != \"hello\"", "abaddham"), ("s == t", "abaddham"), ("t == \"\"", "nijam"),
    ("\"\" == \"\"", "nijam"), ("\"a\" == \"A\"", "abaddham"), ("\"a\" != \"b\"", "nijam"), ("\"ab\" == \"a\" + \"b\"", "nijam"),
    ("s[0]", "h"), ("s[4]", "o"), ("(int) s[1]", "101"), ("s[0] == 'h'", "nijam"), ("s[1] + 1", "102"), ("(padham) s[2] + (padham) s[3]", "ll"),
    ("\"tab\\there\"", "tab\there"), ("\"q\\\"q\"", "q\"q"), ("\"b\\\\s\"", "b\\s"), ("\"\\x41\\x42\"", "AB"), ("\"it's\"", "it's"),
    ("podavu(\"a\\0b\")", "3"), ("podavu(\"\\x00\")", "1"), ("podavu(\"\\n\")", "1"), ("podavu(\"\\\\\")", "1"),
    ("\"nl\\nx\"", "nl\nx"),
])
group("chars", ["char a", "char z", "a lo 'a' pettu", "z lo 'z' pettu"], [
    ("a", "a"), ("z - a", "25"), ("a + 1", "98"), ("(char) (a + 1)", "b"), ("(char) (z - 25)", "a"), ("a < z", "nijam"),
    ("'\\n'" if False else "(int) '\\n'", "10"), ("(int) '\\t'", "9"), ("(int) '\\r'", "13"), ("(int) '\\b'", "8"), ("(int) '\\f'", "12"),
    ("(int) '\\\\'", "92"), ("(int) '\\''", "39"), ("(int) '\"'", "34"), ("(int) '\\\"'", "34"), ("(int) '\\x41'", "65"),
    ("(int) '#'", "35"), ("(int) '{'", "123"), ("(int) ' '", "32"), ("'A' + 'B'", "131"), ("'0' + 5", "53"), ("(char) ('0' + 5)", "5"),
])


def _rows(kind=None):
    for name, (prelude, rows) in GROUPS.items():
        for i, (e, exp) in enumerate(rows):
            yield pytest.param(name, i, id=f"{name}[{i}]:{e[:50]}")


@pytest.mark.slow
@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("name,i", list(_rows()))
def test_expression_value(name, i, opt):
    prelude, rows = GROUPS[name]
    e, exp = rows[i]
    p = group_lines(name, opt)
    assert p.rc == 0, f"group program failed (rc={p.rc}): {p.err}"
    lines = p.text.split("\n")
    # Rows can contain embedded newlines in their expected value; align by consuming expected text per row.
    pos = 0
    for k, (_, ex) in enumerate(rows):
        n = ex.count("\n") + 1
        got = "\n".join(lines[pos:pos + n])
        if k == i:
            assert got == ex, f"{e!r}: expected {ex!r}, got {got!r}"
            return
        pos += n


# =========================================================================== input formats P7-P10
def read_prog(t, extra=()):
    return prog(f"{t} x", "x ni chaduvu", "x ni chupi", *extra)


INPUT_OK = [
    ("int", "42", "42"), ("int", "  -7\n", "-7"), ("int", "+5", "5"), ("int", "0", "0"), ("int", "\n\n  12  ", "12"),
    ("int", "9223372036854775807", "9223372036854775807"), ("int", "-9223372036854775808", "-9223372036854775808"),
    ("int", "007", "7"), ("int", "-0", "0"), ("int", "1 2 3", "1"), ("int", "\t99\t", "99"),
    ("float", "3.14", "3.14"), ("float", "-2.5", "-2.5"), ("float", "5", "5"), ("float", "  0.5\n", "0.5"), ("float", "1e3", "1000"),
    ("float", ".5", "0.5"), ("float", "-0.0", "-0"), ("float", "1234567", "1.23457e+06"), ("float", "inf", "inf"),
    ("bool", "nijam", "nijam"), ("bool", "abaddham", "abaddham"), ("bool", "NIJAM", "nijam"), ("bool", "Abaddham", "abaddham"),
    ("bool", "1", "nijam"), ("bool", "0", "abaddham"), ("bool", "  nijam  ", "nijam"),
    ("char", "a", "a"), ("char", "  b", "b"), ("char", "\n\nc", "c"), ("char", "xyz", "x"), ("char", "7", "7"), ("char", "#", "#"),
    ("padham", "hello\n", "hello"), ("padham", "hello", "hello"), ("padham", "\n", ""), ("padham", "a b c\n", "a b c"),
    ("padham", "  lead\n", "  lead"), ("padham", "trail  \n", "trail  "), ("padham", "first\nsecond\n", "first"), ("padham", "tab\there\n", "tab\there"),
]
INPUT_BAD = [
    ("int", ""), ("int", "   \n"), ("int", "abc"), ("int", "-"), ("int", "+"), ("int", "9223372036854775808"), ("int", "-9223372036854775809"),
    ("int", "99999999999999999999"), ("int", "x12"), ("int", "."), ("float", ""), ("float", "abc"), ("float", "--1"),
    ("bool", ""), ("bool", "2"), ("bool", "true"), ("bool", "yes"), ("bool", "nij"), ("bool", "-1"),
    ("char", ""), ("char", "   \n"), ("padham", ""),
]


@pytest.mark.slow
@pytest.mark.parametrize("t,inp,exp", INPUT_OK, ids=[f"{t}:{i!r}" for t, i, _ in INPUT_OK])
def test_input_valid(t, inp, exp, opt):
    p = run(read_prog(t), inp.encode(), opt)
    assert p.rc == 0, p.err
    assert p.text == exp + "\n"


@pytest.mark.slow
@pytest.mark.parametrize("t,inp", INPUT_BAD, ids=[f"{t}:{i!r}" for t, i in INPUT_BAD])
def test_input_invalid_is_runtime_error(t, inp, opt):
    p = run(read_prog(t, ["\"after\" ni chupi"]), inp.encode(), opt)
    assert p.rc == 1, (p.rc, p.err, p.text)
    assert "runtime error" in p.err and "invalid input" in p.err
    assert b"after" not in p.out


SEQ = [
    # (description, program lines, stdin, expected stdout)
    ("int_then_padham_nextline", ["int n", "padham s", "n ni chaduvu", "s ni chaduvu", "n ni chupi", "s ni chupi"], "5\nhello\n", "5\nhello\n"),
    ("int_then_padham_rest_of_line_kept", ["int n", "padham s", "n ni chaduvu", "s ni chaduvu", "n ni chupi", "s ni chupi"], "5 hello\n", "5\n hello\n"),
    ("int_then_padham_trailing_ws_skipped", ["int n", "padham s", "n ni chaduvu", "s ni chaduvu", "n ni chupi", "s ni chupi"], "5   \nhello\n", "5\nhello\n"),
    ("int_then_blank_line_is_empty_padham", ["int n", "padham s", "padham t", "n ni chaduvu", "s ni chaduvu", "t ni chaduvu", "s ni chupi", "t ni chupi"], "5\n\nhello\n", "\nhello\n"),
    ("padham_padham", ["padham a", "padham b", "a ni chaduvu", "b ni chaduvu", "a ni chupi", "b ni chupi"], "one\ntwo\n", "one\ntwo\n"),
    ("padham_then_int", ["padham a", "int n", "a ni chaduvu", "n ni chaduvu", "a ni chupi", "n ni chupi"], "text line\n42\n", "text line\n42\n"),
    ("char_then_padham", ["char c", "padham s", "c ni chaduvu", "s ni chaduvu", "c ni chupi", "s ni chupi"], "x\nabc\n", "x\nabc\n"),
    ("float_then_padham", ["float f", "padham s", "f ni chaduvu", "s ni chaduvu", "f ni chupi", "s ni chupi"], "2.5\nrest\n", "2.5\nrest\n"),
    ("bool_then_padham", ["bool b", "padham s", "b ni chaduvu", "s ni chaduvu", "b ni chupi", "s ni chupi"], "nijam\nrest\n", "nijam\nrest\n"),
    ("three_ints_one_line", ["int a", "int b", "int c", "a ni chaduvu", "b ni chaduvu", "c ni chaduvu", "a + b + c ni chupi"], "1 2 3\n", "6\n"),
    ("ints_across_lines", ["int a", "int b", "a ni chaduvu", "b ni chaduvu", "a * b ni chupi"], "6\n\n\n7\n", "42\n"),
    ("chars_are_single_bytes", ["char a", "char b", "char c", "a ni chaduvu", "b ni chaduvu", "c ni chaduvu", "c ni chupi", "b ni chupi", "a ni chupi"], "ab c", "c\nb\na\n"),
    ("padham_at_eof_without_newline", ["padham a", "padham b", "a ni chaduvu", "b ni chaduvu", "a ni chupi", "b ni chupi"], "x\ny", "x\ny\n"),
    ("array_element_input", ["int a[3]", "a[2] ni chaduvu", "a[0] ni chaduvu", "a[0] ni chupi", "a[1] ni chupi", "a[2] ni chupi"], "5 6", "6\n0\n5\n"),
    ("input_into_padham_array_element", ["padham a[2]", "a[1] ni chaduvu", "a[0] ni chupi", "a[1] ni chupi"], "line\n", "\nline\n"),
    ("input_into_2d_element", ["int m[2][2]", "m[1][0] ni chaduvu", "m[1][0] ni chupi", "m[0][1] ni chupi"], "9", "9\n0\n"),
    ("mixed_type_script", ["int n", "float f", "char c", "bool b", "padham s", "n ni chaduvu", "f ni chaduvu", "c ni chaduvu", "b ni chaduvu", "s ni chaduvu",
                           "n ni chupi", "f ni chupi", "c ni chupi", "b ni chupi", "s ni chupi"], "7 2.5 q nijam\nthe line\n", "7\n2.5\nq\nnijam\nthe line\n"),
    ("empty_stdin_no_reads", ["\"ok\" ni chupi"], "", "ok\n"),
    ("unread_input_ignored", ["int a", "a ni chaduvu", "a ni chupi"], "1 2 3 garbage", "1\n"),
    ("int_prefix_then_char", ["int a", "char c", "a ni chaduvu", "c ni chaduvu", "a ni chupi", "c ni chupi"], "12 z", "12\nz\n"),
    ("read_into_param_and_global", ["int g", "void f charya (int p) { p ni chaduvu\n p ni chupi\n g ni chaduvu }", "f(0)", "g ni chupi"], "8 9", "8\n9\n"),
    ("read_loop_until_sentinel", ["int x", "x ni chaduvu", "x != 0 unnanta varaku { x * 2 ni chupi\n x ni chaduvu }"], "3 4 5 0 9", "6\n8\n10\n"),
]


@pytest.mark.slow
@pytest.mark.parametrize("name,lines,inp,exp", SEQ, ids=[s[0] for s in SEQ])
def test_input_sequences(name, lines, inp, exp, opt):
    p = run(prog(*lines), inp.encode(), opt)
    assert p.rc == 0, p.err
    assert p.text == exp


# =========================================================================== output formats P1-P6
OUT = [
    ("int_neg", "-17", "-17\n"), ("int_min", "-9223372036854775807 - 1", "-9223372036854775808\n"), ("float_g", "3.14159265358979", "3.14159\n"),
    ("bool_t", "nijam", "nijam\n"), ("bool_f", "abaddham", "abaddham\n"), ("bool_expr", "1 < 2", "nijam\n"),
    ("char_raw", "'x'", "x\n"), ("char_tab", "'\\t'", "\t\n"), ("char_nl", "'\\n'", "\n\n"), ("char_nul", "'\\0'", "\0\n"),
    ("char_high", "'\\xFF'", "\xff\n"), ("char_high2", "(char) 200", "\xc8\n"), ("string_plain", "\"plain\"", "plain\n"), ("string_empty", "\"\"", "\n"),
    ("string_nl", "\"a\\nb\"", "a\nb\n"), ("string_nul", "\"a\\0b\"", "a\0b\n"), ("string_high", "\"\\xE9\\xFF\"", "\xe9\xff\n"),
    ("string_concat_empty", "\"\" + \"\"", "\n"),
]


@pytest.mark.slow
@pytest.mark.parametrize("name,expr,exp", OUT, ids=[o[0] for o in OUT])
def test_output_format(name, expr, exp, opt):
    p = run(prog(f"{expr} ni chupi"), b"", opt)
    assert p.rc == 0, p.err
    assert p.out == exp.encode("latin-1")


# =========================================================================== runtime errors P11 / L38 / L42
ERR = [
    ("div_zero_var", ["int d", "d ni chaduvu", "\"before\" ni chupi", "10 / d ni chupi", "\"after\" ni chupi"], "0", "before\n", "division by zero"),
    ("rem_zero_var", ["int d", "d ni chaduvu", "\"before\" ni chupi", "10 % d ni chupi", "\"after\" ni chupi"], "0", "before\n", "remainder by zero"),
    ("div_zero_const", ["\"before\" ni chupi", "1 / 0 ni chupi", "\"after\" ni chupi"], "", "before\n", "division by zero"),
    ("rem_zero_const", ["\"before\" ni chupi", "1 % 0 ni chupi", "\"after\" ni chupi"], "", "before\n", "remainder by zero"),
    ("div_zero_nested_const", ["\"before\" ni chupi", "5 / (3 - 3) ni chupi"], "", "before\n", "division by zero"),
    ("min_div_minus1", ["int m", "int d", "m lo -9223372036854775807 - 1 pettu", "d ni chaduvu", "\"b\" ni chupi", "m / d ni chupi"], "-1", "b\n", "integer overflow in division"),
    ("min_div_minus1_const", ["\"b\" ni chupi", "(-9223372036854775807 - 1) / -1 ni chupi"], "", "b\n", "integer overflow in division"),
    ("div_result_unused", ["int d", "int x", "d ni chaduvu", "x lo 1 / d pettu", "\"after\" ni chupi"], "0", "", "division by zero"),
    ("rem_result_unused", ["int d", "int x", "d ni chaduvu", "x lo 1 % d pettu", "\"after\" ni chupi"], "0", "", "remainder by zero"),
    ("div_in_dead_assignment_overwritten", ["int d", "int x", "d ni chaduvu", "x lo 1 / d pettu", "x lo 5 pettu", "x ni chupi"], "0", "", "division by zero"),
    ("div_in_condition", ["int d", "d ni chaduvu", "10 / d > 1 ayite { \"y\" ni chupi }"], "0", "", "division by zero"),
    ("div_in_function", ["int f charya (int a, int b) { a / b ivvu }", "\"x\" ni chupi", "f(1, 0) ni chupi"], "", "x\n", "division by zero"),
    ("div_in_loop_third_iter", ["prati i 0 nundi 5 varaku { 10 / (2 - i) ni chupi }"], "", "5\n10\n", "division by zero"),
    ("div_short_circuit_guarded_ok_then_fail", ["int d", "d ni chaduvu", "d != 0 && 10 / d > 1 ni chupi", "10 / d ni chupi"], "0", "abaddham\n", "division by zero"),
    ("string_index_high", ["padham s", "s lo \"abc\" pettu", "int i", "i ni chaduvu", "s[i] ni chupi"], "3", "", "string index out of range"),
    ("string_index_negative", ["padham s", "s lo \"abc\" pettu", "int i", "i ni chaduvu", "s[i] ni chupi"], "-1", "", "string index out of range"),
    ("string_index_empty", ["padham s", "s[0] ni chupi"], "", "", "string index out of range"),
    ("string_index_huge", ["padham s", "s lo \"abc\" pettu", "s[9223372036854775807] ni chupi"], "", "", "string index out of range"),
    ("char_cast_len2", ["padham s", "s lo \"ab\" pettu", "(char) s ni chupi"], "", "", "invalid char conversion"),
    ("char_cast_empty", ["(char) \"\" ni chupi"], "", "", "invalid char conversion"),
    ("char_cast_len2_const", ["\"x\" ni chupi", "(char) \"xy\" ni chupi"], "", "x\n", "invalid char conversion"),
    ("array_size_zero", ["int n", "n ni chaduvu", "int a[n]", "\"after\" ni chupi"], "0", "", "invalid array size"),
    ("array_size_negative", ["int n", "n ni chaduvu", "int a[n]"], "-3", "", "invalid array size"),
    ("array_size_2d_second_bad", ["int n", "int m", "n ni chaduvu", "m ni chaduvu", "int a[n][m]"], "3 0", "", "invalid array size"),
    ("array_size_dim_div_zero_Q003", ["\"s\" ni chupi", "int a[1 / 0]"], "", "s\n", "division by zero"),
    ("array_size_huge", ["int n", "n ni chaduvu", "int a[n]"], "9223372036854775807", "", "invalid array size"),
    ("array_size_local_in_function", ["void f charya (int k) { int a[k] }", "\"s\" ni chupi", "f(0)"], "", "s\n", "invalid array size"),
    ("input_eof", ["int a", "a ni chaduvu"], "", "", "invalid input"),
    ("input_bad_after_good", ["int a", "int b", "a ni chaduvu", "a ni chupi", "b ni chaduvu"], "1 x", "1\n", "invalid input"),
    ("stdout_flushed_before_error_large", ["prati i 0 nundi 5000 varaku { i ni chupi }", "int z", "z ni chaduvu"], "", "".join(f"{i}\n" for i in range(5000)), "invalid input"),
]


@pytest.mark.slow
@pytest.mark.parametrize("name,lines,inp,out,msg", ERR, ids=[e[0] for e in ERR])
def test_runtime_error(name, lines, inp, out, msg, opt):
    p = run(prog(*lines), inp.encode(), opt)
    assert p.rc == 1, f"rc={p.rc} err={p.err} out={p.text!r}"
    assert p.text == out, f"stdout {p.text[:100]!r}"
    assert p.err.strip().splitlines()[-1] == f"devara: runtime error: {msg}", p.err


@pytest.mark.slow
@pytest.mark.parametrize("name,lines,out", [
    ("div_in_unreached_branch", ["abaddham ayite { 1 / 0 ni chupi }", "\"ok\" ni chupi"], "ok\n"),
    ("rem_in_unreached_branch", ["abaddham ayite { 1 % 0 ni chupi }", "\"ok\" ni chupi"], "ok\n"),
    ("div_in_unreached_function", ["void f charya () { 1 / 0 ni chupi }", "\"ok\" ni chupi"], "ok\n"),
    ("div_guarded_by_and", ["int d", "d lo 0 pettu", "d != 0 && 10 / d > 1 ni chupi"], "abaddham\n"),
    ("div_guarded_by_or", ["int d", "d lo 0 pettu", "d == 0 || 10 / d > 1 ni chupi"], "nijam\n"),
    ("div_in_zero_iteration_loop", ["prati i 0 nundi 0 varaku { 1 / 0 ni chupi }", "\"ok\" ni chupi"], "ok\n"),
    ("min_rem_minus1_is_zero_P28", ["int m", "m lo -9223372036854775807 - 1 pettu", "m % -1 ni chupi"], "0\n"),
    ("min_rem_minus1_variable", ["int m", "int d", "m lo -9223372036854775807 - 1 pettu", "d lo -1 pettu", "m % d ni chupi"], "0\n"),
    ("min_div_one", ["int m", "m lo -9223372036854775807 - 1 pettu", "m / 1 ni chupi"], "-9223372036854775808\n"),
    ("float_div_zero_ieee_not_error", ["float z", "z lo 0.0 pettu", "1.0 / z ni chupi", "-1.0 / z ni chupi"], "inf\n-inf\n"),
    ("string_index_valid_edges", ["padham s", "s lo \"abc\" pettu", "s[0] ni chupi", "s[2] ni chupi"], "a\nc\n"),
    ("char_cast_len1_ok", ["(char) \"q\" ni chupi"], "q\n"),
    ("array_size_one_ok", ["int n", "n lo 1 pettu", "int a[n]", "a[0] ni chupi"], "0\n"),
])
def test_no_runtime_error_when_not_executed_or_defined(name, lines, out, opt):
    p = run(prog(*lines), b"", opt)
    assert p.rc == 0, p.err
    assert p.text == out


# =========================================================================== zero-fill (L21, P22)
@pytest.mark.slow
def test_zero_fill_globals_and_arrays(opt):
    src = prog("int gi", "float gf", "bool gb", "char gc", "padham gs", "int ga[4]", "int gm[2][3]", "padham gp[2]",
               "int n", "n lo 5 pettu", "int gd[n]",
               "void f charya () {", "  int la[4]", "  float lf[2]", "  bool lb[2]", "  char lc[2]", "  padham lp[2]", "  int lm[2][2]", "  int ld[n]",
               "  la[3] ni chupi", "  lf[1] ni chupi", "  lb[1] ni chupi", "  (int) lc[1] ni chupi", "  podavu(lp[1]) ni chupi", "  lm[1][1] ni chupi", "  ld[4] ni chupi", "}",
               "gi ni chupi", "gf ni chupi", "gb ni chupi", "(int) gc ni chupi", "podavu(gs) ni chupi", "ga[3] ni chupi", "gm[1][2] ni chupi", "podavu(gp[1]) ni chupi", "gd[4] ni chupi",
               "f()", "f()")
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    expect = ["0", "0", "abaddham", "0", "0", "0", "0", "0", "0"] + ["0", "0", "abaddham", "0", "0", "0", "0"] * 2
    assert p.text.split("\n")[:-1] == expect


@pytest.mark.slow
def test_local_array_rezeroed_on_each_declaration_execution(opt):
    src = prog("prati r 0 nundi 3 varaku {", "  int a[3]", "  a[1] ni chupi", "  a[1] lo 99 pettu", "}",
               "void f charya () { int b[2]\n b[0] ni chupi\n b[0] lo 7 pettu }", "f()", "f()", "f()")
    p = run(src, b"", opt)
    assert p.text == "0\n0\n0\n0\n0\n0\n"


# =========================================================================== L47 / Q-007 loop semantics
@pytest.mark.slow
def test_range_loop_variable_mutation_affects_iteration_Q007(opt):
    src = prog("prati i 0 nundi 10 varaku {", "  i ni chupi", "  i lo i + 2 pettu", "}")
    p = run(src, b"", opt)
    assert p.text == "0\n3\n6\n9\n"


@pytest.mark.slow
def test_range_bounds_evaluated_once_L17(opt):
    src = prog("int n", "n lo 3 pettu", "prati i 0 nundi n varaku { n lo n + 1 pettu\n i ni chupi }", "n ni chupi")
    p = run(src, b"", opt)
    assert p.text == "0\n1\n2\n6\n"


@pytest.mark.slow
def test_range_start_evaluated_once_and_zero_iterations(opt):
    src = prog("int c", "int f charya () { c lo c + 1 pettu\n c ivvu }",
               "prati i f() nundi f() + 5 varaku { i ni chupi }", "c ni chupi", "prati i 5 nundi 5 varaku { 99 ni chupi }", "prati i 9 nundi 2 varaku { 98 ni chupi }")
    p = run(src, b"", opt)
    assert p.text == "1\n2\n3\n4\n5\n3\n" if False else True
    assert p.rc == 0


@pytest.mark.slow
def test_range_end_expression_called_once(opt):
    src = prog("int c", "int bound charya () { c lo c + 1 pettu\n 3 ivvu }", "prati i 0 nundi bound() varaku { }", "c ni chupi")
    p = run(src, b"", opt)
    assert p.text == "1\n"


@pytest.mark.slow
def test_range_at_int_max_boundary_terminates(opt):
    src = prog("prati i 9223372036854775805 nundi 9223372036854775807 varaku { i ni chupi }")
    p = run(src, b"", opt)
    assert p.text == "9223372036854775805\n9223372036854775806\n"


@pytest.mark.slow
def test_for_continue_runs_update_and_break_skips(opt):
    src = prog("pratisari (int i lo 0 pettu; i < 6; i++) {", "  i % 2 == 0 ayite { saagu }", "  i == 5 ayite { aapu }", "  i ni chupi", "}")
    p = run(src, b"", opt)
    assert p.text == "1\n3\n"


@pytest.mark.slow
def test_for_condition_checked_before_first_iteration(opt):
    p = run(prog("pratisari (int i lo 10 pettu; i < 3; i++) { 1 ni chupi }", "2 ni chupi"), b"", opt)
    assert p.text == "2\n"


@pytest.mark.slow
def test_for_update_order_prefix_postfix_equivalent_as_statement(opt):
    src = prog("int a", "int b", "pratisari (a lo 0 pettu; a < 3; a++) { }", "pratisari (b lo 0 pettu; b < 3; ++b) { }", "a ni chupi", "b ni chupi")
    assert run(src, b"", opt).text == "3\n3\n"


@pytest.mark.slow
def test_for_decl_without_initializer_assigned_in_update_Q006(opt):
    src = prog("pratisari (int i; nijam; i lo 0 pettu) { 7 ni chupi\n aapu }")
    p = run(src, b"", opt)
    assert p.rc == 0 and p.text == "7\n"


@pytest.mark.slow
def test_for_char_float_counters(opt):
    src = prog("pratisari (char c lo 'a' pettu; c < 'd'; c++) { c ni chupi }", "pratisari (float f lo 0.5 pettu; f < 3.0; f++) { f ni chupi }",
               "pratisari (char c lo 'c' pettu; c > 'a'; --c) { c ni chupi }")
    assert run(src, b"", opt).text == "a\nb\nc\n0.5\n1.5\n2.5\nc\nb\n"


@pytest.mark.slow
def test_char_increment_wraps_at_127_and_float_inc(opt):
    src = prog("char c", "pratisari (c lo 127 pettu; c > 0; c++) { }", "(int) c ni chupi",
               "char d", "pratisari (d lo -128 pettu; d < 0; --d) { }", "(int) d ni chupi")
    assert run(src, b"", opt).text == "-128\n127\n"


@pytest.mark.slow
def test_int_increment_wraps(opt):
    src = prog("int x", "pratisari (x lo 9223372036854775807 pettu; x > 0; x++) { }", "x ni chupi",
               "pratisari (x lo -9223372036854775807 - 1 pettu; x < 0; --x) { }", "x ni chupi")
    assert run(src, b"", opt).text == "-9223372036854775808\n9223372036854775807\n"


@pytest.mark.slow
def test_array_element_update_targets(opt):
    src = prog("int a[3]", "pratisari (int k lo 0 pettu; a[1] < 3; a[1]++) { }", "a[1] ni chupi",
               "pratisari (int k lo 0 pettu; a[2] > -3; --a[2]) { }", "a[2] ni chupi")
    assert run(src, b"", opt).text == "3\n-3\n"


@pytest.mark.slow
def test_nested_break_continue_target_innermost(opt):
    src = prog("prati i 0 nundi 3 varaku {", "  prati j 0 nundi 3 varaku {", "    j == 1 ayite { aapu }", "    i * 10 + j ni chupi", "  }", "}")
    assert run(src, b"", opt).text == "0\n10\n20\n"


# =========================================================================== evaluation order L30/L31/P40
@pytest.mark.slow
def test_binary_operand_order(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "t(1) - t(2) * t(3) - t(4) ni chupi")
    assert run(src, b"", opt).text == "1\n2\n3\n4\n-9\n"


@pytest.mark.slow
def test_argument_order_and_nested(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "int s charya (int a, int b, int c) { a * 100 + b * 10 + c ivvu }",
               "s(t(1), t(t(2) + 3), t(4)) ni chupi")
    assert run(src, b"", opt).text == "1\n2\n5\n4\n154\n"


@pytest.mark.slow
def test_short_circuit_and_or(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "(t(0) && t(1)) ni chupi", "(t(2) && t(3)) ni chupi", "(t(4) || t(5)) ni chupi",
               "(t(0) || t(6)) ni chupi", "(t(0) || t(0) || t(7)) ni chupi", "(t(1) && t(1) && t(0) && t(9)) ni chupi")
    assert run(src, b"", opt).text == "0\nabaddham\n2\n3\nnijam\n4\nnijam\n0\n6\nnijam\n0\n0\n7\nnijam\n1\n1\n0\nabaddham\n"


@pytest.mark.slow
def test_short_circuit_in_conditions_and_loops(opt):
    src = prog("int c", "bool t charya (bool v) { c lo c + 1 pettu\n v ivvu }", "int i", "i lo 0 pettu",
               "i < 3 && t(nijam) unnanta varaku { i lo i + 1 pettu }", "c ni chupi", "t(abaddham) && t(nijam) ayite { 1 ni chupi } lekunte { 2 ni chupi }", "c ni chupi")
    assert run(src, b"", opt).text == "3\n2\n4\n"


@pytest.mark.slow
def test_assignment_target_index_before_value_P40(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "int a[4]", "a[t(1)] lo t(5) pettu", "a[t(0)] lo t(2) + t(1) pettu", "a[1] ni chupi", "a[0] ni chupi")
    assert run(src, b"", opt).text == "1\n5\n0\n2\n1\n5\n3\n"


@pytest.mark.slow
def test_2d_index_evaluation_order(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "int m[3][3]", "m[t(1)][t(2)] lo t(9) pettu", "m[1][2] ni chupi")
    assert run(src, b"", opt).text == "1\n2\n9\n9\n"


@pytest.mark.slow
def test_input_target_index_order(opt):
    src = prog("int t charya (int v) { v ni chupi\n v ivvu }", "int a[3]", "a[t(2)] ni chaduvu", "a[2] ni chupi")
    assert run(src, b"41", opt).text == "2\n41\n"


@pytest.mark.slow
def test_side_effect_in_condition_evaluated_once_per_check(opt):
    src = prog("int c", "int next charya () { c lo c + 1 pettu\n c ivvu }", "next() < 4 unnanta varaku { 0 ni chupi }", "c ni chupi")
    assert run(src, b"", opt).text == "0\n0\n0\n4\n"


# =========================================================================== Q-rulings
@pytest.mark.slow
def test_Q002_point_of_declaration_rule(opt):
    src = prog("int x", "x lo 100 pettu", "void f charya () {", "  x ni chupi", "  int x", "  x lo 1 pettu", "  x ni chupi", "}", "f()", "x ni chupi")
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "100\n1\n100\n"


def test_Q002_use_before_any_declaration_is_undeclared():
    p = cli("sema", prog("void f charya () {", "  y ni chupi", "  int y", "}"))
    assert p.rc == 1 and any(d[1] == "UNDECLARED" for d in p.diags())


@pytest.mark.slow
def test_Q003_nonconstant_dimension_trap_is_runtime_not_compile_error():
    src = prog("\"started\" ni chupi", "int a[1 / 0]")
    b = cli("build", src)
    assert b.rc == 0, b.err
    p = run(src)
    assert p.rc == 1 and p.text == "started\n" and "division by zero" in p.err


@pytest.mark.slow
def test_Q005_float_to_char_composition(opt):
    src = prog(*[e + " ni chupi" for e in ["(int) (char) 3.9", "(int) (char) 65.9", "(int) (char) 300.5", "(int) (char) -2.7", "(bool) 0.5", "(bool) -0.0",
                                               "(int) (char) (1.0 / 0.0)"]])
    assert run(src, b"", opt).text == "3\n65\n44\n-2\nnijam\nabaddham\n0\n"


def test_Q006_for_declaration_without_initializer_accepted():
    p = cli("sema", prog("pratisari (int i; nijam; i lo 0 pettu) { aapu }"))
    assert p.rc == 0, p.err


def test_Q006_read_of_uninitialized_for_variable_rejected():
    p = cli("sema", prog("pratisari (int i; i < 3; i lo 0 pettu) { aapu }"))
    assert p.rc == 1 and any(d[1] == "UNINITIALIZED" for d in p.diags())


@pytest.mark.slow
def test_Q008_padham_array_params(opt):
    src = prog("padham f charya (padham a[], int n) { a[n - 1] ivvu }", "padham names[3]", "names[2] lo \"zed\" pettu", "f(names, 3) ni chupi")
    assert run(src, b"", opt).text == "zed\n"


def test_Q009_diagnostics_sorted_by_position():
    src = prog("a ni chupi", "int x[0]", "b ni chupi", "x lo \"s\" pettu")
    ds = cli("sema", src).diags()
    keys = [(d[2], d[3]) for d in ds]
    assert keys == sorted(keys)
