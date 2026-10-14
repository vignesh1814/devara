"""Audit F3: the input helpers used malloc/realloc unchecked, so running out of memory while reading a
huge token or line dereferenced NULL (a crash) instead of the defined runtime error."""

import pytest

from tests.helpers.native import built, execute

HUGE = 96 * 1024 * 1024      # bytes of input, far more than the 48 MB address-space cap below

LINE = "padham s\ns ni chaduvu\npodavu(s) ni chupi\n"
TOKEN = "int x\nx ni chaduvu\nx ni chupi\n"
# kind -> (program, input builder). The input is built inside the test: a 96 MB parameter would end up
# in the test id and in PYTEST_CURRENT_TEST, which makes every subprocess fail with E2BIG.
CASES = {
    "line": (LINE, lambda: b"a" * HUGE + b"\n"),
    "token": (TOKEN, lambda: b"1" * HUGE + b"\n"),
    "blank-then-text": (LINE, lambda: b" " * HUGE + b"x\n"),
}


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("kind", list(CASES))
def test_f3_out_of_memory_while_reading_input_is_a_runtime_error(kind, level):
    src, make = CASES[kind]
    with built(src, level) as exe:
        p = execute(exe, make(), timeout=120, max_vmem_mb=48)
    assert p.returncode == 1, p.stderr[-300:]
    assert p.stderr.decode().strip().endswith("devara: runtime error: out of memory")
