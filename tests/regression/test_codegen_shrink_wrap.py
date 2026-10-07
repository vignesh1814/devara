"""Audit F7: callee-saved registers used only inside the single-entry region that contains all calls are
saved when that region is entered and restored by the returns inside it, so a recursive function's
base case returns without touching them. The transformation must apply only where it is sound."""

import re
import subprocess

import pytest

from compiler.codegen import prep
from tests.helpers.cli import DEVARA_CMD
from tests.helpers.native import build_and_run
from tests.helpers.pipeline import to_ir
from tests.helpers.ref import ref_run

FIB = "int fib charya (int n) {\n n < 2 ayite { n ivvu }\n fib(n - 1) + fib(n - 2) ivvu\n}\nfib(10) ni chupi\n"


def wrap_of(src, fname):
    fn = next(f for f in to_ir(src, 1).functions if f.name == fname)
    return getattr(prep.prepare_function(fn), "wrap", None)


# ── where the region exists ──

def test_f7_recursive_base_case_gets_a_region():
    n, region = wrap_of(FIB, "fib")
    assert region == frozenset({n})


@pytest.mark.parametrize("name, src", [
    ("calls in the entry block",
     "int sq charya (int x) { x * x ivvu }\nint f charya (int n) { sq(n) + n ivvu }\nf(3) ni chupi\n"),
    ("calls on both branches (common dominator is the entry)",
     "int sq charya (int x) { x * x ivvu }\n"
     "int f charya (int n) { n > 0 ayite { sq(n) + n ivvu } lekunte { sq(0 - n) ivvu } }\nf(3) ni chupi\n"),
    ("no call at all", "int f charya (int a, int b) { a * b + 1 ivvu }\nf(3, 4) ni chupi\n"),
    ("the call is inside a loop whose header would be the region entry",
     "int sq charya (int x) { x * x ivvu }\n"
     "int f charya (int n) {\n n < 0 ayite { 0 ivvu }\n int s\n s lo 0 pettu\n"
     " prati i 0 nundi n varaku { s lo s + sq(i) pettu }\n s ivvu\n}\nf(4) ni chupi\n"),
])
def test_f7_no_region_where_it_would_not_be_sound_or_useful(name, src):
    fname = "f"
    wrap = wrap_of(src, fname)
    if name.startswith("the call is inside a loop"):
        # a region may exist (the loop is entered once from outside) but it must never contain its own entry
        # as a loop head: every predecessor of N lies outside S
        if wrap is not None:
            n, region = wrap
            fn = prep.prepare_function(next(f for f in to_ir(src, 1).functions if f.name == fname))
            _, pred = prep._cfg(fn)
            assert not any(q in region for q in pred[n])
    else:
        assert wrap is None, name


# ── the emitted code ──

def test_f7_base_case_path_has_no_callee_saved_traffic(tmp_path):
    f = tmp_path / "fib.tel"
    f.write_text(FIB, newline="\n")
    text = subprocess.run([*DEVARA_CMD, "-O1", "asm", str(f)], capture_output=True, text=True).stdout
    fib = re.search(r"^dv_f_fib:\n(.*?)(?=^[^.\s]\S*:\n)", text, re.S | re.M).group(1)
    first_label_after_entry = fib.index("endif")
    before_region, region = fib[:first_label_after_entry], fib[first_label_after_entry:]
    assert not re.search(r"\[rbp - \d+\], (rbx|r12|r13|r14|r15)", before_region), before_region
    assert re.search(r"\[rbp - \d+\], rbx", region)           # the save moved into the region
    assert re.search(r"rbx, QWORD PTR \[rbp - \d+\]", region)    # and so did the restore


# ── behaviour: every shape must still compute exactly what the reference computes ──

PROGRAMS = {
    "fib_and_fact": FIB + "int fact charya (int n) { n <= 1 ayite { 1 ivvu } n * fact(n - 1) ivvu }\nfact(15) ni chupi\n",
    "param_changed_after_call": (
        "int g charya (int n, int acc) {\n n == 0 ayite { acc ivvu }\n int r\n r lo g(n - 1, acc + n) pettu\n"
        " n lo n * 2 pettu\n r + n ivvu\n}\ng(12, 0) ni chupi\n"),
    "ackermann": (
        "int ack charya (int m, int n) {\n m == 0 ayite { n + 1 ivvu }\n n == 0 ayite { ack(m - 1, 1) ivvu }\n"
        " ack(m - 1, ack(m, n - 1)) ivvu\n}\nack(2, 3) ni chupi\nack(3, 2) ni chupi\n"),
    "mutual_with_loop_in_region": (
        "int a charya (int n) { n <= 0 ayite { 0 ivvu } int s\n s lo 0 pettu\n prati i 0 nundi n varaku { s lo s + b(i) pettu }\n s ivvu }\n"
        "int b charya (int n) { n <= 1 ayite { n ivvu } a(n - 1) + 1 ivvu }\na(7) ni chupi\nb(9) ni chupi\n"),
    "void_early_return": (
        "void down charya (int n) {\n n <= 0 ayite { 0 ni chupi }\n lekunte { n ni chupi down(n - 1) n * 10 ni chupi }\n}\ndown(3)\n"),
    "float_param_across_calls": (
        "float h charya (float x, int n) {\n n <= 0 ayite { x ivvu }\n float y\n y lo h(x * 0.5, n - 1) pettu\n y + x ivvu\n}\n"
        "h(8.0, 5) ni chupi\nh(1.5, 0) ni chupi\n"),
    "string_param_across_calls": (
        "padham rep charya (padham s, int n) {\n n <= 0 ayite { \"\" ivvu }\n s + rep(s, n - 1) ivvu\n}\nrep(\"ab\", 4) ni chupi\n"),
    "array_param_across_calls": (
        "int sumto charya (int v[], int n) {\n n <= 0 ayite { 0 ivvu }\n v[n - 1] + sumto(v, n - 1) ivvu\n}\n"
        "int a[6]\nprati i 0 nundi 6 varaku { a[i] lo i * i pettu }\nsumto(a, 6) ni chupi\n"),
}
@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("name", list(PROGRAMS))
def test_f7_recursive_shapes_match_the_reference(name, level):
    src = PROGRAMS[name]
    ref = ref_run(src)
    assert ref.status == 0, ref.error
    out, rc, err = build_and_run(src, level=level)
    assert (out, rc) == (ref.stdout, 0), err


def test_f7_windows_target_saves_xmm_registers_inside_the_region(tmp_path):
    src = PROGRAMS["float_param_across_calls"]
    f = tmp_path / "h.tel"
    f.write_text(src, newline="\n")
    text = subprocess.run([*DEVARA_CMD, "-O1", "--target", "windows", "asm", str(f)], capture_output=True, text=True).stdout
    h = re.search(r"^dv_f_h:\n(.*?)(?=^[^.\s]\S*:\n)", text, re.S | re.M).group(1)
    save = h.index("movups XMMWORD PTR")                       # a callee-saved xmm is used and saved ...
    assert save > h.index("endif"), h                          # ... only after the early-return path, not in the prologue
    assert h.index("ret") < save                               # the first return (base case) comes before any save
