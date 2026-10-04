"""Small IR helpers shared by the verifier, optimizer and code generator."""

from __future__ import annotations

from compiler.ir import ir as I


def regs_of(ops) -> list[I.Reg]:
    return [o for o in ops if isinstance(o, I.Reg)]


def uses(i: I.Instr) -> list[I.Reg]:
    if isinstance(i, (I.Copy, I.UnOp, I.Convert)):
        return regs_of([i.src])
    if isinstance(i, (I.BinOp, I.Cmp)):
        return regs_of([i.a, i.b])
    if isinstance(i, I.Load):
        return regs_of([i.addr])
    if isinstance(i, I.Store):
        return regs_of([i.addr, i.value])
    if isinstance(i, I.PtrAdd):
        return regs_of([i.base, i.index])
    if isinstance(i, I.NewArray):
        return regs_of([i.count])
    if isinstance(i, (I.Call, I.RtCall)):
        return regs_of(i.args)
    raise TypeError(type(i))


def term_uses(t: I.Terminator) -> list[I.Reg]:
    if isinstance(t, I.Branch):
        return regs_of([t.cond])
    if isinstance(t, I.Return) and t.value is not None:
        return regs_of([t.value])
    return []


def defs(i: I.Instr) -> I.Reg | None:
    if isinstance(i, I.Store):
        return None
    return i.dst


def successors(t: I.Terminator) -> list[str]:
    if isinstance(t, I.Jump):
        return [t.target]
    if isinstance(t, I.Branch):
        return [t.then_target] if t.then_target == t.else_target else [t.then_target, t.else_target]
    return []


def operand_fields(i: I.Instr) -> list[str]:
    """Names of fields holding *read* operands (single operands only)."""
    if isinstance(i, (I.Copy, I.UnOp, I.Convert)):
        return ["src"]
    if isinstance(i, (I.BinOp, I.Cmp)):
        return ["a", "b"]
    if isinstance(i, I.Load):
        return ["addr"]
    if isinstance(i, I.Store):
        return ["addr", "value"]
    if isinstance(i, I.PtrAdd):
        return ["base", "index"]
    if isinstance(i, I.NewArray):
        return ["count"]
    return []


def map_operands(i: I.Instr, fn) -> None:
    """Apply ``fn`` to every read operand of ``i`` in place."""
    for name in operand_fields(i):
        setattr(i, name, fn(getattr(i, name)))
    if isinstance(i, (I.Call, I.RtCall)):
        i.args = [fn(a) for a in i.args]


def map_term_operands(t: I.Terminator, fn) -> None:
    if isinstance(t, I.Branch):
        t.cond = fn(t.cond)
    elif isinstance(t, I.Return) and t.value is not None:
        t.value = fn(t.value)
