"""Typed three-address IR with an explicit CFG (design §5).

Non-SSA: scalar source variables and temporaries are mutable virtual registers
(:class:`Reg`); memory (arrays, global scalars) is accessed only through
``load``/``store`` on ``addr`` operands. Every block ends in exactly one
terminator. All element/value slots are 8 bytes (plan §D).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "IRType", "Const", "Reg", "GlobalRef", "Operand", "Instr", "Copy", "UnOp", "BinOp",
    "Cmp", "Convert", "Load", "Store", "PtrAdd", "NewArray", "Call", "RtCall",
    "Terminator", "Jump", "Branch", "Return", "BasicBlock", "IRFunction", "IRGlobal",
    "IRModule", "ENTRY_FUNCTION",
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

@dataclass
class Instr:
    pass


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
    dst: Reg
    addr: Operand


@dataclass
class Store(Instr):
    addr: Operand
    value: Operand


@dataclass
class PtrAdd(Instr):
    """``dst = base + index * 8`` (index is an element count)."""

    dst: Reg
    base: Operand
    index: Operand


@dataclass
class NewArray(Instr):
    """Zero-filled array of ``count`` 8-byte elements."""

    dst: Reg
    count: Operand


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
    pass


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
