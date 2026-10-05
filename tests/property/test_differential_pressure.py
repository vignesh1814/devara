"""Hypothesis differential tests in the high-register-pressure mode of the program generator
(tests/property/proggen.py, `generate(..., pressure=True)`): 10-26 parameter functions, 10-22 simultaneously live
locals of every type, deep expression trees, loops inside functions, every local read again after the calls.

-O0 output == -O1 output == reference interpreter (stdout bytes up to NaN sign, exit status 0)."""
import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from tests.property.proggen import generate
from tests.reference.interp import run_ast
from tests.validation.astutil import ast as parse_ast
from tests.validation.helpers import cli
from tests.validation.stress_util import norm

pytestmark = pytest.mark.slow


def differential(seed: int, size: int):
    src, stdin = generate(seed, size, pressure=True)
    s = cli("sema", src)
    assert s.rc == 0, f"pressure generator produced a rejected program (seed={seed}):\n{s.err}\n{src}"
    ref = run_ast(parse_ast(src), stdin, max_steps=60_000_000)
    assert ref.status == 0, f"reference interpreter raised runtime error {ref.error!r} for seed {seed}"
    outs = {}
    for opt in ("-O0", "-O1"):
        p = cli("run", src, (opt,), stdin)
        assert p.rc == 0, f"seed={seed} {opt}: rc={p.rc}\n{p.err}\n{src}"
        assert norm(p.out) == norm(ref.stdout), f"seed={seed} size={size} {opt}: output differs from reference\n{src}"
        outs[opt] = p.out
    assert norm(outs["-O0"]) == norm(outs["-O1"]), f"seed={seed}: -O0 and -O1 disagree"


@pytest.mark.parametrize("seed", range(40))
def test_pressure_fixed_seeds(seed):
    differential(5000 + seed, 10)


def test_pressure_regression_seed_276_signed_zero_join():
    differential(276, 6)     # F-006: -O1 merged 0.0 and -0.0 constants at a loop join


@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, 2 ** 32 - 1))
def test_pressure_small_programs_match_reference(seed):
    differential(seed, 6)


@settings(max_examples=15, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, 2 ** 32 - 1))
def test_pressure_larger_programs_match_reference(seed):
    differential(seed, 30)


def test_pressure_generator_is_deterministic_and_default_mode_unchanged():
    a = generate(77, 12, pressure=True)
    assert a == generate(77, 12, pressure=True)
    assert generate(77, 12) == generate(77, 12, pressure=False)
    assert a != generate(77, 12)
    # the pressure mode really is wide: at least one function with >= 10 parameters
    import re
    assert any(len(m.split(",")) >= 10 for m in re.findall(r"charya \(([^)]*)\)", a[0]))
