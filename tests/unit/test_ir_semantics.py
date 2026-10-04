"""Phases 5+6: language semantics, executed at O0 and O1 by (a) the Python IR interpreter and
(b) the real x86-64 back end (``native``, slow). Both must produce identical results."""

import pytest

from tests.helpers import native
from tests.helpers.pipeline import run_ir

_BACKEND = {"name": "interp"}


@pytest.fixture(autouse=True, params=["interp", pytest.param("native", marks=pytest.mark.slow)])
def backend(request):
    _BACKEND["name"] = request.param
    yield request.param


def run_backend(src, stdin, level):
    if _BACKEND["name"] == "native":
        return native.build_and_run(src, stdin, level)
    return run_ir(src, stdin, level)


def both(src, stdin=b""):
    a = run_backend(src, stdin, 0)
    b = run_backend(src, stdin, 1)
    assert a == b, f"O0 {a} != O1 {b}"
    return a


def out(src, stdin=b""):
    o, status, err = both(src, stdin)
    assert status == 0, err
    return o.decode("latin-1")


def fail(src, msg, stdin=b""):
    o, status, err = both(src, stdin)
    assert status == 1 and msg in err, (status, err)
    return o


def test_output_formats_p1_to_p6():
    assert out('1 ni chupi\n-5 ni chupi\n3.14 ni chupi\n10.0 ni chupi\n1000000.0 ni chupi\n'
               'nijam ni chupi\nabaddham ni chupi\n\'A\' ni chupi\n"hi" ni chupi\n"" ni chupi') == \
        "1\n-5\n3.14\n10\n1e+06\nnijam\nabaddham\nA\nhi\n\n"


def test_integer_wraparound_l37():
    assert out("9223372036854775807 + 1 ni chupi\n-9223372036854775807 - 2 ni chupi\n"
               "4611686018427387904 * 2 ni chupi") == \
        "-9223372036854775808\n9223372036854775807\n-9223372036854775808\n"


def test_division_semantics_and_traps():
    assert out("7 / 2 ni chupi\n-7 / 2 ni chupi\n7 / -2 ni chupi\n7 % 3 ni chupi\n-7 % 3 ni chupi\n"
               "7 % -3 ni chupi\n(-9223372036854775807 - 1) % -1 ni chupi") == "3\n-3\n-3\n1\n-1\n1\n0\n"
    fail("int z\nz lo 0 pettu\n1 / z ni chupi", "division by zero")
    fail("int z\nz lo 0 pettu\n1 % z ni chupi", "remainder by zero")
    fail("int m\nm lo -9223372036854775807 - 1 pettu\nm / -1 ni chupi", "integer overflow in division")
    fail("1 / 0 ni chupi", "division by zero")


def test_unused_trapping_division_is_not_removed_by_optimizer():
    fail("int z\nz lo 0 pettu\nint u\nu lo 5 / z pettu\n\"after\" ni chupi", "division by zero")
    o = fail("\"before\" ni chupi\nint u\nu lo 5 / 0 pettu\n\"after\" ni chupi", "division by zero")
    assert o == b"before\n"


def test_float_semantics():
    assert out("1.0 / 0.0 ni chupi\n-1.0 / 0.0 ni chupi\n0.1 + 0.2 ni chupi\n(int) 3.99 ni chupi\n"
               "(int) -3.99 ni chupi\n(float) 3 / 2 ni chupi\n(int) (0.0 / 0.0) ni chupi") == \
        "inf\n-inf\n0.3\n3\n-3\n1.5\n-9223372036854775808\n"


def test_conversions_p27():
    assert out("int i\ni lo 3.9 pettu\ni ni chupi\nchar c\nc lo 321 pettu\nc ni chupi\n"
               "(int) c ni chupi\nbool b\nb lo 5 pettu\nb ni chupi\nb lo 0.0 pettu\nb ni chupi\n"
               "(int) nijam + 1 ni chupi\n'a' + 1 ni chupi\nchar d\nd lo 200 pettu\n(int) d ni chupi") == \
        "3\nA\n65\nnijam\nabaddham\n2\n98\n-56\n"


