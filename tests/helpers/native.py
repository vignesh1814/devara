"""Test helper: compile Devara source to a native executable and run it."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from compiler import driver
from compiler.codegen.x86_64 import generate
from tests.helpers.pipeline import to_ir


def asm_of(src: str, level: int = 1) -> str:
    return generate(to_ir(src, level), regalloc=level > 0)


def build_and_run(src: str, stdin: bytes = b"", level: int = 1, timeout: float = 10.0):
    """Returns (stdout bytes, exit status, stderr text)."""
    asm = asm_of(src, level)
    with tempfile.TemporaryDirectory(prefix="devara_t_") as tmp:
        exe = Path(tmp) / "prog"
        driver.link_executable(asm, exe)
        p = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=timeout)
    return p.stdout, p.returncode, p.stderr.decode("latin-1").strip()
