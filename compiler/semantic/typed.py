"""The typed tree produced by semantic analysis (plan §F).

Every expression carries a semantic ``type``; every implicit conversion is an
explicit :class:`TConvert`; every name is a symbol id into
:attr:`TypedProgram.symbols`; loop-control statements name their target loop.
The tree is a pure tree (symbols are referenced by id) so it serializes to JSON.

Stable JSON contract (``devara sema --json``): the envelope's ``data`` is one
``TypedProgram`` object; see ``docs/STAGE_FORMATS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from compiler.ast.nodes import BinaryOp
from compiler.diagnostics import Span
from compiler.semantic.types import ArrayType, FuncType, PrimType

__all__ = [
    "Symbol", "TNode", "TExpr", "TLiteral", "TVar", "TIndex", "TStringIndex",
    "TUnary", "TBinary", "TConvert", "TCall", "TStmt", "TBlock", "TDecl",
    "TAssign", "TInput", "TOutput", "TIncDec", "TIf", "TWhile", "TRange", "TFor",
    "TBreak", "TContinue", "TReturn", "TExprStmt", "TFunction", "TypedProgram",
    "ENTRY_OWNER",
]

ENTRY_OWNER = "__entry"


@dataclass
class Symbol:
    id: int
    name: str
    kind: str                # variable | parameter | function | builtin
    type: PrimType | ArrayType | FuncType
    scope_depth: int
    is_global: bool
    owner: str               # defining function name, ENTRY_OWNER, or "" for globals/functions
    span: Span | None


@dataclass
class TNode:
    span: Span


# ── Expressions ──

@dataclass
class TExpr(TNode):
    type: PrimType | ArrayType | FuncType


@dataclass
class TLiteral(TExpr):
    """int/char -> int, float -> float, bool -> bool, padham -> bytes."""

    value: int | float | bool | bytes


@dataclass
class TVar(TExpr):
    symbol: int


@dataclass
class TIndex(TExpr):
    """``a[i][j]``: element lvalue when len(indices)==rank, else a partial view."""

    symbol: int
    indices: list[TExpr]


@dataclass
class TStringIndex(TExpr):
    """``s[i]`` on a padham: an rvalue ``char`` (runtime bounds-checked)."""

    string: TExpr
    index: TExpr


@dataclass
class TUnary(TExpr):
    op: str                  # NEG | NOT   (unary plus is a plain promotion)
    operand: TExpr


@dataclass
class TBinary(TExpr):
    op: BinaryOp
    left: TExpr
    right: TExpr


@dataclass
class TConvert(TExpr):
    """Conversion of ``operand`` to ``type`` (arithmetic<->arithmetic, char<->padham)."""

    operand: TExpr
    explicit: bool


@dataclass
class TCall(TExpr):
    callee: int
    args: list[TExpr]


# ── Statements ──

@dataclass
class TStmt(TNode):
    pass


@dataclass
class TBlock(TStmt):
    stmts: list[TStmt]


@dataclass
class TDecl(TStmt):
    symbol: int
    dims: list[TExpr]        # int-typed dimension expressions (array declarations)


@dataclass
class TAssign(TStmt):
    target: TExpr            # TVar | TIndex(full)
    value: TExpr             # already converted to the target's type


@dataclass
class TInput(TStmt):
    target: TExpr


@dataclass
class TOutput(TStmt):
    value: TExpr


@dataclass
class TIncDec(TStmt):
    target: TExpr
    delta: int               # +1 or -1
    prefix: bool


@dataclass
class TIf(TStmt):
    condition: TExpr         # bool
    then_block: TBlock
    else_block: TBlock | None


@dataclass
class TWhile(TStmt):
    loop_id: int
    condition: TExpr         # bool
    body: TBlock


@dataclass
class TRange(TStmt):
    loop_id: int
    variable: int
    start: TExpr             # int
    end: TExpr               # int
    body: TBlock


@dataclass
class TFor(TStmt):
    loop_id: int
    init: list[TStmt]        # executed once in the loop scope
    condition: TExpr         # bool
    update: TStmt            # TAssign | TIncDec
    body: TBlock


@dataclass
class TBreak(TStmt):
    loop_id: int


@dataclass
class TContinue(TStmt):
    loop_id: int


@dataclass
class TReturn(TStmt):
    value: TExpr | None      # converted to the function's return type


@dataclass
class TExprStmt(TStmt):
    call: TCall


# ── Program ──

@dataclass
class TFunction(TNode):
    symbol: int
    name: str
    params: list[int]
    ret: PrimType
    body: TBlock


@dataclass
class TypedProgram(TNode):
    symbols: list[Symbol]
    globals: list[int]       # global variable symbol ids in declaration order
    functions: list[TFunction]
    entry: TBlock            # top-level statements (incl. global declarations) in source order
