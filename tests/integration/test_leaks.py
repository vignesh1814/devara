"""Leak accounting (plan P22): heap arrays are freed at scope exit, padham values are reference
counted. Every program runs natively at -O0 and -O1 with DEVARA_RT_STATS=1 and must report
``live=0`` at normal exit (the runtime counts live heap arrays + live strings)."""

import pytest

from tests.helpers import native
from tests.helpers.ref import ref_run

pytestmark = pytest.mark.slow

LEVELS = [0, 1]


def prog(*lines):
    return "\n".join(lines) + "\n"


def check(src, expect_out, level, stdin=b"", **kw):
    out, rc, err, live = native.run_stats(src, stdin, level, **kw)
    assert rc == 0, err
    assert out.decode("latin-1") == expect_out
    assert live == 0, f"leaked {live} allocations"


# ── arrays ──

@pytest.mark.parametrize("level", LEVELS)
def test_vla_in_loop_body_one_million_times_is_bounded(level):
    src = prog(
        "int n", "n lo 1000 pettu",
        "int i", "i lo 0 pettu",
        "int total", "total lo 0 pettu",
        "i < 1000000 unnanta varaku {",
        "  int a[n]",
        "  a[i % n] lo i pettu",
        "  total lo total + a[i % n] pettu",
        "  i lo i + 1 pettu",
        "}",
        "total ni chupi",
    )
    # 8 KB per iteration x 10^6 would be 8 GB if leaked: a 256 MB address-space cap proves it is freed
    check(src, "499999500000\n", level, timeout=60, max_vmem_mb=256)


@pytest.mark.parametrize("level", LEVELS)
def test_vla_in_range_and_for_loops(level):
    src = prog(
        "int n", "n lo 50 pettu",
        "int s", "s lo 0 pettu",
        "prati i 0 nundi 20000 varaku {",
        "  int a[n]", "  a[3] lo i pettu", "  s lo s + a[3] pettu",
        "}",
        "pratisari (int j lo 0 pettu; j < 20000; j++) {",
        "  int b[n][2]", "  b[1][1] lo j pettu", "  s lo s + b[1][1] pettu",
        "}",
        "s ni chupi",
    )
    check(src, str(sum(range(20000)) * 2) + "\n", level, timeout=60, max_vmem_mb=256)


@pytest.mark.parametrize("level", LEVELS)
def test_break_continue_return_out_of_nested_scopes_with_arrays(level):
    src = prog(
        "int f charya (int n, int mode) {",
        "  int outer[n]",
        "  outer[0] lo 100 pettu",
        "  int i",
        "  i lo 0 pettu",
        "  i < 10 unnanta varaku {",
        "    int a[n]",
        "    a[0] lo i pettu",
        "    i lo i + 1 pettu",
        "    a[0] == 2 ayite {",
        "      int b[n + 1]",
        "      b[0] lo 7 pettu",
        "      mode == 1 ayite { saagu }",
        "      mode == 2 ayite { aapu }",
        "      mode == 3 ayite { b[0] + a[0] + outer[0] ivvu }",
        "    }",
        "  }",
        "  int tail[n]",
        "  tail[1] lo i pettu",
        "  tail[1] + outer[0] ivvu",
        "}",
        "prati m 0 nundi 4 varaku { f(3, m) ni chupi }",
    )
    # mode 0/1: loop runs to i=10 -> 110; mode 2: break at i=3 -> 103; mode 3: 7+2+100
    check(src, "110\n110\n103\n109\n", level)


@pytest.mark.parametrize("level", LEVELS)
def test_array_parameters_are_views_never_freed_by_the_callee(level):
    src = prog(
        "int fill charya (int a[], int n) {",
        "  prati i 0 nundi n varaku { a[i] lo i * i pettu }",
        "  a[n - 1] ivvu",
        "}",
        "int sum charya (int a[], int n) {",
        "  int s", "  s lo 0 pettu",
        "  prati i 0 nundi n varaku { s lo s + a[i] pettu }",
        "  s ivvu",
        "}",
        "int n", "n lo 6 pettu",
        "int g[n]",
        "int m[n][n]",
        "fill(g, n) ni chupi",
        "sum(g, n) ni chupi",
        "fill(m[2], n) ni chupi",
        "sum(m[2], n) ni chupi",
        "prati k 0 nundi 3 varaku {",
        "  int loc[n]", "  fill(loc, n) ni chupi", "  sum(loc, n) ni chupi",
        "}",
    )
    check(src, "25\n55\n25\n55\n25\n55\n" * 1 + "25\n55\n25\n55\n", level)


