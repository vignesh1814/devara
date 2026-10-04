"""Semantic analysis (Stage 3): symbols, types, conversions, flow checks."""

from __future__ import annotations

from compiler.ast.nodes import Program
from compiler.diagnostics import Diagnostic
from compiler.semantic import flow
from compiler.semantic.checker import Checker
from compiler.semantic.typed import Symbol, TypedProgram
from compiler.serialize import format_tree

__all__ = ["analyze", "format_typed", "TypedProgram", "Symbol"]


def analyze(program: Program, filename: str = "<stdin>") -> tuple[TypedProgram | None, list[Diagnostic]]:
    """Check ``program``; returns ``(typed_tree, [])`` or ``(None, diagnostics)``."""
    ck = Checker(filename)
    typed = ck.run(program)
    diags = list(ck.diags)
    if not diags:
        diags.extend(flow.analyze_entry(typed.entry, typed.symbols, filename))
    diags.sort(key=lambda d: (d.line, d.column, str(d.category)))
    if diags:
        return None, diags
    return typed, []


def format_typed(typed: TypedProgram) -> str:
    lines = ["symbols:"]
    for s in typed.symbols:
        where = "global" if s.is_global else (s.owner or "-")
        lines.append(f"  #{s.id} {s.kind} {s.name}: {s.type.compact()}  [depth {s.scope_depth}, {where}]")
    lines.append("")
    lines.append("functions:")
    lines.append(format_tree(typed.functions, spans=False))
    lines.append("")
    lines.append("entry:")
    lines.append(format_tree(typed.entry, spans=False))
    return "\n".join(lines)
