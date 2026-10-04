"""Definite-initialization (P24) and return-path (P25) analysis over the typed tree."""

from __future__ import annotations

from compiler.diagnostics import Diagnostic, SemCategory as S, Span
from compiler.semantic import typed as T
from compiler.semantic.types import ArrayType, VOID

ALL = None  # "unreachable": every variable counts as assigned


def _meet(a, b):
    if a is ALL:
        return b
    if b is ALL:
        return a
    return a & b


def is_const_true(cond: T.TExpr) -> bool:
    """Literal ``nijam`` or a non-zero int literal (through implicit conversions)."""
    while isinstance(cond, T.TConvert):
        cond = cond.operand
    return isinstance(cond, T.TLiteral) and not isinstance(cond.value, (bytes, float)) and bool(cond.value)


class _Init:
    def __init__(self, symbols: list[T.Symbol], filename: str) -> None:
        self.symbols = symbols
        self.filename = filename
        self.diags: list[Diagnostic] = []
        self.breaks: dict[int, list] = {}
        self.continues: dict[int, list] = {}
        self.reported: set[tuple[int, int, int]] = set()

    def tracked(self, sid: int) -> bool:
        s = self.symbols[sid]
        return (
            s.kind == "variable" and not s.is_global and not isinstance(s.type, ArrayType)
        )

    # expressions: reads only (assignment is statement-only)
    def reads(self, e: T.TExpr, st):
        if isinstance(e, T.TVar):
            if st is not ALL and self.tracked(e.symbol) and e.symbol not in st:
                key = (e.span.start_line, e.span.start_column, e.symbol)
                if key not in self.reported:
                    self.reported.add(key)
                    name = self.symbols[e.symbol].name
                    self.diags.append(Diagnostic(
                        "semantic", S.UNINITIALIZED,
                        f"variable '{name}' may be used before it is initialized",
                        e.span, self.filename))
                st = st | {e.symbol}
            return st
        if isinstance(e, T.TLiteral):
            return st
        if isinstance(e, T.TIndex):
            for i in e.indices:
                st = self.reads(i, st)
            return st
        if isinstance(e, T.TStringIndex):
            st = self.reads(e.string, st)
            return self.reads(e.index, st)
        if isinstance(e, T.TUnary):
            return self.reads(e.operand, st)
        if isinstance(e, T.TConvert):
            return self.reads(e.operand, st)
        if isinstance(e, T.TBinary):
            st = self.reads(e.left, st)
            return self.reads(e.right, st)
        if isinstance(e, T.TCall):
            for a in e.args:
                st = self.reads(a, st)
            return st
        raise AssertionError(type(e))

    def target_effect(self, target: T.TExpr, st, *, also_reads: bool = False):
        if isinstance(target, T.TVar):
            if also_reads:
                st = self.reads(target, st)
            if st is not ALL and self.tracked(target.symbol):
                st = st | {target.symbol}
            return st
        return self.reads(target, st)  # TIndex: index expressions are read

    def block(self, b: T.TBlock, st):
        for s in b.stmts:
            st = self.stmt(s, st)
        return st

    def stmt(self, s: T.TStmt, st):
        if isinstance(s, T.TBlock):
            return self.block(s, st)
        if isinstance(s, T.TDecl):
            for d in s.dims:
                st = self.reads(d, st)
            if st is not ALL and s.symbol in st:
                st = st - {s.symbol}
            return st
        if isinstance(s, T.TAssign):
            if isinstance(s.target, T.TIndex):
                st = self.reads(s.target, st)
            st = self.reads(s.value, st)
            if isinstance(s.target, T.TVar):
                st = self.target_effect(s.target, st)
            return st
        if isinstance(s, T.TInput):
            return self.target_effect(s.target, st)
        if isinstance(s, T.TOutput):
            return self.reads(s.value, st)
        if isinstance(s, T.TIncDec):
            return self.target_effect(s.target, st, also_reads=True)
        if isinstance(s, T.TExprStmt):
            return self.reads(s.call, st)
        if isinstance(s, T.TIf):
            st = self.reads(s.condition, st)
            a = self.block(s.then_block, st)
            b = self.block(s.else_block, st) if s.else_block is not None else st
            return _meet(a, b)
        if isinstance(s, T.TWhile):
            self.breaks[s.loop_id] = []
            self.continues[s.loop_id] = []
            st = self.reads(s.condition, st)
            self.block(s.body, st)
            return self.loop_exit(s.loop_id, s.condition, st)
        if isinstance(s, T.TRange):
            self.breaks[s.loop_id] = []
            self.continues[s.loop_id] = []
            st = self.reads(s.start, st)
            st = self.reads(s.end, st)
            inner = st if st is ALL else st | {s.variable}
            self.block(s.body, inner)
            return st
        if isinstance(s, T.TFor):
            self.breaks[s.loop_id] = []
            self.continues[s.loop_id] = []
            for i in s.init:
                st = self.stmt(i, st)
            st = self.reads(s.condition, st)
            end = self.block(s.body, st)
            at_update = end
            for c in self.continues[s.loop_id]:
                at_update = _meet(at_update, c)
            self.stmt(s.update, at_update)
            return self.loop_exit(s.loop_id, None, st)
        if isinstance(s, T.TBreak):
            self.breaks[s.loop_id].append(st)
            return ALL
        if isinstance(s, T.TContinue):
            self.continues[s.loop_id].append(st)
            return ALL
        if isinstance(s, T.TReturn):
            if s.value is not None:
                self.reads(s.value, st)
            return ALL
        raise AssertionError(type(s))

    def loop_exit(self, loop_id: int, cond, st_after_cond):
        """State after a loop: after-condition, except constant-true ``while``."""
        if cond is not None and is_const_true(cond):
            out = ALL
            for b in self.breaks[loop_id]:
                out = _meet(out, b)
            return out
        return st_after_cond


