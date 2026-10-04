"""Deterministic mutation fuzzing of the whole front/middle end: the compiler may report
diagnostics but must never crash, produce unverifiable IR, or let O1 change behavior."""

import glob
import random
from pathlib import Path

import pytest

from compiler import driver
from compiler.ir.verify import verify_module
from compiler.opt import optimize
from tests.helpers.irinterp import Interp

ROOT = Path(__file__).parent.parent.parent
FILES = sorted(glob.glob(str(ROOT / "tests/corpus/**/*.tel"), recursive=True)
               + glob.glob(str(ROOT / "tests/programs/**/*.tel"), recursive=True))
INSERTS = ["1", "x", "(", ")", "{", "}", "[", "]", "+", "lo", "pettu", "ni", "chupi", "ayite", "0", "nijam",
           '"s"', "'c'", "int", "float", "prati", "2.5", "-", "%", "/", "&&", "++", ";", "ivvu", "aapu"]


def mutate(rng: random.Random, tokens: list[str]) -> str:
    toks = list(tokens)
    for _ in range(rng.randint(0, 3)):
        if not toks:
            break
        i = rng.randrange(len(toks))
        op = rng.choice(["del", "dup", "swap", "ins"])
        if op == "del":
            del toks[i]
        elif op == "dup":
            toks.insert(i, toks[i])
        elif op == "swap":
            j = rng.randrange(len(toks))
            toks[i], toks[j] = toks[j], toks[i]
        else:
            toks.insert(i, rng.choice(INSERTS))
    return (" " if rng.random() < 0.5 else "\n").join(toks)


@pytest.mark.parametrize("seed", range(4))
def test_mutated_programs_never_crash_the_compiler(seed):
    rng = random.Random(1000 + seed)
    ran = 0
    for _ in range(60):
        path = rng.choice(FILES)
        src = Path(path).read_bytes().decode("latin-1")
        base, _ = driver.run_lex(src, "f")
        text = mutate(rng, [t.lexeme for t in base if t.lexeme])
        toks, d = driver.run_lex(text, "f")
        if d:
            continue
        prog, d = driver.run_parse(toks, "f")           # must not raise
        if d:
            assert all(x.stage == "syntax" for x in d)
            continue
        typed, d = driver.run_sema(prog, "f")           # must not raise
        if d:
            assert all(x.stage == "semantic" for x in d)
            continue
        m = driver.run_lower(typed)
        m0, m1 = optimize(m, 0), optimize(m, 1)
        verify_module(m0)
        verify_module(m1)
        stdin = b"3 5 7 11 13 17 19 23\n" * 4
        try:
            r0 = Interp(m0, stdin).run(100_000)
            r1 = Interp(m1, stdin).run(100_000)
        except (IndexError, TypeError, AttributeError, KeyError, RecursionError):
            continue            # out-of-bounds / runaway recursion in the *source program* (UB, L32/P38)
        if "step limit" in r0[2] or "step limit" in r1[2]:
            continue
        assert r0 == r1, (path, text)
        ran += 1


def test_lexer_and_parser_survive_random_byte_soup():
    rng = random.Random(7)
    alphabet = list(" \t\n\r(){}[];,+-*/%<>=!&|\"'\\#.0123456789abcxyz_") + ["ayite", "lo", "pettu", "int", "\x00", "\xff"]
    for _ in range(300):
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 80)))
        toks, d = driver.run_lex(s, "f")
        if not d:
            driver.run_parse(toks, "f")
