import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEVARA = str(ROOT / "devara")


def run(*args, stdin=b""):
    return subprocess.run([DEVARA, *args], capture_output=True, input=stdin)


def test_lex_text_format():
    r = run("lex", str(ROOT / "examples" / "example.tel"))
    assert r.returncode == 0
    first = r.stdout.decode().splitlines()[0]
    assert first == "1:1 INT 'int'"


def test_lex_error_status_and_format(tmp_path):
    f = tmp_path / "bad.tel"
    f.write_text("int x @\n")
    r = run("lex", str(f))
    assert r.returncode == 1
    assert r.stderr.decode().strip() == (
        f"{f}:1:7: lexical error [INVALID_CHARACTER]: Unexpected character '@'"
    )


def test_missing_file_is_usage_error():
    assert run("lex", "/nonexistent/file.tel").returncode == 2


def test_no_command_is_usage_error():
    assert run().returncode == 2


def test_stdin_input():
    r = run("lex", "-", stdin=b"int a")
    assert r.returncode == 0 and "INT" in r.stdout.decode()


def test_python_m_entry_point():
    r = subprocess.run([sys.executable, "-m", "compiler.cli", "lex", str(ROOT / "examples/example.tel")],
                       capture_output=True, cwd=ROOT)
    assert r.returncode == 0
