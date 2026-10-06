"""CLI behaviour around I/O, build outputs, diagnostics positions and robustness (plan §E, exit statuses 0/1/2/3)."""
import os
import subprocess
import threading
import pytest
from tests.helpers.cli import DEVARA_CMD
from tests.validation.helpers import run_cli, cli, prog, WORK, ROOT


def test_F001_build_to_unwritable_output_is_io_error_not_ice(tmp_path):
    src = tmp_path / "a.tel"
    src.write_text("1 ni chupi\n")
    p = run_cli(["build", str(src), "-o", "/nonexistent/dir/out"])
    assert p.rc == 2, f"I/O error must exit 2 (plan §E), got {p.rc}: {p.err}"
    assert "internal compiler error" not in p.err


def test_F001_build_output_is_a_directory_is_io_error(tmp_path):
    src = tmp_path / "a.tel"
    src.write_text("1 ni chupi\n")
    d = tmp_path / "outdir"
    d.mkdir()
    p = run_cli(["build", str(src), "-o", str(d)])
    assert p.rc == 2, f"got {p.rc}: {p.err}"


def test_missing_input_files_exit_2():
    for cmd in ("lex", "parse", "sema", "ir", "opt", "asm", "build", "run"):
        assert run_cli([cmd, "/nonexistent/x.tel"]).rc == 2, cmd


def test_directory_as_input_exit_2():
    assert run_cli(["lex", str(ROOT)]).rc == 2


def test_build_default_output_name_is_file_stem(tmp_path):
    src = tmp_path / "hello_prog.tel"
    src.write_text("42 ni chupi\n")
    p = subprocess.run([*DEVARA_CMD, "build", str(src)], cwd=tmp_path, capture_output=True)
    assert p.returncode == 0, p.stderr
    exe = tmp_path / "hello_prog"
    assert exe.exists() and os.access(exe, os.X_OK)
    assert subprocess.run([str(exe)], capture_output=True).stdout == b"42\n"


def test_build_explicit_output_and_assembly_input(tmp_path):
    src = tmp_path / "p.tel"
    src.write_text("int x\nx ni chaduvu\nx * 2 ni chupi\n")
    asm = run_cli(["asm", str(src)])
    s = tmp_path / "p.s"
    s.write_bytes(asm.out)
    exe = tmp_path / "out.bin"
    assert run_cli(["build", str(s), "-o", str(exe)]).rc == 0
    r = subprocess.run([str(exe)], input=b"21\n", capture_output=True)
    assert r.stdout == b"42\n" and r.returncode == 0


def test_build_does_not_leave_temporary_files_next_to_output(tmp_path):
    src = tmp_path / "p.tel"
    src.write_text("1 ni chupi\n")
    run_cli(["build", str(src), "-o", str(tmp_path / "p.exe")])
    assert sorted(f.name for f in tmp_path.iterdir()) == ["p.exe", "p.tel"]


def test_run_passes_program_exit_status_and_streams(tmp_path):
    p = run_cli(["run", str(WORK / "x.tel")]) if False else None
    src = prog("int d", "d ni chaduvu", "\"before\" ni chupi", "5 / d ni chupi")
    r = cli("run", src, (), b"0")
    assert r.rc == 1 and r.text == "before\n" and "division by zero" in r.err


def test_run_does_not_leave_temp_files_behind(tmp_path):
    # a private TMPDIR: other processes (parallel test workers) also create devara_* dirs in /tmp
    env = dict(os.environ, TMPDIR=str(tmp_path))
    for _ in range(3):
        p = subprocess.run([*DEVARA_CMD, "run", str(ROOT / "tests/corpus/arrays/003_reverse.tel")],
                           input=b"1\n5\n", capture_output=True, env=env)
        assert p.returncode == 0, p.stderr
    assert sorted(os.listdir(tmp_path)) == [], "leaked temp files"