@pytest.mark.parametrize("level", LEVELS)
def test_recursion_with_per_frame_heap_arrays(level):
    src = prog(
        "int f charya (int n) {",
        "  int a[n + 1]",
        "  a[0] lo n pettu",
        "  n == 0 ayite { 0 ivvu }",
        "  int r",
        "  r lo f(n - 1) pettu",
        "  a[0] + r ivvu",
        "}",
        "f(50) ni chupi",
    )
    check(src, str(sum(range(51))) + "\n", level)


@pytest.mark.parametrize("level", LEVELS)
def test_large_constant_size_arrays_and_frame_arrays(level):
    src = prog(
        "int small charya () { int a[4][4]\n a[3][3] lo 9 pettu\n a[3][3] ivvu }",
        "int big charya () { int a[20000]\n a[19999] lo 5 pettu\n a[19999] ivvu }",
        "small() ni chupi", "big() ni chupi",
        "int g[100000]", "g[99999] lo 1 pettu", "g[99999] ni chupi",
    )
    check(src, "9\n5\n1\n", level)



# ── padham (reference counted) ──
# Expected output comes from the independent reference interpreter; `expect` pins a few values
# computed by hand so the oracle itself stays honest.

def check_ref(src, level, stdin=b"", expect=None, **kw):
    ref = ref_run(src, stdin)
    assert ref.status == 0, ref.error
    out, rc, err, live = native.run_stats(src, stdin, level, **kw)
    assert rc == 0, err
    assert out == ref.stdout
    if expect is not None:
        assert out.decode("latin-1") == expect
    assert live == 0, f"leaked {live} allocations"


@pytest.mark.parametrize("level", LEVELS)
def test_string_concatenation_in_a_loop(level):
    src = prog(
        "padham s", "s lo \"\" pettu",
        "prati i 0 nundi 3000 varaku { s lo s + \"ab\" pettu }",
        "podavu(s) ni chupi",
        "int n", "n lo 0 pettu",
        "prati i 0 nundi 1000 varaku { n lo n + podavu(\"a\" + \"bc\" + (padham) 'd' + s) pettu }",
        "n ni chupi",
    )
    check_ref(src, level, expect="6000\n" + str(1000 * 6004) + "\n")


@pytest.mark.parametrize("level", LEVELS)
def test_string_temporaries_in_a_million_iteration_loop_stay_bounded(level):
    long_lit = "z" * 62
    src = prog(
        "int total", "total lo 0 pettu",
        "prati i 0 nundi 1000000 varaku {",
        "  padham t",
        f"  t lo \"x\" + (padham) 'y' + \"{long_lit}\" pettu",
        "  total lo total + podavu(t) pettu",
        "}",
        "total ni chupi",
    )
    # without freeing, 10^6 x ~100 bytes = 100 MB: the 48 MB cap proves strings are released
    check_ref(src, level, expect="64000000\n", timeout=60, max_vmem_mb=48)


@pytest.mark.parametrize("level", LEVELS)
def test_reassigning_strings_locals_globals_and_elements(level):
    src = prog(
        "padham g", "padham arr[3]", "padham h[2][2]",
        "g lo \"one\" + \"1\" pettu",
        "g lo g + g pettu",
        "g lo g pettu",
        "arr[0] lo g pettu", "arr[1] lo arr[0] + \"!\" pettu", "arr[0] lo arr[1] pettu",
        "arr[0] lo arr[0] pettu",
        "h[1][1] lo arr[0] + arr[1] pettu", "h[0][1] lo h[1][1] pettu", "h[1][1] lo \"\" pettu",
        "g ni chupi", "arr[0] ni chupi", "arr[1] ni chupi", "h[0][1] ni chupi", "h[1][1] ni chupi",
        "padham l", "l lo g pettu", "g lo \"changed\" pettu", "l ni chupi", "g ni chupi",
        "l lo l + l pettu", "l lo \"\" pettu", "podavu(l) ni chupi",
    )
    expect = ("one1one1\n" "one1one1!\n" "one1one1!\n" "one1one1!one1one1!\n" "\n"
              "one1one1\n" "changed\n" "0\n")
    check_ref(src, level, expect=expect)


