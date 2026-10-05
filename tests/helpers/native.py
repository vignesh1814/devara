"""Test helper: compile Devara source to a native executable and run it."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from compiler import driver
from compiler.codegen.x86_64 import generate
from tests.helpers.pipeline import to_ir

LIVE_RE = re.compile(r"^devara-rt: live=(-?\d+)$", re.M)


def asm_of(src: str, level: int = 1) -> str:
    return generate(to_ir(src, level))


@contextmanager
def built(src: str, level: int = 1):
    """Compile ``src`` and yield the path of the executable (removed afterwards)."""
    asm = asm_of(src, level)
    with tempfile.TemporaryDirectory(prefix="devara_t_") as tmp:
        exe = Path(tmp) / "prog"
        driver.link_executable(asm, exe)
        yield exe


def execute(exe: Path, stdin: bytes = b"", timeout: float = 10.0, env: dict | None = None,
            max_vmem_mb: int | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    full_env.update(env or {})

    preexec = None
    if max_vmem_mb is not None:
        def preexec():  # runs in the child between fork and exec (POSIX test helper only)
            import resource
            lim = max_vmem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (lim, lim))

    return subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=timeout,
                          env=full_env, preexec_fn=preexec)


def build_and_run(src: str, stdin: bytes = b"", level: int = 1, timeout: float = 10.0):
    """Returns (stdout bytes, exit status, stderr text)."""
    with built(src, level) as exe:
        p = execute(exe, stdin, timeout)
    return p.stdout, p.returncode, p.stderr.decode("latin-1").strip()


def run_stats(src: str, stdin: bytes = b"", level: int = 1, timeout: float = 30.0,
              max_vmem_mb: int | None = None):
    """Run with DEVARA_RT_STATS=1: returns (stdout bytes, exit status, stderr without the stats
    line, live count or None when the program did not reach a normal exit)."""
    with built(src, level) as exe:
        p = execute(exe, stdin, timeout, {"DEVARA_RT_STATS": "1"}, max_vmem_mb)
    err = p.stderr.decode("latin-1")
    m = LIVE_RE.search(err)
    live = int(m.group(1)) if m else None
    return p.stdout, p.returncode, LIVE_RE.sub("", err).strip(), live