def test_short_circuit_and_evaluation_order():
    src = """
int f charya(int x) { x ni chupi\nx ivvu }
f(1) + f(2) * f(3) ni chupi
f(0) && f(5) ni chupi
f(1) || f(6) ni chupi
f(1) && f(7) ni chupi
f(0) || f(8) ni chupi
"""
    o = out(src)
    assert o.split() == ["1", "2", "3", "7", "0", "abaddham", "1", "nijam", "1", "7", "nijam",
                         "0", "8", "nijam"]


def test_argument_evaluation_left_to_right():
    src = """
int f charya(int x) { x ni chupi\nx ivvu }
int g charya(int a, int b, int c) { a * 100 + b * 10 + c ivvu }
g(f(1), f(2), f(3)) ni chupi
"""
    assert out(src).split() == ["1", "2", "3", "123"]


def test_if_else_chains_and_loops():
    src = """
int x
x lo 5 pettu
x < 3 ayite { 1 ni chupi } lekunte x < 7 ayite { 2 ni chupi } lekunte { 3 ni chupi }
int i
i lo 0 pettu
i < 5 unnanta varaku {
  i lo i + 1 pettu
  i == 2 ayite { saagu }
  i == 4 ayite { aapu }
  i ni chupi
}
"""
    assert out(src).split() == ["2", "1", "3"]


def test_range_loop_semantics_l12_to_l17():
    src = """
int n
n lo 3 pettu
prati i 0 nundi n varaku { n lo 10 pettu\ni ni chupi }
prati j 5 nundi 5 varaku { "never" ni chupi }
prati k 3 nundi 1 varaku { "never" ni chupi }
prati m -1 nundi 2 varaku { m ni chupi }
"""
    assert out(src).split() == ["0", "1", "2", "-1", "0", "1"]


def test_range_variable_mutable_l47():
    assert out("prati i 0 nundi 6 varaku { i ni chupi\ni lo i + 1 pettu }").split() == ["0", "2", "4"]


def test_for_loop_forms_and_continue_runs_update():
    src = """
pratisari (int i lo 0 pettu; i < 6; i++) { i % 2 == 0 ayite { saagu } i ni chupi }
int k
pratisari (k 10 tho modhalu; k > 7; --k) { k ni chupi }
int j
pratisari (j lo 0 pettu; j < 3; j lo j + 2 pettu) { j ni chupi }
pratisari (int z; z < 1; z++) { }
"""
    # last loop reads uninitialized z: rejected by sema, so drop it in a separate test
    src = src.replace("pratisari (int z; z < 1; z++) { }\n", "")
    assert out(src).split() == ["1", "3", "5", "10", "9", "8", "0", "2"]


def test_prefix_postfix_updates_on_arrays_chars_floats():
    src = """
int a[3]
a[0] lo 5 pettu
char c
c lo 'x' pettu
float f
f lo 0.5 pettu
pratisari (int i lo 0 pettu; a[0] < 7; a[0]++) { }
pratisari (int j lo 0 pettu; c < 'z'; ++c) { }
pratisari (int k lo 0 pettu; f > -1.5; f--) { }
a[0] ni chupi\nc ni chupi\nf ni chupi
"""
    assert out(src) == "7\nz\n-1.5\n"


def test_char_increment_wraps_to_eight_bits():
    src = "char c\nc lo 127 pettu\npratisari (int i lo 0 pettu; c > 0; c++) { }\n(int) c ni chupi"
    assert out(src) == "-128\n"


