"""Audit F8: bool and char array elements are one byte (they were eight). Every storage class and access
path of such arrays is compared with the reference interpreter at -O0 and -O1, and the memory saving is
checked with an address-space cap."""


import pytest

from tests.helpers.native import asm_of, build_and_run, built, execute
from tests.helpers.ref import ref_run

LEVELS = [0, 1]

# Each program fills arrays with a position-dependent pattern and reads *every* element back, so a
# write that spills into a neighbouring byte, a wrong sign/zero extension or a wrong stride shows up.
FILL = """
{decl}
prati i 0 nundi {n} varaku {{ a[i] lo {expr} pettu }}
int sum
prati i 0 nundi {n} varaku {{ sum lo sum * 31 + (int) a[i] pettu }}
sum ni chupi
a[0] ni chupi
a[{last}] ni chupi
a[{mid}] ni chupi
"""

CASES = {
    # (declaration, element count, value expression)
    "char_global_const": ("char a[37]", 37, "(char) (i * 7 - 90)"),
    "bool_global_const": ("bool a[37]", 37, "(i * 5) % 3 == 1"),
    "char_global_runtime": ("int n\nn lo 41 pettu\nchar a[n]", 41, "(char) (i * 11 + 100)"),
    "bool_global_runtime": ("int n\nn lo 41 pettu\nbool a[n]", 41, "i % 4 > 1"),
    "char_negative_values": ("char a[256]", 256, "(char) i"),
    "char_large_heap_local": ("void f charya () {\n char a[70000]\n prati i 0 nundi 70000 varaku { a[i] lo (char) (i * 3) pettu }\n"
                              " int s\n s lo 0 pettu\n prati i 0 nundi 70000 varaku { s lo s + (int) a[i] pettu }\n s ni chupi\n}\nf()\n"
                              "char a[1]", 1, "'q'"),
}


def program(name):
    decl, n, expr = CASES[name]
    if name == "char_large_heap_local":
        return decl
    return FILL.format(decl=decl, n=n, expr=expr, last=n - 1, mid=n // 2)


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("name", list(CASES))
def test_f8_byte_arrays_match_the_reference(name, level):
    src = program(name)
    ref = ref_run(src)
    assert ref.status == 0
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (ref.stdout, 0), err


LOCAL_SMALL = """
void f charya () {
    char a[3]
    char b[5]
    bool c[7]
    int x
    int y
    float z
    x lo 1111 pettu
    y lo 2222 pettu
    z lo 3.5 pettu
    a[0] lo 'a' pettu  a[1] lo 'b' pettu  a[2] lo 'c' pettu
    prati i 0 nundi 5 varaku { b[i] lo (char) (100 + i) pettu }
    prati i 0 nundi 7 varaku { c[i] lo i % 2 == 0 pettu }
    a[0] ni chupi  a[1] ni chupi  a[2] ni chupi
    prati i 0 nundi 5 varaku { b[i] ni chupi }
    prati i 0 nundi 7 varaku { c[i] ni chupi }
    x ni chupi  y ni chupi  z ni chupi
}
f()
"""

PARAMS = """
int sumc charya (char v[], int n) {
    int s
    s lo 0 pettu
    prati i 0 nundi n varaku { s lo s + (int) v[i] pettu }
    s ivvu
}
int countb charya (bool v[], int n) {
    int s
    s lo 0 pettu
    prati i 0 nundi n varaku { v[i] ayite { s lo s + 1 pettu } }
    s ivvu
}
void setc charya (char v[], int i, char x) { v[i] lo x pettu }
void setb charya (bool v[], int i, bool x) { v[i] lo x pettu }
char m[4][6]
bool g[3][5]
int r
r lo 3 pettu
bool h[r][r + 2]
prati i 0 nundi 4 varaku { prati j 0 nundi 6 varaku { m[i][j] lo (char) (i * 10 - j * 3) pettu } }
prati i 0 nundi 3 varaku { prati j 0 nundi 5 varaku { g[i][j] lo (i + j) % 2 == 0 pettu } }
prati i 0 nundi r varaku { prati j 0 nundi r + 2 varaku { h[i][j] lo j > i pettu } }
sumc(m[2], 6) ni chupi
sumc(m[0], 6) ni chupi
countb(g[1], 5) ni chupi
countb(h[0], r + 2) ni chupi
setc(m[3], 5, 'Z')
setb(g[2], 4, nijam)
setb(h[2], 0, nijam)
m[3][5] ni chupi
m[3][4] ni chupi
g[2][4] ni chupi
h[2][0] ni chupi
h[2][1] ni chupi
sumc(m[3], 6) ni chupi
"""


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("src", [LOCAL_SMALL, PARAMS], ids=["frame_neighbours", "params_2d_partial"])
def test_f8_frame_arrays_and_array_parameters_match_the_reference(src, level):
    ref = ref_run(src)
    assert ref.status == 0
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (ref.stdout, 0), err


@pytest.mark.parametrize("level", LEVELS)
def test_f8_bool_and_char_use_byte_accesses_and_ints_still_use_eight(level):
    src = "bool b[16]\nchar c[16]\nint i[16]\nb[3] lo nijam pettu\nc[3] lo 'x' pettu\ni[3] lo 9 pettu\nb[3] ni chupi\nc[3] ni chupi\ni[3] ni chupi\n"
    text = asm_of(src, level=level)
    assert "BYTE PTR" in text
    assert text.count("BYTE PTR") == 4                      # one store and one load for each of b and c
    assert "movzx" in text and "movsx" in text               # bool zero-extends, char sign-extends
    assert ".zero 16\n" in text and ".zero 128\n" in text    # 16-byte bool and char arrays, 128-byte int array


@pytest.mark.parametrize("level", LEVELS)
def test_f8_a_hundred_million_bools_fit_in_a_small_address_space(level):
    # 100 MB of bool elements; with 8-byte elements this needs 800 MB and fails under the 400 MB cap
    src = ("int n\nn lo 100000000 pettu\nbool a[n]\na[n - 1] lo nijam pettu\na[0] lo nijam pettu\n"
           "int c\nprati i 0 nundi n varaku { a[i] ayite { c lo c + 1 pettu } }\nc ni chupi\n")
    with built(src, level) as exe:
        p = execute(exe, b"", timeout=120, max_vmem_mb=400)
    assert (p.stdout, p.returncode) == (b"2\n", 0), p.stderr[-300:]
