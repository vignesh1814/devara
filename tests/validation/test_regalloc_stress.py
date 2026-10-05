"""Register-allocation / peephole attacks.

Every program is compiled at -O0 (naive reference code path) and -O1 (register allocator + peephole) and the stdout, exit
status and runtime-error message must equal each other *and* the independent reference interpreter.  Inputs that would let
the optimiser constant-fold the pressure away are read from stdin.  These tests are black-box: they hold on any correct
compiler, whatever its register allocation strategy.
"""
import pytest

from tests.validation import stress_progs as sp
from tests.validation.stress_util import check_against_reference, run, reference, norm

pytestmark = pytest.mark.slow


def agree(case, expect_status=None):
    src, stdin = case
    return check_against_reference(src, stdin, expect_status=expect_status)


# ------------------------------------------------------------------------------------------ many simultaneously live values
@pytest.mark.parametrize("ni,nf,seed", [(20, 1, 1), (21, 2, 2), (1, 20, 3), (28, 1, 4), (24, 16, 5), (40, 24, 6), (14, 14, 7), (8, 22, 8), (60, 30, 9)])
def test_many_live_ints_and_floats_across_calls(ni, nf, seed):
    agree(sp.many_live(seed, ni, nf, 70))


@pytest.mark.parametrize("seed", range(10, 16))
def test_many_live_with_chars_bools_strings(seed):
    agree(sp.many_live(seed, 22, 12, 60, extra_types=True))


@pytest.mark.parametrize("seed", range(20, 24))
def test_many_live_long_straight_line(seed):
    agree(sp.many_live(seed, 33, 20, 250))


# ------------------------------------------------------------------------------------------ deep expression trees
@pytest.mark.parametrize("kind", ["int", "float", "mixed", "bool"])
@pytest.mark.parametrize("shape,depth", [("left", 40), ("right", 40), ("bal", 7), ("rand", 8), ("right", 120), ("left", 150)])
def test_deep_expression_trees(kind, shape, depth):
    agree(sp.deep_expr(depth * 7 + len(kind), depth, shape, kind, calls=False))


@pytest.mark.parametrize("kind", ["int", "float", "mixed"])
@pytest.mark.parametrize("shape,depth", [("right", 30), ("bal", 6), ("rand", 7)])
def test_deep_expression_trees_with_calls_at_nodes(kind, shape, depth):
    agree(sp.deep_expr(depth * 13 + len(kind), depth, shape, kind, calls=True))


@pytest.mark.parametrize("n", [12, 20, 31, 48, 70])
@pytest.mark.parametrize("calls", [False, True])
def test_wide_right_nested_tree_over_n_live_variables(n, calls):
    agree(sp.wide_sum_tree(n, calls))


# ------------------------------------------------------------------------------------------ many parameters
@pytest.mark.parametrize("n", [10, 11, 13, 17, 24, 33, 40])
@pytest.mark.parametrize("seed", [1, 2])
def test_functions_with_10_to_40_mixed_params(n, seed):
    agree(sp.many_params(seed * 100 + n, n))


@pytest.mark.parametrize("t,n", [("int", 40), ("float", 40), ("char", 30), ("bool", 30), ("padham", 14), ("float", 12), ("int", 7)])
def test_homogeneous_parameter_lists(t, n):
    agree(sp.many_params(n, n, [t] * n))


@pytest.mark.parametrize("pattern", ["if", "fi", "ifif", "ffff_iiii", "iiii_ffff", "cbpcbp"])
def test_alternating_param_kinds(pattern):
    m = {"i": "int", "f": "float", "c": "char", "b": "bool", "p": "padham", "_": None}
    ts = [m[c] for c in pattern * 3 if m[c]]
    agree(sp.many_params(len(pattern), len(ts), ts))


# ------------------------------------------------------------------------------------------ recursion
@pytest.mark.parametrize("n", [1, 2, 5, 8, 10])
def test_recursion_with_many_live_values(n):
    agree(sp.recursion_live(n))


@pytest.mark.parametrize("nlive", [12, 24])
def test_recursion_live_count_variants(nlive):
    agree(sp.recursion_live(7, nlive))


# ------------------------------------------------------------------------------------------ loops, aapu/saagu
@pytest.mark.parametrize("seed", range(1, 9))
def test_values_live_across_loops_break_continue(seed):
    agree(sp.loops_live(seed))


