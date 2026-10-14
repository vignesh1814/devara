"""Hypothesis fuzzing of lexer / parser / semantic analysis through the CLI entry point.

Invariant (master prompt §14): arbitrary input yields exit 0 or 1 with well-formed diagnostics — never exit 3 (ICE),
never a hang, never a Python traceback.  Calls `compiler.cli.main` in-process (same code path as ./devara) for speed.
"""
import contextlib
import os
import io
import random
import signal
import sys

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st, assume

from tests.validation.helpers import WORK, DIAG_RE, ROOT
from tests.validation.corpus_util import programs

pytestmark = pytest.mark.slow
sys.path.insert(0, str(ROOT))
from compiler import cli as devara_cli  # noqa: E402  (entry point under test)

KEYWORDS = ["int", "float", "bool", "char", "padham", "void", "nijam", "abaddham", "ayite", "lekunte", "unnanta", "varaku",
            "prati", "pratisari", "nundi", "modhalu", "lo", "pettu", "ni", "tho", "chaduvu", "chupi", "charya", "ivvu", "aapu", "saagu"]
PUNCT = ["+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=", "&&", "||", "!", "++", "--", "(", ")", "[", "]", "{", "}", ";", ","]
ATOMS = ["x", "y", "a", "f", "i", "n", "0", "1", "42", "0x1F", "075", "3.14", "'c'", "'\\n'", '"s"', '"a\\tb"', "podavu"]
VOCAB = KEYWORDS + PUNCT + ATOMS
BAD_FRAGMENTS = ["@", "$", "'", '"', "'ab'", '"\\q"', "\\", "=", "&", "|", "0x", "1.", ".5", "#c", "\r", "\x00", "\xe9", "~", "`", "?"]

_files = {}


class Hang(Exception):
    pass


def _alarm(signum, frame):
    raise Hang()


def run_cli_inproc(cmd, text: str):
    """Run the CLI entry point in a big-stack thread exactly like `./devara` does (deep nesting needs the stack)."""
    import threading
    path = WORK / f"fuzz_input_{os.getpid()}.tel"
    path.write_bytes(text.encode("latin-1", "replace"))
    box = []

    def target():
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = devara_cli.main([cmd, str(path)])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
        box.append((rc, err.getvalue()))

    old_lim, old_stack = sys.getrecursionlimit(), threading.stack_size()
    sys.setrecursionlimit(200_000)
    for mib in (512, 256, 64, 16):   # Windows rejects the largest sizes (same fallback as compiler/cli.py)
        try:
            threading.stack_size(mib * 1024 * 1024)
            break
        except (ValueError, RuntimeError):
            continue
    try:
        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(30)
        if t.is_alive():
            raise Hang(f"{cmd} did not finish within 30 s on {text[:200]!r}")
    finally:
        sys.setrecursionlimit(old_lim)
        threading.stack_size(old_stack)
    return box[0]


def check_outcome(cmd, src):
    rc, err = run_cli_inproc(cmd, src)
    assert rc in (0, 1), f"{cmd}: exit {rc} (ICE or crash) for input {src!r}\n{err}"
    assert "Traceback" not in err, err
    if rc == 1:
        lines = [l for l in err.splitlines() if l.strip()]
        assert lines and all(DIAG_RE.match(l) for l in lines), f"malformed diagnostics: {err!r}"
    return rc


@settings(max_examples=400, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(st.sampled_from(VOCAB), max_size=60), st.sampled_from([" ", "\n", "  ", "\t"]))
def test_token_soup_never_crashes(toks, sep):
    src = sep.join(toks) + "\n"
    for cmd in ("lex", "parse", "sema"):
        check_outcome(cmd, src)


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(st.sampled_from(VOCAB + BAD_FRAGMENTS), max_size=40))
def test_token_soup_with_bad_fragments(toks):
    src = " ".join(toks) + "\n"
    for cmd in ("lex", "parse", "sema"):
        check_outcome(cmd, src)


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=255), max_size=200))
def test_arbitrary_latin1_text(text):
    for cmd in ("lex", "parse"):
        check_outcome(cmd, text)


@settings(max_examples=100, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="()[]{}\"'\\;,+-*/%<>=!&|#. \n\t0aixnlop", max_size=120))
def test_delimiter_heavy_text(text):
    for cmd in ("lex", "parse", "sema"):
        check_outcome(cmd, text)


CORPUS_TEXTS = [p.read_text() for p in programs()]


def mutate(text: str, rnd: random.Random, n: int) -> str:
    toks = text.split(" ")
    for _ in range(n):
        k = rnd.randrange(7)
        if not toks:
            break
        i = rnd.randrange(len(toks))
        if k == 0:
            del toks[i]
        elif k == 1:
            toks.insert(i, rnd.choice(VOCAB + BAD_FRAGMENTS))
        elif k == 2:
            j = rnd.randrange(len(toks))
            toks[i], toks[j] = toks[j], toks[i]
        elif k == 3:
            toks[i] = rnd.choice(VOCAB)
        elif k == 4:
            toks[i] = toks[i][: rnd.randrange(len(toks[i]) + 1)]
        elif k == 5:
            j = rnd.randrange(len(toks))
            toks.insert(i, toks[j])
        else:
            text2 = " ".join(toks)
            c = rnd.randrange(max(1, len(text2)))
            toks = (text2[:c] + text2[c + rnd.randrange(1, 4):]).split(" ")
    return " ".join(toks)


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, len(CORPUS_TEXTS) - 1), st.integers(0, 2 ** 31), st.integers(1, 6))
def test_mutated_corpus_programs_never_crash(idx, seed, nmut):
    src = mutate(CORPUS_TEXTS[idx], random.Random(seed), nmut)
    for cmd in ("lex", "parse", "sema"):
        check_outcome(cmd, src)


@settings(max_examples=150, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, len(CORPUS_TEXTS) - 1), st.integers(0, 10 ** 6))
def test_truncated_corpus_programs_never_crash(idx, cut):
    t = CORPUS_TEXTS[idx]
    src = t[: cut % (len(t) + 1)]
    for cmd in ("parse", "sema"):
        check_outcome(cmd, src)


@settings(max_examples=100, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(1, 400), st.sampled_from(["(", "[", "{", "-", "!", "f(", "a[", "(int) ", "x ayite { ", "prati i 0 nundi 1 varaku { "]))
def test_deep_nesting_is_controlled(depth, opener):
    close = {"(": ")", "[": "]", "{": "}", "-": "", "!": "", "f(": ")", "a[": "]", "(int) ": "", "x ayite { ": "}",
             "prati i 0 nundi 1 varaku { ": "}"}[opener]
    src = ("x lo " if opener in "([{-!" or opener in ("f(", "a[", "(int) ") else "") + opener * depth + "1" + close * depth + " pettu\n"
    for cmd in ("parse", "sema"):
        check_outcome(cmd, src)


@settings(max_examples=100, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(0, 2 ** 32))
def test_lexer_is_deterministic_and_total(seed):
    rnd = random.Random(seed)
    src = "".join(rnd.choice(["a", "1", " ", "\n", "'", '"', "\\", "#", "0x", ".", "+", "=", "&", "{"]) for _ in range(rnd.randrange(80)))
    a = run_cli_inproc("lex", src)
    b = run_cli_inproc("lex", src)
    assert a == b and a[0] in (0, 1)
