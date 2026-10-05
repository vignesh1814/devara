"""Test helper: run Devara source through the independent reference interpreter
(tests/reference/interp.py, a tree-walker that knows nothing about memory management)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tests.reference.interp import run_file


def ref_run(src: str, stdin: bytes = b""):
    """Returns the interpreter's Result (stdout bytes, status, error)."""
    with tempfile.TemporaryDirectory(prefix="devara_ref_") as tmp:
        f = Path(tmp) / "p.tel"
        f.write_bytes(src.encode("latin-1"))
        return run_file(f, stdin, max_steps=50_000_000)
