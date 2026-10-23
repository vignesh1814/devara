"""Browser entry point: run Devara source without a C toolchain, threads or a subprocess.

The playground (``playground/``) loads this package into Pyodide and calls :func:`run` / :func:`stage`.
Pipeline: lex -> parse -> sema (full diagnostics, exactly as ``devara run``) -> the independent reference
interpreter (``compiler.interp``), which is the same engine as ``devara debug``.  Nothing here touches the
filesystem, ``subprocess`` or ``threading``, so it also works in any restricted Python host.

Every function returns plain JSON-serialisable data.
"""

from __future__ import annotations

import sys
import time

DEFAULT_MAX_STEPS = 5_000_000
# Pyodide's WASM stack is small: stay well below the point where the engine itself would overflow.
RECURSION_LIMIT = 6000


def _decode(source: str) -> str:
    from compiler import driver

    return driver.decode_source(source.encode("utf-8"))


def _front_end(source: str, filename: str):
    """(program, typed, diagnostics as strings). Stops at the first failing stage, like the CLI."""
    from compiler import driver

    text = _decode(source)
    toks, diags = driver.run_lex(text, filename)
    if diags:
        return None, None, diags
    program, diags = driver.run_parse(toks, filename)
    if diags:
        return None, None, diags
    typed, diags = driver.run_sema(program, filename)
    return program, typed, diags


def _diag(d) -> dict:
    span = getattr(d, "span", None)
    return {
        "line": getattr(span, "start_line", None) if span else None,
        "column": getattr(span, "start_column", None) if span else None,
        "text": str(d),
    }


def check(source: str, filename: str = "main.tel") -> dict:
    """Diagnostics only (no execution)."""
    _, _, diags = _front_end(source, filename)
    return {"diagnostics": [_diag(d) for d in diags]}


def run(source: str, stdin: str = "", max_steps: int = DEFAULT_MAX_STEPS, filename: str = "main.tel",
        recursion_limit: int = RECURSION_LIMIT) -> dict:
    """Compile-check and interpret ``source``.

    Result keys: ``ok`` (ran to completion), ``status`` (0 ok, 1 compile/runtime error, 124 step limit,
    125 stack limit), ``output`` (stdout text), ``error`` (runtime error message or ""), ``diagnostics``
    (list of {line, column, text}), ``ms`` and ``steps``. ``recursion_limit`` is the Python frame limit
    (about 6 frames per Devara call).
    """
    from compiler import interp, serialize

    started = time.perf_counter()
    program, _typed, diags = _front_end(source, filename)
    if diags:
        return {"ok": False, "status": 1, "output": "", "error": "", "diagnostics": [_diag(d) for d in diags],
                "ms": round((time.perf_counter() - started) * 1000), "steps": 0}

    data = serialize.to_data(program)
    it = interp.Interp(stdin.encode("utf-8"), max_steps)
    status, error = 0, ""
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(1000, int(recursion_limit)))
    try:
        it.run_program(data)
    except interp.RuntimeErr as e:
        status, error = 1, str(e)
    except interp.StepLimit:
        status, error = 124, f"step limit exceeded ({max_steps:,} steps): possible infinite loop"
    except RecursionError:
        status, error = 125, "stack overflow: recursion too deep for the playground"
    finally:
        sys.setrecursionlimit(old_limit)
    return {
        "ok": status == 0,
        "status": status,
        "output": bytes(it.out).decode("utf-8", errors="replace"),
        "error": error,
        "diagnostics": [],
        "ms": round((time.perf_counter() - started) * 1000),
        "steps": it.steps,
    }


def stage(source: str, which: str, filename: str = "main.tel") -> dict:
    """Text of an intermediate stage: ``tokens``, ``ast``, ``ir`` or ``opt``. For the playground's inspector tabs."""
    from compiler import driver, serialize

    if which == "tokens":
        toks, diags = driver.run_lex(_decode(source), filename)
        if diags:
            return {"text": "", "diagnostics": [_diag(d) for d in diags]}
        return {"text": "\n".join(f"{t.line}:{t.column}\t{t.type.value}\t{t.lexeme!r}" for t in toks), "diagnostics": []}

    program, typed, diags = _front_end(source, filename)
    if diags:
        return {"text": "", "diagnostics": [_diag(d) for d in diags]}
    if which == "ast":
        return {"text": serialize.format_tree(program, spans=False), "diagnostics": []}
    from compiler.ir.printer import format_module

    module = driver.run_lower(typed)
    if which == "opt":
        module = driver.run_opt(module, 1)
    elif which != "ir":
        raise ValueError(f"unknown stage {which!r}")
    return {"text": format_module(module), "diagnostics": []}


_PUBLIC = {"run": run, "check": check, "stage": stage}


def dispatch(name: str, args_json: str) -> str:
    """JSON in, JSON out: the single function the browser worker calls (``name`` is run / check / stage)."""
    import json

    try:
        fn = _PUBLIC[name]
    except KeyError:
        return json.dumps({"fatal": f"unknown function {name!r}"})
    try:
        return json.dumps(fn(*json.loads(args_json)))
    except Exception as exc:  # an internal compiler error must reach the page as data, never as a worker crash
        return json.dumps({"fatal": f"internal compiler error: {type(exc).__name__}: {exc}"})
