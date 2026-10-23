"""Golden / snapshot tests for every front-to-middle compiler stage.

Each program in examples/ is pushed through `lex`, `parse`, `sema`, `ir` and
`opt` and the exact text is compared with tests/golden/stages/. An unintended
change anywhere in those stages fails with a diff. After reviewing an
intentional change, accept it with:

    DEVARA_UPDATE_GOLDEN=1 python -m pytest tests/regression/test_golden_stages.py

Assembly is deliberately not snapshotted: it is target- and register-allocator
specific and is covered by the O0/O1 differential tests instead.
"""

from __future__ import annotations

import difflib
import os
import subprocess

import pytest

from tests.helpers.cli import DEVARA_CMD, ROOT

GOLDEN = ROOT / "tests" / "golden" / "stages"
EXAMPLES = sorted((ROOT / "examples").glob("*.tel"))
STAGES = ["lex", "parse", "sema", "ir", "opt"]
UPDATE = os.environ.get("DEVARA_UPDATE_GOLDEN") == "1"


def _run(stage: str, program) -> str:
    rel = program.relative_to(ROOT).as_posix()  # relative path => stable diagnostics
    proc = subprocess.run(
        DEVARA_CMD + [stage, rel], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", timeout=120,
    )
    assert proc.returncode == 0, f"{stage} {rel} failed:\n{proc.stderr}"
    return proc.stdout.replace("\r\n", "\n")


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("program", EXAMPLES, ids=lambda p: p.stem)
def test_stage_output_matches_golden(program, stage):
    actual = _run(stage, program)
    golden = GOLDEN / f"{program.stem}.{stage}"
    if UPDATE:
        GOLDEN.mkdir(parents=True, exist_ok=True)
        golden.write_text(actual, encoding="utf-8", newline="\n")
        return
    assert golden.exists(), f"missing {golden.name}; run with DEVARA_UPDATE_GOLDEN=1"
    expected = golden.read_text(encoding="utf-8")
    diff = "".join(difflib.unified_diff(
        expected.splitlines(True), actual.splitlines(True), "golden", "actual", n=2))
    assert actual == expected, f"{stage} output of {program.name} changed:\n{diff[:3000]}"


def test_stage_output_is_deterministic():
    """Two runs of the same stage on the same input are byte-identical."""
    program = EXAMPLES[0]
    for stage in ("ir", "opt"):
        assert _run(stage, program) == _run(stage, program)
