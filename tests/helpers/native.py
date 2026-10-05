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

# When set (by the sanitizer tests), programs are linked against this AddressSanitizer/UBSan
# build of the runtime instead of the cached production object.
SANITIZED_RT: Path | None = None
SAN_FLAGS = ["-fsanitize=address,undefined", "-fno-sanitize-recover=undefined"]
SAN_ENV = {"ASAN_OPTIONS": "detect_leaks=1:abort_on_error=0:detect_stack_use_after_return=0",
           "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"}


def build_sanitized_runtime(out_dir: Path) -> Path | None:
    """Compile runtime/devara_rt.c with ASan+UBSan; None when the toolchain lacks them."""
    obj = out_dir / "devara_rt_asan.o"
    probe = subprocess.run(["gcc", "-O1", "-g", *SAN_FLAGS, "-c", str(driver.RUNTIME_SRC),
                            "-o", str(obj)], capture_output=True, text=True)
    if probe.returncode != 0:
        return None
    # the sanitizer runtime must also be linkable and runnable here
    c = out_dir / "probe.c"
    c.write_text("int main(void){return 0;}\n")
    exe = out_dir / "probe"
    link = subprocess.run(["gcc", *SAN_FLAGS, str(c), "-o", str(exe)], capture_output=True, text=True)
    if link.returncode != 0 or subprocess.run([str(exe)], capture_output=True).returncode != 0:
        return None
    return obj


def link_sanitized(asm_text: str, out: Path) -> None:
    assert SANITIZED_RT is not None
    with tempfile.TemporaryDirectory(prefix="devara_san_") as tmp:
        asm_path = Path(tmp) / "prog.s"
        asm_path.write_text(asm_text)
        proc = subprocess.run(["gcc", "-no-pie", *SAN_FLAGS, str(asm_path), str(SANITIZED_RT),
                               "-o", str(out), "-lm"], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr


def asm_of(src: str, level: int = 1) -> str:
    return generate(to_ir(src, level), regalloc=level > 0)


@contextmanager
def built(src: str, level: int = 1):
    """Compile ``src`` and yield the path of the executable (removed afterwards)."""
    asm = asm_of(src, level)
    with tempfile.TemporaryDirectory(prefix="devara_t_") as tmp:
        exe = Path(tmp) / "prog"
        if SANITIZED_RT is None:
            driver.link_executable(asm, exe)
        else:
            link_sanitized(asm, exe)
        yield exe


def execute(exe: Path, stdin: bytes = b"", timeout: float = 10.0, env: dict | None = None,
            max_vmem_mb: int | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if SANITIZED_RT is not None:
        full_env.update(SAN_ENV)
    full_env.update(env or {})

    preexec = None
    if max_vmem_mb is not None and SANITIZED_RT is None:   # ASan reserves terabytes of address space
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
