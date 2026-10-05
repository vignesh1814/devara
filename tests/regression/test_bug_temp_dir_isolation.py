"""Regression: "run/build leave no temp files" was asserted by diffing /tmp, which fails whenever
another process (a parallel pytest worker, another build) creates a devara_* directory meanwhile.
The compiler honours TMPDIR, so the check uses a private one."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DEVARA = str(ROOT / "devara")


def test_bug_run_and_build_use_tmpdir_and_clean_up_after_themselves(tmp_path):
    work = tmp_path / "private_tmp"
    work.mkdir()
    env = dict(os.environ, TMPDIR=str(work))
    src = tmp_path / "p.tel"
    src.write_text("1 + 2 ni chupi\n")

    run = subprocess.run([DEVARA, "run", str(src)], capture_output=True, env=env)
    build = subprocess.run([DEVARA, "build", str(src), "-o", str(tmp_path / "p.exe")],
                           capture_output=True, env=env)

    assert (run.returncode, build.returncode) == (0, 0), (run.stderr, build.stderr)
    assert run.stdout == b"3\n"
    assert list(work.iterdir()) == []