def test_arrays_row_major_and_partial_views():
    src = """
int m[3][4]
prati i 0 nundi 3 varaku { prati j 0 nundi 4 varaku { m[i][j] lo i * 10 + j pettu } }
int rowsum charya(int r[], int n) { int s\ns lo 0 pettu\nprati k 0 nundi n varaku { s lo s + r[k] pettu } s ivvu }
rowsum(m[1], 4) ni chupi
rowsum(m[2], 4) ni chupi
m[2][3] ni chupi
int cube[2][3][4]
cube[1][2][3] lo 99 pettu
int flat charya(int r[]) { r[3] ivvu }
flat(cube[1][2]) ni chupi
flat(cube[1][2]) + cube[1][2][3] ni chupi
"""
    assert out(src).split() == ["46", "86", "23", "99", "198"]


def test_arrays_zero_filled_and_dynamic_sizes():
    src = """
int n
n ni chaduvu
float a[n]
bool b[n][2]
a[0] ni chupi\nb[1][1] ni chupi
int j
j lo 0 pettu
int c[3]
c[1] lo 4 pettu
c[1] ni chupi
"""
    assert out(src, b"3\n") == "0\nabaddham\n4\n"
    fail("int n\nn ni chaduvu\nint a[n]", "invalid array size", b"0")
    fail("int n\nn ni chaduvu\nint a[n]", "invalid array size", b"-4")
    fail("int n\nn ni chaduvu\nint a[3][n]", "invalid array size", b"0")


def test_local_array_rezeroed_each_execution():
    src = """
prati i 0 nundi 2 varaku { int a[2]\na[0] ni chupi\na[0] lo 9 pettu }
"""
    assert out(src).split() == ["0", "0"]


def test_global_arrays_and_scalars_visible_in_functions():
    src = """
int g
int t[4]
void setit charya(int v) { g lo v pettu\nt[2] lo v * 2 pettu }
setit(21)
g ni chupi
t[2] ni chupi
t[1] ni chupi
"""
    assert out(src).split() == ["21", "42", "0"]


def test_global_dynamic_array_used_in_function():
    src = """
int n
n ni chaduvu
int d[n]
int f charya(int i) { d[i] ivvu }
d[2] lo 8 pettu
f(2) ni chupi
"""
    assert out(src, b"4").split() == ["8"]


def test_recursion_and_mutual_recursion():
    src = """
int fib charya(int n) { n < 2 ayite { n ivvu } fib(n - 1) + fib(n - 2) ivvu }
fib(15) ni chupi
int even charya(int n) { n == 0 ayite { 1 ivvu } odd(n - 1) ivvu }
int odd charya(int n) { n == 0 ayite { 0 ivvu } even(n - 1) ivvu }
even(10) ni chupi
"""
    assert out(src).split() == ["610", "1"]


def test_void_function_and_call_statement():
    assert out('void hi charya() { "hi" ni chupi }\nhi()\nhi()') == "hi\nhi\n"


def test_padham_operations_l4():
    src = """
padham s
s lo "ab" + "cd" pettu
s ni chupi
podavu(s) ni chupi
s[2] ni chupi
s == "abcd" ni chupi
s != "abcd" ni chupi
(padham) 'x' ni chupi
(char) "y" ni chupi
padham e
podavu(e) ni chupi
"""
    assert out(src) == "abcd\n4\nc\nnijam\nabaddham\nx\ny\n0\n"


def test_padham_runtime_errors():
    fail('padham s\ns lo "ab" pettu\ns[2] ni chupi', "string index out of range")
    fail('padham s\ns lo "ab" pettu\ns[0 - 1] ni chupi', "string index out of range")
    fail('(char) "ab" ni chupi', "invalid char conversion")
    fail('(char) "" ni chupi', "invalid char conversion")


def test_input_formats_p7_to_p10():
    src = """
int a\nfloat f\nbool b\nbool c\nchar ch\nchar d\npadham s\npadham t
a ni chaduvu\nf ni chaduvu\nb ni chaduvu\nc ni chaduvu\nch ni chaduvu\nd ni chaduvu
s ni chaduvu\nt ni chaduvu
a ni chupi\nf ni chupi\nb ni chupi\nc ni chupi\nch ni chupi\nd ni chupi\ns ni chupi\nt ni chupi
"""
    data = b"  -42 \n 2.5e1  NIJAM  0 \n x   y\nhello world\nsecond line\n"
    assert out(src, data) == "-42\n25\nnijam\nabaddham\nx\ny\nhello world\nsecond line\n"


