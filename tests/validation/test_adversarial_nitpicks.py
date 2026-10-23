"""Adversarial / nitpicking probes with hand-verified expected results.

Every expectation below was derived from the spec and implementation plan (rulings cited per group) or from
plain 64-bit arithmetic -- NOT copied from the compiler's own output -- and each program runs at -O0 and -O1
through the real CLI. Programs that must be rejected assert the diagnostic category.
"""
from __future__ import annotations

import re

import pytest

from tests.validation.stress_util import run

MIN = "-9223372036854775807 - 1"


def lines(*xs) -> bytes:
    return ("".join(f"{x}\n" for x in xs)).encode()


# (id, source, stdin, expected stdout, expected rc, expected stderr regex)
RUNS = [
    # -- integer edge cases (P27/P28, L38) --
    ("max+1 wraps", "int x\nx lo 9223372036854775807 pettu\nx + 1 ni chupi\n", b"", lines(-2**63), 0, None),
    ("min*-1 wraps", f"int x\nx lo {MIN} pettu\nx * -1 ni chupi\n", b"", lines(-2**63), 0, None),
    ("min/-1 traps", f"int x\nint y\nx lo {MIN} pettu\ny lo -1 pettu\nx / y ni chupi\n", b"", b"", 1, r"integer overflow in division"),
    ("min%-1 is 0", f"int x\nint y\nx lo {MIN} pettu\ny lo -1 pettu\nx % y ni chupi\n", b"", lines(0), 0, None),
    ("div/mod signs", "int a\na lo -7 pettu\na / 2 ni chupi\na % 2 ni chupi\n7 % -2 ni chupi\n-7 / -2 ni chupi\n",
     b"", lines(-3, -1, 1, 3), 0, None),
    ("div by zero", "int z\n5 / z ni chupi\n", b"", b"", 1, r"division by zero"),
    ("mod by zero", "int z\n5 % z ni chupi\n", b"", b"", 1, r"remainder by zero"),
    # -- floats (P3, Q-004, 12.4) --
    ("ieee div", "float z\n1.0 / z ni chupi\n-1.0 / z ni chupi\n", b"", lines("inf", "-inf"), 0, None),
    ("negative zero", "float z\n(0.0 - z) ni chupi\n(-z) ni chupi\n", b"", lines("0", "-0"), 0, None),
    ("-0 == 0, 1/-0", "float z\n(-z == z) ni chupi\n(1.0 / -z) ni chupi\n", b"", lines("nijam", "-inf"), 0, None),
    ("%g six digits", "123456789.123 ni chupi\n100000000.0 ni chupi\n0.1 + 0.2 ni chupi\n3.0 ni chupi\n0.000123 ni chupi\n",
     b"", lines("1.23457e+08", "1e+08", 0.3, 3, 0.000123), 0, None),
    ("nan compares", "float z\nfloat n\nn lo z / z pettu\n(n == n) ni chupi\n(n != n) ni chupi\n(n < 1.0) ni chupi\n(n >= 1.0) ni chupi\n",
     b"", lines("abaddham", "nijam", "abaddham", "abaddham"), 0, None),
    ("float->int cast", "(int) 2.9999 ni chupi\n(int) -2.9999 ni chupi\n(int) -0.5 ni chupi\n", b"", lines(2, -2, 0), 0, None),
    ("float->int out of range", "float z\n(int)(z / z) ni chupi\n", b"", lines(-2**63), 0, None),
    ("int->float rounds", "(9007199254740993 == 9007199254740992.0) ni chupi\n", b"", lines("nijam"), 0, None),
    # -- char / bool conversions (P27, Q-005) --
    ("char narrowing", "(char) 300 ni chupi\n(int)(char) 300 ni chupi\n(int)(char) -1 ni chupi\n", b"", b",\n44\n-1\n", 0, None),
    ("bool conversions", "(int) nijam ni chupi\n(bool) 5 ni chupi\n(bool) 0.0 ni chupi\nnijam + 1 ni chupi\n",
     b"", lines(1, "nijam", "abaddham", 2), 0, None),
    ("narrowing assignment", "int i\ni lo 3.99 pettu\ni ni chupi\nbool b\nb lo 0.5 pettu\nb ni chupi\n", b"", lines(3, "nijam"), 0, None),
    ("byte-sized elements", "char c[2]\nc[0] lo 300 pettu\n(int) c[0] ni chupi\nbool b[1]\nb[0] lo 5 pettu\n(int) b[0] ni chupi\n",
     b"", lines(44, 1), 0, None),
    # -- strings (P6, P7, P9) --
    ("string length counts bytes", '"h\xc3\xa9llo" ni chupi\npodavu("h\xc3\xa9llo") ni chupi\n', b"", "h\xc3\xa9llo\n6\n".encode("latin-1"), 0, None),
    ("embedded NUL", 'padham s\ns lo "a\\0b" pettu\npodavu(s) ni chupi\n', b"", lines(3), 0, None),
    ("string index oob", 'padham s\ns lo "abc" pettu\ns[3] ni chupi\n', b"", b"", 1, r"string index out of range"),
    ("string negative index", 'padham s\nint i\ni lo -1 pettu\ns lo "abc" pettu\ns[i] ni chupi\n', b"", b"", 1, r"string index out of range"),
    ("string concat aliasing", 'padham s\ns lo "ab" pettu\ns lo s + s pettu\ns lo s + s pettu\ns ni chupi\n', b"", lines("abababab"), 0, None),
    ("empty string cast to char", '(char) "" ni chupi\n', b"", b"", 1, r"invalid char conversion"),
    # -- control flow (Q-007, P24) --
    ("range reversed/equal", "int i\nprati i 5 nundi 1 varaku { i ni chupi }\nprati i 3 nundi 3 varaku { i ni chupi }\n1 ni chupi\n", b"", lines(1), 0, None),
    ("range end evaluated once", "int n\nn lo 3 pettu\nint i\nprati i 0 nundi n varaku { n lo 10 pettu\ni ni chupi }\n", b"", lines(0, 1, 2), 0, None),
    ("range var is scoped; body edits count", "int i\ni lo 99 pettu\nprati i 0 nundi 5 varaku { i lo i + 2 pettu\ni ni chupi }\ni ni chupi\n",
     b"", lines(2, 5, 99), 0, None),
    ("continue runs the update", "int i\npratisari (i 0 tho modhalu; i < 5; i++) { i == 2 ayite { saagu }\ni ni chupi }\n", b"", lines(0, 1, 3, 4), 0, None),
    ("break leaves inner loop only", "int i\nint j\npratisari (i 0 tho modhalu; i < 3; i++) { pratisari (j 0 tho modhalu; j < 3; j++) { j == 1 ayite { aapu }\n(i * 10 + j) ni chupi } }\n",
     b"", lines(0, 10, 20), 0, None),
    ("else binds to nearest if", "nijam ayite { abaddham ayite { 1 ni chupi } } lekunte { 2 ni chupi }\n", b"", b"", 0, None),
    ("short circuit", "int c\nint f charya() { c lo c + 1 pettu\n1 ivvu }\nabaddham && f() ni chupi\nnijam || f() ni chupi\nc ni chupi\n",
     b"", lines("abaddham", "nijam", 0), 0, None),
    ("argument evaluation order is left to right", "int c\nint f charya() { c lo c + 1 pettu\nc ivvu }\nint g charya(int a, int b) { a * 10 + b ivvu }\ng(f(), f()) ni chupi\n",
     b"", lines(12), 0, None),
    ("deep recursion 50k", "int f charya(int n) { n == 0 ayite { 0 ivvu }\n1 + f(n - 1) ivvu }\nf(50000) ni chupi\n", b"", lines(50000), 0, None),
    ("keywords case-insensitive, idents case-sensitive", "INT X\nint x\nX LO 1 PETTU\nx lo 2 pettu\nX NI CHUPI\nx ni chupi\n", b"", lines(1, 2), 0, None),
    # -- arrays (P21, P22) --
    ("runtime array size 0", "int n\nint a[n]\n1 ni chupi\n", b"", b"", 1, r"invalid array size"),
    ("runtime array size overflow", "int n\nn lo 4611686018427387904 pettu\nint a[n][4]\n1 ni chupi\n", b"", b"", 1, r"invalid array size"),
    ("arrays are zero filled", "float f[2]\nint i[2]\nf[1] + 0.5 ni chupi\ni[1] ni chupi\n", b"", lines(0.5, 0), 0, None),
    ("2d indexing", "int a[2][3]\na[1][2] lo 7 pettu\na[1][2] ni chupi\na[0][0] ni chupi\n", b"", lines(7, 0), 0, None),
    # -- input (P7, P9) --
    ("int input whitespace", "int x\nx ni chaduvu\nx ni chupi\n", b"   \n\t 42  \n", lines(42), 0, None),
    ("int input sign forms", "int x\nint y\nx ni chaduvu\ny ni chaduvu\n(x + y) ni chupi\n", b"+5 -0", lines(5), 0, None),
    ("int input limits", "int x\nint y\nx ni chaduvu\ny ni chaduvu\nx ni chupi\ny ni chupi\n", b"9223372036854775807 -9223372036854775808",
     lines(2**63 - 1, -2**63), 0, None),
    ("float input forms", "float f\nint i\nprati i 0 nundi 4 varaku { f ni chaduvu\nf ni chupi }\n", b"1e3 .5 -2. inf", lines(1000, 0.5, -2, "inf"), 0, None),
    ("char input skips whitespace", "char c\nc ni chaduvu\nc ni chupi\n", b"  \n xyz", lines("x"), 0, None),
    ("line input drops CR", "padham s\ns ni chaduvu\ns ni chupi\npodavu(s) ni chupi\n", b"hello world\r\nnext\n", lines("hello world", 11), 0, None),
    ("token then line skips blank remainder", "int x\npadham s\nx ni chaduvu\ns ni chaduvu\ns ni chupi\n", b"5   \nthe line\n", lines("the line"), 0, None),
    ("token then line keeps rest of line", "int x\npadham s\nx ni chaduvu\ns ni chaduvu\ns ni chupi\n", b"5 rest\nz\n", lines(" rest"), 0, None),
    ("line input without newline", "padham s\ns ni chaduvu\ns ni chupi\n", b"abc", lines("abc"), 0, None),
    ("line input embedded NUL", "padham s\ns ni chaduvu\npodavu(s) ni chupi\n", b"ab\x00cd\n", lines(5), 0, None),
    ("1 MB line", "padham s\ns ni chaduvu\npodavu(s) ni chupi\n", b"a" * 1_000_000 + b"\n", lines(1_000_000), 0, None),
]
for bad, name in [(b"0x10", "hex int"), (b"9223372036854775808", "int overflow"), (b"abc", "junk"), (b"12abc", "trailing junk"),
                  (b"3.7", "float token"), (b"", "EOF")]:
    RUNS.append((f"int input rejects {name}", "int x\nx ni chaduvu\nx ni chupi\n", bad, b"", 1, r"invalid input"))
