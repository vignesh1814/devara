"""Windows editors (Notepad, PowerShell `Out-File -Encoding utf8`) start UTF-8 files with a byte order mark. It was
decoded as three latin-1 characters and every such file failed with "Unexpected character" (plan A-006)."""

import subprocess
import sys
from pathlib import Path

from compiler import driver

ROOT = Path(__file__).parent.parent.parent
BOM = b"\xef\xbb\xbf"
PROGRAM = b'int a\na lo 40 + 2 pettu\na ni chupi\n"hi" ni chupi\n'


def cli(*args):
    return subprocess.run([sys.executable, "-m", "compiler.cli", *args], cwd=ROOT, capture_output=True, timeout=120)


def test_leading_bom_is_dropped():
    assert driver.decode_source(BOM + PROGRAM) == driver.decode_source(PROGRAM)


def test_only_a_leading_bom_is_dropped():
    assert driver.decode_source(PROGRAM + BOM) == PROGRAM.decode("latin-1") + "\xef\xbb\xbf"
    assert driver.decode_source(BOM + BOM) == "\xef\xbb\xbf"
    assert driver.decode_source(b"\xef\xbb") == "\xef\xbb"          # a partial mark is not a mark
    assert driver.decode_source(BOM) == ""


def test_run_accepts_a_bom_file_with_lf_and_crlf(tmp_path):
    for name, text in (("lf", PROGRAM), ("crlf", PROGRAM.replace(b"\n", b"\r\n"))):
        f = tmp_path / f"{name}.tel"
        f.write_bytes(BOM + text)
        r = cli("run", str(f))
        assert (r.returncode, r.stdout, r.stderr) == (0, b"42\nhi\n", b""), name


def test_diagnostic_positions_ignore_the_bom(tmp_path):
    plain, bom = tmp_path / "plain.tel", tmp_path / "bom.tel"
    plain.write_bytes(b"int x\nx lo 1 +\n")
    bom.write_bytes(BOM + b"int x\nx lo 1 +\n")
    a, b = cli("run", str(plain)), cli("run", str(bom))
    assert a.returncode == b.returncode == 1
    assert a.stderr.replace(b"plain.tel", b"F") == b.stderr.replace(b"bom.tel", b"F") != b""