class _Returns:
    """P25: does a statement list complete normally?"""

    def __init__(self) -> None:
        self.has_break: set[int] = set()

    def scan_breaks(self, s: T.TStmt) -> None:
        if isinstance(s, T.TBreak):
            self.has_break.add(s.loop_id)
        elif isinstance(s, T.TBlock):
            for x in s.stmts:
                self.scan_breaks(x)
        elif isinstance(s, T.TIf):
            self.scan_breaks(s.then_block)
            if s.else_block:
                self.scan_breaks(s.else_block)
        elif isinstance(s, (T.TWhile, T.TRange)):
            self.scan_breaks(s.body)
        elif isinstance(s, T.TFor):
            self.scan_breaks(s.body)

    def completes(self, stmts: list[T.TStmt]) -> bool:
        return all(self.stmt_completes(s) for s in stmts)

    def stmt_completes(self, s: T.TStmt) -> bool:
        if isinstance(s, T.TReturn):
            return False
        if isinstance(s, T.TBlock):
            return self.completes(s.stmts)
        if isinstance(s, T.TIf):
            if s.else_block is None:
                return True
            return self.completes(s.then_block.stmts) or self.completes(s.else_block.stmts)
        if isinstance(s, T.TWhile) and is_const_true(s.condition):
            return s.loop_id in self.has_break
        return True


def analyze_function(fn: T.TFunction, symbols: list[T.Symbol], name_span: Span,
                     filename: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    init = _Init(symbols, filename)
    init.block(fn.body, frozenset(fn.params))
    diags.extend(init.diags)
    if fn.ret != VOID:
        r = _Returns()
        r.scan_breaks(fn.body)
        if r.completes(fn.body.stmts):
            diags.append(Diagnostic(
                "semantic", S.MISSING_RETURN,
                f"function '{fn.name}' may reach its end without returning a value",
                name_span, filename))
    return diags


def analyze_entry(entry: T.TBlock, symbols: list[T.Symbol], filename: str) -> list[Diagnostic]:
    init = _Init(symbols, filename)
    init.block(entry, frozenset())
    return init.diags
