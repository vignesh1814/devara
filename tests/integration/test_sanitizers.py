"""AddressSanitizer + UBSan run of the runtime on padham/array-heavy programs: catches double
frees, use-after-free and out-of-bounds accesses that the live counter alone cannot see.

The runtime is compiled once with ``-fsanitize=address,undefined``; the targeted programs of
test_leaks.py (minus the multi-million-iteration ones) and every corpus program that uses
padham are then linked against it and run at -O0 and -O1. The tests are skipped only when the
toolchain cannot build and run sanitized binaries."""

import inspect
from pathlib import Path

import pytest

from tests.helpers import native
from tests.integration import test_leaks as leaks

pytestmark = pytest.mark.slow

CORPUS = Path(__file__).parent.parent / "corpus"
HEAVY = ("million", "vla_in_loop_body")      # long loops: covered natively by test_leaks.py

LEAK_TESTS = [name for name, fn in inspect.getmembers(leaks, inspect.isfunction)
              if name.startswith("test_") and not any(h in name for h in HEAVY)]


def _expected_exit(tel: Path) -> int:
    f = tel.with_suffix(".exit")
    return int(f.read_text().strip()) if f.exists() else 0


STRING_PROGRAMS = [p for p in sorted(CORPUS.rglob("*.tel"))
                   if _expected_exit(p) == 0 and b"padham" in p.read_bytes()]


@pytest.fixture(scope="module")
def sanitized_runtime(tmp_path_factory):
    rt = native.build_sanitized_runtime(tmp_path_factory.mktemp("asan_rt"))
    if rt is None:
        pytest.skip("AddressSanitizer/UBSan not available in this toolchain")
    old = native.SANITIZED_RT
    native.SANITIZED_RT = rt
    yield rt
    native.SANITIZED_RT = old


def test_there_are_programs_to_sanitize():
    assert len(LEAK_TESTS) >= 10 and len(STRING_PROGRAMS) >= 25


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("name", LEAK_TESTS)
def test_targeted_programs_are_clean_under_asan_ubsan(sanitized_runtime, name, level):
    getattr(leaks, name)(level)


@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("tel", STRING_PROGRAMS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_padham_corpus_is_clean_under_asan_ubsan(sanitized_runtime, tel, level):
    src = tel.read_bytes().decode("latin-1")
    expected = tel.with_suffix(".out").read_bytes() if tel.with_suffix(".out").exists() else b""
    stdin = tel.with_suffix(".in").read_bytes() if tel.with_suffix(".in").exists() else b""
    out, rc, err, live = native.run_stats(src, stdin, level, timeout=60)
    assert rc == 0, err
    assert out == expected
    assert live == 0
