"""`devara debug`: scripted sessions on the examples (compiler/debugger.py)."""
import io
import subprocess
import sys
from pathlib import Path

import pytest

from compiler import debugger, driver, serialize
from tests.validation.stress_util import reference

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def session(name_or_src: str, commands: list[str], stdin: bytes = b"", max_steps=None):
    src = (EXAMPLES / name_or_src).read_bytes().decode("latin-1") if name_or_src.endswith(".tel") else name_or_src
    toks, _ = driver.run_lex(src, "prog.tel")
    prog, _ = driver.run_parse(toks, "prog.tel")
    out = io.StringIO()
    dbg = debugger.Debugger(serialize.to_data(prog), src, "prog.tel", stdin, iter(commands), max_steps or 1_000_000, out)
    rc = dbg.run()
    return rc, out.getvalue(), dbg


def lines_after(text: str, command: str) -> list[str]:
    """Output between `(devara-db) <command>` and the next prompt."""
    got, cur = [], None
    for ln in text.splitlines():
        if ln.startswith(debugger.PROMPT):
            cur = ln[len(debugger.PROMPT):]
            continue
        if cur == command:
            got.append(ln)
    return got


# ------------------------------------------------------------------------------------------ stepping
def test_session_starts_before_the_first_statement():
    rc, out, dbg = session("hello.tel", ["q"])
    assert rc == 0 and "=>    1 | " in out and bytes(dbg.interp.out) == b""


def test_step_executes_one_statement_at_a_time():
    rc, out, _ = session("example.tel", ["s", "s", "p a", "p b", "q"])
    assert lines_after(out, "p a") == ["5"] and lines_after(out, "p b") == ["10"]


def test_continue_runs_to_the_end_and_output_matches_the_reference():
    src = "int n\nn ni chaduvu\nprati i 0 nundi n varaku { i * i ni chupi }\n"
    rc, out, dbg = session(src, ["c"], stdin=b"4\n")
    assert rc == 0 and "Program exited normally." in out
    assert bytes(dbg.interp.out) == reference(src, b"4\n").stdout == b"0\n1\n4\n9\n"


@pytest.mark.parametrize("name,stdin", [
    ("hello.tel", b""), ("example.tel", b""), ("squares.tel", b"4\n"), ("fizzbuzz.tel", b""), ("primes.tel", b"30\n"),
    ("sort.tel", b"6\n5 2 9 1 7 3\n"), ("factorial.tel", b"10\n"), ("fibonacci.tel", b"10\n"), ("collatz.tel", b"27\n"),
    ("reverse.tel", b"hello\n"),
])
def test_every_example_gives_the_same_output_under_the_debugger(name, stdin):
    src = (EXAMPLES / name).read_bytes().decode("latin-1")
    rc, _, dbg = session(name, ["c"], stdin=stdin)
    assert rc == 0 and bytes(dbg.interp.out) == reference(src, stdin).stdout


def test_stepping_through_every_statement_gives_the_same_output():
    rc, out, dbg = session("fibonacci.tel", ["s"] * 400, stdin=b"5\n")
    assert bytes(dbg.interp.out) == b"0\n1\n1\n2\n3\n"


# ------------------------------------------------------------------------------------------ calls
def test_step_enters_a_call_and_next_steps_over_it():
    _, out, _ = session("factorial.tel", ["b 9", "c", "s", "bt", "q"], stdin=b"3\n")
    assert "fact(n=3) at prog.tel:" in out
    _, out, _ = session("factorial.tel", ["b 9", "c", "n", "q"], stdin=b"3\n")
    assert "6\n" in out and "fact(n=" not in out


def test_backtrace_up_down_and_print_in_the_selected_frame():
    _, out, _ = session("factorial.tel", ["b 3 if n == 1", "c", "bt", "up", "p n", "up", "p n", "down", "q"], stdin=b"3\n")
    bt = lines_after(out, "bt")
    assert len(bt) == 4 and bt[0].startswith("*#0  fact(n=1)") and bt[3].startswith(" #3  main()")
    assert lines_after(out, "p n")[0] == "2"


def test_finish_reports_the_returned_value():
    _, out, _ = session("factorial.tel", ["b 3 if n == 1", "c", "fin", "q"], stdin=b"3\n")
    assert "Run till exit: fact returned 1" in out


# ------------------------------------------------------------------------------------------ breakpoints and watches
def test_conditional_breakpoint_and_listing():
    _, out, _ = session("fibonacci.tel", ["b 11 if i == 3", "c", "p i", "p a", "info break", "q"], stdin=b"6\n")
    assert lines_after(out, "p i") == ["3"] and lines_after(out, "p a") == ["2"]
    assert any("breakpoint  line 11  if i == 3" in ln for ln in lines_after(out, "info break"))


def test_breakpoint_on_a_line_without_a_statement_moves_to_the_next():
    _, out, _ = session("# comment\n\nint x\nx lo 1 pettu\n", ["b 1", "q"])
    assert "Breakpoint 1 at line 4 (no statement on line 1)" in out


