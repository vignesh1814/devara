"""Windows: concurrent first builds raced on the cached runtime object. `os.replace(tmp, obj)` raises PermissionError
(WinError 5) on Windows when another build has `obj` open or is replacing it at that moment, which surfaced as
"internal compiler error: PermissionError" in one of several parallel `devara build` runs on a cold cache."""

import os
import subprocess
import sys
from pathlib import Path

from compiler import driver

ROOT = Path(__file__).parent.parent.parent


def test_losing_the_publish_race_is_not_an_error(tmp_path, monkeypatch):
    real_replace = os.replace

    def lose_race(src, dst):
        real_replace(src, dst)          # the other build publishes the identical object first ...
        raise PermissionError(5, "Access is denied")   # ... and our own replace is then refused

    monkeypatch.setattr(driver.os, "replace", lose_race)
    obj = driver.runtime_object(cache_dir=tmp_path)
    assert obj.exists() and obj.read_bytes()
    assert [p.name for p in tmp_path.iterdir()] == [obj.name]      # no leftover .tmp files


def test_a_failed_publish_without_a_winner_is_still_reported(tmp_path, monkeypatch):
    def always_fail(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(driver.os, "replace", always_fail)
    monkeypatch.setattr(driver.time, "sleep", lambda s: None)
    try:
        driver.runtime_object(cache_dir=tmp_path)
    except PermissionError:
        pass
    else:
        raise AssertionError("a publish that fails with no object in place must not be swallowed")
    assert list(tmp_path.iterdir()) == []


def test_parallel_cold_cache_builds_all_succeed(tmp_path):
    code = ("import sys; from pathlib import Path; from compiler import driver; "
            "print(driver.runtime_object(cache_dir=Path(sys.argv[1])))")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    procs = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], cwd=ROOT, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(8)]
    results = [(p.wait(), p.stderr.read().decode()) for p in procs]
    assert all(rc == 0 for rc, _ in results), results
    assert len(list(tmp_path.glob("*.o"))) == 1 and not list(tmp_path.glob("*.tmp"))
