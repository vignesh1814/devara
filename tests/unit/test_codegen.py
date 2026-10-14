"""Phase 6: x86-64 code generation and the C runtime (native execution)."""

import glob
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from compiler import driver
from compiler.codegen.target import host_target
from tests.helpers.native import asm_of, build_and_run
from tests.helpers.pipeline import run_ir

ROOT = Path(__file__).parent.parent.parent
pytestmark = pytest.mark.slow


def agree(src, stdin=b"", expect=None, status=0):
    outs = {}
    for level in (0, 1):
        outs[("native", level)] = build_and_run(src, stdin, level)
        outs[("interp", level)] = run_ir(src, stdin, level)
    vals = set((o, s) for (o, s, _e) in outs.values())
    assert len(vals) == 1, outs
    o, s, _ = outs[("native", 1)]
    assert s == status, outs
    if expect is not None:
        assert o.decode("latin-1") == expect
    return o


def test_assembly_is_intel_syntax_and_has_entry_and_main():
    a = asm_of("1 ni chupi", 1)
    assert a.startswith("    .intel_syntax noprefix")
    assert "main:" in a and "call dv_entry" in a and ".globl dv_entry" in a
    assert ('GNU-stack' in a) == host_target().elf   # the non-executable-stack note exists on ELF targets only


