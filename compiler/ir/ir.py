"""Typed three-address IR with an explicit CFG (design §5).

Non-SSA: scalar source variables and temporaries are mutable virtual registers
(:class:`Reg`); memory (arrays, global scalars) is accessed only through
``load``/``store`` on ``addr`` operands. Every block ends in exactly one
terminator. All element/value slots are 8 bytes (plan §D).
"""

from __future__ import annotations

import copy

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "IRType", "Const", "Reg", "GlobalRef", "Operand", "Instr", "Copy", "UnOp", "BinOp",
    "Cmp", "Convert", "Load", "Store", "PtrAdd", "NewArray", "Call", "RtCall",
    "Terminator", "Jump", "Branch", "Return", "BasicBlock", "IRFunction", "IRGlobal",
    "IRModule", "ENTRY_FUNCTION", "clone_function", "clone_module",
]

ENTRY_FUNCTION = "$entry"


class IRType(StrEnum):
    I64 = "i64"
    F64 = "f64"
    BOOL = "bool"
    CHAR = "char"
    STR = "str"
    ADDR = "addr"
    VOID = "void"


@dataclass(frozen=True)
class Const:
    type: IRType
    value: int | float | bool | bytes


@dataclass(frozen=True)
class Reg:
    name: str
    type: IRType


@dataclass(frozen=True)
class GlobalRef:
    """Address of a module global's storage (type ``addr``)."""

    name: str


Operand = Const | Reg | GlobalRef


# ── Instructions ──

# Source line a (debug build) instruction came from. Never serialized, printed or compared: it only feeds the
# `.loc` directives of `devara build -g` and does not take part in what the IR means.
_LINE = dict(default=0, kw_only=True, compare=False, repr=False, metadata={"debug": True})


@dataclass
class Instr:
    line: int = field(**_LINE)


@dataclass
class Copy(Instr):
    dst: Reg
    src: Operand


@dataclass
class UnOp(Instr):
    op: str            # NEG (i64|f64) | NOT (bool)
    dst: Reg
    src: Operand


@dataclass
class BinOp(Instr):
    op: str            # ADD SUB MUL DIV MOD; type = dst.type (i64 | f64)
    dst: Reg
    a: Operand
    b: Operand


@dataclass
class Cmp(Instr):
    cond: str          # LT LE GT GE EQ NE; operands i64 | f64 | str (EQ/NE only)
    dst: Reg           # bool
    a: Operand
    b: Operand


@dataclass
class Convert(Instr):
    """Arithmetic conversion among i64/f64/bool/char, from ``src`` type to ``dst`` type."""

    dst: Reg
    src: Operand


@dataclass
class Load(Instr):
    """Memory read. A ``bool`` or ``char`` occupies one byte in memory (zero- or sign-extended on
    load, like the array elements of those types); every other type occupies eight."""

    dst: Reg
    addr: Operand


@dataclass
class Store(Instr):
    addr: Operand
    value: Operand


@dataclass
class PtrAdd(Instr):
    """``dst = base + index * scale`` (index is an element count, scale the element size: 1 or 8)."""

    dst: Reg
    base: Operand
    index: Operand
    scale: int = 8


@dataclass
class NewArray(Instr):
    """Zero-filled array of ``count`` elements of ``elsize`` bytes (1 for bool/char, else 8)."""

    dst: Reg
    count: Operand
    elsize: int = 8


@dataclass
class Call(Instr):
    dst: Reg | None
    callee: str
    args: list[Operand]


@dataclass
class RtCall(Instr):
    dst: Reg | None
    name: str
    args: list[Operand]


# ── Terminators ──

@dataclass
class Terminator:
    line: int = field(**_LINE)


@dataclass
class Jump(Terminator):
    target: str


@dataclass
class Branch(Terminator):
    cond: Operand
    then_target: str
    else_target: str


@dataclass
class Return(Terminator):
    value: Operand | None


# ── Containers ──

@dataclass
class BasicBlock:
    label: str
    instrs: list[Instr]
    term: Terminator


@dataclass
class IRFunction:
    name: str
    params: list[Reg]
    ret: IRType
    blocks: list[BasicBlock]


def at(new, old):
    """Give the instruction or terminator ``new``, which replaces ``old``, the source line of ``old``."""
    new.line = old.line
    return new


def clone_function(f: IRFunction) -> IRFunction:
    """Independent copy of ``f`` for passes that rewrite it in place.

    Instructions, terminators, blocks and the lists they hold are new objects; operands (``Reg``,
    ``Const``, ``GlobalRef``) are frozen dataclasses, so they are shared. Much faster than
    ``copy.deepcopy`` on large programs, which dominated -O1 compile time."""
    blocks = []
    for b in f.blocks:
        instrs = []
        for i in b.instrs:
            j = copy.copy(i)
            if hasattr(j, "args"):
                j.args = list(j.args)           # type: ignore[attr-defined]
            instrs.append(j)
        blocks.append(BasicBlock(b.label, instrs, copy.copy(b.term)))
    g = copy.copy(f)                            # keeps attributes attached by the code generator
    g.params = list(f.params)
    g.blocks = blocks
    return g


def clone_module(m: "IRModule") -> "IRModule":
    return IRModule([copy.copy(g) for g in m.globals], [clone_function(f) for f in m.functions])


@dataclass
class IRGlobal:
    name: str
    type: IRType        # value type (element type for arrays)
    kind: str           # scalar | array_static | array_ptr
    count: int          # elements for array_static, else 1


@dataclass
class IRModule:
    globals: list[IRGlobal]
    functions: list[IRFunction]
