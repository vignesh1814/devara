"""Leak accounting (plan P22): heap arrays are freed at scope exit, padham values are reference
counted. Every program runs natively at -O0 and -O1 with DEVARA_RT_STATS=1 and must report
``live=0`` at normal exit (the runtime counts live heap arrays + live strings)."""

import pytest

from tests.helpers import native

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
