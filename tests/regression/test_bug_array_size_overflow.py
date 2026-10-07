"""Audit F1/F2: the element count of a multi-dimensional array must not wrap (heap corruption with
exit 0), and constant arrays too large to represent or to place statically must not reach the assembler."""

import pytest

from compiler.diagnostics import SemCategory as S
from tests.helpers.native import build_and_run
from tests.unit.test_semantic import reject

OPTS = [0, 1]


@pytest.mark.parametrize("level", OPTS)
@pytest.mark.parametrize("n", ["4611686018427387905", "2305843009213693953", "9223372036854775807"])
def test_f1_runtime_dimension_product_overflow_is_a_runtime_error(n, level):
    src = f"int n\nn lo {n} pettu\nint a[n][4]\n\"allocated\" ni chupi\na[1][0] lo 7 pettu\na[1][0] ni chupi\n"
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (b"", 1)
    assert err.strip() == "devara: runtime error: invalid array size"


@pytest.mark.parametrize("level", OPTS)
def test_f1_three_dimensions_and_local_scope(level):
    src = ("void f charya (int n) {\n  int a[n][n][3]\n  \"in f\" ni chupi\n}\n"
           "int k\nk lo 3037000500 pettu\n\"before\" ni chupi\nf(k)\n\"after\" ni chupi\n")
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (b"before\n", 1)
    assert err.strip() == "devara: runtime error: invalid array size"


@pytest.mark.parametrize("level", OPTS)
def test_f1_representable_sizes_still_work(level):
    src = "int n\nn lo 300 pettu\nint a[n][n]\na[299][299] lo 5 pettu\na[299][299] ni chupi\n"
    assert build_and_run(src, level=level)[:2] == (b"5\n", 0)


@pytest.mark.parametrize("dims", ["[4611686018427387905][4]", "[2000000000][2000000000]", "[3037000500][3037000500]"])
def test_f2_constant_array_too_large_is_a_semantic_error(dims):
    reject(f"int a{dims}\n", S.INVALID_ARRAY_SIZE)
    reject(f"void f charya () {{ int a{dims} }}\n", S.INVALID_ARRAY_SIZE)


@pytest.mark.parametrize("level", OPTS)
def test_f2_huge_global_array_is_not_an_internal_error(level):
    # 800 GB: used to be a linker "relocation truncated" internal compiler error
    out, rc, err = build_and_run("int a[100000000000]\n\"start\" ni chupi\na[5] ni chupi\n", level=level)
    assert rc == 1 and err.strip() == "devara: runtime error: invalid array size"


@pytest.mark.parametrize("level", OPTS)
def test_f2_large_global_array_over_the_static_limit_works(level):
    # 2.4 GB zero-filled lazily by the OS: heap path instead of .bss
    src = "int a[300000000]\na[299999999] lo 9 pettu\na[299999999] ni chupi\na[0] ni chupi\n"
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (b"9\n0\n", 0), err
