"""The programs shown in README.md (examples/*.tel) produce the output the README claims, at -O0 and -O1, and agree
with the reference interpreter."""
from pathlib import Path

import pytest

from tests.validation.stress_util import check_against_reference

EXAMPLES = Path(__file__).parent.parent.parent / "examples"

CASES = [
    ("hello.tel", b"", b"Hello, Devara!\n"),
    ("example.tel", b"", b"15\n"),
    ("squares.tel", b"4\n", b"sum of squares:\n30\n"),
    ("fizzbuzz.tel", b"", b"1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz\n"),
    ("primes.tel", b"30\n", b"2\n3\n5\n7\n11\n13\n17\n19\n23\n29\n"),
    ("sort.tel", b"6\n5 2 9 1 7 3\n", b"1\n2\n3\n5\n7\n9\n"),
]


@pytest.mark.parametrize("name,stdin,expected", CASES, ids=[c[0] for c in CASES])
def test_example_output(name, stdin, expected):
    src = (EXAMPLES / name).read_bytes().decode("latin-1")
    ref = check_against_reference(src, stdin, expect_status=0)
    assert ref.stdout == expected
