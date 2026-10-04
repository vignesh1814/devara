"""Differential fuzz of the input/output model (P7-P10): random read sequences over random stdin byte streams;
compiled behaviour must equal the reference interpreter (stdout bytes and exit status)."""
import random
import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from tests.reference.interp import run_ast
from tests.validation.astutil import ast as parse_ast
from tests.validation.helpers import cli

pytestmark = pytest.mark.slow

PIECES = [b"0", b"7", b"-3", b"+12", b"007", b"9223372036854775807", b"-9223372036854775808", b"9223372036854775808", b"3.5", b"-0.25", b"1e3", b".5", b"nijam",
          b"abaddham", b"NIJAM", b"1", b"0", b"x", b"hello", b"two words", b"  ", b"\t", b"abc\x00def", b"\xe9\xff", b"", b"12abc", b"inf", b"#"]
SEPS = [b" ", b"\n", b"\r\n", b"  \n", b"\n\n", b"\t", b"", b" \r\n"]
TYPES = ["int", "float", "char", "bool", "padham"]


def program(types):
    lines = []
    for i, t in enumerate(types):
        lines += [f"{t} v{i}", f"v{i} ni chaduvu", f"v{i} ni chupi"]
    return "\n".join(lines) + "\n\"end\" ni chupi\n"


def run_both(types, data, opt):
    src = program(types)
    tree = parse_ast(src)
    ref = run_ast(tree, data, max_steps=1_000_000)
    strict = run_ast(tree, data, max_steps=1_000_000, strict_tokens=True)
    if (ref.stdout, ref.status) != (strict.stdout, strict.status):
        return  # P7 token-vs-prefix ambiguity (Q-010): the spec does not decide this input
    p = cli("run", src, (opt,), data)
    assert p.out == ref.stdout, f"stdout differs\ntypes={types}\ndata={data!r}\nref={ref.stdout!r}\ngot={p.out!r}\nstderr={p.err}"
    assert p.rc == ref.status, f"exit differs types={types} data={data!r} ref={ref.status} ({ref.error}) got={p.rc} {p.err}"
    if ref.status:
        assert ref.error in p.err


@settings(max_examples=120, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(st.sampled_from(TYPES), min_size=1, max_size=8),
       st.lists(st.tuples(st.sampled_from(PIECES), st.sampled_from(SEPS)), max_size=10))
def test_random_read_sequences_match_reference(types, chunks):
    data = b"".join(a + b for a, b in chunks)
    run_both(types, data, "-O1")


@pytest.mark.parametrize("types,data", [
    (["int", "padham"], b"5\r\nhello\r\n"), (["padham", "padham"], b"a\r\nb\r\n"), (["int", "int", "padham"], b"1\r\n2\r\nline\r\n"),
    (["char", "padham"], b"x\r\nrest\r\n"), (["padham"], b"abc\r\n"), (["bool", "bool"], b"nijam\r\nabaddham\r\n"),
    (["int", "padham", "padham"], b"5  \r\n\r\nx\r\n"), (["padham", "int"], b"\r\n7\r\n"), (["float", "padham"], b"1.5\n"), (["int", "padham"], b"5"),
    (["int", "padham"], b"5\n"), (["padham", "padham"], b"\n\n"), (["padham", "padham"], b"\n"), (["char", "char"], b"\xe9\xff"),
    (["padham"], b"\x00\n"), (["int"], b"\x00 5"), (["bool"], b"nijamX"), (["bool"], b"1x"), (["float"], b"1.5.5"), (["int"], b"1_000"),
    (["int", "int"], b"1,2"), (["char"], b"\n \t\r x"), (["padham", "char"], b"line\nz"),
])
@pytest.mark.parametrize("opt", ["-O0", "-O1"])
def test_crlf_and_edge_streams_match_reference(types, data, opt):
    run_both(types, data, opt)