# ------------------------------------------------------------------------------------------ nested calls in arguments
@pytest.mark.parametrize("depth", [1, 2, 3, 5, 8, 12])
def test_nested_calls_in_arguments_keep_left_to_right_order(depth):
    agree(sp.nested_call_args(depth))


def test_f_of_g_h_and_expression_trace_is_g_h_f():
    # f(g(a,b), h(c), a+b*c) must call g, h, then f: trace 1,2,3 (exact, not just matching the reference)
    src = sp.prog(sp.BASIC, "int tr",
                  "int g charya (int a, int b) { tr lo tr * 10 + 1 pettu\n a + b ivvu }",
                  "int h charya (int a) { tr lo tr * 10 + 2 pettu\n a * 2 ivvu }",
                  "int f charya (int a, int b, int c) { tr lo tr * 10 + 3 pettu\n a * 100 + b * 10 + c ivvu }",
                  "int a", "int b", "int c", "a ni chaduvu", "b ni chaduvu", "c ni chaduvu",
                  "f(g(a, b), h(c), a + b * c) ni chupi", "tr ni chupi")
    for opt in ("-O0", "-O1"):
        p = run(src, opt, b"2 3 4\n")
        assert (p.rc, p.out) == (0, b"594\n123\n"), (opt, p.out, p.err)


# ------------------------------------------------------------------------------------------ short-circuit with side effects
@pytest.mark.parametrize("seed", range(1, 13))
def test_short_circuit_with_side_effecting_operands(seed):
    agree(sp.short_circuit(seed, nterms=10, depth=4))


def test_short_circuit_exact_traces():
    src = sp.prog("int tr",
                  "bool t charya (int id, bool v) { tr lo tr * 10 + id pettu\n v ivvu }",
                  "int run charya (int k) {",
                  "  int l0", "  int l1", "  int l2", "  int l3", "  int l4", "  int l5", "  int l6", "  int l7", "  int l8", "  int l9",
                  "  l0 lo k pettu", "  l1 lo k + 1 pettu", "  l2 lo k + 2 pettu", "  l3 lo k + 3 pettu", "  l4 lo k + 4 pettu",
                  "  l5 lo k + 5 pettu", "  l6 lo k + 6 pettu", "  l7 lo k + 7 pettu", "  l8 lo k + 8 pettu", "  l9 lo k + 9 pettu",
                  "  bool r",
                  "  r lo t(1, abaddham) && t(2, nijam) pettu", "  tr ni chupi", "  tr lo 0 pettu",
                  "  r lo t(1, nijam) || t(2, nijam) pettu", "  tr ni chupi", "  tr lo 0 pettu",
                  "  r lo t(1, abaddham) || t(2, nijam) && t(3, abaddham) || t(4, nijam) pettu", "  tr ni chupi", "  r ni chupi", "  tr lo 0 pettu",
                  "  r lo !t(1, nijam) && t(2, nijam) || t(3, abaddham) pettu", "  tr ni chupi", "  r ni chupi",
                  "  l0 + l1 + l2 + l3 + l4 + l5 + l6 + l7 + l8 + l9 ivvu", "}",
                  "int q", "q ni chaduvu", "run(q) ni chupi")
    exp = b"1\n1\n1234\nnijam\n13\nabaddham\n" + str(10 * 5 + 45).encode() + b"\n"
    for opt in ("-O0", "-O1"):
        p = run(src, opt, b"5\n")
        assert (p.rc, p.out) == (0, exp), (opt, p.out, p.err)


# ------------------------------------------------------------------------------------------ aliasing
def test_array_parameters_aliasing_each_other_and_globals():
    agree(sp.array_aliasing())


# ------------------------------------------------------------------------------------------ INT64 / char / float specials
def test_int64_edge_values_in_registers():
    agree(sp.int_edges())


@pytest.mark.parametrize("stdin", [b"9223372036854775807 -9223372036854775808 -1 1\n", b"0 0 0 0\n", b"-1 -1 -1 -1\n",
                                   b"4611686018427387904 4611686018427387904 3037000500 3037000501\n"])
def test_int64_edge_values_other_inputs(stdin):
    src, _ = sp.int_edges()
    check_against_reference(src, stdin)


def test_char_sign_extension_in_registers():
    agree(sp.char_signext())


