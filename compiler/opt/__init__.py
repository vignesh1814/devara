"""Optimizer driver: verified IR in, verified IR out (design §6)."""

from __future__ import annotations

from compiler.ir.ir import IRModule, clone_module
from compiler.ir.verify import module_context, verify_function, verify_module
from compiler.opt.passes import PIPELINE, prune_literals

MAX_ROUNDS = 12


def optimize(module: IRModule, level: int = 1, *, passes=None) -> IRModule:
    """Return an optimized copy of ``module`` (``level`` 0 only verifies).

    Every pass works on one function at a time, so each function is taken to its own fixed point
    (at most ``MAX_ROUNDS`` rounds) instead of re-running every pass over every function until the
    slowest one settles. The verifier still runs after each pass that changed a function (on that
    function only), and the whole module is verified once more at the end (plan §F).
    """
    verify_module(module)
    out = clone_module(module)
    if level <= 0:
        return out
    pipeline = passes if passes is not None else PIPELINE
    ctx = module_context(out)
    for f in out.functions:
        for _ in range(MAX_ROUNDS):
            changed = False
            for _name, fn_pass in pipeline:
                if fn_pass(f):
                    changed = True
                    verify_function(f, ctx)
            if not changed:
                break
    prune_literals(out)
    verify_module(out)
    return out
