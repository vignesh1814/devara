"""Stage boundaries: each stage's JSON feeds the next stage and gives identical results."""

import glob
import json
import subprocess
from pathlib import Path

import pytest

from compiler import driver, serialize
from compiler.diagnostics import SemCategory as S

ROOT = Path(__file__).parent.parent.parent
DEVARA = str(ROOT / "devara")
FILES = sorted(
    glob.glob(str(ROOT / "tests" / "**" / "*.tel"), recursive=True)
    + glob.glob(str(ROOT / "examples" / "*.tel"))
)
# Legacy parse-only programs that are not valid Devara (rank-1 array params indexed twice,
# undefined helper): they must be rejected with the documented semantic categories.
EXPECTED_SEMANTIC_ERRORS = {
    "17_bfs_mock.tel": {S.TOO_MANY_INDICES},
    "18_n_queens.tel": {S.TOO_MANY_INDICES, S.UNDECLARED},
}


def pipeline(path: Path):
    src = driver.decode_source(path.read_bytes())
    toks, d = driver.run_lex(src, path.name)
    assert not d
    prog, d = driver.run_parse(toks, path.name)
    assert not d
    return toks, prog


@pytest.mark.parametrize("filepath", FILES, ids=lambda p: Path(p).name)
def test_sema_accepts_or_rejects_with_expected_categories(filepath):
    path = Path(filepath)
    _, prog = pipeline(path)
    typed, diags = driver.run_sema(prog, path.name)
    if path.name in EXPECTED_SEMANTIC_ERRORS:
        assert typed is None
        assert {d.category for d in diags} == EXPECTED_SEMANTIC_ERRORS[path.name]
    else:
        assert not diags, [str(d) for d in diags]
        assert serialize.loads(serialize.dumps(typed)) == typed


@pytest.mark.parametrize("filepath", FILES[:6], ids=lambda p: Path(p).name)
def test_cli_json_stage_chain(filepath, tmp_path):
    """lex --json -> parse --json -> sema, via files; equals the direct run."""
    def run(*a):
        return subprocess.run([DEVARA, *a], capture_output=True, text=True)

    tok = tmp_path / "t.json"
    ast = tmp_path / "a.json"
    r = run("lex", "--json", filepath)
    assert r.returncode == 0
    tok.write_text(r.stdout)
    r = run("parse", "--json", str(tok))
    assert r.returncode == 0, r.stderr
    direct = run("parse", "--json", filepath)
    assert json.loads(r.stdout)["data"] == json.loads(direct.stdout)["data"]
    ast.write_text(r.stdout)
    r = run("sema", str(ast))
    direct = run("sema", filepath)
    assert r.returncode == direct.returncode
    assert r.stdout == direct.stdout


def test_cli_semantic_error_format_and_status(tmp_path):
    f = tmp_path / "e.tel"
    f.write_text('int x\nx lo "s" pettu\n')
    r = subprocess.run([DEVARA, "sema", str(f)], capture_output=True, text=True)
    assert r.returncode == 1
    assert r.stderr.strip() == (
        f"{f}:2:6: semantic error [TYPE_MISMATCH]: cannot convert padham to int in assignment"
    )


def test_deeply_nested_input_via_cli(tmp_path):
    f = tmp_path / "deep.tel"
    f.write_text("(" * 3000 + "1" + ")" * 3000 + " ni chupi\n")
    r = subprocess.run([DEVARA, "parse", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]


def test_ir_json_feeds_opt_and_matches_direct_run(tmp_path):
    src = tmp_path / "p.tel"
    src.write_text("int a\na lo 2 * 3 pettu\na ni chupi\nnijam ayite { 1 ni chupi }\n")
    def run(*a):
        return subprocess.run([DEVARA, *a], capture_output=True, text=True)
    r = run("ir", "--json", str(src))
    assert r.returncode == 0, r.stderr
    j = tmp_path / "p.json"
    j.write_text(r.stdout)
    via_json = run("opt", str(j))
    direct = run("opt", str(src))
    assert via_json.returncode == 0 and via_json.stdout == direct.stdout
    typed = run("sema", "--json", str(src))
    t = tmp_path / "t.json"
    t.write_text(typed.stdout)
    assert run("ir", str(t)).stdout == run("ir", str(src)).stdout
