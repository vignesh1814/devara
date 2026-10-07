"""Shared harness for the register-allocation, memory and Windows-target attack suites.

Everything runs through the public CLI (`./devara`, plan §E) as a subprocess; the only other oracle is the
independent reference interpreter in tests/reference/interp.py.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tests.reference.interp import run_ast
from tests.validation.astutil import ast as parse_ast
from tests.helpers.cli import DEVARA_CMD
from tests.validation.helpers import ROOT, WORK

MINGW = "x86_64-w64-mingw32-gcc"
HAVE_WINDOWS_TOOLS = shutil.which(MINGW) is not None and shutil.which("wine") is not None

WIN_ENV = {"DEVARA_CC": MINGW, "DEVARA_RUNNER": "wine", "WINEDEBUG": "-all"}

SCRATCH = WORK / "stress"
SCRATCH.mkdir(parents=True, exist_ok=True)


@dataclass
class Out:
    rc: int
    out: bytes
    err: str


def src_path(src: str) -> str:
    h = hashlib.sha1(src.encode("latin-1", "replace")).hexdigest()[:16]
    p = SCRATCH / f"s_{h}.tel"
    if not p.exists():
        p.write_bytes(src.encode("latin-1"))
    return str(p)


def devara(args, stdin: bytes = b"", env: dict | None = None, timeout: float = 300) -> Out:
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([*DEVARA_CMD, *args], input=stdin, capture_output=True, timeout=timeout, env=e)
    return Out(p.returncode, p.stdout, p.stderr.decode("utf-8", "replace"))


WINE_RETRIES = 3


def is_wine_transport_error(p: "Out") -> bool:
    """wine losing its connection to its server under load ("...Connection reset by peer"): the program
    never ran, so it says nothing about the compiler. No Devara program or diagnostic prints this."""
    return p.rc != 0 and "reset by peer" in p.err.lower()


@lru_cache(maxsize=2048)
def _run_cached(src: str, opt: str, stdin: bytes, target: str | None, envkey: tuple) -> Out:
    args = ["run"]
    if target:
        args += ["--target", target]
    args += [opt, src_path(src)]
    p = devara(args, stdin, dict(envkey))
    for _ in range(WINE_RETRIES if target == "windows" else 0):
        if not is_wine_transport_error(p):
            break
        p = devara(args, stdin, dict(envkey))      # a failed attempt is never cached: only the final result is
    return p


def run(src: str, opt: str = "-O1", stdin: bytes = b"", target: str | None = None, env: dict | None = None) -> Out:
    """`devara run [--target T] -Ox FILE`, cached."""
    return _run_cached(src, opt, stdin, target, tuple(sorted((env or {}).items())))


def run_win(src: str, opt: str = "-O1", stdin: bytes = b"") -> Out:
    return run(src, opt, stdin, "windows", WIN_ENV)


def norm(b: bytes) -> bytes:
    """NaN sign is not pinned by the plan (Q-004): compare `nan` and `-nan` as equal."""
    return re.sub(rb"-?nan", b"nan", b)


@lru_cache(maxsize=1024)
def reference(src: str, stdin: bytes = b""):
    return run_ast(parse_ast(src), stdin, max_steps=60_000_000)


RT_ERR_RE = re.compile(r"devara: runtime error: (.*)")


def check_against_reference(src: str, stdin: bytes = b"", opts=("-O0", "-O1"), runner=run, expect_status: int | None = None):
    """-O0 output == -O1 output == reference interpreter (stdout bytes, exit status, runtime-error message)."""
    ref = reference(src, stdin)
    if expect_status is not None:
        assert ref.status == expect_status, f"reference status {ref.status} ({ref.error}) != expected {expect_status}"
    outs = {}
    for opt in opts:
        p = runner(src, opt, stdin)
        assert p.rc == ref.status, f"{opt}: rc={p.rc} (reference {ref.status} {ref.error!r})\n{p.err}\n--- source ---\n{src}"
        assert norm(p.out) == norm(ref.stdout), (
            f"{opt}: stdout differs from reference\n got={p.out[:600]!r}\n ref={ref.stdout[:600]!r}\n--- source ---\n{src}")
        if ref.status:
            m = RT_ERR_RE.search(p.err)
            assert m and m.group(1).strip() == ref.error, f"{opt}: runtime error message {p.err!r} != {ref.error!r}"
        outs[opt] = p
    if len(outs) > 1:
        vals = list(outs.values())
        for v in vals[1:]:
            assert (v.rc, norm(v.out)) == (vals[0].rc, norm(vals[0].out)), "-O0 and -O1 disagree"
    return ref


# ---------------------------------------------------------------------------------------------- build + exec helpers
_exe_n = 0


def build(src: str, opt: str = "-O1", target: str | None = None, env: dict | None = None) -> Path:
    """Build an executable (cached on disk by content hash). Returns the path."""
    h = hashlib.sha1((src + opt + str(target)).encode("latin-1", "replace")).hexdigest()[:16]
    exe = SCRATCH / f"x_{h}{'.exe' if target == 'windows' else ''}"
    if not exe.exists():
        args = ["build"]
        if target:
            args += ["--target", target]
        args += [opt, src_path(src), "-o", str(exe)]
        b = devara(args, env=env)
        assert b.rc == 0, f"build failed rc={b.rc}\n{b.err}\n--- source ---\n{src}"
    return exe


def run_exe_limited(exe: Path, stdin: bytes = b"", vmem_kb: int | None = None, env: dict | None = None,
                    timeout: float = 120) -> Out:
    """Run a built executable through `bash -c 'ulimit -v N; exec exe'` with optional address-space cap."""
    e = dict(os.environ)
    e.update(env or {})
    pre = f"ulimit -v {vmem_kb}; " if vmem_kb else ""
    p = subprocess.run(["bash", "-c", pre + 'exec "$0"', str(exe)], input=stdin, capture_output=True, timeout=timeout, env=e)
    return Out(p.returncode, p.stdout, p.stderr.decode("utf-8", "replace"))