@pytest.mark.parametrize("level", LEVELS)
def test_padham_arrays_all_storage_classes(level):
    src = prog(
        "padham gs[4]",                       # global, constant size (static storage)
        "int n", "n lo 5 pettu",
        "padham gv[n]",                       # global, run-time size (heap)
        "padham gm[n][2]",                    # global, 2-D run-time size
        "padham f charya (int k) {",
        "  padham loc[3]",                    # frame array
        "  padham vla[k]",                    # heap array
        "  padham vm[k][2]",
        "  prati i 0 nundi 3 varaku { loc[i] lo (padham) 'a' + loc[i] + (padham) 'b' pettu }",
        "  prati i 0 nundi k varaku {",
        "    vla[i] lo loc[i % 3] + loc[0] pettu",
        "    vm[i][1] lo vla[i] + \"#\" pettu",
        "  }",
        "  vm[k - 1][1] + vla[0] ivvu",
        "}",
        "prati i 0 nundi 4 varaku { gs[i] lo f(i + 1) + gs[i] pettu }",
        "prati i 0 nundi n varaku { gv[i] lo gs[i % 4] pettu  gm[i][0] lo gv[i] + gv[i] pettu }",
        "gs[3] ni chupi", "gv[4] ni chupi", "podavu(gm[4][0]) ni chupi",
        "podavu(gm[2][1]) ni chupi",
    )
    check_ref(src, level)


@pytest.mark.parametrize("level", LEVELS)
def test_padham_arrays_in_loops_and_overwritten_elements(level):
    src = prog(
        "int n", "n lo 4 pettu",
        "int total", "total lo 0 pettu",
        "prati r 0 nundi 2000 varaku {",
        "  padham a[n]", "  padham b[3]",
        "  prati i 0 nundi n varaku { a[i] lo \"k\" + a[i] + (padham) 'v' pettu }",
        "  prati i 0 nundi n varaku { a[i] lo a[i] + a[(i + 1) % n] pettu }",
        "  b[1] lo a[0] + a[3] pettu", "  b[1] lo b[1] + b[1] pettu",
        "  total lo total + podavu(b[1]) + podavu(a[2]) + podavu(b[0]) pettu",
        "}",
        "total ni chupi",
    )
    check_ref(src, level, expect=str(2000 * 24) + "\n", timeout=60, max_vmem_mb=64)


@pytest.mark.parametrize("level", LEVELS)
def test_break_continue_return_out_of_nested_scopes_with_strings_and_arrays(level):
    src = prog(
        "padham f charya (int n, int mode) {",
        "  padham outer",
        "  outer lo \"O\" + \"o\" pettu",
        "  padham ra[n]",
        "  ra[0] lo outer + outer pettu",
        "  int i", "  i lo 0 pettu",
        "  i < 10 unnanta varaku {",
        "    padham s", "    s lo ra[0] + \"s\" pettu",
        "    int a[n]", "    padham t[2]", "    t[1] lo s + s pettu",
        "    i lo i + 1 pettu",
        "    i == 2 ayite {",
        "      padham u",
        "      u lo t[1] + \"u\" pettu",
        "      mode == 1 ayite { saagu }",
        "      mode == 2 ayite { aapu }",
        "      mode == 3 ayite { u + s + outer ivvu }",
        "      mode == 4 ayite { s ivvu }",
        "      mode == 5 ayite { ra[0] ivvu }",
        "      mode == 6 ayite { t[1] + (padham) 'x' ivvu }",
        "    }",
        "  }",
        "  padham tail",
        "  tail lo outer + ra[0] pettu",
        "  tail ivvu",
        "}",
        "prati m 0 nundi 7 varaku { f(3, m) ni chupi }",
    )
    check_ref(src, level)


@pytest.mark.parametrize("level", LEVELS)
def test_break_and_continue_in_for_loop_with_declared_string(level):
    src = prog(
        "padham last", "last lo \"\" pettu",
        "pratisari (padham s lo \"a\" pettu; podavu(s) < 20; s lo s + s pettu) {",
        "  padham inner", "  inner lo s + \"!\" pettu",
        "  podavu(s) == 2 ayite { saagu }",
        "  podavu(s) == 8 ayite { last lo inner pettu aapu }",
        "}",
        "last ni chupi",
        "pratisari (padham s lo \"b\" pettu; podavu(s) < 5; s lo s + \"b\" pettu) { s ni chupi }",
    )
    check_ref(src, level, expect="aaaaaaaa!\nb\nbb\nbbb\nbbbb\n")


