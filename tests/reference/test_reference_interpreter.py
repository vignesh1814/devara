"""The reference interpreter is itself under test: it must reproduce every oracle-derived corpus expectation
(independent evidence that interpreter, oracles and parser agree) and a battery of hand-checked semantics."""
import os
import pytest
from tests.reference.interp import run_ast, run_file, StepLimit
from tests.validation.helpers import cli, prog, WORK
from tests.validation.astutil import ast as parse_ast
from tests.validation.corpus_util import programs, pid, expected

PROGS = programs()


def interp(src, stdin=b""):
    return run_ast(parse_ast(src), stdin)


@pytest.mark.slow
@pytest.mark.parametrize("tel", PROGS, ids=pid)
def test_reference_matches_corpus_oracles(tel):
    inp, out, ex, err = expected(tel)
    r = run_file(str(tel), inp, max_steps=300_000_000)
    assert r.stdout == out
    assert r.status == ex
    if ex:
        assert r.error == err.strip().replace("devara: runtime error: ", "")


@pytest.mark.parametrize("src,out", [
    ("7 / 2 ni chupi", "3\n"), ("-7 / 2 ni chupi", "-3\n"), ("-7 % 3 ni chupi", "-1\n"), ("7 % -3 ni chupi", "1\n"),
    ("9223372036854775807 + 1 ni chupi", "-9223372036854775808\n"),
    ("(char) 321 ni chupi", "A\n"), ("(int) (char) 200 ni chupi", "-56\n"), ("(int) 3.99 ni chupi", "3\n"),
    ("(int) -3.99 ni chupi", "-3\n"), ("0.1 + 0.2 ni chupi", "0.3\n"), ("1.0 / 0.0 ni chupi", "inf\n"),
    ("1 < 2 ni chupi", "nijam\n"), ("\"ab\" + \"cd\" ni chupi", "abcd\n"), ("(padham) 'q' ni chupi", "q\n"),
    ("nijam + nijam ni chupi", "2\n"), ("!5 ni chupi", "abaddham\n"), ("'a' + 1 ni chupi", "98\n"),
])
def test_reference_expression_semantics(src, out):
    r = interp(src + "\n")
    assert r.stdout.decode() == out and r.status == 0


def test_reference_runtime_errors():
    for src, msg in [("int d\n10 / d ni chupi\n", "division by zero"), ("int d\n10 % d ni chupi\n", "remainder by zero"),
                     ("padham s\ns[0] ni chupi\n", "string index out of range"), ("(char) \"ab\" ni chupi\n", "invalid char conversion"),
                     ("int n\nn lo -1 pettu\nint a[n]\n", "invalid array size"), ("int a\na ni chaduvu\n", "invalid input")]:
        r = interp(src)
        assert r.status == 1 and r.error == msg, (src, r)


def test_reference_step_limit_terminates_infinite_loop():
    with pytest.raises(StepLimit):
        run_ast(parse_ast("nijam unnanta varaku { }\n"), b"", max_steps=10_000)