def test_generated_assembly_assembles_with_gcc_dash_c(tmp_path):
    a = asm_of("int f charya(int x) { x * 2 ivvu }\nf(21) ni chupi", 1)
    s = tmp_path / "a.s"
    s.write_text(a)
    r = subprocess.run(["gcc", "-c", str(s), "-o", str(tmp_path / "a.o")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_many_integer_arguments_use_stack_slots():
    src = """
int f charya(int a, int b, int c, int d, int e, int f, int g, int h, int i) {
  a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 + h * 8 + i * 9 ivvu }
f(1, 2, 3, 4, 5, 6, 7, 8, 9) ni chupi
"""
    agree(src, expect="285\n")


def test_odd_and_even_stack_argument_counts_keep_alignment():
    src = """
int s8 charya(int a, int b, int c, int d, int e, int f, int g, int h) { a + b + c + d + e + f + g + h ivvu }
int s7 charya(int a, int b, int c, int d, int e, int f, int g) { a + b + c + d + e + f + g ivvu }
s8(1, 2, 3, 4, 5, 6, 7, 8) ni chupi
s7(1, 2, 3, 4, 5, 6, 7) ni chupi
"""
    agree(src, expect="36\n28\n")


def test_many_float_arguments_and_mixed_classes():
    src = """
float f charya(float a, float b, float c, float d, float e, float f, float g, float h, float i, float j) {
  a + b + c + d + e + f + g + h + i * 10.0 + j * 100.0 ivvu }
f(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0) ni chupi
float mix charya(int a, float b, int c, float d, padham s, char ch, bool t) {
  (float) a + b + (float) c + d + (float) podavu(s) + (float) ch + (float) t ivvu }
mix(1, 0.5, 2, 0.25, "abcd", 'A', nijam) ni chupi
"""
    agree(src, expect="1126\n73.75\n")


def test_float_return_and_recursion_depth():
    src = """
float half charya(float x) { x / 2.0 ivvu }
half(half(10.0)) ni chupi
int depth charya(int n) { n == 0 ayite { 0 ivvu } 1 + depth(n - 1) ivvu }
depth(20000) ni chupi
"""
    agree(src, expect="2.5\n20000\n")


def test_large_constant_and_dynamic_arrays_use_heap_and_frame_arrays_rezero():
    src = """
int big[200000]
big[199999] lo 7 pettu
big[0] ni chupi
big[199999] ni chupi
int f charya() { int local[100000]\nlocal[99999] lo 3 pettu\nlocal[99999] ivvu }
f() ni chupi
int g charya() { int a[4]\nint s\ns lo a[0] + a[1] + a[2] + a[3] pettu\na[0] lo 5 pettu\na[1] lo 6 pettu s ivvu }
g() ni chupi
g() ni chupi
int n\nn lo 1000\nfloat d[n * 10]\nd[9999] lo 1.5 pettu
d[9999] ni chupi
"""
    src = src.replace("n lo 1000\n", "n lo 1000 pettu\n")
    agree(src, expect="0\n7\n3\n0\n0\n1.5\n")


def test_string_runtime_functions_natively():
    src = """
padham a\npadham b
a lo "foo" pettu\nb lo a + "bar" + (padham) '!' pettu
b ni chupi
podavu(b) ni chupi
b == "foobar!" ni chupi
b[3] ni chupi
a == "fo" + "o" ni chupi
padham e
e == "" ni chupi
(e + e) == e ni chupi
podavu("a\\x00b") ni chupi
"""
    agree(src, expect="foobar!\n7\nnijam\nb\nnijam\nnijam\nnijam\n3\n")


def test_embedded_nul_and_high_bytes_in_strings():
    src = '"a\\x00b" ni chupi\n"\\xE9" ni chupi\npodavu("\\xFF\\xFE") ni chupi\n\'\\xFF\' ni chupi\n(int) \'\\xFF\' ni chupi'
    o = agree(src)
    assert o == b"a\x00b\n\xe9\n2\n\xff\n-1\n"


def test_runtime_error_messages_and_exit_status_natively():
    for src, msg in [
        ("int z\nz lo 0 pettu\n1 / z ni chupi", "division by zero"),
        ("int z\nz lo 0 pettu\n1 % z ni chupi", "remainder by zero"),
        ("int m\nm lo -9223372036854775807 - 1 pettu\nint k\nk lo -1 pettu\nm / k ni chupi", "integer overflow in division"),
        ('padham s\ns lo "a" pettu\ns[5] ni chupi', "string index out of range"),
        ('(char) "ab" ni chupi', "invalid char conversion"),
        ("int n\nn lo -1 pettu\nint a[n]", "invalid array size"),
        ("int x\nx ni chaduvu", "invalid input"),
    ]:
        o, st, err = build_and_run(src, b"", 1)
        assert st == 1 and err == f"devara: runtime error: {msg}", (src, st, err)


def test_stdout_is_flushed_before_runtime_error_natively():
    o, st, err = build_and_run('"before" ni chupi\n1 / 0 ni chupi', b"", 1)
    assert o == b"before\n" and st == 1


def test_min_int_remainder_by_minus_one_is_zero_not_a_crash():
    src = "int m\nm lo -9223372036854775807 - 1 pettu\nint k\nk lo -1 pettu\nm % k ni chupi\n(m + 1) % k ni chupi\nm / 1 ni chupi"
    agree(src, expect="0\n0\n-9223372036854775808\n")


def test_float_special_values_output_matches_c_printf():
    src = """
float z\nz lo 0.0 pettu
1.0 / z ni chupi\n-1.0 / z ni chupi\nz / z ni chupi\n-(z / z) ni chupi\nz * -1.0 ni chupi
(int) (z / z) ni chupi\n(int) (1.0 / z) ni chupi\n(bool) (z / z) ni chupi\n(bool) z ni chupi
0.0 == z / z ni chupi\n(z / z) != (z / z) ni chupi\n(z / z) < 1.0 ni chupi
123456789.0 ni chupi\n0.000012345 ni chupi\n1e300 * 1e300 ni chupi
"""
    src = src.replace("1e300 * 1e300", "100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0 * 100000000.0")
    o, st, err = build_and_run(src, b"", 1)
    assert st == 0, err
    lines = [re.sub(r"-?nan", "nan", ln) for ln in o.decode().split("\n")]   # NaN sign is platform printf (Q-004)
    assert lines[:5] == ["inf", "-inf", "nan", "nan", "-0"]
    assert lines[5:9] == ["-9223372036854775808", "-9223372036854775808", "nijam", "abaddham"]
    assert lines[9:12] == ["abaddham", "nijam", "abaddham"]
    assert lines[12:14] == ["1.23457e+08", "1.2345e-05"]
    assert build_and_run(src, b"", 0) == build_and_run(src, b"", 1)


def test_input_edge_cases_natively():
    src = "int a\npadham s\npadham t\na ni chaduvu\ns ni chaduvu\nt ni chaduvu\na ni chupi\ns ni chupi\nt ni chupi"
    agree(src, b"5   \nhello\nworld", expect="5\nhello\nworld\n")
    agree(src, b"5 tail\nsecond\n", expect="5\n tail\nsecond\n")
    agree("padham s\npadham t\ns ni chaduvu\nt ni chaduvu\ns ni chupi\nt ni chupi", b"x y\n\nz", expect="x y\n\n")


def test_every_valid_bundled_program_assembles_and_links_at_o0_and_o1():
    files = sorted(glob.glob(str(ROOT / "tests/programs/**/*.tel"), recursive=True)
                   + glob.glob(str(ROOT / "examples/*.tel")))
    skipped = {"17_bfs_mock.tel", "18_n_queens.tel"}
    n = 0
    for f in files:
        if Path(f).name in skipped:
            continue
        src = Path(f).read_bytes().decode("latin-1")
        for level in (0, 1):
            asm = asm_of(src, level)
            with tempfile.TemporaryDirectory() as tmp:
                driver.link_executable(asm, Path(tmp) / "x")
        n += 1
    assert n >= 20