@pytest.mark.parametrize("level", LEVELS)
def test_recursion_returning_padham(level):
    src = prog(
        "padham rep charya (padham s, int n) {",
        "  n == 0 ayite { \"\" ivvu }",
        "  padham rest",
        "  rest lo rep(s, n - 1) pettu",
        "  s + rest ivvu",
        "}",
        "padham rev charya (padham s) {",
        "  podavu(s) <= 1 ayite { s ivvu }",
        "  padham head", "  head lo (padham) s[0] pettu",
        "  padham tail", "  tail lo \"\" pettu",
        "  prati i 1 nundi podavu(s) varaku { tail lo tail + (padham) s[i] pettu }",
        "  rev(tail) + head ivvu",
        "}",
        "padham fib charya (int n) {",
        "  n < 2 ayite { \"x\" ivvu }",
        "  fib(n - 1) + fib(n - 2) ivvu",
        "}",
        "podavu(rep(\"ab\", 100)) ni chupi",
        "rev(\"stressed\") ni chupi",
        "podavu(fib(15)) ni chupi",
        "podavu(rev(rep(\"xyz\", 200))) ni chupi",
    )
    check_ref(src, level, expect="200\ndesserts\n987\n600\n")


@pytest.mark.parametrize("level", LEVELS)
def test_passing_strings_and_arrays_to_functions(level):
    src = prog(
        "padham gs", "padham ga[2]",
        "padham ident charya (padham a) { a ivvu }",
        "padham twice charya (padham a) { a + a ivvu }",
        "padham reassign charya (padham a) { a lo a + \"?\" pettu  a lo a + a pettu  a ivvu }",
        "padham clobber charya (padham a) {",   # callee overwrites the global its argument came from
        "  gs lo \"new\" pettu", "  ga[1] lo \"NEW\" pettu", "  a ivvu",
        "}",
        "void fill charya (padham a[], int n) { prati i 0 nundi n varaku { a[i] lo (padham) 'q' + a[i] pettu } }",
        "int total charya (padham a[], int n) {",
        "  int s", "  s lo 0 pettu",
        "  prati i 0 nundi n varaku { s lo s + podavu(a[i]) pettu }",
        "  s ivvu",
        "}",
        "gs lo \"o\" + \"ld\" pettu", "ga[1] lo \"O\" + \"LD\" pettu",
        "ident(gs) ni chupi", "twice(ident(twice(gs))) ni chupi", "reassign(gs) ni chupi",
        "clobber(gs) ni chupi", "gs ni chupi",
        "ga[1] lo \"O\" + \"LD\" pettu", "clobber(ga[1]) ni chupi", "ga[1] ni chupi",
        "ident(gs + \"1\") ni chupi", "twice(\"lit\") ni chupi", "ident(\"\") ni chupi",
        "int n", "n lo 5 pettu",
        "padham v[n]", "fill(v, n)", "fill(v, n)", "total(v, n) ni chupi",
        "padham m[3][n]", "fill(m[1], n)", "total(m[1], n) ni chupi", "total(m[2], n) ni chupi",
        "prati k 0 nundi 3 varaku { padham loc[4]  fill(loc, 4)  total(loc, 4) ni chupi }",
        "ident(ident(ident(\"deep\"))) ni chupi",
    )
    check_ref(src, level)


@pytest.mark.parametrize("level", LEVELS)
def test_string_input_discarded_results_and_comparisons(level):
    src = prog(
        "padham mk charya (padham a) { a + \"!\" ivvu }",
        "padham g", "padham arr[2]",
        "int n", "n lo 0 pettu",
        "prati i 0 nundi 3 varaku { padham line  line ni chaduvu  arr[i % 2] ni chaduvu  g ni chaduvu",
        "  line lo line + arr[i % 2] + g pettu",
        "  line ni chupi }",
        "mk(\"discarded\")", "mk(g)",
        "mk(\"a\") == \"a!\" ayite { \"eq\" ni chupi }",
        "mk(\"a\") != mk(\"a\") ayite { \"bad\" ni chupi } lekunte { \"same\" ni chupi }",
        "g + \"x\" == arr[0] + \"x\" ayite { \"cmp\" ni chupi } lekunte { \"differ\" ni chupi }",
        "padham z", "z lo mk(\"zz\") pettu", "(padham) z[1] ni chupi",
        "(char) \"c\" ni chupi", "(char) (mk(\"\") + \"\") == '!' ayite { \"bang\" ni chupi }",
        "podavu(mk(\"abc\")) + podavu(\"de\" + g) ni chupi",
    )
    stdin = b"l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\nl9\n"
    check_ref(src, level, stdin=stdin)