@pytest.mark.parametrize("stdin", [b"a b 3\n", b"\x80 \x7f 0\n", b"\xff \x01 -7\n", b"\xc8 \xc8 100000\n"])
def test_char_sign_extension_other_inputs(stdin):
    src, _ = sp.char_signext()
    check_against_reference(src, stdin)


def test_float_nan_and_negative_zero_kept_in_registers():
    agree(sp.float_specials())


@pytest.mark.parametrize("stdin", [b"0.0 1.0 3\n", b"-0.0 2.5 -3\n", b"0.0 -1.0 0\n", b"1e308 1e308 5\n"])
def test_float_specials_other_inputs(stdin):
    src, _ = sp.float_specials()
    check_against_reference(src, stdin)


# ------------------------------------------------------------------------------------------ traps with values held in registers
@pytest.mark.parametrize("kind,msg", [("div", "division by zero"), ("rem", "remainder by zero"),
                                      ("ovf", "integer overflow in division"), ("idx", "string index out of range")])
def test_runtime_error_with_many_live_values(kind, msg):
    src, stdin = sp.trap_under_pressure(kind)
    ref = check_against_reference(src, stdin, expect_status=1)
    assert ref.error == msg
    assert b"unreachable" not in ref.stdout
    for opt in ("-O0", "-O1"):
        p = run(src, opt, stdin)
        assert p.rc == 1 and f"devara: runtime error: {msg}" in p.err
        assert p.out.count(b"\n") == ref.stdout.count(b"\n")   # stdout flushed up to the trap


# ------------------------------------------------------------------------------------------ misc register-sensitive idioms
def test_swap_and_rotate_through_many_registers():
    L = ["int rot charya (int a, int b, int c, int d, int e, int f, int g, int h, int n) {",
         "  int t",
         "  prati i 0 nundi n varaku {",
         "    t lo a pettu", "    a lo b pettu", "    b lo c pettu", "    c lo d pettu", "    d lo e pettu", "    e lo f pettu", "    f lo g pettu", "    g lo h pettu", "    h lo t pettu",
         "    a lo a + h * i pettu",
         "  }",
         "  a ni chupi", "  b ni chupi", "  c ni chupi", "  d ni chupi", "  e ni chupi", "  f ni chupi", "  g ni chupi", "  h ni chupi",
         "  a * 1 + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 + h * 8 ivvu", "}",
         "int x", "x ni chaduvu", "rot(x, x + 1, x + 2, x + 3, x + 4, x + 5, x + 6, x + 7, 11) ni chupi"]
    agree((sp.prog(*L), b"3\n"))


def test_same_value_passed_in_every_argument_position_and_returned_unchanged():
    L = ["int s9 charya (int a, int b, int c, int d, int e, int f, int g, int h, int i) {",
         "  a lo a + b pettu", "  b lo b + c pettu", "  i lo i * a pettu", "  a + b + c + d + e + f + g + h + i ivvu }",
         "int x", "x ni chaduvu", "s9(x, x, x, x, x, x, x, x, x) ni chupi", "s9(s9(x, x, x, x, x, x, x, x, x), x, x, x, x, x, x, x, s9(x, x, x, x, x, x, x, x, x)) ni chupi"]
    agree((sp.prog(*L), b"-7\n"))


def test_division_and_remainder_heavy_expression_keeps_rdx_rax_correct():
    # idiv clobbers rax/rdx: values living in those registers must be preserved by the allocator
    L = ["int dv charya (int a, int b, int c, int d, int e, int f) {",
         "  int r1", "  int r2", "  int r3", "  r1 lo a / b pettu", "  r2 lo c % b pettu", "  r3 lo (a + c) / (b - 1) pettu",
         "  a * r1 + b * r2 + c * r3 + d / b + e % b + f / (a / b + 1) + (a % b) * (c / b) + (d / e) * (e % f + 1) ivvu }",
         "int a", "int b", "int c", "int d", "int e", "int f", "a ni chaduvu", "b ni chaduvu", "c ni chaduvu", "d ni chaduvu", "e ni chaduvu", "f ni chaduvu",
         "dv(a, b, c, d, e, f) ni chupi", "dv(c, d, e, f, a, b) ni chupi", "dv(-a, b, -c, d, -e, f) ni chupi", "dv(a, -b, c, -d, e, -f) ni chupi"]
    agree((sp.prog(*L), b"100 7 -250 31 9000 13\n"))