RUNS.append(("padham input at EOF", "padham s\ns ni chaduvu\n", b"", b"", 1, r"invalid input"))
RUNS.append(("char input at EOF", "char c\nc ni chaduvu\n", b"   ", b"", 1, r"invalid input"))

# (id, source, expected diagnostic category)
REJECTS = [
    ("INT_MIN literal needs the long form (P36)", "-9223372036854775808 ni chupi\n", "LITERAL_OUT_OF_RANGE"),
    ("literal > INT64_MAX", "9223372036854775808 ni chupi\n", "LITERAL_OUT_OF_RANGE"),
    ("constant array size 0", "int a[0]\n", "INVALID_ARRAY_SIZE"),
    ("constant array size folds to 0", "int a[2 * 3 - 6]\n", "INVALID_ARRAY_SIZE"),
    ("negative constant array size", "int a[-1]\n", "INVALID_ARRAY_SIZE"),
    ("too many indices", "int a[3]\na[0][0] ni chupi\n", "TOO_MANY_INDICES"),
    ("array assignment", "int a[2]\nint b[2]\na lo b pettu\n", "INVALID_OPERAND|TYPE_MISMATCH|NOT_ASSIGNABLE"),
    ("array element type mismatch", "void g charya(float a[]) { }\nint a[3]\ng(a)\n", "TYPE_MISMATCH"),
    ("float modulo", "5.5 % 2 ni chupi\n", "INVALID_OPERAND"),
    ("string ordering", 'padham a\npadham b\n(a < b) ni chupi\n', "INVALID_OPERAND"),
    ("string element assignment", 'padham s\ns lo "abc" pettu\ns[0] lo \'z\' pettu\n', "NOT_ASSIGNABLE"),
    ("string used as condition", '"a" ayite { }\n', "INVALID_CONDITION"),
    ("redeclaration", "int x\nint x\n", "REDECLARATION"),
    ("podavu is predeclared (12.2)", "int podavu\n", "REDECLARATION"),
    ("use before declaration", "x ni chupi\nint x\n", "UNDECLARED"),
    ("uninitialized local", "int f charya() { int x\nx ni chupi\n0 ivvu }\nf()\n", "UNINITIALIZED"),
    ("conditionally initialized local", "int f charya(int c) { int x\nc > 0 ayite { x lo 1 pettu }\nx ni chupi\n0 ivvu }\nf(1)\n", "UNINITIALIZED"),
    ("missing return", "int f charya(int a) { a > 0 ayite { 1 ivvu } }\nf(-1) ni chupi\n", "MISSING_RETURN"),
    ("void value used", "void g charya() { }\ng() + 1 ni chupi\n", "VOID_MISUSE"),
    ("wrong arity", "int f charya(int a) { a ivvu }\nf(1, 2) ni chupi\n", "ARGUMENT_COUNT"),
    ("break outside loop", "aapu\n", "BREAK_OUTSIDE_LOOP"),
    ("continue outside loop", "saagu\n", "CONTINUE_OUTSIDE_LOOP"),
    ("return at top level", "5 ivvu\n", "INVALID_RETURN"),
    ("for-loop variable not visible after loop", "pratisari (int i lo 0 pettu; i < 2; i++) { }\ni ni chupi\n", "UNDECLARED"),
    ("multidimensional parameter is unspecified (sec. 6)", "int s charya(int a[][], int n) { a[1][1] ivvu }\n", None),
    ("2D array to 1D parameter", "int s charya(int a[], int n) { a[0] ivvu }\nint m[2][2]\ns(m, 2) ni chupi\n", "TYPE_MISMATCH"),
]


@pytest.mark.parametrize("opt", ["-O0", "-O1"])
@pytest.mark.parametrize("name,src,stdin,out,rc,err_re", RUNS, ids=[r[0] for r in RUNS])
def test_adversarial_run(name, src, stdin, out, rc, err_re, opt):
    p = run(src, opt, stdin)
    assert p.rc == rc, f"rc {p.rc} != {rc}\nstderr: {p.err}"
    if rc == 0:
        assert p.out == out
    else:
        assert p.out == out  # stdout produced before the trap is flushed first (P11)
        assert re.search(r"devara: runtime error: " + err_re, p.err), p.err


@pytest.mark.parametrize("name,src,category", REJECTS, ids=[r[0] for r in REJECTS])
def test_adversarial_rejection(name, src, category):
    p = run(src, "-O1")
    assert p.rc == 1, f"expected a compile error, got rc={p.rc}\n{p.out!r}"
    assert "runtime error" not in p.err, "must be rejected at compile time"
    if category:
        first = p.err.strip().splitlines()[0]
        assert re.search(rf"\[({category})\]", first), first
