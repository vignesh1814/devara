"""Adversarial runtime/optimizer/codegen probes derived from the language rules (L25, L29-L31, L37-L39, L49, P22-P28, P40).

Every expected value is computed by the independent model in rtmodel.py or follows directly from a cited rule.
"""
import math
import pytest
from tests.validation.helpers import run, prog, OPTS
from tests.validation.rtmodel import *

pytestmark = pytest.mark.slow


def lines(p):
    return p.text.split("\n")[:-1]


# ---------------------------------------------------------------- evaluation order with variable operands (L30/L31/P40)
SIDE = ["int gi", "int bump charya () { gi lo gi + 100 pettu\n gi ivvu }", "int one charya () { gi lo 7 pettu\n 1 ivvu }"]


@pytest.mark.parametrize("name,body,exp", [
    ("left_var_read_before_call_add", ["gi lo 1 pettu", "gi + bump() ni chupi"], ["102"]),
    ("left_var_read_before_call_sub", ["gi lo 1 pettu", "gi - bump() ni chupi"], ["-100"]),
    ("left_var_read_before_call_mul", ["gi lo 2 pettu", "gi * bump() ni chupi"], ["204"]),
    ("left_var_read_before_call_cmp", ["gi lo 1 pettu", "gi < bump() ni chupi"], ["nijam"]),
    ("left_var_cmp_eq", ["gi lo 5 pettu", "gi == one() ni chupi"], ["abaddham"]),
    ("right_var_read_after_call", ["gi lo 1 pettu", "bump() + gi ni chupi"], ["202"]),
    ("arg_order_var_then_call", ["int s charya (int a, int b) { a * 1000 + b ivvu }", "gi lo 3 pettu", "s(gi, bump()) ni chupi"], ["3103"]),
    ("arg_order_call_then_var", ["int s charya (int a, int b) { a * 1000 + b ivvu }", "gi lo 3 pettu", "s(bump(), gi) ni chupi"], ["103103"]),
    ("assign_self_plus_call", ["gi lo 1 pettu", "gi lo gi + bump() pettu", "gi ni chupi"], ["102"]),
    ("array_target_index_before_rhs_call", ["int a[400]", "gi lo 1 pettu", "a[gi] lo bump() pettu", "a[1] ni chupi", "a[101] ni chupi"], ["101", "0"]),
    ("array_target_2d_index_before_call", ["int m[3][3]", "gi lo 1 pettu", "m[gi][gi] lo one() pettu", "m[1][1] ni chupi", "m[7][7]" if False else "gi ni chupi"], ["1", "7"]),
    ("array_read_index_before_call", ["int a[400]", "a[1] lo 11 pettu", "a[101] lo 22 pettu", "gi lo 1 pettu", "a[gi] + bump() ni chupi"], ["112"]),
    ("short_circuit_var_then_call", ["gi lo 0 pettu", "gi && bump() ni chupi", "gi ni chupi"], ["abaddham", "0"]),
    ("or_var_then_call", ["gi lo 1 pettu", "gi || bump() ni chupi", "gi ni chupi"], ["nijam", "1"]),
    ("cond_var_then_call_in_while", ["gi lo 0 pettu", "int n", "n lo 0 pettu", "gi < 250 unnanta varaku { n lo n + 1 pettu\n bump() }", "n ni chupi"], ["3"]),
    ("input_target_index_before_read_side_effect", ["int a[400]", "gi lo 1 pettu", "a[gi] ni chaduvu", "a[1] ni chupi"], ["5"]),
    ("float_var_before_call", ["float gf2", "float setf charya () { gf2 lo 9.5 pettu\n 0.5 ivvu }", "gf2 lo 1.0 pettu", "gf2 + setf() ni chupi"], ["1.5"]),
    ("char_var_before_call", ["char gc", "char setc charya () { gc lo 'z' pettu\n 'a' ivvu }", "gc lo 'b' pettu", "(padham) gc + (padham) setc() ni chupi"], ["ba"]),
    ("padham_var_before_call", ["padham gs", "padham sets charya () { gs lo \"new\" pettu\n \"!\" ivvu }", "gs lo \"old\" pettu", "gs + sets() ni chupi"], ["old!"]),
    ("bool_var_before_call", ["bool gb", "bool setb charya () { gb lo abaddham pettu\n nijam ivvu }", "gb lo nijam pettu", "(gb == setb()) ni chupi"], ["nijam"]),
    ("unary_neg_var_then_call", ["gi lo 4 pettu", "-gi + bump() ni chupi"], ["100"]),
    ("nested_call_args_order", ["int s charya (int a, int b, int c) { a * 1000000 + b * 1000 + c ivvu }", "gi lo 1 pettu", "s(gi, one(), gi) ni chupi"], ["1001007"]),
])
@pytest.mark.parametrize("opt", OPTS)
def test_evaluation_order_with_side_effecting_calls(name, body, exp, opt):
    prelude = [l for l in body if "charya" in l or l.startswith(("float gf2", "char gc", "padham gs", "bool gb"))]
    rest = [l for l in body if l not in prelude]
    p = run(prog(*SIDE, *prelude, *rest), b"5\n", opt)
    assert p.rc == 0, p.err
    assert lines(p) == exp


# ---------------------------------------------------------------- array parameter aliasing (L25) and global visibility across calls
@pytest.mark.parametrize("opt", OPTS)
def test_array_params_alias_the_same_storage(opt):
    src = prog("void f charya (int x[], int y[]) { x[0] lo 1 pettu\n y[0] ni chupi\n y[0] lo 2 pettu\n x[0] ni chupi }",
               "int a[2]", "f(a, a)", "a[0] ni chupi")
    assert lines(run(src, b"", opt)) == ["1", "2", "2"]


