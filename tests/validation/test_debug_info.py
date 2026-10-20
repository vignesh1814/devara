"""`-g` builds: source-line tables for gdb/lldb (`.file` / `.loc`), and `devara gdb`.

The default (no -g) output must stay exactly what it was; a -g build must be the same code plus directives."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from compiler import driver, serialize
from compiler.codegen.target import host_target

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.tel"))
CORPUS = sorted((ROOT / "tests" / "corpus").rglob("*.tel"))
LOC = re.compile(r"^    \.(loc|file) ")


def pipeline(path: Path):
    src = driver.decode_source(path.read_bytes())
    toks, _ = driver.run_lex(src, str(path))
    prog, _ = driver.run_parse(toks, str(path))
    typed, diags = driver.run_sema(prog, str(path))
    return driver.run_lower(typed) if not diags else None


def asm(path: Path, level: int, target: str, debug: bool) -> str:
    ir = pipeline(path)
    if ir is None:
        pytest.skip("does not compile")
    ir = driver.run_opt(ir, level) if level else ir
    return driver.run_codegen(ir, target, level, path.resolve().as_posix() if debug else None)


def strip_debug(text: str) -> str:
    return "\n".join(ln for ln in text.split("\n") if not LOC.match(ln))


# ----------------------------------------------------------------------------------- the line number rides on the IR
def test_ir_stage_output_is_unchanged_by_line_numbers():
    p = subprocess.run([sys.executable, "-m", "compiler.cli", "ir", "--json", str(ROOT / "examples" / "factorial.tel")],
                       capture_output=True, cwd=ROOT)
    assert p.returncode == 0 and b'"line"' not in p.stdout
    serialize.from_data(json.loads(p.stdout)["data"])                       # still decodes


def test_lowering_stamps_statement_lines():
    ir = pipeline(ROOT / "examples" / "factorial.tel")
    fact = next(f for f in ir.functions if f.name == "fact")
    lines = {i.line for b in fact.blocks for i in b.instrs} | {b.term.line for b in fact.blocks}
    assert lines == {3, 4} and fact.decl_line == 2


# ----------------------------------------------------------------------------------- default output is untouched
@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("target", ["linux", "windows"])
def test_without_g_there_are_no_debug_directives(level, target):
    for path in EXAMPLES:
        assert not any(LOC.match(ln) for ln in asm(path, level, target, False).split("\n")), path.name


@pytest.mark.slow
@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("target", ["linux", "windows"])
def test_g_adds_only_directives(level, target):
    """Same machine code with and without -g (the peephole pass must see through the .loc lines)."""
    for path in [*EXAMPLES, *CORPUS]:
        plain = asm(path, level, target, False)
        dbg = asm(path, level, target, True)
        assert strip_debug(dbg) == plain, path.name


# ----------------------------------------------------------------------------------- what the directives say
def test_g_output_names_the_absolute_source_and_every_statement_line():
    path = ROOT / "examples" / "factorial.tel"
    text = asm(path, 0, "linux", True)
    assert f'.file 1 "{path.resolve().as_posix()}"' in text
    locs = {int(m.group(1)) for m in re.finditer(r"^    \.loc 1 (\d+)$", text, re.M)}
    assert locs == {2, 3, 4, 8, 9}
    assert text.index("dv_f_fact:\n    .loc 1 2\n") > 0                       # function entry: its declaration line


@pytest.mark.parametrize("level", [0, 1])
def test_every_function_starts_with_a_location_and_lines_are_in_range(level):
    for path in EXAMPLES:
        n_lines = len(path.read_bytes().split(b"\n"))
        text = asm(path, level, "windows", True)
        for m in re.finditer(r"^    \.loc 1 (\d+)$", text, re.M):
            assert 1 <= int(m.group(1)) <= n_lines, (path.name, m.group(0))
        for m in re.finditer(r"^(dv_f_\w+):\n((?:    \..*\n)*)", text, re.M):
            assert ".loc 1 " in m.group(2), (path.name, m.group(1))


def test_g_defaults_to_o0_and_o1_can_be_requested(tmp_path):
    def build_asm(*flags):
        return subprocess.run([sys.executable, "-m", "compiler.cli", "asm", *flags, str(ROOT / "examples" / "hello.tel")],
                              capture_output=True, text=True, cwd=ROOT).stdout

    o0, g, g1, o1 = build_asm("-O0"), build_asm("-g"), build_asm("-g", "-O1"), build_asm("-O1")
    assert strip_debug(g) == o0 and strip_debug(g1) == o1 and o0 != o1


# ----------------------------------------------------------------------------------- the real thing: a linked program
def decoded_lines(exe: Path) -> list[tuple[int, int]]:
    out = subprocess.run(["objdump", "--dwarf=decodedline", str(exe)], capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        m = re.match(r"^factorial\.tel\s+(\d+)\s+(0x[0-9a-f]+)", ln)
        if m:
            rows.append((int(m.group(1)), int(m.group(2), 16)))
    return rows


@pytest.mark.skipif(shutil.which("objdump") is None or shutil.which(driver.cc_command(host_target())[0]) is None,
                    reason="needs objdump and a C compiler")
def test_linked_program_has_a_line_table_that_matches_the_source(tmp_path):
    exe = tmp_path / "fact"
    p = subprocess.run([sys.executable, "-m", "compiler.cli", "build", "-g", str(ROOT / "examples" / "factorial.tel"),
                        "-o", str(exe)], capture_output=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    rows = decoded_lines(driver.executable_path(exe, host_target()))
    assert {ln for ln, _ in rows} >= {2, 3, 4, 8, 9}
    addr = dict(rows)
    assert addr[2] < addr[3] < addr[4] < addr[8] < addr[9]                  # fact's lines, then the main program's
    run = subprocess.run([str(driver.executable_path(exe, host_target()))], input=b"6\n", capture_output=True)
    assert run.stdout == b"720\n"


@pytest.mark.parametrize("name,stdin,expected", [
    ("squares.tel", b"4\n", b"sum of squares:\n30\n"), ("primes.tel", b"20\n", b"2\n3\n5\n7\n11\n13\n17\n19\n"),
    ("sort.tel", b"4\n3 1 2 0\n", b"0\n1\n2\n3\n"),
])
@pytest.mark.parametrize("flags", [["-g"], ["-g", "-O1"]])
def test_g_builds_behave_like_normal_builds(tmp_path, name, stdin, expected, flags):
    exe = tmp_path / "prog"
    p = subprocess.run([sys.executable, "-m", "compiler.cli", "build", *flags, str(ROOT / "examples" / name), "-o", str(exe)],
                       capture_output=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    run = subprocess.run([str(driver.executable_path(exe, host_target()))], input=stdin, capture_output=True)
    assert run.stdout.replace(b"\r\n", b"\n") == expected


# ----------------------------------------------------------------------------------- devara gdb
@pytest.mark.skipif(shutil.which(driver.cc_command(host_target())[0]) is None, reason="needs a C compiler")
def test_gdb_command_builds_a_debug_executable_and_launches_gdb(monkeypatch, capsys):
    from compiler import cli

    seen = {}

    def fake_call(cmd):
        seen["cmd"] = cmd
        seen["exe_exists"] = Path(cmd[-1]).exists()
        seen["has_line_table"] = b".debug_line" in Path(cmd[-1]).read_bytes()
        return 0

    monkeypatch.setenv("DEVARA_GDB", sys.executable)             # any existing program: it is never run
    monkeypatch.setattr(cli.subprocess, "call", fake_call)
    rc = cli.main(["gdb", str(ROOT / "examples" / "factorial.tel")])
    cmd = seen["cmd"]
    assert rc == 0 and cmd[0] == sys.executable and cmd[-2] == "--args"
    assert seen["exe_exists"] and seen["has_line_table"]
    assert f"directory {(ROOT / 'examples').as_posix()}" in cmd and any("factorial.tel:LINE" in a for a in cmd)


def test_gdb_command_explains_a_missing_gdb(tmp_path):
    env = {**os.environ, "DEVARA_GDB": "no-such-gdb-xyz"}
    p = subprocess.run([sys.executable, "-m", "compiler.cli", "gdb", str(ROOT / "examples" / "hello.tel")],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert p.returncode == 2 and "not found" in p.stderr and "DEVARA_GDB" in p.stderr


@pytest.mark.skipif(shutil.which("gdb") is None, reason="gdb is not installed")
def test_real_gdb_stops_at_a_source_line(tmp_path):
    exe = tmp_path / "fact"
    subprocess.run([sys.executable, "-m", "compiler.cli", "build", "-g", str(ROOT / "examples" / "factorial.tel"), "-o", str(exe)],
                   check=True, cwd=ROOT)
    (tmp_path / "in.txt").write_text("4\n")
    p = subprocess.run(["gdb", "-batch", "-ex", "break factorial.tel:3", "-ex", f"run < {tmp_path / 'in.txt'}", "-ex", "bt",
                        str(driver.executable_path(exe, host_target()))], capture_output=True, text=True, timeout=120)
    assert "factorial.tel:3" in p.stdout and "dv_f_fact" in p.stdout