def test_watchpoint_reports_old_and_new_values():
    _, out, _ = session("collatz.tel", ["watch n", "c", "c", "q"], stdin=b"6\n")
    assert "old: 0" in out and "new: 6" in out and "old: 6" in out and "new: 3" in out


def test_delete_removes_a_breakpoint():
    _, out, _ = session("hello.tel", ["b 1", "delete 1", "c"])
    assert "Deleted breakpoint 1" in out and "Program exited normally." in out


# ------------------------------------------------------------------------------------------ values and expressions
def test_print_formats_every_type():
    src = ("int a[3]\na[1] lo 7 pettu\nfloat f\nf lo 2.5 pettu\nbool b\nb lo nijam pettu\nchar c\nc lo 'x' pettu\n"
           "padham s\ns lo \"hi\" pettu\nint m[2][2]\nm[1][0] lo 5 pettu\n0 ni chupi\n")
    cmds = ["p a", "p f", "p b", "p c", "p s", "p m", "p a[1] + 1", "p podavu(s)"]
    _, out, _ = session(src, ["b 13", "c", *cmds, "q"])
    got = {c: lines_after(out, c)[0] for c in cmds}
    assert got == {"p a": "[0, 7, 0]", "p f": "2.5", "p b": "nijam", "p c": "120 'x'", "p s": '"hi"',
                   "p m": "[[0, 0], [5, 0]]", "p a[1] + 1": "8", "p podavu(s)": "2"}


def test_print_errors_do_not_stop_the_session():
    _, out, _ = session("int x\nx lo 1 pettu\n", ["p nosuch", "p 1 +", "p 1 / 0", "p x", "q"])
    assert "no symbol 'nosuch'" in out and "division by zero" in out and lines_after(out, "p x") == ["0"]


def test_info_locals_args_globals():
    _, out, _ = session("factorial.tel", ["b 3", "c", "info args", "info locals", "info globals", "q"], stdin=b"3\n")
    assert lines_after(out, "info args") == ["n = 3"] and lines_after(out, "info locals") == ["No locals."]
    assert lines_after(out, "info globals") == ["n = 3"]


# ------------------------------------------------------------------------------------------ failures
def test_runtime_error_leaves_the_state_inspectable():
    src = "int z\nz lo 0 pettu\nint a\na lo 10 / z pettu\n"
    rc, out, _ = session(src, ["c", "p z", "info globals", "n", "q"])
    assert rc == 1 and "Runtime error: division by zero" in out and "=>    4 | a lo 10 / z pettu" in out
    assert lines_after(out, "p z") == ["0"] and lines_after(out, "n") == ["The program is not being run."]


def test_runtime_error_inside_a_function_keeps_its_frames():
    src = "int f charya (int d) {\n  10 / d ivvu\n}\nf(0) ni chupi\n"
    rc, out, _ = session(src, ["c", "bt", "p d", "q"])
    assert rc == 1 and lines_after(out, "bt")[0].startswith("*#0  f(d=0)") and lines_after(out, "p d") == ["0"]


def test_runaway_program_is_stopped_and_can_be_inspected():
    src = "int i\ni lo 0 pettu\nnijam unnanta varaku { i lo i + 1 pettu }\n"
    rc, out, _ = session(src, ["c", "p i", "q"], max_steps=3000)
    assert rc == 1 and "possible infinite loop" in out and int(lines_after(out, "p i")[0]) > 0


def test_end_of_commands_quits_cleanly():
    rc, out, _ = session("hello.tel", [])
    assert rc == 0


# ------------------------------------------------------------------------------------------ command line
def cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "compiler.cli", *args], cwd=ROOT, capture_output=True, input=stdin, timeout=120)


def test_cli_debug_with_command_and_input_files(tmp_path):
    (tmp_path / "c.txt").write_text("b 3\nc\np n\nq\n")
    (tmp_path / "in.txt").write_text("5\n")
    p = cli("debug", "examples/factorial.tel", "--input", str(tmp_path / "in.txt"), "--commands", str(tmp_path / "c.txt"))
    assert p.returncode == 0 and b"fact(n=5)" in p.stdout and b"Breakpoint 1, line 3" in p.stdout


def test_cli_debug_reads_commands_from_a_pipe():
    p = cli("debug", "examples/hello.tel", stdin=b"c\n")
    assert p.returncode == 0 and b"Hello, Devara!" in p.stdout and b"Program exited normally." in p.stdout


def test_cli_debug_reports_compile_errors_without_starting(tmp_path):
    (tmp_path / "bad.tel").write_text("total ni chupi\n")
    p = cli("debug", str(tmp_path / "bad.tel"))
    assert p.returncode == 1 and b"[UNDECLARED]" in p.stderr and b"Devara debugger" not in p.stdout


def test_cli_debug_exit_status_after_runtime_error(tmp_path):
    (tmp_path / "dz.tel").write_text("int z\nz lo 0 pettu\n(10 / z) ni chupi\n")
    p = cli("debug", str(tmp_path / "dz.tel"), stdin=b"c\nq\n")
    assert p.returncode == 1 and b"Runtime error: division by zero" in p.stdout