def test_input_failures_p10():
    fail("int a\na ni chaduvu", "invalid input", b"")
    fail("int a\na ni chaduvu", "invalid input", b"abc")
    fail("int a\na ni chaduvu", "invalid input", b"99999999999999999999")
    fail("bool b\nb ni chaduvu", "invalid input", b"maybe")
    fail("padham s\ns ni chaduvu", "invalid input", b"")


def test_stdout_flushed_before_runtime_error():
    assert fail('"a" ni chupi\n1 / 0 ni chupi', "division by zero") == b"a\n"


def test_input_into_array_element_and_string_via_read_loop():
    src = "int a[3]\nprati i 0 nundi 3 varaku { a[i] ni chaduvu }\na[0] + a[1] + a[2] ni chupi"
    assert out(src, b"1 2 3") == "6\n"


def test_globals_zero_initialized_l21():
    assert out("int a\nfloat b\nbool c\nchar d\npadham e\na ni chupi\nb ni chupi\nc ni chupi\n(int) d ni chupi\ne ni chupi") \
        == "0\n0\nabaddham\n0\n\n"


def test_function_scalar_params_by_value_and_array_by_reference():
    src = """
void bump charya(int x, int a[]) { x lo x + 1 pettu\na[0] lo a[0] + 1 pettu }
int v\nv lo 1 pettu\nint arr[1]\narr[0] lo 1 pettu
bump(v, arr)
v ni chupi\narr[0] ni chupi
"""
    assert out(src) == "1\n2\n"


def test_while_true_with_break_and_return_from_loop():
    src = "int f charya() { int i\ni lo 0 pettu\nnijam unnanta varaku { i lo i + 1 pettu\ni == 4 ayite { i ivvu } } }\nf() ni chupi"
    assert out(src) == "4\n"


def test_top_level_return_rejected_and_nested_loop_break_targets_inner():
    src = "prati i 0 nundi 2 varaku { prati j 0 nundi 5 varaku { j == 1 ayite { aapu } j ni chupi } i ni chupi }"
    assert out(src).split() == ["0", "0", "0", "1"]


def test_shadowing_and_scopes_execute_correctly():
    src = "int x\nx lo 1 pettu\nnijam ayite { int x\nx lo 2 pettu\nx ni chupi }\nx ni chupi"
    assert out(src) == "2\n1\n"


def test_float_loop_and_comparison_chain():
    src = "float f\npratisari (f lo 0.0 pettu; f < 1.0; f lo f + 0.25 pettu) { f ni chupi }"
    assert out(src).split() == ["0", "0.25", "0.5", "0.75"]


def test_q001_unary_minus_wraps_on_int64_min():
    src = "int m\nm lo -9223372036854775807 - 1 pettu\n-m ni chupi\n- -m ni chupi"
    assert out(src) == "-9223372036854775808\n-9223372036854775808\n"


def test_padham_arrays_zero_filled_and_assignable():
    src = 'padham a[3]\npodavu(a[2]) ni chupi\na[1] lo "hi" + "!" pettu\na[1] ni chupi\n' \
          'int f charya(padham p[], int i) { podavu(p[i]) ivvu }\nf(a, 1) ni chupi\nf(a, 0) ni chupi'
    assert out(src) == "0\nhi!\n3\n0\n"


def test_q005_float_to_char_composition():
    src = "float f\nf lo 300.7 pettu\nchar c\nc lo f pettu\n(int) c ni chupi\n(int) (char) 3.9 ni chupi\n" \
          "bool b\nb lo 0.0 / 0.0 pettu\nb ni chupi"
    assert out(src) == "44\n3\nnijam\n"
