"""Register allocator / -O1 code generator: targeted stress programs, each run at -O0 (reference
stack-slot code) and -O1 (register allocation) with identical expected output."""

import pytest

from tests.helpers.native import asm_of, build_and_run

N_LOCALS = 24


def _pressure_program() -> tuple[str, str]:
    decls = "\n".join(f"    int v{i}\n    v{i} lo n + {i} pettu" for i in range(N_LOCALS))
    total = " + ".join(f"v{i} * {i + 1}" for i in range(N_LOCALS))
    src = (
        "int id charya (int x) { x ivvu }\n"
        "int f charya (int n) {\n" + decls + "\n"
        "    int mid\n    mid lo id(n) pettu\n"           # a call with every local live across it
        "    mid + " + total + " ivvu\n}\n"
        "f(3) ni chupi\nf(-7) ni chupi\n"
    )
    exp = []
    for n in (3, -7):
        exp.append(n + sum((n + i) * (i + 1) for i in range(N_LOCALS)))
    return src, "".join(f"{v}\n" for v in exp)


PROGRAMS = {
    "argument_cycles": (
        "int g charya (int a, int b, int c) { a * 100 + b * 10 + c ivvu }\n"
        "int f charya (int a, int b, int c) { g(b, c, a) + g(c, a, b) * 1000 ivvu }\n"
        "f(1, 2, 3) ni chupi\n",
        f"{231 + 312 * 1000}\n",
    ),
    "many_mixed_params": (
        "float mix charya (int a, float b, int c, float d, int e, float f, int g, float h, bool i) {\n"
        "    float r\n"
        "    r lo a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 + h * 8 pettu\n"
        "    i ayite { r lo r + 1000 pettu }\n    r ivvu\n}\n"
        "mix(1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5, nijam) ni chupi\n"
        "mix(1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5, abaddham) ni chupi\n",
        "1214\n214\n",
    ),
    "floats_across_calls": (
        "float half charya (float x) { x / 2 ivvu }\n"
        "float f charya (int n) {\n"
        "    float a\n    float b\n    float c\n    a lo 1.5 pettu\n    b lo 2.25 pettu\n    c lo 0.0 pettu\n"
        "    prati i 0 nundi n varaku {\n"
        "        c lo c + half(a) + half(b) * i pettu\n        a lo a + 1 pettu\n        b lo b - 0.5 pettu\n    }\n"
        "    a + b + c ivvu\n}\n"
        "f(10) ni chupi\n",
        None,
    ),
    "pow2_division": (
        "int d charya (int x) { x / 8 ivvu }\nint m charya (int x) { x % 8 ivvu }\n"
        "int d2 charya (int x) { x / 2 ivvu }\nint m2 charya (int x) { x % 2 ivvu }\n"
        "int d1 charya (int x) { x / 1 ivvu }\nint m1 charya (int x) { x % 1 ivvu }\n"
        "int dn charya (int x) { x / (0 - 4) ivvu }\n"
        "int mn charya (int x) { x % (0 - 4) ivvu }\n"
        "int big charya () { 0 - 9223372036854775807 - 1 ivvu }\n"
        "prati x -17 nundi 18 varaku { d(x) ni chupi  m(x) ni chupi  d2(x) ni chupi  m2(x) ni chupi\n"
        "    d1(x) ni chupi  m1(x) ni chupi  dn(x) ni chupi  mn(x) ni chupi }\n"
        "d(big()) ni chupi\nm(big()) ni chupi\nd2(big()) ni chupi\nm2(big()) ni chupi\n"
        "d(9223372036854775807) ni chupi\nm(9223372036854775807) ni chupi\n",
        None,
    ),
    "branchy_compares": (
        "int cls charya (int a, int b, float x, float y) {\n"
        "    int r\n    r lo 0 pettu\n"
        "    a < b ayite { r lo r + 1 pettu }\n    a <= b ayite { r lo r + 2 pettu }\n"
        "    a == b ayite { r lo r + 4 pettu }\n    a != b ayite { r lo r + 8 pettu }\n"
        "    x < y ayite { r lo r + 16 pettu }\n    x <= y ayite { r lo r + 32 pettu }\n"
        "    x == y ayite { r lo r + 64 pettu }\n    x != y ayite { r lo r + 128 pettu }\n"
        "    x > y ayite { r lo r + 256 pettu }\n    x >= y ayite { r lo r + 512 pettu }\n"
        "    r ivvu\n}\n"
        "float nan charya () { float z\n z lo 0.0 pettu\n 0.0 / z ivvu }\n"
        "cls(1, 2, 1.5, 2.5) ni chupi\ncls(2, 2, 2.5, 2.5) ni chupi\ncls(3, 2, 3.5, 2.5) ni chupi\n"
        "cls(1, 1, nan(), 1.0) ni chupi\ncls(1, 1, 1.0, nan()) ni chupi\ncls(1, 1, nan(), nan()) ni chupi\n",
        None,
    ),
    "loops_with_arrays": (
        "int f charya (int n) {\n"
        "    int a[100]\n    int s\n    s lo 0 pettu\n"
        "    prati i 0 nundi 100 varaku { a[i] lo i * n pettu }\n"
        "    prati i 1 nundi 100 varaku { a[i] lo a[i] + a[i - 1] pettu  s lo s + a[i] % 7 pettu }\n"
        "    s + a[99] ivvu\n}\n"
        "f(3) ni chupi\nf(-5) ni chupi\n",
        None,
    ),
    "register_pressure_over_call": _pressure_program(),
}


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_o1_matches_o0(name):
    src, expected = PROGRAMS[name]
    o0 = build_and_run(src, level=0)
    o1 = build_and_run(src, level=1)
    assert o0[1] == 0, o0
    assert o1 == o0, (o0, o1)
    if expected is not None:
        assert o1[0].decode() == expected


def test_o1_uses_registers_not_stack_slots():
    src = ("int f charya (int n) {\n    int s\n    s lo 0 pettu\n"
           "    prati i 0 nundi n varaku { s lo s + i * i pettu }\n    s ivvu\n}\nf(10) ni chupi\n")
    o0, o1 = asm_of(src, 0), asm_of(src, 1)
    body = o1[o1.index("dv_f_f:"):o1.index("dv_entry:")]
    assert o0.count("[rbp") > 20
    assert body.count("[rbp") <= 4          # no stack-slot traffic (at most callee-saved save/restore)
    assert len(o1.splitlines()) < len(o0.splitlines())


def test_callee_saved_registers_are_preserved_for_callers():
    """A value kept in a callee-saved register across calls to functions that also use them."""
    src = (
        "int inner charya (int a, int b) {\n"
        "    int x\n    int y\n    int z\n    x lo a * 3 pettu\n    y lo b * 5 pettu\n    z lo x + y pettu\n"
        "    z + inner2(x, y) ivvu\n}\n"
        "int inner2 charya (int a, int b) { a - b ivvu }\n"
        "int outer charya (int n) {\n"
        "    int keep1\n    int keep2\n    int keep3\n    keep1 lo n + 1 pettu\n    keep2 lo n + 2 pettu\n"
        "    keep3 lo n + 3 pettu\n"
        "    int r\n    r lo inner(keep1, keep2) + inner(keep2, keep3) pettu\n"
        "    r + keep1 * 100 + keep2 * 10 + keep3 ivvu\n}\n"
        "outer(4) ni chupi\nouter(-9) ni chupi\n"
    )
    assert build_and_run(src, level=1) == build_and_run(src, level=0)
