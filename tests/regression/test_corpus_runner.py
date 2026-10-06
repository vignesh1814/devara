"""scripts/run_corpus.py: parallel builds/runs (-j, default CPU count) with an unchanged
statistics report."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
SCRIPT = str(ROOT / "scripts" / "run_corpus.py")

STAT_KEYS = ["total", "compiled", "failed_compilation", "executed", "runtime_failed",
             "incorrect_output", "timeout", "correct"]


def make_corpus(d: Path) -> Path:
    d.mkdir(parents=True)
    (d / "001_ok.tel").write_text("1 + 2 ni chupi\n", newline="\n")
    (d / "001_ok.out").write_text("3\n", newline="\n")
    (d / "002_stdin.tel").write_text("int x\nx ni chaduvu\nx * 2 ni chupi\n", newline="\n")
    (d / "002_stdin.in").write_text("21\n", newline="\n")
    (d / "002_stdin.out").write_text("42\n", newline="\n")
    (d / "003_wrong.tel").write_text("5 ni chupi\n", newline="\n")
    (d / "003_wrong.out").write_text("6\n", newline="\n")
    (d / "004_rt_error.tel").write_text("int d\nd lo 0 pettu\n1 / d ni chupi\n", newline="\n")
    (d / "004_rt_error.exit").write_text("1\n", newline="\n")
    return d


def run(corpus: Path, *args: str):
    report = ["--report", str(corpus.parent / "report.json")] if corpus.is_dir() else []
    return subprocess.run([sys.executable, SCRIPT, "--corpus", str(corpus), *report, *args],
                          capture_output=True, text=True, cwd=ROOT)


def test_report_format_is_unchanged_and_counts_are_right(tmp_path):
    p = run(make_corpus(tmp_path / "c"), "-j", "3")
    lines = p.stdout.splitlines()
    assert lines[:2] == ["Corpus statistics", "-----------------"]
    stats = {k: int(v) for k, v in (ln.split() for ln in lines[2:10])}
    assert list(stats) == STAT_KEYS
    assert stats == {"total": 4, "compiled": 4, "failed_compilation": 0, "executed": 4,
                     "runtime_failed": 0, "incorrect_output": 1, "timeout": 0, "correct": 3}
    assert any(ln.lstrip().startswith("incorrect") and "003_wrong.tel" in ln for ln in lines[10:])
    assert p.returncode == 1


@pytest.mark.parametrize("jobs", ["1", "2", "8"])
def test_results_do_not_depend_on_the_number_of_workers(tmp_path, jobs):
    c = make_corpus(tmp_path / "c")
    (c / "003_wrong.out").write_text("5\n", newline="\n")
    p = run(c, "-j", jobs, "-O0")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "correct              4" in p.stdout


def test_report_file_lists_programs_in_sorted_order(tmp_path):
    run(make_corpus(tmp_path / "c"), "--jobs", "4")
    rep = json.loads((tmp_path / "report.json").read_text())
    names = [Path(r["program"]).name for r in rep["programs"]]
    assert names == sorted(names) and rep["stats"]["total"] == 4


def test_default_job_count_is_the_cpu_count_and_invalid_counts_are_rejected(tmp_path):
    help_text = run(tmp_path, "--help").stdout
    assert "-j JOBS" in help_text and str(os.cpu_count() or 1) in help_text
    bad = run(make_corpus(tmp_path / "c"), "-j", "0")
    assert bad.returncode == 2 and "at least 1" in bad.stderr
