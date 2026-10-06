"""Phase 7: end-to-end `build` / `run` through the CLI, exit-status and diagnostics contract."""

import os
import subprocess

import pytest

from tests.helpers.cli import DEVARA_CMD


pytestmark = pytest.mark.slow


def dv(*args, stdin=b"", cwd=None):
    return subprocess.run([*DEVARA_CMD, *args], input=stdin, capture_output=True, cwd=cwd)


HELLO = 'int n\nn ni chaduvu\nprati i 0 nundi n varaku { i * i ni chupi }\n"done" ni chupi\n'


@pytest.fixture
def prog(tmp_path):
    p = tmp_path / "hello.tel"
    p.write_text(HELLO)
    return p


def test_run_passes_stdin_stdout_and_zero_status(prog):
    r = dv("run", str(prog), stdin=b"4")
    assert r.returncode == 0 and r.stdout == b"0\n1\n4\n9\ndone\n" and r.stderr == b""


def test_run_returns_program_exit_status_on_runtime_error(tmp_path):
    p = tmp_path / "e.tel"
    p.write_text('"a" ni chupi\nint z\nz lo 0 pettu\n1 / z ni chupi\n')
    r = dv("run", str(p))
    assert r.returncode == 1
    assert r.stdout == b"a\n"
    assert r.stderr == b"devara: runtime error: division by zero\n"


def test_build_writes_executable_with_o_flag_and_default_name(prog, tmp_path):
    out = tmp_path / "bin" / "x"
    out.parent.mkdir()
    r = dv("build", str(prog), "-o", str(out))
    assert r.returncode == 0 and os.access(out, os.X_OK)
    run = subprocess.run([str(out)], input=b"2", capture_output=True)
    assert run.stdout == b"0\n1\ndone\n"
    r = dv("build", str(prog), cwd=tmp_path)
    assert r.returncode == 0 and (tmp_path / "hello").exists()


def test_opt_level_flags_accepted_before_and_after_command(prog):
    outs = set()
    for args in (["-O0", "run", str(prog)], ["run", "-O0", str(prog)], ["-O1", "run", str(prog)],
                 ["run", "-O1", str(prog)], ["run", str(prog)]):
        r = dv(*args, stdin=b"3")
        assert r.returncode == 0, args
        outs.add(r.stdout)
    assert len(outs) == 1


def test_asm_command_emits_assembly_and_build_accepts_dot_s(prog, tmp_path):
    a = dv("asm", str(prog))
    assert a.returncode == 0 and b".intel_syntax noprefix" in a.stdout
    s = tmp_path / "p.s"
    s.write_bytes(a.stdout)
    out = tmp_path / "from_s"
    r = dv("build", str(s), "-o", str(out))
    assert r.returncode == 0
    assert subprocess.run([str(out)], input=b"2", capture_output=True).stdout == b"0\n1\ndone\n"


def test_o0_and_o1_assembly_differ_but_behave_the_same(prog):
    a0 = dv("asm", "-O0", str(prog)).stdout
    a1 = dv("asm", "-O1", str(prog)).stdout
    assert a0 != a1 and len(a1) < len(a0)
    assert dv("run", "-O0", str(prog), stdin=b"5").stdout == dv("run", "-O1", str(prog), stdin=b"5").stdout


@pytest.mark.parametrize("src,stage,cat", [
    ("int x @", "lexical", "INVALID_CHARACTER"),
    ("x lo 1", "syntax", "UNEXPECTED_EOF"),
    ("int x\nx lo \"s\" pettu", "semantic", "TYPE_MISMATCH"),
])
def test_user_errors_exit_1_with_stage_and_category(tmp_path, src, stage, cat):
    p = tmp_path / "bad.tel"
    p.write_text(src)
    for cmd in ("run", "build", "asm", "ir", "opt", "sema"):
        r = dv(cmd, str(p), cwd=tmp_path)
        assert r.returncode == 1, (cmd, r.stderr)
        line = r.stderr.decode().splitlines()[0]
        assert f"{stage} error [{cat}]" in line and line.startswith(f"{p}:"), line
        assert r.stdout == b""
    assert not (tmp_path / "bad").exists()


def test_stage_failure_stops_the_pipeline_lexical_before_syntax(tmp_path):
    p = tmp_path / "bad.tel"
    p.write_text("x lo @ pettu\nint y y\n")
    r = dv("parse", str(p))
    assert r.returncode == 1
    lines = r.stderr.decode().splitlines()
    assert all("lexical error" in l for l in lines)


def test_usage_and_io_errors_exit_2(tmp_path):
    assert dv().returncode == 2
    assert dv("frobnicate", "x").returncode == 2
    assert dv("run", str(tmp_path / "missing.tel")).returncode == 2
    assert dv("lex").returncode == 2
    j = tmp_path / "x.json"
    j.write_text("{not json")
    assert dv("parse", str(j)).returncode == 2
    j.write_text('{"devara": "ast", "version": 1, "file": "x", "data": {"_node": "Nope"}}')
    assert dv("sema", str(j)).returncode in (2, 3)


def test_requesting_an_earlier_stage_from_a_later_artifact_is_a_usage_error(prog, tmp_path):
    ir = tmp_path / "p.json"
    ir.write_bytes(dv("ir", "--json", str(prog)).stdout)
    r = dv("lex", str(ir))
    assert r.returncode == 2 and b"already at stage" in r.stderr


def test_user_supplied_bad_assembly_is_a_user_error_not_an_ice(tmp_path):
    s = tmp_path / "bad.s"
    s.write_text("this is not assembly\n")
    r = dv("build", str(s), "-o", str(tmp_path / "o"))
    assert r.returncode == 1                      # Q-012; exit 3 is reserved for generated code
    assert b"assembler error" in r.stderr and b"internal compiler error" not in r.stderr


def test_every_stage_artifact_chain_to_executable(prog, tmp_path):
    """source -> tokens -> AST -> typed -> IR -> optimized IR -> asm -> executable, all via files."""
    cur = str(prog)
    for cmd, name in (("lex", "t.json"), ("parse", "a.json"), ("sema", "s.json"),
                      ("ir", "i.json"), ("opt", "o.json")):
        r = dv(cmd, "--json", cur)
        assert r.returncode == 0, (cmd, r.stderr)
        (tmp_path / name).write_bytes(r.stdout)
        cur = str(tmp_path / name)
    a = dv("asm", cur)
    assert a.returncode == 0
    (tmp_path / "p.s").write_bytes(a.stdout)
    out = tmp_path / "exe"
    assert dv("build", str(tmp_path / "p.s"), "-o", str(out)).returncode == 0
    assert subprocess.run([str(out)], input=b"3", capture_output=True).stdout == b"0\n1\n4\ndone\n"


def test_deep_recursion_compile_and_run_via_cli(tmp_path):
    p = tmp_path / "deep.tel"
    p.write_text("int f charya(int n) { n == 0 ayite { 0 ivvu } 1 + f(n - 1) ivvu }\nf(50000) ni chupi\n")
    r = dv("run", str(p))
    assert r.returncode == 0 and r.stdout == b"50000\n"
