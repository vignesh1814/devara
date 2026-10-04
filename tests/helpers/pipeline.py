"""Test helpers: compile Devara source through the stages."""

from __future__ import annotations

from compiler import driver
from compiler.opt import optimize
from tests.helpers.irinterp import run_module


def to_typed(src: str, name: str = "t.tel"):
    toks, d = driver.run_lex(src, name)
    assert not d, [str(x) for x in d]
    prog, d = driver.run_parse(toks, name)
    assert not d, [str(x) for x in d]
    typed, d = driver.run_sema(prog, name)
    assert not d, [str(x) for x in d]
    return typed


def to_ir(src: str, level: int = 0):
    m = driver.run_lower(to_typed(src))
    return optimize(m, level)


def run_ir(src: str, stdin: bytes = b"", level: int = 0):
    return run_module(to_ir(src, level), stdin)
