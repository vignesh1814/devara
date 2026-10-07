"""Audit F12/F9: leaf functions with an empty frame are emitted without rbp/stack frame, and r11 is an
allocatable caller-saved register, so small leaf loops no longer borrow a callee-saved one."""

import re
import subprocess

import pytest

from tests.helpers.cli import DEVARA_CMD
from tests.helpers.native import build_and_run

TARGETS = ["linux", "windows"]


def asm(src, target, tmp_path, level="-O1"):
    f = tmp_path / "t.tel"
    f.write_text(src, newline="\n")
    p = subprocess.run([*DEVARA_CMD, level, "--target", target, "asm", str(f)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def body(text, symbol):
    """The instructions of one function, from its label to the next function label."""
    m = re.search(rf"^{symbol}:\n(.*?)(?=^[^.\s]\S*:\n|\Z)", text, re.S | re.M)   # next *function* label
    assert m, symbol
    lines = [ln for ln in m.group(1).splitlines() if ln.strip() and not ln.lstrip().startswith(".")]
    return "\n".join(lines) + "\n"          # instructions only (no block labels or directives)


SQ = "int sq charya (int x) { x * x ivvu }\nsq(7) ni chupi\n"


@pytest.mark.parametrize("target", TARGETS)
def test_f12_small_leaf_has_no_frame(target, tmp_path):
    b = body(asm(SQ, target, tmp_path), "dv_f_sq")
    assert "rbp" not in b and "leave" not in b and "push" not in b, b
    assert b.strip().endswith("ret")


# Linux only: the Win64 allocatable caller-saved pool is just r8, r9, r11 (rcx/rdx are argument
# registers and scratch), so a loop with five live values legitimately uses callee-saved ones there.
@pytest.mark.parametrize("target", ["linux"])
def test_f12_leaf_loop_stays_in_caller_saved_registers(target, tmp_path):
    src = ("int sum charya (int v[], int n) {\n  int s\n  s lo 0 pettu\n"
           "  prati i 0 nundi n varaku { s lo s + v[i] pettu }\n  s ivvu\n}\n"
           "int a[4]\na[1] lo 5 pettu\nsum(a, 4) ni chupi\n")
    b = body(asm(src, target, tmp_path), "dv_f_sum")
    assert not re.search(r"\b(rbx|rbp|r12|r13|r14|r15)\b", b), b          # nothing callee-saved, no frame
    assert "push" not in b and "leave" not in b


@pytest.mark.parametrize("name, src, why", [
    ("dv_f_divide", "int divide charya (int a, int b) { a / b ivvu }\ndivide(9, 2) ni chupi\n", "integer division traps call the runtime"),
    ("dv_f_caller", "int sq charya (int x) { x * x ivvu }\nint caller charya (int x) { sq(x) + 1 ivvu }\ncaller(2) ni chupi\n", "it makes a call"),
    ("dv_f_locarr", "int locarr charya (int n) {\n int a[4]\n a[1] lo n pettu\n a[1] ivvu\n}\nlocarr(2) ni chupi\n", "it has a frame array"),
    ("dv_f_many", "int many charya (int a, int b, int c, int d, int e, int f, int g, int h) { a + g + h ivvu }\nmany(1, 2, 3, 4, 5, 6, 7, 8) ni chupi\n", "stack parameters are addressed from rbp"),
])
@pytest.mark.parametrize("target", TARGETS)
def test_f12_functions_that_need_a_frame_keep_it(name, src, why, target, tmp_path):
    assert "push rbp" in body(asm(src, target, tmp_path), name), why


@pytest.mark.parametrize("level", [0, 1])
def test_f12_leaf_results_are_unchanged(level):
    src = ("int addmul charya (int a, int b, int c) { (a + b) * c ivvu }\n"
           "float half charya (float x) { x / 2.0 ivvu }\n"
           "bool lt charya (int a, int b) { a < b ivvu }\n"
           "int sum7 charya (int a, int b, int c, int d, int e, int f, int g) { a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 ivvu }\n"
           "addmul(2, 3, 4) ni chupi\nhalf(5.0) ni chupi\nlt(1, 2) ni chupi\nsum7(1, 2, 3, 4, 5, 6, 7) ni chupi\n")
    assert build_and_run(src, level=level)[:2] == (b"20\n2.5\nnijam\n140\n", 0)
