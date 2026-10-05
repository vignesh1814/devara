"""Code-generator-local IR extensions (never serialized, never seen by the optimizer).

The register-allocating back end rewrites a *copy* of each function before allocation:

* ``LoadIdx`` / ``StoreIdx``  -- a ``ptradd`` folded into the addressing mode of the
  single ``load``/``store`` that consumes it (``[base + index*8]``);
* ``CmpBranch``               -- a ``cmp`` fused into the ``branch`` that consumes it.

``uses`` / ``defs`` / ``term_uses`` / ``successors`` extend :mod:`compiler.ir.util` to them.
"""

from __future__ import annotations

from dataclasses import dataclass

from compiler.ir import ir as I
from compiler.codegen.x86_64 import FRAME_ARRAY_LIMIT   # bytes; larger constant-size arrays use the heap
from compiler.ir import util

IT = I.IRType



@dataclass
class LoadIdx(I.Instr):
    dst: I.Reg
    base: I.Operand
    index: I.Operand


@dataclass
class StoreIdx(I.Instr):
    base: I.Operand
    index: I.Operand
    value: I.Operand


@dataclass
class CmpBranch(I.Terminator):
    cond: str
    a: I.Operand
    b: I.Operand
    then_target: str
    else_target: str


def uses(i: I.Instr) -> list[I.Reg]:
    if isinstance(i, LoadIdx):
        return util.regs_of([i.base, i.index])
    if isinstance(i, StoreIdx):
        return util.regs_of([i.base, i.index, i.value])
    return util.uses(i)


def defs(i: I.Instr) -> I.Reg | None:
    if isinstance(i, StoreIdx):
        return None
    return util.defs(i)


def term_uses(t: I.Terminator) -> list[I.Reg]:
    if isinstance(t, CmpBranch):
        return util.regs_of([t.a, t.b])
    return util.term_uses(t)


def successors(t: I.Terminator) -> list[str]:
    if isinstance(t, CmpBranch):
        return [t.then_target] if t.then_target == t.else_target else [t.then_target, t.else_target]
    return util.successors(t)


def operand_type(o: I.Operand) -> IT:
    return IT.ADDR if isinstance(o, I.GlobalRef) else o.type


def newarray_in_frame(i: I.NewArray) -> bool:
    """Constant-size, small arrays live in the stack frame; everything else is heap allocated."""
    return isinstance(i.count, I.Const) and 1 <= i.count.value and i.count.value * 8 <= FRAME_ARRAY_LIMIT


def is_call(i: I.Instr) -> bool:
    """Does the emitted code for ``i`` contain a call (clobbering all caller-saved registers)?"""
    if isinstance(i, (I.Call, I.RtCall)):
        return True
    if isinstance(i, I.Cmp):
        return operand_type(i.a) == IT.STR
    if isinstance(i, I.NewArray):
        return not newarray_in_frame(i)
    return False
