"""Randomized-AST testing of the middle and back end (no lexer/parser involved).

Real corpus ASTs are structurally mutated (operators, types, literal kinds, identifiers, dropped /
duplicated / swapped statements, call arities) and fed straight into sema -> lower -> optimize ->
both code generators. Invariants, for every mutant:

  * no stage raises: sema must answer with diagnostics or a typed tree;
  * if sema accepts, the IR verifies (before and after -O1; `optimize` verifies internally);
  * -O0 and -O1 IR agree on stdout / exit status / message whenever neither hits the step limit;
  * both assembly generators accept the module.

Seeds are fixed so a failure is reproducible with `-k "seed-<n>"`. Raise DEVARA_AST_MUTANTS to soak.
"""

from __future__ import annotations

import copy
import os
import random
from pathlib import Path

import pytest

from compiler import driver
from compiler.ast import nodes as N
from compiler.ir.verify import check_module
from compiler.opt import optimize
from tests.helpers.irinterp import Interp

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = int(os.environ.get("DEVARA_AST_MUTANTS", "250"))
STEP_LIMIT = 150_000
LITERALS = [
    (N.LiteralKind.INTEGER, "0"), (N.LiteralKind.INTEGER, "1"), (N.LiteralKind.INTEGER, "2147483648"),
    (N.LiteralKind.INTEGER, "9223372036854775807"), (N.LiteralKind.INTEGER, "0x7F"),
    (N.LiteralKind.FLOAT, "1.5"), (N.LiteralKind.FLOAT, "0.0"), (N.LiteralKind.CHAR, "'a'"),
    (N.LiteralKind.STRING, '"s"'), (N.LiteralKind.STRING, '""'), (N.LiteralKind.BOOL, "nijam"),
    (N.LiteralKind.BOOL, "abaddham"),
]
NAMES = ["x", "y", "i", "n", "a", "main", "f", "undefined_name"]

_cache: dict[Path, tuple[N.Program, bytes]] = {}


def _corpus() -> list[Path]:
    return sorted((ROOT / "tests" / "corpus").glob("*/*.tel")) + sorted((ROOT / "examples").glob("*.tel"))


def _load(path: Path):
    if path not in _cache:
        toks, d = driver.run_lex(driver.decode_source(path.read_bytes()), path.name)
        assert not d
        prog, d = driver.run_parse(toks, path.name)
        assert not d
        stdin_file = path.with_suffix(".in")
        _cache[path] = (prog, stdin_file.read_bytes() if stdin_file.exists() else b"")
    return _cache[path]


def _walk(node):
    yield node
    for c in N.children(node):
        yield from _walk(c)


def _mutate_once(rng: random.Random, program: N.Program) -> None:
    nodes = list(_walk(program))
    node = rng.choice(nodes)
    if isinstance(node, N.BinaryExpression):
        if rng.random() < 0.5:
            node.operator = rng.choice(list(N.BinaryOp))
        else:
            node.left, node.right = node.right, node.left
    elif isinstance(node, N.UnaryExpression):
        node.operator = rng.choice(list(N.UnaryOp))
    elif isinstance(node, N.Literal):
        # kind and lexeme must stay consistent: the lexer can never produce a mismatched pair
        node.kind, node.lexeme = rng.choice(LITERALS)
    elif isinstance(node, N.Identifier):
        node.name = rng.choice(NAMES)
    elif isinstance(node, N.TypeSyntax):
        node.primitive = rng.choice(list(N.PrimitiveType))
    elif isinstance(node, N.FunctionCall):
        if node.arguments and rng.random() < 0.5:
            node.arguments.pop(rng.randrange(len(node.arguments)))
        elif node.arguments:
            node.arguments.append(copy.deepcopy(rng.choice(node.arguments)))
    elif isinstance(node, N.CastExpression):
        node.target_type.primitive = rng.choice(list(N.PrimitiveType))
    elif isinstance(node, N.ArrayAccess):
        if len(node.indices) > 1 and rng.random() < 0.5:
            node.indices.pop()
        else:
            node.indices.append(copy.deepcopy(rng.choice(node.indices)))
    elif isinstance(node, N.Block) and node.statements:
        k = rng.randrange(3)
        i = rng.randrange(len(node.statements))
        if k == 0:
            node.statements.pop(i)
        elif k == 1:
            node.statements.insert(i, copy.deepcopy(node.statements[i]))
        elif len(node.statements) > 1:
            j = rng.randrange(len(node.statements))
            node.statements[i], node.statements[j] = node.statements[j], node.statements[i]


def _run(module, stdin: bytes):
    try:
        return Interp(module, stdin).run(step_limit=STEP_LIMIT)
    except Exception as exc:  # RuntimeFailure("step limit exceeded") and friends
        return (b"", -1, f"{type(exc).__name__}: {exc}")


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(MUTANTS), ids=lambda s: f"seed-{s}")
def test_mutated_ast_never_crashes_and_levels_agree(seed):
    rng = random.Random(f"ast-{seed}")
    corpus = _corpus()
    path = corpus[rng.randrange(len(corpus))]
    original, stdin = _load(path)
    program = copy.deepcopy(original)
    for _ in range(rng.randint(1, 3)):
        _mutate_once(rng, program)

    typed, diags = driver.run_sema(program, path.name)     # must not raise
    if diags:
        assert all(str(d) for d in diags)
        return
    module = driver.run_lower(typed)
    assert check_module(module) == []
    o0, o1 = optimize(module, 0), optimize(module, 1)       # verify before + after every pass
    assert check_module(o0) == [] and check_module(o1) == []
    for level, m in ((0, o0), (1, o1)):
        driver.run_codegen(m, level=level)                  # both back ends accept it

    r0, r1 = _run(o0, stdin), _run(o1, stdin)
    if "step limit" in r0[2] or "step limit" in r1[2]:
        return                                              # a mutant may loop forever; only compare terminating runs
    assert r0 == r1, f"{path.name} seed {seed}: -O0 {r0!r} != -O1 {r1!r}"