@pytest.mark.parametrize("opt", OPTS)
def test_array_param_aliases_global_array(opt):
    src = prog("int g[3]", "void f charya (int p[]) { p[1] lo 5 pettu\n g[1] ni chupi\n g[1] lo 6 pettu\n p[1] ni chupi }", "f(g)", "g[1] ni chupi")
    assert lines(run(src, b"", opt)) == ["5", "6", "6"]


@pytest.mark.parametrize("opt", OPTS)
def test_row_views_alias_into_parent_array(opt):
    src = prog("void set charya (int r[], int v) { r[1] lo v pettu }", "int m[3][4]", "set(m[2], 9)", "set(m[0], 4)", "m[2][1] ni chupi", "m[0][1] ni chupi",
               "m[1][1] ni chupi", "int c[2][3][4]", "set(c[1][2], 8)", "c[1][2][1] ni chupi", "c[0][2][1] ni chupi")
    assert lines(run(src, b"", opt)) == ["9", "4", "0", "8", "0"]


@pytest.mark.parametrize("opt", OPTS)
def test_overlapping_row_views_same_row_twice(opt):
    src = prog("void f charya (int a[], int b[]) { a[2] lo a[2] + 1 pettu\n b[2] lo b[2] * 10 pettu }", "int m[2][3]", "m[1][2] lo 4 pettu",
               "f(m[1], m[1])", "m[1][2] ni chupi")
    assert lines(run(src, b"", opt)) == ["50"]


@pytest.mark.parametrize("opt", OPTS)
def test_value_cached_across_call_that_modifies_global(opt):
    src = prog("int g", "int a[3]", "void touch charya () { g lo g + 1 pettu\n a[1] lo a[1] + 10 pettu }",
               "g lo 5 pettu", "a[1] lo 1 pettu", "g ni chupi", "a[1] ni chupi", "touch()", "g ni chupi", "a[1] ni chupi", "g + a[1] ni chupi")
    assert lines(run(src, b"", opt)) == ["5", "1", "6", "11", "17"]


@pytest.mark.parametrize("opt", OPTS)
def test_scalar_params_are_copies(opt):
    src = prog("void f charya (int p) { p lo p + 1 pettu\n p ni chupi }", "int x", "x lo 5 pettu", "f(x)", "x ni chupi", "f(x + 1)", "x ni chupi")
    assert lines(run(src, b"", opt)) == ["6", "5", "7", "5"]


@pytest.mark.parametrize("opt", OPTS)
def test_padham_value_semantics_across_calls(opt):
    src = prog("padham f charya (padham s) { s lo s + \"!\" pettu\n s ivvu }", "padham a", "a lo \"hi\" pettu", "padham b", "b lo f(a) pettu", "a ni chupi", "b ni chupi")
    assert lines(run(src, b"", opt)) == ["hi", "hi!"]


@pytest.mark.parametrize("opt", OPTS)
def test_padham_array_elements_value_semantics(opt):
    src = prog("padham a[2]", "a[0] lo \"x\" pettu", "a[1] lo a[0] pettu", "a[0] lo a[0] + \"y\" pettu", "a[0] ni chupi", "a[1] ni chupi")
    assert lines(run(src, b"", opt)) == ["xy", "x"]


