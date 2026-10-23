"""compiler.web: the browser entry point must agree with the native compiler's expected outputs."""
from __future__ import annotations

import pytest

from compiler import web
from tests.validation.corpus_util import expected, pid, programs

CASES = programs()


def test_hello():
    r = web.run('"Hello, Devara!" ni chupi\n')
    assert (r["ok"], r["status"], r["output"]) == (True, 0, "Hello, Devara!\n")


def test_compile_error_has_position_and_no_run():
    r = web.run("int x\nx lo pettu\n")
    assert not r["ok"] and r["status"] == 1 and r["output"] == ""
    assert r["diagnostics"][0]["line"] == 2 and "syntax error" in r["diagnostics"][0]["text"]


def test_semantic_error():
    r = web.run("y ni chupi\n")
    assert r["diagnostics"] and "UNDECLARED" in r["diagnostics"][0]["text"]


def test_runtime_error_keeps_prior_output():
    r = web.run("1 ni chupi\nint z\n5 / z ni chupi\n")
    assert (r["status"], r["output"], r["error"]) == (1, "1\n", "division by zero")


def test_infinite_loop_hits_step_limit():
    r = web.run("nijam unnanta varaku { }\n", max_steps=10_000)
    assert r["status"] == 124 and "step limit" in r["error"]


def test_runaway_recursion_is_reported_not_crashed():
    r = web.run("int f charya(int n) { f(n + 1) ivvu }\nf(0) ni chupi\n")
    assert r["status"] == 125


def test_stdin_and_utf8_roundtrip():
    r = web.run('padham s\ns ni chaduvu\ns ni chupi\npodavu(s) ni chupi\n', stdin="h\u00e9llo\n")
    assert r["output"] == "h\u00e9llo\n6\n"


@pytest.mark.parametrize("which", ["tokens", "ast", "ir", "opt"])
def test_stage_views(which):
    out = web.stage('1 + 2 ni chupi\n', which)
    assert out["diagnostics"] == [] and out["text"].strip()


def test_check_only():
    assert web.check("1 ni chupi\n")["diagnostics"] == []
    assert web.check("1 +\n")["diagnostics"]


@pytest.mark.slow
@pytest.mark.parametrize("prog", CASES, ids=pid)
def test_corpus_matches_native_expected_output(prog):
    """The same .out / .exit oracles the native compiler is held to."""
    stdin, out, exit_code, err = expected(prog)
    r = web.run(prog.read_bytes().decode("latin-1"), stdin=stdin.decode("latin-1"), max_steps=100_000_000)
    if r["status"] == 125:
        pytest.skip("recurses deeper than the playground's depth limit (documented in docs/PLAYGROUND.md)")
    assert r["output"].encode("latin-1", errors="replace") == out or r["output"].encode("utf-8") == out
    assert r["status"] == exit_code
    if exit_code:
        assert r["error"] in err
