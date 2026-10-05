"""Optimizer driver: verified IR in, verified IR out (design §6)."""

from __future__ import annotations

import copy

from compiler.ir.ir import IRModule
from compiler.ir.verify import verify_module
from compiler.opt.passes import PIPELINE, prune_literals

MAX_ROUNDS = 12


def optimize(module: IRModule, level: int = 1, *, passes=None) -> IRModule:
    """Return an optimized copy of ``module`` (``level`` 0 only verifies)."""
    verify_module(module)
    out = copy.deepcopy(module)
    if level <= 0:
        return out
    pipeline = passes if passes is not None else PIPELINE
    for _ in range(MAX_ROUNDS):
        changed = False
        for _name, fn_pass in pipeline:
            for f in out.functions:
                if fn_pass(f):
                    changed = True
            verify_module(out)       # re-run after every pass (plan §F)
        if not changed:
            break
    if prune_literals(out):
        verify_module(out)
    return out