# ---------------------------------------------------------------- IEEE-754 comparisons with NaN (L39) in value and branch contexts
NAN_PRE = ["float z", "z lo 0.0 pettu", "float n", "n lo z / z pettu", "float inf", "inf lo 1.0 / z pettu"]
NAN_ROWS = [
    ("n == n", "abaddham"), ("n != n", "nijam"), ("n < 1.0", "abaddham"), ("n > 1.0", "abaddham"), ("n <= n", "abaddham"), ("n >= n", "abaddham"),
    ("1.0 < n", "abaddham"), ("1.0 >= n", "abaddham"), ("n == 1.0", "abaddham"), ("n != 1.0", "nijam"), ("!(n < 1.0)", "nijam"), ("!(n == n)", "nijam"),
    ("(n < 1.0) || (n >= 1.0)", "abaddham"), ("(n < 1.0) || (n >= 1.0) || (n != n)", "nijam"), ("(bool) n", "nijam"), ("!n", "abaddham"),
    ("(int) n", str(INT_MIN)), ("(int) (char) n", "0"), ("inf == inf", "nijam"), ("inf > 1.0", "nijam"), ("inf - inf == inf - inf", "abaddham"),
    ("-inf < 1.0" if False else "(0.0 - inf) < 1.0", "nijam"), ("inf * 0.0 == 0.0", "abaddham"), ("n == z", "abaddham"), ("n + 1.0 == n + 1.0", "abaddham"),
    ("(int) inf", str(INT_MIN)), ("(int) (0.0 - inf)", str(INT_MIN)), ("(float) 1 / z == inf", "nijam"),
]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("expr,exp", NAN_ROWS, ids=[r[0] for r in NAN_ROWS])
def test_nan_comparison_value_context(expr, exp, opt):
    p = run(prog(*NAN_PRE, f"{expr} ni chupi"), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == [exp]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("expr,exp", [r for r in NAN_ROWS if r[1] in ("nijam", "abaddham")], ids=[r[0] for r in NAN_ROWS if r[1] in ("nijam", "abaddham")])
def test_nan_comparison_branch_context(expr, exp, opt):
    src = prog(*NAN_PRE, f"{expr} ayite {{ \"nijam\" ni chupi }} lekunte {{ \"abaddham\" ni chupi }}",
               f"int c", "c lo 0 pettu", f"{expr} unnanta varaku {{ c lo c + 1 pettu\n c > 2 ayite {{ aapu }} }}", "c ni chupi")
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == [exp, "3" if exp == "nijam" else "0"]


@pytest.mark.parametrize("opt", OPTS)
def test_nan_in_for_condition_terminates_immediately(opt):
    src = prog(*NAN_PRE, "pratisari (int i lo 0 pettu; n == n; i++) { \"loop\" ni chupi }", "\"done\" ni chupi")
    assert lines(run(src, b"", opt)) == ["done"]


# ---------------------------------------------------------------- float algebra must not be simplified (spec §12.4, L49)
NZ_PRE = ["float z", "float one", "z lo -0.0 pettu", "one lo 1.0 pettu"]
NZ_ROWS = [("z + 0.0", "0"), ("z - 0.0", "-0"), ("0.0 - z", "0"), ("z * 1.0", "-0"), ("1.0 * z", "-0"), ("z / 1.0", "-0"), ("z * 0.0", "-0"),
           ("0.0 * z", "-0"), ("z * -1.0", "0"), ("z + z", "-0"), ("z - z", "0"), ("-z", "0"), ("-(-z)", "-0"), ("z + 0", "0"), ("z * 1", "-0"),
           ("(0.0 - 0.0) - 0.0", "0"), ("0.0 + -0.0", "0"), ("-0.0 + -0.0", "-0"), ("-0.0 * 5", "-0"), ("one * z", "-0"), ("z / one", "-0"),
           ("one / z", "-inf"), ("(one / z) * 0.0 == 0.0", "abaddham"), ("z == 0.0", "nijam"), ("(0.0 - z) + z", "0"), ("one - one", "0"), ("(float) 0 * -1", "-0")]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("expr,exp", NZ_ROWS, ids=[r[0] for r in NZ_ROWS])
def test_signed_zero_and_no_float_identities(expr, exp, opt):
    p = run(prog(*NZ_PRE, f"{expr} ni chupi"), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == [exp]


@pytest.mark.parametrize("opt", OPTS)
def test_float_reassociation_forbidden(opt):
    # (a + b) + c != a + (b + c) in binary64; folding/regrouping would change the printed value
    src = prog("float a", "float b", "float c", "a lo 100000000.0 pettu", "b lo -100000000.0 pettu", "c lo 0.1 pettu",
               "(a + b) + c ni chupi", "a + (b + c) ni chupi", "((a + c) - a) ni chupi", "(a + 1.0) - a ni chupi")
    exp = [g((1e8 + -1e8) + 0.1), g(1e8 + (-1e8 + 0.1)), g(((1e8 + 0.1) - 1e8)), g((1e8 + 1.0) - 1e8)]
    assert lines(run(src, b"", opt)) == exp


@pytest.mark.parametrize("opt", OPTS)
def test_float_overflow_to_inf_and_underflow(opt):
    src = prog("float x", "x lo 1.0 pettu", "prati i 0 nundi 400 varaku { x lo x * 10.0 pettu }", "x ni chupi", "x lo 1.0 pettu",
               "prati i 0 nundi 400 varaku { x lo x / 10.0 pettu }", "x ni chupi", "x == 0.0 ni chupi")
    assert lines(run(src, b"", opt)) == ["inf", "0", "nijam"]


# ---------------------------------------------------------------- integer algebra must keep traps and truncating division
XS = [0, 1, -1, 2, -2, 3, -3, 7, -7, 8, -8, 9, 100, -100, 12345, -12345, 2 ** 31, -2 ** 31, 2 ** 62, -2 ** 62, INT_MAX, INT_MIN, INT_MIN + 1]
CS = [1, 2, 3, 4, 5, 7, 8, 10, 16, 100, 1000, 1024, 65536, 2 ** 31, -1, -2, -3, -8, -10, -1000]


def build_div_program(xs, cs):
    lines_ = ["int x"]
    for x in xs:
        lines_.append(f"x lo {x if x > INT_MIN else '-9223372036854775807 - 1'} pettu")
        for c in cs:
            if x == INT_MIN and c == -1:
                continue
            lines_ += [f"x / {c} ni chupi" if c > 0 else f"x / ({c}) ni chupi", f"x % {c} ni chupi" if c > 0 else f"x % ({c}) ni chupi"]
    return lines_


def expected_div(xs, cs):
    out = []
    for x in xs:
        for c in cs:
            if x == INT_MIN and c == -1:
                continue
            out += [str(tdiv(x, c)), str(trem(x, c))]
    return out


@pytest.mark.parametrize("opt", OPTS)
def test_division_by_constants_truncates_toward_zero(opt):
    p = run(prog(*build_div_program(XS, CS)), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == expected_div(XS, CS)


@pytest.mark.parametrize("opt", OPTS)
def test_division_by_variables_truncates_toward_zero(opt):
    body = ["int x", "int c"]
    for x in XS:
        body.append(f"x lo {x if x > INT_MIN else '-9223372036854775807 - 1'} pettu")
        for c in CS:
            if x == INT_MIN and c == -1:
                continue
            body += [f"c lo {c} pettu", "x / c ni chupi", "x % c ni chupi"]
    p = run(prog(*body), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == expected_div(XS, CS)


@pytest.mark.parametrize("opt", OPTS)
def test_multiplication_and_identities_wrap(opt):
    body = ["int x"]
    exp = []
    for x in XS:
        body.append(f"x lo {x if x > INT_MIN else '-9223372036854775807 - 1'} pettu")
        for c in [0, 1, -1, 2, 3, 8, 10, 1000003, 2 ** 40, -2 ** 20, INT_MAX]:
            body.append(f"x * {c} ni chupi" if c >= 0 else f"x * ({c}) ni chupi")
            exp.append(str(wrap(x * c)))
        body += ["x + 0 ni chupi", "x - 0 ni chupi", "x - x ni chupi", "x * 1 ni chupi", "x / 1 ni chupi", "x % 1 ni chupi", "x + x ni chupi", "x * x ni chupi", "-x ni chupi",
                 "x - (-x) ni chupi" if False else "0 - x ni chupi"]
        exp += [str(x), str(x), "0", str(x), str(x), "0", str(wrap(2 * x)), str(wrap(x * x)), str(wrap(-x)), str(wrap(-x))]
    p = run(prog(*body), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == exp


@pytest.mark.parametrize("expr", ["0 / x", "x / x", "x % x", "0 % x", "x * 0 / x", "(x - x) / x", "(x - x) % x", "1 / (x - x)", "x / (x - x)", "1 % (x * 0)", "(x + 1) / (x * 0)"])
@pytest.mark.parametrize("opt", OPTS)
def test_algebraic_rewrites_must_not_remove_division_traps(expr, opt):
    # x == 0 at run time: all of these divide or take a remainder by zero and must raise the runtime error
    src = prog("int x", "x ni chaduvu", "\"start\" ni chupi", f"{expr} ni chupi", "\"end\" ni chupi")
    p = run(src, b"0", opt)
    assert p.rc == 1 and p.text == "start\n", (p.rc, p.text, p.err)
    assert "runtime error" in p.err and ("division by zero" in p.err or "remainder by zero" in p.err)


@pytest.mark.parametrize("expr,val", [("0 / x", 0), ("x / x", 1), ("x % x", 0), ("0 % x", 0), ("x * 0 / x", 0), ("(x - x) / x", 0)])
@pytest.mark.parametrize("opt", OPTS)
def test_same_expressions_with_nonzero_x(expr, val, opt):
    src = prog("int x", "x ni chaduvu", f"{expr} ni chupi")
    assert lines(run(src, b"37", opt)) == [str(val)]


@pytest.mark.parametrize("opt", OPTS)
def test_dead_division_result_still_traps(opt):
    src = prog("int f charya (int d) { int unused\n unused lo 100 / d pettu\n 5 ivvu }", "\"a\" ni chupi", "f(0) ni chupi")
    p = run(src, b"", opt)
    assert p.rc == 1 and p.text == "a\n"


@pytest.mark.parametrize("opt", OPTS)
def test_constant_divisions_that_trap_survive_folding_and_are_runtime_errors(opt):
    for e, msg in [("1 / 0", "division by zero"), ("(-9223372036854775807 - 1) / -1", "integer overflow in division"), ("5 % (2 - 2)", "remainder by zero")]:
        src = prog("\"p\" ni chupi", f"{e} ni chupi")
        b = run(src, b"", opt)
        assert b.rc == 1 and b.text == "p\n" and msg in b.err, (e, b.rc, b.err)


# ---------------------------------------------------------------- conversions through storage classes (P27)
@pytest.mark.parametrize("opt", OPTS)
def test_bool_conversion_uses_full_width(opt):
    rows = [("256", "nijam"), ("65536", "nijam"), ("4294967296", "nijam"), ("-9223372036854775807 - 1", "nijam"), ("0", "abaddham"), ("1", "nijam"), ("-1", "nijam")]
    src = prog("int x", *[l for v, _ in rows for l in (f"x lo {v} pettu", "(bool) x ni chupi", "bool b", "b lo x pettu", "b ni chupi")][: 0],
               *sum(([f"x lo {v} pettu", "(bool) x ni chupi", f"{{ bool b2\n b2 lo x pettu\n b2 ni chupi }}"] for v, _ in rows[:0]), []))
    body = ["int x", "bool b"]
    exp = []
    for v, e in rows:
        body += [f"x lo {v} pettu", "(bool) x ni chupi", "b lo x pettu", "b ni chupi", "!x ni chupi"]
        exp += [e, e, "abaddham" if e == "nijam" else "nijam"]
    assert lines(run(prog(*body), b"", opt)) == exp


@pytest.mark.parametrize("opt", OPTS)
def test_char_storage_wraps_and_sign_extends(opt):
    src = prog("char c", "int x", "char arr[2]", "char f charya (char p) { p ivvu }", "char g charya (int q) { q ivvu }",
               "x lo 200 pettu", "c lo x pettu", "(int) c ni chupi", "c < 0 ni chupi", "arr[1] lo 300 pettu", "(int) arr[1] ni chupi",
               "(int) f(300) ni chupi", "(int) g(200) ni chupi", "(int) g(-129) ni chupi", "c lo 127 pettu", "c + 1 ni chupi", "(int) (char) (c + 1) ni chupi",
               "c lo 255 pettu", "(int) c ni chupi", "c lo 'a' pettu", "c lo c + 200 pettu", "(int) c ni chupi", "c lo 3.99 pettu", "(int) c ni chupi", "c lo nijam pettu", "(int) c ni chupi",
               "(int) (char) 65536 ni chupi", "(int) (char) 65537 ni chupi")
    assert lines(run(src, b"", opt)) == ["-56", "nijam", "44", "44", "-56", "127", "128", "-128", "-1", "41", "3", "1", "0", "1"][:0] or True
    out = lines(run(src, b"", opt))
    assert out == ["-56", "nijam", "44", "44", "-56", "127", "128", "-128", "-1", str(s8(97 + 200)), "3", "1", "0", "1"]


@pytest.mark.parametrize("opt", OPTS)
def test_bool_storage_normalised(opt):
    src = prog("bool b", "bool arr[2]", "bool f charya (bool p) { p ivvu }", "bool h charya (int q) { q ivvu }",
               "b lo 256 pettu", "b ni chupi", "arr[1] lo 512 pettu", "arr[1] ni chupi", "f(65536) ni chupi", "h(4294967296) ni chupi", "h(0) ni chupi",
               "(int) b ni chupi", "(int) arr[1] ni chupi", "b + b ni chupi", "b lo 0.5 pettu", "b ni chupi", "b lo 0.0 pettu", "b ni chupi", "b lo 'a' pettu", "(int) b ni chupi")
    assert lines(run(src, b"", opt)) == ["nijam", "nijam", "nijam", "nijam", "abaddham", "1", "1", "2", "nijam", "abaddham", "1"]


@pytest.mark.parametrize("opt", OPTS)
def test_float_to_int_edges(opt):
    rows = [("9223372036854775807.0", INT_MIN), ("9223372036854775808.0", INT_MIN), ("-9223372036854775808.0", INT_MIN), ("1000000.9", 1000000),
            ("-1000000.9", -1000000), ("4611686018427387904.0", 4611686018427387904), ("-4611686018427387904.0", -4611686018427387904),
            ("9007199254740993.0", 9007199254740992), ("0.9999999", 0), ("-0.9999999", 0), ("2147483648.5", 2147483648), ("-2147483649.5", -2147483649),
            ("100000000000000000000.0", INT_MIN), ("-100000000000000000000.0", INT_MIN)]
    src = prog(*[f"(int) {v} ni chupi" for v, _ in rows])
    assert lines(run(src, b"", opt)) == [str(e) for _, e in rows]


@pytest.mark.parametrize("opt", OPTS)
def test_int_to_float_rounding(opt):
    xs = [9007199254740993, 9007199254740995, INT_MAX, INT_MIN, INT_MIN + 1, 4611686018427387905, 123456789012345678, -123456789012345678]
    src = prog(*[f"(float) {x if x > INT_MIN else '(-9223372036854775807 - 1)'} ni chupi" for x in xs],
               *[f"(float) {x if x > INT_MIN else '(-9223372036854775807 - 1)'} == (float) {x if x > INT_MIN else '(-9223372036854775807 - 1)'} ni chupi" for x in xs[:2]])
    assert lines(run(src, b"", opt)) == [g(float(x)) for x in xs] + ["nijam", "nijam"]


# ---------------------------------------------------------------- strings with embedded NULs and large strings
@pytest.mark.parametrize("opt", OPTS)
def test_padham_with_embedded_nul(opt):
    src = prog("padham a", "padham b", "a lo \"a\\0b\" pettu", "b lo \"a\\0c\" pettu", "a == b ni chupi", "a != b ni chupi", "a == a ni chupi",
               "podavu(a + b) ni chupi", "podavu(\"\\0\") ni chupi", "(int) a[1] ni chupi", "a[2] ni chupi", "(a + \"\\0\") == (a + \"\\0\") ni chupi", "a + \"\" == a ni chupi",
               "\"\\0\" == \"\" ni chupi", "\"a\\0\" == \"a\" ni chupi", "podavu(a + \"\\0\\0\") ni chupi")
    assert lines(run(src, b"", opt)) == ["abaddham", "nijam", "nijam", "6", "1", "0", "b", "nijam", "nijam", "abaddham", "abaddham", "5"]


@pytest.mark.parametrize("opt", OPTS)
def test_padham_input_with_nul_and_high_bytes(opt):
    src = prog("padham s", "s ni chaduvu", "podavu(s) ni chupi", "(int) s[1] ni chupi", "(int) s[3] ni chupi", "s ni chupi")
    data = b"a\x00b\xffc\n"
    p = run(src, data, opt)
    assert p.out == b"5\n0\n-1\n" + data
    assert p.rc == 0


@pytest.mark.parametrize("opt", OPTS)
def test_long_strings_and_concatenation_loops(opt):
    src = prog("padham s", "s lo \"\" pettu", "prati i 0 nundi 20000 varaku { s lo s + \"ab\" pettu }", "podavu(s) ni chupi", "s[39999] ni chupi", "s[0] ni chupi",
               "padham t", "t lo s + s pettu", "podavu(t) ni chupi", "t == s + s ni chupi", "t != s ni chupi")
    p = run(src, b"", opt)
    assert lines(p) == ["40000", "b", "a", "80000", "nijam", "nijam"]


@pytest.mark.parametrize("opt", OPTS)
def test_long_input_line(opt):
    line = ("0123456789" * 100000)
    src = prog("padham s", "s ni chaduvu", "podavu(s) ni chupi", "s[999999] ni chupi", "int n", "n ni chaduvu", "n ni chupi")
    p = run(src, (line + "\n42\n").encode(), opt)
    assert lines(p) == ["1000000", "9", "42"]


@pytest.mark.parametrize("opt", OPTS)
def test_many_ints_input_and_large_output(opt):
    n = 100000
    data = " ".join(str(i * 7919 % 100003) for i in range(n)) + "\n"
    src = prog("int n", "n lo 100000 pettu", "int s", "s lo 0 pettu", "prati i 0 nundi n varaku { int v\n v ni chaduvu\n s lo s + v pettu\n i % 10000 == 0 ayite { s ni chupi } }", "s ni chupi")
    vals = [i * 7919 % 100003 for i in range(n)]
    exp, s = [], 0
    for i, v in enumerate(vals):
        s += v
        if i % 10000 == 0:
            exp.append(str(s))
    exp.append(str(s))
    p = run(src, data.encode(), opt)
    assert lines(p) == exp


@pytest.mark.parametrize("opt", OPTS)
def test_output_volume_one_million_lines(opt):
    src = prog("prati i 0 nundi 1000000 varaku { i ni chupi }")
    p = run(src, b"", opt)
    assert p.rc == 0
    assert p.out == "".join(f"{i}\n" for i in range(1000000)).encode()


# ---------------------------------------------------------------- calling convention stress
def many_params_program(ni, nf):
    ps = ", ".join([f"int a{i}" for i in range(ni)] + [f"float f{i}" for i in range(nf)])
    ex = " + ".join([f"a{i} * {i + 1}" for i in range(ni)] + [f"(int) (f{i} * {i + 2}.0)" for i in range(nf)]) or "0"
    args = ", ".join([str(100 + i) for i in range(ni)] + [f"{i}.5" for i in range(nf)])
    exp = sum((100 + i) * (i + 1) for i in range(ni)) + sum(int((i + 0.5) * (i + 2.0)) for i in range(nf))
    return prog(f"int h charya ({ps}) {{ {ex} ivvu }}", f"h({args}) ni chupi", f"h({args}) + h({args}) ni chupi"), [str(exp), str(2 * exp)]


@pytest.mark.parametrize("ni,nf", [(0, 0), (1, 0), (6, 0), (7, 0), (8, 0), (9, 0), (15, 0), (0, 8), (0, 9), (0, 12), (3, 3), (6, 8), (7, 9), (9, 10), (12, 12), (20, 20), (31, 1), (1, 31)])
@pytest.mark.parametrize("opt", OPTS)
def test_many_parameters_mixed_register_and_stack(ni, nf, opt):
    src, exp = many_params_program(ni, nf)
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == exp


@pytest.mark.parametrize("opt", OPTS)
def test_mixed_type_parameters_and_returns(opt):
    src = prog("padham mix charya (int a, float b, bool c, char d, padham e, int f, float g, bool h, char i, padham j, int k) {",
               "  e + j + (padham) d + (padham) i ivvu }", "float fl charya (float x, float y, float z) { x * 100.0 + y * 10.0 + z ivvu }",
               "char ch charya (int x) { (char) (x + 64) ivvu }", "bool bo charya (float x) { x > 0.5 ivvu }",
               "mix(1, 2.5, nijam, 'x', \"E\", 6, 7.5, abaddham, 'y', \"J\", 11) ni chupi", "fl(1.5, 2.5, 3.5) ni chupi", "ch(1) ni chupi", "bo(0.75) ni chupi", "bo(0.25) ni chupi",
               "fl(ch(1), 2, bo(1.0) + 1) ni chupi")
    assert lines(run(src, b"", opt)) == ["EJxy", g(1.5 * 100 + 25 + 3.5), "A", "nijam", "abaddham", g(65.0 * 100 + 20 + 2)]


@pytest.mark.parametrize("opt", OPTS)
def test_deep_recursion_20000_frames(opt):
    src = prog("int depth charya (int n) { n == 0 ayite { 0 ivvu }\n 1 + depth(n - 1) ivvu }", "depth(20000) ni chupi", "float fd charya (float x, int n) { n == 0 ayite { x ivvu }\n fd(x + 0.5, n - 1) ivvu }", "fd(0.0, 20000) ni chupi")
    assert lines(run(src, b"", opt)) == ["20000", "10000"]


@pytest.mark.parametrize("opt", OPTS)
def test_recursion_with_array_param_and_many_locals(opt):
    src = prog("int f charya (int a[], int n, int l1, int l2, int l3, int l4, int l5, int l6, int l7, int l8) {",
               "  n == 0 ayite { l1 + l2 + l3 + l4 + l5 + l6 + l7 + l8 + a[0] ivvu }", "  int t1", "  int t2", "  t1 lo a[0] + n pettu", "  t2 lo t1 * 2 pettu", "  a[0] lo t2 % 1000 pettu",
               "  f(a, n - 1, l1 + 1, l2 + 2, l3 + 3, l4 + 4, l5 + 5, l6 + 6, l7 + 7, l8 + t1) + t2 ivvu }", "int a[1]", "f(a, 30, 0, 0, 0, 0, 0, 0, 0, 0) ni chupi", "a[0] ni chupi")

    def f(a, n, l):
        if n == 0:
            return sum(l) + a[0]
        t1 = a[0] + n
        t2 = t1 * 2
        a[0] = t2 % 1000
        return f(a, n - 1, [l[0] + 1, l[1] + 2, l[2] + 3, l[3] + 4, l[4] + 5, l[5] + 6, l[6] + 7, l[7] + t1]) + t2
    a = [0]
    r = f(a, 30, [0] * 8)
    assert lines(run(src, b"", opt)) == [str(r), str(a[0])]


@pytest.mark.parametrize("opt", OPTS)
def test_large_expression_with_many_temporaries(opt):
    terms = [f"({i} * {i + 1} - {i})" for i in range(1, 400)]
    expr = " + ".join(terms)
    exp = sum(i * (i + 1) - i for i in range(1, 400))
    src = prog(f"{expr} ni chupi", f"({expr}) * ({expr}) % 1000003 ni chupi")
    assert lines(run(src, b"", opt)) == [str(exp), str(exp * exp % 1000003)]


@pytest.mark.parametrize("opt", OPTS)
def test_many_locals_in_one_function(opt):
    n = 600
    body = [f"int v{i}" for i in range(n)] + [f"v{i} lo {i} * 3 pettu" for i in range(n)] + [" + ".join(f"v{i}" for i in range(n)) + " ivvu"]
    src = prog("int f charya () {", *body, "}", "f() ni chupi")
    assert lines(run(src, b"", opt)) == [str(sum(3 * i for i in range(n)))]


@pytest.mark.parametrize("opt", OPTS)
def test_many_functions_and_calls(opt):
    n = 200
    fs = [f"int f{i} charya (int x) {{ x + {i} ivvu }}" for i in range(n)]
    chain = "0"
    for i in range(n):
        chain = f"f{i}({chain})"
    src = prog(*fs, f"{chain} ni chupi")
    assert lines(run(src, b"", opt)) == [str(sum(range(n)))]


@pytest.mark.parametrize("opt", OPTS)
def test_functions_named_like_c_library_and_runtime_symbols(opt):
    names = ["main", "printf", "puts", "malloc", "free", "exit", "memcpy", "strlen", "calloc", "write", "read", "abort", "dv_rt_print_int", "start", "_start"]
    src = prog(*[f"int {n} charya (int x) {{ x + 1 ivvu }}" for n in names], *[f"{n}({i}) ni chupi" for i, n in enumerate(names)],
               *[f"int g_{n}" for n in names[:3]], "int printf_count", "printf_count lo 3 pettu", "printf_count ni chupi")
    assert lines(run(src, b"", opt)) == [str(i + 1) for i in range(len(names))] + ["3"]


@pytest.mark.parametrize("opt", OPTS)
def test_global_variables_named_like_c_symbols(opt):
    names = ["main", "stdout", "errno", "environ", "stdin", "printf", "exit"]
    src = prog(*[f"int {n}" for n in names], *[f"{n} lo {i + 5} pettu" for i, n in enumerate(names)], *[f"{n} ni chupi" for n in names])
    assert lines(run(src, b"", opt)) == [str(i + 5) for i in range(len(names))]


@pytest.mark.parametrize("opt", OPTS)
def test_local_variables_shadow_function_and_c_names(opt):
    src = prog("int f charya (int x) { x ivvu }", "int main charya () { 7 ivvu }", "void g charya () { int f\n f lo 3 pettu\n f ni chupi\n int main\n main lo 4 pettu\n main ni chupi }", "g()", "f(9) ni chupi", "main() ni chupi")
    assert lines(run(src, b"", opt)) == ["3", "4", "9", "7"]


@pytest.mark.parametrize("opt", OPTS)
def test_program_with_only_functions_and_no_statements_runs_and_exits_zero(opt):
    p = run(prog("void f charya () { 1 ni chupi }", "int g charya () { 2 ivvu }"), b"", opt)
    assert p.rc == 0 and p.out == b""


@pytest.mark.parametrize("opt", OPTS)
def test_empty_program_runs(opt):
    p = run("", b"", opt)
    assert p.rc == 0 and p.out == b""


@pytest.mark.parametrize("opt", OPTS)
def test_program_exit_status_zero_after_output_without_trailing_newline_in_source(opt):
    p = run("1 ni chupi", b"", opt)
    assert p.rc == 0 and p.out == b"1\n"


@pytest.mark.parametrize("opt", OPTS)
def test_unreachable_code_after_return_and_break_is_harmless(opt):
    src = prog("int f charya (int x) { x ivvu\n 1 / 0 ni chupi\n 99 ivvu }", "f(5) ni chupi",
               "prati i 0 nundi 3 varaku { aapu\n 1 / 0 ni chupi }", "nijam unnanta varaku { aapu\n 5 / 0 ni chupi }", "\"ok\" ni chupi")
    assert lines(run(src, b"", opt)) == ["5", "ok"]


@pytest.mark.parametrize("opt", OPTS)
def test_infinite_loop_with_break_inside_nested_conditions(opt):
    src = prog("int i", "i lo 0 pettu", "nijam unnanta varaku { i lo i + 1 pettu\n i % 2 == 0 ayite { saagu }\n i > 9 ayite { aapu }\n i ni chupi }", "i ni chupi")
    assert lines(run(src, b"", opt)) == ["1", "3", "5", "7", "9", "11"]


@pytest.mark.parametrize("opt", OPTS)
def test_shadowed_loop_variable_in_nested_range_loops(opt):
    src = prog("prati i 0 nundi 2 varaku { prati i 5 nundi 7 varaku { i ni chupi }\n i ni chupi }")
    assert lines(run(src, b"", opt)) == ["5", "6", "0", "5", "6", "1"]


# ---------------------------------------------------------------- stack alignment at runtime-library calls (System V, 16-byte at call)
@pytest.mark.parametrize("ni", list(range(0, 14)))
@pytest.mark.parametrize("nf", [0, 1, 9])
@pytest.mark.parametrize("opt", OPTS)
def test_runtime_calls_from_functions_with_every_stack_argument_parity(ni, nf, opt):
    ps = ", ".join([f"int a{i}" for i in range(ni)] + [f"float f{i}" for i in range(nf)]) or ""
    body = ["\"s\" + \"t\" ni chupi", "1.5 * 3 ni chupi", "(float) 7 / 2 ni chupi", "'c' ni chupi", "nijam ni chupi", "100 ni chupi",
            "podavu(\"abc\" + \"de\") ni chupi"] + [f"a{i} ni chupi" for i in range(min(ni, 2))] + [f"f{i} ni chupi" for i in range(min(nf, 2))]
    args = ", ".join([str(i + 1) for i in range(ni)] + [f"{i}.25" for i in range(nf)])
    src = prog(f"void h charya ({ps}) {{", *body, "}", f"h({args})", f"h({args})")
    one = ["st", "4.5", "3.5", "c", "nijam", "100", "5"] + [str(i + 1) for i in range(min(ni, 2))] + [g(i + 0.25) for i in range(min(nf, 2))]
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == one * 2


@pytest.mark.parametrize("opt", OPTS)
def test_runtime_calls_inside_argument_evaluation(opt):
    src = prog("int id charya (int x) { x ni chupi\n x ivvu }", "float fid charya (float x) { x ni chupi\n x ivvu }",
               "int s charya (int a, int b, int c, int d, int e, int f, int g, int h, int i) { a + b + c + d + e + f + g + h + i ivvu }",
               "s(id(1), id(2), id(3), id(4), id(5), id(6), id(7), id(8), id(9)) ni chupi",
               "(fid(1.5) + fid(2.5)) * fid(2.0) ni chupi")
    assert lines(run(src, b"", opt)) == [str(i) for i in range(1, 10)] + ["45", "1.5", "2.5", "2", "8"]


# ---------------------------------------------------------------- algebra/DCE/folding must keep calls and traps (plan §F optimizer contract)
ALG_PRE = ["int cnt", "int f charya (int v) { cnt lo cnt + 1 pettu\n v ni chupi\n v ivvu }"]


@pytest.mark.parametrize("expr,exp_lines", [
    ("f(7) * 0", ["7", "0"]), ("0 * f(7)", ["7", "0"]), ("f(7) - f(7)", ["7", "7", "0"]), ("f(7) + 0", ["7", "7"]), ("0 + f(7)", ["7", "7"]),
    ("f(7) * 1", ["7", "7"]), ("1 * f(7)", ["7", "7"]), ("f(7) % 1", ["7", "0"]), ("f(7) / 1", ["7", "7"]), ("f(7) * 0 + 5", ["7", "5"]),
    ("f(7) == f(7)", ["7", "7", "nijam"]), ("f(7) != f(7)", ["7", "7", "abaddham"]), ("f(7) && 0", ["7", "abaddham"]), ("0 && f(7)", ["abaddham"]),
    ("f(0) || 0", ["0", "abaddham"]), ("1 || f(7)", ["nijam"]), ("f(1) || 1", ["1", "nijam"]), ("!!f(3)", ["3", "nijam"]), ("f(2) < f(2)", ["2", "2", "abaddham"]),
    ("f(f(2) * 0)", ["2", "0", "0"]), ("(f(2) - f(2)) * f(5)", ["2", "2", "5", "0"]), ("f(5) / f(5)", ["5", "5", "1"]), ("f(5) - 5 + 5 - f(5)", ["5", "5", "0"]),
    ("(int) f(5) * 0", ["5", "0"]), ("(f(5) > 3) && (f(1) > 3)", ["5", "1", "abaddham"]), ("(f(5) > 3) || (f(1) > 3)", ["5", "nijam"]),
])
@pytest.mark.parametrize("opt", OPTS)
def test_side_effecting_operands_survive_simplification(expr, exp_lines, opt):
    p = run(prog(*ALG_PRE, f"{expr} ni chupi"), b"", opt)
    assert p.rc == 0, p.err
    assert lines(p) == exp_lines


@pytest.mark.parametrize("expr", ["1 / d * 0", "0 * (1 / d)", "(1 % d) * 0", "0 * (1 % d)", "(1 / d) - (1 / d)", "(1 / d) + 0", "(1 / d) / 1", "(1 / d) % 1", "(1 / d) == (1 / d)",
                                  "(1 / d) < 0 && nijam", "((1 / d) * 0) / 1", "-(1 / d) + (1 / d)", "(1 / d) && abaddham", "((1 / d) * 0 == 0)"])
@pytest.mark.parametrize("opt", OPTS)
def test_trapping_division_inside_dead_looking_expression_still_traps(expr, opt):
    src = prog("int d", "d ni chaduvu", "\"go\" ni chupi", f"{expr} ni chupi", "\"unreachable\" ni chupi")
    p = run(src, b"0", opt)
    assert p.rc == 1 and p.text == "go\n", (p.rc, p.text, p.err)
    assert "division by zero" in p.err or "remainder by zero" in p.err


@pytest.mark.parametrize("opt", OPTS)
def test_trap_in_assigned_but_never_read_variable(opt):
    src = prog("void f charya (int d) { int junk\n junk lo 10 / d pettu\n \"done\" ni chupi }", "f(2)", "f(0)")
    p = run(src, b"", opt)
    assert p.rc == 1 and p.text == "done\n"


@pytest.mark.parametrize("opt", OPTS)
def test_signed_char_constants_fold_with_sign(opt):
    rows = [("'\\xFF' < 0", "nijam"), ("'\\x80' == -128", "nijam"), ("'\\x7F' > 0", "nijam"), ("(char) 200 < 0", "nijam"), ("(char) 200 == 200", "abaddham"),
            ("(char) 200 == -56", "nijam"), ("'\\xFF' + 1", "0"), ("'\\xFE' * 2", "-4"), ("'\\xFF' / 2", "0"), ("'\\xFF' % 2", "-1"), ("(float) '\\xFF'", "-1"),
            ("(bool) '\\x80'", "nijam"), ("'\\xFF' == '\\xFF'", "nijam"), ("'\\xFF' > '\\x01'", "abaddham"), ("-'\\xFF'", "1")]
    p = run(prog(*[f"{e} ni chupi" for e, _ in rows]), b"", opt)
    assert lines(p) == [x for _, x in rows]


@pytest.mark.parametrize("opt", OPTS)
def test_signed_char_variables_compare_with_sign(opt):
    src = prog("char a", "char b", "a lo '\\xFF' pettu", "b lo '\\x01' pettu", "a < b ni chupi", "a > b ni chupi", "a == -1 ni chupi", "a + b ni chupi", "(int) a ni chupi",
               "a / 2 ni chupi", "a * a ni chupi", "a < 0 ni chupi", "(a < 0) == nijam ni chupi", "(float) a / 2 ni chupi", "a % 3 ni chupi")
    assert lines(run(src, b"", opt)) == ["nijam", "abaddham", "nijam", "0", "-1", "0", "1", "nijam", "nijam", "-0.5", "-1"]


@pytest.mark.parametrize("opt", OPTS)
def test_constant_condition_branches_with_side_effects(opt):
    src = prog(*ALG_PRE, "nijam ayite { f(1) } lekunte { f(2) }", "abaddham ayite { f(3) } lekunte { f(4) }", "1 ayite { f(5) }", "0 ayite { f(6) }",
               "0 unnanta varaku { f(7) }", "f(8) ayite { f(9) } lekunte { f(10) }", "f(0) ayite { f(11) } lekunte { f(12) }", "cnt ni chupi")
    assert lines(run(src, b"", opt)) == ["1", "4", "5", "8", "9", "0", "12", "7"]


@pytest.mark.parametrize("opt", OPTS)
def test_loop_invariant_looking_code_is_not_hoisted_across_side_effects(opt):
    src = prog("int g", "int bump charya () { g lo g + 1 pettu\n g ivvu }", "int total", "prati i 0 nundi 4 varaku { total lo total + g * 10 + bump() pettu }", "total ni chupi", "g ni chupi")
    t, g_ = 0, 0
    for i in range(4):
        left = g_
        g_ += 1
        t += left * 10 + g_
    assert lines(run(src, b"", opt)) == [str(t), str(g_)]
