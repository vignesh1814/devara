"""The browser playground bundle: what `scripts/build_playground.py` ships must stand alone."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_playground  # noqa: E402


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    out = tmp_path_factory.mktemp("playground")
    assert build_playground.main(["--out", str(out)]) == 0
    return out


def test_expected_files(bundle):
    names = {p.name for p in bundle.iterdir()}
    assert {"index.html", "embed.html", "devara-playground.js", "devara.zip", "examples.json"} <= names


def test_zip_ships_only_what_the_browser_needs(bundle):
    names = zipfile.ZipFile(bundle / "devara.zip").namelist()
    assert "compiler/web.py" in names and "compiler/interp.py" in names
    forbidden = ("compiler/cli.py", "compiler/debugger.py", "compiler/codegen/x86_64.py")
    assert not [n for n in names if n in forbidden]
    assert all(n.endswith(".py") for n in names) and not any("__pycache__" in n for n in names)


def test_build_is_reproducible(tmp_path):
    build_playground.main(["--out", str(tmp_path / "a")])
    build_playground.main(["--out", str(tmp_path / "b")])
    assert (tmp_path / "a" / "devara.zip").read_bytes() == (tmp_path / "b" / "devara.zip").read_bytes()


def test_zip_runs_standalone_without_the_repo(bundle, tmp_path):
    """Import the compiler from the zip alone in an isolated interpreter, exactly as Pyodide will."""
    script = tmp_path / "probe.py"
    script.write_text(
        "import sys, json\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import compiler.web as W\n"
        "print(json.dumps(json.loads(W.dispatch('run', json.dumps(['\"zip ok\" ni chupi\\n'])))['output']))\n",
        encoding="utf-8",
    )
    p = subprocess.run([sys.executable, "-I", str(script), str(bundle / "devara.zip")],
                       capture_output=True, text=True, cwd=tmp_path, timeout=120)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == "zip ok\n"


def test_every_example_runs_with_its_sample_input(bundle):
    from compiler import web

    examples = json.loads((bundle / "examples.json").read_text(encoding="utf-8"))
    assert "hello" in examples
    for name, ex in examples.items():
        r = web.run(ex["code"], ex["stdin"])
        assert r["status"] == 0 and r["output"], f"{name}: {r}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_component_is_valid_javascript(bundle):
    p = subprocess.run(["node", "--check", str(bundle / "devara-playground.js")], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_component_declares_documented_attributes():
    js = (ROOT / "playground" / "devara-playground.js").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "PLAYGROUND.md").read_text(encoding="utf-8")
    for attr in ("code", "src", "stdin", "height", "theme", "tabs", "readonly", "autorun", "timeout", "max-steps",
                 "max-depth", "base", "pyodide"):
        assert f'"{attr}"' in js, f"component does not read attribute {attr!r}"
        assert f"`{attr}`" in docs, f"docs/PLAYGROUND.md does not document {attr!r}"
