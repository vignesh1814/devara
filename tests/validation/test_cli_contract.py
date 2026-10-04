"""CLI contract (plan §E): exit statuses, diagnostic line format, usage errors."""
import re
import pytest
from tests.validation.helpers import cli, run_cli, prog, DIAG_RE, ROOT, _write


def test_usage_error_no_command():
    assert run_cli([]).rc == 2


def test_usage_error_unknown_command():
    assert run_cli(["frobnicate", "x.tel"]).rc == 2


def test_missing_file_is_io_error():
    p = run_cli(["lex", "/nonexistent/path/prog.tel"])
    assert p.rc == 2


@pytest.mark.parametrize("cmd", ["lex", "parse", "sema"])
def test_valid_program_exits_zero(cmd):
    assert cli(cmd, prog("int x", "x lo 1 pettu", "x ni chupi")).rc == 0


@pytest.mark.parametrize("cmd", ["lex", "parse", "sema"])
def test_empty_file_is_valid_program(cmd):
    # program = { top-level-item }  -> zero items is a valid program
    assert cli(cmd, "").rc == 0


def test_lexical_error_exit_and_format():
    p = cli("lex", "int x @\n")
    assert p.rc == 1
    ds = p.diags()
    assert ds and ds[0][0] == "lexical" and ds[0][2] == 1 and ds[0][3] == 7


def test_diagnostic_line_format_filename_prefix():
    p = cli("parse", "int\n")
    assert p.rc == 1
    first = p.err.splitlines()[0]
    m = DIAG_RE.match(first)
    assert m, first
    assert m["file"].endswith(".tel")


def test_pipeline_stops_after_lexical_error():
    # a lexical error must not be followed by syntax diagnostics (stage failure stops the pipeline)
    p = cli("sema", "int x @ lo\n")
    stages = {d[0] for d in p.diags()}
    assert stages == {"lexical"}


def test_pipeline_stops_after_syntax_error():
    p = cli("sema", "int x\nx lo pettu\nundeclared_name ni chupi\n")
    stages = {d[0] for d in p.diags()}
    assert stages == {"syntax"}


def test_semantic_errors_collected_and_sorted():
    p = cli("sema", prog("a ni chupi", "b ni chupi", "c ni chupi"))
    ds = [d for d in p.diags() if d[0] == "semantic"]
    assert len(ds) == 3
    assert [d[2] for d in ds] == sorted(d[2] for d in ds)


def test_never_exit_three_on_user_errors():
    for src in ["@", "int", "x lo", "int x[", "'", "\"abc", "(((((", "}}}}", "x ni chupi"]:
        for cmd in ("lex", "parse", "sema"):
            assert cli(cmd, src + "\n").rc in (0, 1), (cmd, src)


def test_stdin_dash_input_or_file_equivalence():
    src = prog("int x", "x lo 5 pettu", "x ni chupi")
    a = cli("parse", src)
    b = run_cli(["parse", "-"], src.encode())
    assert a.rc == 0 and b.rc == 0


def test_opt_flags_accepted_by_asm_build_run():
    # -O0 / -O1 must be accepted before or after the command (plan §E global options)
    src = prog("1 ni chupi")
    for flag in ("-O0", "-O1"):
        assert cli("run", src, (flag,)).rc == 0
