"""Audit F10/F11: static-array base addresses are kept in a register instead of being rebuilt with
``lea reg, [rip + sym]`` on every access, and multiplication by a constant reads its source in place."""

import re
import subprocess

import pytest

from tests.helpers.cli import DEVARA_CMD
from tests.helpers.native import build_and_run
from tests.helpers.ref import ref_run


def asm(src, tmp_path, target="linux"):
    f = tmp_path / "t.tel"
    f.write_text(src, newline="\n")
    p = subprocess.run([*DEVARA_CMD, "-O1", "--target", target, "asm", str(f)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def loop_body(text, symbol_hint="rbody"):
    """Instructions from the first loop-body label to the end of that block run."""
    m = re.search(rf"^\.L\d+_{symbol_hint}\d+:\n(.*?)(?=^\.L\d+_rexit)", text, re.S | re.M)
    assert m
    return m.group(1)


FILL = "int a[100]\nprati i 0 nundi 100 varaku { a[i] lo i pettu }\na[5] ni chupi\n"


@pytest.mark.parametrize("target", ["linux", "windows"])
def test_f10_loop_does_not_rebuild_the_array_address(target, tmp_path):
    body = loop_body(asm(FILL, tmp_path, target))
    assert "rip" not in body, body


def test_f10_array_used_once_outside_a_loop_is_not_hoisted(tmp_path):
    text = asm("int a[3]\na[1] lo 5 pettu\n", tmp_path)
    assert text.count("rip + dv_g_a") == 1


def test_f10_function_with_a_loop_over_a_static_array(tmp_path):
    src = ("int a[50]\nint total charya (int n) {\n int s\n s lo 0 pettu\n"
           " prati i 0 nundi n varaku { s lo s + a[i] pettu }\n s ivvu\n}\n"
           "prati i 0 nundi 50 varaku { a[i] lo i pettu }\ntotal(50) ni chupi\n")
    text = asm(src, tmp_path)
    fn = re.search(r"^dv_f_total:\n(.*?)(?=^[^.\s]\S*:\n)", text, re.S | re.M).group(1)
    loop = re.search(r"^\.L\d+_rbody\d+:\n(.*?)(?=^\.L\d+_rexit)", fn, re.S | re.M).group(1)
    assert "rip" not in loop, loop


def test_f11_constant_multiply_reads_its_source_in_place(tmp_path):
    text = asm("int f charya (int a) { a * 400 ivvu }\nf(3) ni chupi\n", tmp_path)
    fn = re.search(r"^dv_f_f:\n(.*?)(?=^[^.\s]\S*:\n)", text, re.S | re.M).group(1)
    assert re.search(r"imul r\w+, rdi, 400", fn), fn
    assert "mov" not in fn.split("imul")[0].replace(".L0_entry1:", ""), fn


MANY = """
int a[10]
int b[10]
int c[10]
int d[10]
int e[10]
int f[10]
int g[10]
int h[10]
prati i 0 nundi 10 varaku {
    a[i] lo i pettu  b[i] lo i * 2 pettu  c[i] lo i * 3 pettu  d[i] lo i * 4 pettu
    e[i] lo i * 5 pettu  f[i] lo i * 6 pettu  g[i] lo i * 7 pettu  h[i] lo i * 8 pettu
}
int s
prati i 0 nundi 10 varaku {
    s lo s + a[i] + b[i] * 2 + c[i] * 3 + d[i] * 4 + e[i] * 5 + f[i] * 6 + g[i] * 7 + h[i] * 8 pettu
}
s ni chupi
int pick charya (int k) { a[k] + b[k] + c[k] + d[k] + e[k] + f[k] + g[k] + h[k] ivvu }
pick(3) ni chupi
pick(9) ni chupi
a[9] ni chupi
h[9] ni chupi
"""


@pytest.mark.parametrize("level", [0, 1])
def test_f10_more_arrays_than_registers_still_computes_correctly(level):
    ref = ref_run(MANY)
    assert ref.status == 0
    assert build_and_run(MANY, level=level)[:2] == (ref.stdout, 0)


@pytest.mark.parametrize("level", [0, 1])
def test_f11_constant_multiplies_match_the_reference(level):
    src = ("int f charya (int a, int b) { a * 400 + b * 7 + 3 * a + a * (0 - 5) + b * 2147483647 ivvu }\n"
           "f(3, 4) ni chupi\nf(-9, 123456789) ni chupi\nf(9223372036854775807, 2) ni chupi\n"
           "int x\nx lo 123456789 pettu\nx * 1000003 ni chupi\nx * 4294967296 ni chupi\n")
    ref = ref_run(src)
    assert build_and_run(src, level=level)[:2] == (ref.stdout, 0)
