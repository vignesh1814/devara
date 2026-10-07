"""Windows x64 (MinGW-w64) target: a representative corpus subset, built with
``--target windows`` and executed natively (Windows host) or under wine.

Skipped only when the toolchain is absent (no MinGW-w64 gcc, or no wine on a non-Windows host).
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from compiler import driver
from compiler.codegen.target import WINDOWS, host_target
from compiler.codegen.x86_64 import generate
from tests.helpers.pipeline import to_ir

CORPUS = Path(__file__).parent.parent / "corpus"
HOST_IS_WINDOWS = host_target().is_windows


def _toolchain_present() -> bool:
    cc = driver.cc_command(WINDOWS)
    if shutil.which(cc[0]) is None:
        return False
    if HOST_IS_WINDOWS:
        return True
    runner = driver.runner_command() or ["wine"]
    return shutil.which(runner[0]) is not None


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not _toolchain_present(), reason="needs MinGW-w64 gcc and wine (or a Windows host)"),
]

# arrays, recursion, floats, strings, input, scopes, casts and every runtime-error category
SUBSET = [
    "arrays/009_stats", "recursion/063_factorial_fib_digsum", "misc/109_output_formats", "misc/113_padham_operations", "math/058_float_stats",
    "misc/104_loop_forms_matrix", "misc/107_casts_conversions", "misc/108_input_kinds",
    "misc/119_rt_division_by_zero", "misc/120_rt_remainder_by_zero", "misc/121_rt_int_min_division",
]


def _programs() -> list[Path]:
    found = {p.relative_to(CORPUS).with_suffix("").as_posix(): p for p in CORPUS.rglob("*.tel")}
    chosen = [found[k] for k in SUBSET if k in found]
    # plus every program that expects a runtime error (stderr and exit status are checked)
    chosen += [p for p in sorted(found.values())
               if p.with_suffix(".err").exists() and p not in chosen]
    return chosen


def _run_windows(tel: Path, level: int, monkeypatch, src: str | None = None) -> subprocess.CompletedProcess:
    if not HOST_IS_WINDOWS:
        monkeypatch.setenv("DEVARA_RUNNER", os.environ.get("DEVARA_RUNNER") or "wine")
        monkeypatch.setenv("WINEDEBUG", "-all")
    if src is None:
        src = tel.read_bytes().decode("latin-1")
    stdin = tel.with_suffix(".in").read_bytes() if tel.with_suffix(".in").exists() else b""
    asm = generate(to_ir(src, level), WINDOWS, regalloc=level > 0)
    with tempfile.TemporaryDirectory(prefix="devara_win_") as tmp:
        exe = Path(tmp) / "prog.exe"
        driver.link_executable(asm, exe, WINDOWS)
        for _ in range(4):
            p = driver.run_executable(exe, WINDOWS, input=stdin, capture_output=True, timeout=60)
            # wine losing its server connection under load ("...Connection reset by peer") means the program
            # never ran; retry that, and only that (audit F14)
            if not (p.returncode != 0 and b"reset by peer" in p.stderr.lower()):
                break
        return p


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("tel", _programs(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_windows_corpus_subset(tel: Path, level: int, monkeypatch):
    p = _run_windows(tel, level, monkeypatch)
    expected = tel.with_suffix(".out").read_bytes() if tel.with_suffix(".out").exists() else b""
    exit_f = tel.with_suffix(".exit")
    expected_exit = int(exit_f.read_text().strip()) if exit_f.exists() else 0
    assert p.returncode == expected_exit, p.stderr.decode(errors="replace")
    assert p.stdout == expected          # byte-identical: no CRLF translation
    err = tel.with_suffix(".err")
    if err.exists():
        assert p.stderr.strip() == err.read_bytes().strip()


def test_windows_asm_has_no_elf_directives():
    asm = generate(to_ir("int x\nx lo 1 pettu\nx ni chupi\n", 1), WINDOWS)
    assert ".type dv_" not in asm and "@function" not in asm and ".note.GNU-stack" not in asm
    assert "call dv_entry" in asm and "sub rsp, 32" in asm


def test_windows_abi_stress(monkeypatch):
    """>4 parameters mixing int/float (positional registers + stack), a >4 KiB frame, recursion."""
    src = (
        "float mix charya (int a, float b, int c, float d, int e, float f, int g, float h, bool i) {\n"
        "    float r\n"
        "    r lo a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 + h * 8 pettu\n"
        "    i ayite { r lo r + 1000 pettu }\n"
        "    r ivvu\n}\n"
        "int big charya (int n) {\n"
        "    int a[7000]\n    a[0] lo n pettu\n    a[6999] lo n * 2 pettu\n"
        "    n > 0 ayite { a[3] lo big(n - 1) pettu }\n"
        "    a[0] + a[6999] + a[3] ivvu\n}\n"
        "mix(1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5, nijam) ni chupi\n"
        "mix(1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5, abaddham) ni chupi\n"
        "big(20) ni chupi\n"
    )
    for level in (0, 1):
        with tempfile.TemporaryDirectory(prefix="devara_win_") as tmp:
            tel = Path(tmp) / "abi.tel"
            tel.write_text(src)
            p = _run_windows(tel, level, monkeypatch)
        assert p.stdout == b"1214\n214\n630\n", (level, p.stderr)


def test_windows_callee_saved_xmm_are_saved_and_restored():
    """Floats live across calls use xmm6-xmm15 on Win64 and the function preserves them for its caller."""
    from tests.unit.test_regalloc import PROGRAMS

    asm = generate(to_ir(PROGRAMS["floats_across_calls"][0], 1), WINDOWS, regalloc=True)
    assert "movups XMMWORD PTR [rbp - " in asm
    assert "sub rsp, 32" in asm


@pytest.mark.parametrize("name", ["argument_cycles", "many_mixed_params", "floats_across_calls",
                                  "pow2_division", "branchy_compares", "register_pressure_over_call"])
def test_windows_register_allocated_programs_match_linux(name, monkeypatch):
    """The -O1 register allocator under the Win64 ABI computes what the reference -O0 code computes."""
    from tests.helpers.native import build_and_run
    from tests.unit.test_regalloc import PROGRAMS

    src = PROGRAMS[name][0]
    expected = build_and_run(src, level=0)
    assert expected[1] == 0
    for level in (0, 1):
        with tempfile.TemporaryDirectory(prefix="devara_win_") as tmp:
            p = _run_windows(Path(tmp) / "x.tel", level, monkeypatch, src=src)
        assert (p.stdout, p.returncode) == (expected[0], 0), (level, p.stderr)
