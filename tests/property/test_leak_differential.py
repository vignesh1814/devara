"""Generated programs (tests/property/proggen.py, padham- and array-heavy) must produce the
reference interpreter's output and leave nothing live at exit, at -O0 and -O1."""

import re

import pytest

from tests.helpers import native
from tests.helpers.ref import ref_run
from tests.property.proggen import generate

pytestmark = pytest.mark.slow


def norm(b: bytes) -> bytes:
    return re.sub(rb"-?nan", b"nan", b)      # the NaN sign is hardware-defined (Q-004)


@pytest.mark.parametrize("seed", range(5000, 5040))
def test_generated_program_matches_reference_and_leaks_nothing(seed):
    src, stdin = generate(seed, 60)
    ref = ref_run(src, stdin)
    assert ref.status == 0, ref.error        # these seeds were checked: no runtime error, no step limit
    for level in (0, 1):
        out, rc, err, live = native.run_stats(src, stdin, level, timeout=60)
        assert rc == 0, err
        assert norm(out) == norm(ref.stdout)
        assert live == 0, f"-O{level}: {live} allocation(s) still live"
