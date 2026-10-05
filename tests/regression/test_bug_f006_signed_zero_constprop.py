"""F-006: constant propagation merged +0.0 and -0.0 at control-flow joins (-O1 printed -0)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
DEVARA = str(ROOT / "devara")

SRC = """void f charya (int n) {
float b
b lo ({init}) pettu
n > 0 ayite {{ b lo {branch} pettu }}
b ni chupi
}}
int n
n ni chaduvu
f(n)
"""


@pytest.mark.slow
@pytest.mark.parametrize("opt", ["-O0", "-O1"])
@pytest.mark.parametrize("init,branch,n,expected", [
    ("-0.0", "0.0", "1", "0"),
    ("-0.0", "0.0", "0", "-0"),
    ("0.0", "-0.0", "1", "-0"),
    ("0.0", "-0.0", "0", "0"),
])
def test_bug_f006_signed_zero_survives_join(tmp_path, opt, init, branch, n, expected):
    p = tmp_path / "z.tel"
    p.write_text(SRC.format(init=init, branch=branch))
    r = subprocess.run([DEVARA, opt, "run", str(p)], input=n + "\n", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == expected + "\n"
