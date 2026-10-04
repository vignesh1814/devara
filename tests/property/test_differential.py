"""Hypothesis differential tests: compiled output at -O0 and -O1 must equal the reference interpreter."""
import re
import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from tests.property.proggen import generate
from tests.reference.interp import run_ast
from tests.validation.astutil import ast as parse_ast
from tests.validation.helpers import cli

pytestmark = pytest.mark.slow


def norm(b: bytes) -> bytes:
    return re.sub(rb"-?nan", b"nan", b)


def differential(seed: int, size: int):
    src, stdin = generate(seed, size)
    s = cli("sema", src)
    assert s.rc == 0, f"generator produced a rejected program (seed={seed}):\n{s.err}\n{src}"
    ref = run_ast(parse_ast(src), stdin, max_steps=20_000_000)
    assert ref.status == 0, f"reference interpreter raised runtime error {ref.error!r} for seed {seed}"
    for opt in ("-O0", "-O1"):
        p = cli("run", src, (opt,), stdin)
        assert p.rc == 0, f"seed={seed} {opt}: rc={p.rc}\n{p.err}\n{src}"
        assert norm(p.out) == norm(ref.stdout), f"seed={seed} {opt}: output differs from reference\n{src}"


@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck), derandomize=False)
@given(st.integers(0, 2 ** 32 - 1))
def test_small_programs_match_reference(seed):
    differential(seed, 12)


@settings(max_examples=15, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, 2 ** 32 - 1))
def test_larger_programs_match_reference(seed):
    differential(seed, 60)


@pytest.mark.parametrize("seed", range(25))
def test_fixed_seed_programs_match_reference(seed):
    differential(1000 + seed, 25)