def test_float_compare_and_convert_chain_with_many_xmm_values():
    L = ["float fc charya (float a, float b, float c, float d, float e, float f, float g, float h, float i, float j) {",
         "  float s", "  s lo 0.0 pettu",
         "  a < b ayite { s lo s + a pettu } lekunte { s lo s - b pettu }",
         "  c >= d && e != f ayite { s lo s * 2.0 pettu }",
         "  g == h || i > j ayite { s lo s + (float) ((int) g) pettu }",
         "  s + a * b - c / d + e * f - g / h + i * j + (float) ((int) a + (int) b + (int) c + (int) d + (int) e) ivvu }",
         "float x", "x ni chaduvu",
         "fc(x, x + 1.0, x * 2.0, 3.5, x - 1.25, x, x * x, 0.5, x / 3.0, 9.75) ni chupi",
         "fc(x + 1.0, x, 2.0, x * 2.0, x, x - 1.25, 0.5, x * x, 9.75, x / 3.0) ni chupi"]
    agree((sp.prog(*L), b"2.5\n"))


# ------------------------------------------------------------------------------------------ randomised parameter sweeps (hypothesis)
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

_S = dict(max_examples=25, deadline=None, suppress_health_check=list(HealthCheck))


@settings(**_S)
@given(st.integers(0, 10 ** 6), st.integers(1, 48), st.integers(1, 30), st.integers(5, 120), st.booleans())
def test_random_many_live_shapes(seed, ni, nf, rounds, extra):
    agree(sp.many_live(seed, ni, nf, rounds, extra_types=extra))


@settings(**_S)
@given(st.integers(0, 10 ** 6), st.integers(2, 60), st.sampled_from(["left", "right", "bal", "rand"]), st.sampled_from(["int", "float", "mixed", "bool"]), st.booleans())
def test_random_deep_expression_trees(seed, depth, shape, kind, calls):
    if shape in ("bal", "rand"):
        depth = min(depth, 8)
    agree(sp.deep_expr(seed, depth, shape, kind, calls))


@settings(**_S)
@given(st.integers(0, 10 ** 6), st.integers(1, 45))
def test_random_parameter_lists(seed, n):
    agree(sp.many_params(seed, n))


@settings(**_S)
@given(st.integers(0, 10 ** 6), st.integers(4, 18), st.integers(2, 6))
def test_random_short_circuit_programs(seed, nterms, depth):
    agree(sp.short_circuit(seed, nterms, depth))


# ------------------------------------------------------------------------------------------ F-006: -0.0 / 0.0 merged by constant propagation
F006 = {
    "join_negzero_then_zero": ("void f charya (int n) {\nfloat b\nb lo (-0.0) pettu\nn > 0 ayite { b lo 0.0 pettu }\nb ni chupi\n}\nint n\nn ni chaduvu\nf(n)\n",
                               {b"1\n": b"0\n", b"0\n": b"-0\n"}),
    "join_zero_then_negzero": ("void f charya (int n) {\nfloat b\nb lo 0.0 pettu\nn > 0 ayite { b lo (-0.0) pettu }\nb ni chupi\n}\nint n\nn ni chaduvu\nf(n)\n",
                               {b"1\n": b"-0\n", b"0\n": b"0\n"}),
    "loop_body_assigns_zero": ("void f charya () {\nfloat a\na lo (-0.0) pettu\nfloat b\nb lo a pettu\nprati i 0 nundi 5 varaku { b lo a - a pettu }\nb ni chupi\n}\nf()\n",
                               {b"": b"0\n"}),
    "while_assigns_zero": ("void f charya (int n) {\nfloat b\nb lo (-0.0) pettu\nint i\ni lo 0 pettu\ni < n unnanta varaku { b lo 0.0 pettu\n i lo i + 1 pettu }\nb ni chupi\n}\nint n\nn ni chaduvu\nf(n)\n",
                           {b"1\n": b"0\n", b"0\n": b"-0\n"}),
}


@pytest.mark.parametrize("opt", ["-O0", "-O1"])
@pytest.mark.parametrize("name", list(F006))
def test_F006_signed_zero_constants_are_not_merged_at_control_flow_joins(name, opt):
    src, cases = F006[name]
    for stdin, exp in cases.items():
        p = run(src, opt, stdin)
        assert (p.rc, p.out) == (0, exp), f"{name} {opt} stdin={stdin!r}: got {p.out!r}, expected {exp!r}"