def test_parallel_runs_do_not_interfere():
    results = []

    def work(i):
        src = prog(f"{i} * 3 ni chupi")
        results.append((i, run_cli(["run", "-"], src.encode())))

    ts = [threading.Thread(target=work, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(results) == 12
    for i, r in results:
        assert r.rc == 0 and r.out == f"{i * 3}\n".encode(), (i, r.err)


def test_paths_with_spaces_and_unicode(tmp_path):
    d = tmp_path / "dir with space"
    d.mkdir()
    f = d / "prög ram.tel"
    f.write_text("7 ni chupi\n")
    p = run_cli(["run", str(f)])
    assert p.rc == 0 and p.out == b"7\n"


def test_assembly_output_is_deterministic():
    f = ROOT / "tests/corpus/dp/087_lcs.tel"
    for lvl in ("-O0", "-O1"):
        assert run_cli([lvl, "asm", str(f)]).out == run_cli([lvl, "asm", str(f)]).out


def test_ir_and_sema_text_are_deterministic():
    f = ROOT / "tests/corpus/graphs/099_topological_sort.tel"
    for cmd in ("lex", "parse", "sema", "ir", "opt"):
        assert run_cli([cmd, str(f)]).out == run_cli([cmd, str(f)]).out


def test_optimizer_changes_ir_but_not_behaviour():
    src = prog("int x", "x lo 2 + 3 * 4 pettu", "x ni chupi")
    a = cli("ir", src).out
    b = cli("opt", src).out
    assert a != b            # constant folding visible at the IR level
    assert cli("run", src, ("-O0",)).out == cli("run", src, ("-O1",)).out == b"14\n"


def test_O1_is_default():
    src = prog("int x", "x lo 2 + 3 * 4 pettu", "x ni chupi")
    assert cli("asm", src).out == cli("asm", src, ("-O1",)).out
    assert cli("asm", src).out != cli("asm", src, ("-O0",)).out


# ------------------------------------------------------------------ diagnostic positions
@pytest.mark.parametrize("src,cat,line,col", [
    ("int x\nx lo 1 pettu\ny ni chupi\n", "UNDECLARED", 3, 1),
    ("int a\n  b lo 2 pettu\n", "UNDECLARED", 2, 3),
    ("int x\nint x\n", "REDECLARATION", 2, 5),
    ("1 ni chupi\naapu\n", "BREAK_OUTSIDE_LOOP", 2, 1),
    ("1 ni chupi\n  saagu\n", "CONTINUE_OUTSIDE_LOOP", 2, 3),
    ("int f charya () { }\n", "MISSING_RETURN", 1, 5),
    ("1 ivvu\n", "INVALID_RETURN", 1, 1),
    ("int a[0]\n", "INVALID_ARRAY_SIZE", 1, 7),
])
def test_semantic_diagnostic_positions(src, cat, line, col):
    p = cli("sema", src)
    hit = [d for d in p.diags() if d[1] == cat]
    assert hit, p.err
    assert (hit[0][2], hit[0][3]) == (line, col), p.err


@pytest.mark.parametrize("src,line,col", [
    ("int x @\n", 1, 7), ("\n\n  $\n", 3, 3), ("\"abc\n", 1, 1), ("x lo 'ab' pettu\n", 1, 6), ("a\n\"\\q\"\n", 2, 2),
])
def test_lexical_diagnostic_positions(src, line, col):
    d = cli("lex", src).diags()
    assert d and (d[0][2], d[0][3]) == (line, col)


def test_syntax_error_position_points_at_offending_token():
    p = cli("parse", "int x\nx lo 1 2 pettu\n")
    d = p.diags()
    assert d and d[0][2] == 2 and d[0][3] in (8, 10, 12)  # at or just after the stray `2`


def u8(text: str) -> str:
    """UTF-8 bytes of `text`, carried through the latin-1 file helper unchanged."""
    return text.encode("utf-8").decode("latin-1")


def test_semantic_error_after_multibyte_strings_keeps_columns():
    # columns count source *bytes*/units (OQ3: one byte = one character unit)
    p = cli("sema", u8("\"é€\" ni chupi\nzz ni chupi\n"))
    assert [(d[2], d[3]) for d in p.diags() if d[1] == "UNDECLARED"] == [(2, 1)]


# ------------------------------------------------------------------ byte transparency (OQ3)
def test_utf8_bytes_in_strings_and_comments_round_trip():
    text = "é€✓"
    src = u8("# comment é€ ✓\n\"" + text + "\" ni chupi\npodavu(\"" + text + "\") ni chupi\n")
    p = cli("run", src)
    assert p.rc == 0, p.err
    assert p.out == text.encode("utf-8") + b"\n" + f"{len(text.encode('utf-8'))}\n".encode()


def test_utf8_in_char_literal_is_rejected_cleanly():
    # a two-byte UTF-8 sequence is two character units, so it is not a single-character literal (OQ3)
    p = cli("lex", u8("'é' ni chupi\n"))
    assert p.rc == 1 and p.diags()


def test_utf8_identifier_is_rejected_cleanly():
    p = cli("lex", u8("int é\n"))
    assert p.rc == 1 and p.diags()[0][1] == "INVALID_CHARACTER"


def test_assembler_keyword_identifiers_do_not_break_codegen():
    names = ["rax", "eax", "rsp", "rbp", "ptr", "offset", "xmm0", "byte", "qword", "mov", "st0", "dword", "flags", "al", "ax", "r8", "r15", "ymm0", "cs", "jmp", "call", "ret"]
    src = prog(*[f"int {n}" for n in names], *[f"{n} lo {i} pettu" for i, n in enumerate(names)],
               "int fsum charya (int rcx, int rdx) { int rdi\n rdi lo rcx + rdx pettu\n rdi ivvu }",
               *[f"int {n}_f charya (int {n}) {{ {n} ivvu }}" for n in names[:5]],
               " + ".join(names) + " ni chupi", "fsum(rax, eax) ni chupi", *[f"{n}_f({i}) ni chupi" for i, n in enumerate(names[:5])])
    p = cli("run", src)
    assert p.rc == 0, p.err
    assert p.text.split("\n")[:-1] == [str(sum(range(len(names)))), "1"] + [str(i) for i in range(5)]


def test_function_named_same_as_local_label_prefixes():
    src = prog("int L1 charya () { 1 ivvu }", "int entry1 charya () { 2 ivvu }", "int t1 charya () { 3 ivvu }", "int B0 charya () { 4 ivvu }", "int dv_f_L1 charya () { 5 ivvu }",
               "L1() + entry1() + t1() + B0() + dv_f_L1() ni chupi")
    p = cli("run", src)
    assert p.rc == 0, p.err
    assert p.text == "15\n"
