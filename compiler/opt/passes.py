"""IR optimization passes (design §6). Every pass preserves observable behavior.

Safety rules enforced here:
* calls, I/O, stores and potentially-trapping division are never removed or reordered;
* **no algebraic identity is applied to float operands** (L49, spec §12.4);
* float constant folding is exact binary64 evaluation, except that results that
  would be NaN (whose sign bit is hardware-defined) or float division by zero
  are left for run time so O0 and O1 behave identically.
"""

from __future__ import annotations

import math
from collections import deque

from compiler import arith
from compiler.ir import ir as I
from compiler.ir.runtime import PURE
from compiler.ir.util import (
    defs, map_operands, map_term_operands, successors, term_uses, uses,
)

IT = I.IRType


# ── CFG helpers ──

def predecessors(fn: I.IRFunction) -> dict[str, list[str]]:
    preds: dict[str, list[str]] = {b.label: [] for b in fn.blocks}
    for b in fn.blocks:
        for s in successors(b.term):
            preds[s].append(b.label)
    return preds


def reachable(fn: I.IRFunction) -> set[str]:
    by = {b.label: b for b in fn.blocks}
    seen = {fn.blocks[0].label}
    stack = [fn.blocks[0].label]
    while stack:
        for s in successors(by[stack.pop()].term):
            if s not in seen:
                seen.add(s)
                stack.append(s)
    return seen


# ── constant folding ──

def convert_const(v, src: IT, dst: IT):
    if dst == IT.BOOL:
        return v != 0
    if dst == IT.F64:
        return float(v)
    iv = arith.float_to_int(v) if src == IT.F64 else int(v)
    if dst == IT.I64:
        return iv
    if dst == IT.CHAR:
        return arith.wrap8(iv)
    raise ValueError(dst)


def _fold_float(x: float):
    return None if math.isnan(x) else x


def fold_instr(i: I.Instr, const_of) -> I.Const | None:
    """Compile-time value of ``i`` if it is exactly computable and cannot trap."""
    if isinstance(i, I.Copy):
        return const_of(i.src)
    if isinstance(i, I.UnOp):
        c = const_of(i.src)
        if c is None:
            return None
        if i.op == "NOT":
            return I.Const(IT.BOOL, not c.value)
        if i.dst.type == IT.I64:
            return I.Const(IT.I64, arith.wrap64(-c.value))
        return I.Const(IT.F64, -c.value)
    if isinstance(i, I.Convert):
        c = const_of(i.src)
        if c is None:
            return None
        v = convert_const(c.value, c.type, i.dst.type)
        return I.Const(i.dst.type, v)
    if isinstance(i, I.BinOp):
        a, b = const_of(i.a), const_of(i.b)
        if a is None or b is None:
            return None
        x, y = a.value, b.value
        if i.dst.type == IT.I64:
            if i.op == "ADD":
                return I.Const(IT.I64, arith.wrap64(x + y))
            if i.op == "SUB":
                return I.Const(IT.I64, arith.wrap64(x - y))
            if i.op == "MUL":
                return I.Const(IT.I64, arith.wrap64(x * y))
            if y == 0 or (i.op == "DIV" and x == arith.INT64_MIN and y == -1):
                return None
            if i.op == "DIV":
                return I.Const(IT.I64, arith.idiv(x, y))
            return I.Const(IT.I64, arith.irem(x, y))
        if i.op == "DIV" and y == 0.0:
            return None
        try:
            r = {"ADD": x + y, "SUB": x - y, "MUL": x * y}[i.op] if i.op != "DIV" else x / y
        except (OverflowError, ZeroDivisionError):
            return None
        r = _fold_float(r)
        return None if r is None else I.Const(IT.F64, r)
    if isinstance(i, I.Cmp):
        a, b = const_of(i.a), const_of(i.b)
        if a is None or b is None:
            return None
        x, y = a.value, b.value
        res = {"LT": x < y, "LE": x <= y, "GT": x > y, "GE": x >= y,
               "EQ": x == y, "NE": x != y}[i.cond] if a.type != IT.STR else (
            (x == y) if i.cond == "EQ" else (x != y))
        return I.Const(IT.BOOL, bool(res))
    return None


# ── pass: constant propagation + folding + branch simplification ──

def _meet_consts(envs: list[dict]) -> dict:
    if not envs:
        return {}
    out = dict(envs[0])
    for e in envs[1:]:
        for k in list(out):
            if k not in e or e[k] != out[k]:
                del out[k]
    return out


def const_prop(fn: I.IRFunction) -> bool:
    by = {b.label: b for b in fn.blocks}
    preds = predecessors(fn)
    entry = fn.blocks[0].label
    out_env: dict[str, dict] = {}

    def in_env(label: str) -> dict:
        if label == entry:
            return {}
        return _meet_consts([out_env[p] for p in preds[label] if p in out_env])

    def step(env: dict, ins: I.Instr) -> None:
        d = defs(ins)
        if d is None:
            return
        c = fold_instr(ins, lambda o: _const(o, env))
        if c is not None:
            env[d.name] = c
        else:
            env.pop(d.name, None)

    work = deque(b.label for b in fn.blocks)
    while work:
        lab = work.popleft()
        if lab != entry and not any(p in out_env for p in preds[lab]):
            continue
        env = in_env(lab)
        for ins in by[lab].instrs:
            step(env, ins)
        if out_env.get(lab) != env:
            out_env[lab] = env
            for s in successors(by[lab].term):
                work.append(s)

    changed = False
    for b in fn.blocks:
        if b.label != entry and not any(p in out_env for p in preds[b.label]):
            continue
        env = in_env(b.label)
        new_instrs: list[I.Instr] = []
        for ins in b.instrs:
            before = repr(ins)
            map_operands(ins, lambda o: _subst(o, env))
            d = defs(ins)
            if d is not None and not isinstance(ins, I.Copy):
                c = fold_instr(ins, lambda o: _const(o, env))
                if c is not None:
                    ins = I.Copy(d, c)
            if repr(ins) != before:
                changed = True
            step(env, ins)
            new_instrs.append(ins)
        b.instrs = new_instrs
        before = repr(b.term)
        map_term_operands(b.term, lambda o: _subst(o, env))
        if isinstance(b.term, I.Branch):
            if isinstance(b.term.cond, I.Const):
                tgt = b.term.then_target if b.term.cond.value else b.term.else_target
                b.term = I.Jump(tgt)
            elif b.term.then_target == b.term.else_target:
                b.term = I.Jump(b.term.then_target)
        if repr(b.term) != before:
            changed = True
    return changed


def _const(o: I.Operand, env: dict) -> I.Const | None:
    if isinstance(o, I.Const):
        return o
    if isinstance(o, I.Reg):
        return env.get(o.name)
    return None


def _subst(o: I.Operand, env: dict) -> I.Operand:
    if isinstance(o, I.Reg):
        c = env.get(o.name)
        if c is not None:
            return c
    return o


# ── pass: copy propagation ──

def copy_prop(fn: I.IRFunction) -> bool:
    by = {b.label: b for b in fn.blocks}
    preds = predecessors(fn)
    entry = fn.blocks[0].label
    out_env: dict[str, dict] = {}

    def meet(label: str) -> dict:
        if label == entry:
            return {}
        envs = [out_env[p] for p in preds[label] if p in out_env]
        if not envs:
            return {}
        out = dict(envs[0])
        for e in envs[1:]:
            for k in list(out):
                if k not in e or e[k] != out[k]:
                    del out[k]
        return out

    def kill(env: dict, name: str) -> None:
        env.pop(name, None)
        for k in [k for k, v in env.items() if v.name == name]:
            del env[k]

    def step(env: dict, ins: I.Instr) -> None:
        d = defs(ins)
        if d is None:
            return
        kill(env, d.name)
        if isinstance(ins, I.Copy) and isinstance(ins.src, I.Reg) and ins.src.name != d.name:
            env[d.name] = ins.src

    work = deque(b.label for b in fn.blocks)
    while work:
        lab = work.popleft()
        if lab != entry and not any(p in out_env for p in preds[lab]):
            continue
        env = meet(lab)
        for ins in by[lab].instrs:
            step(env, ins)
        if out_env.get(lab) != env:
            out_env[lab] = env
            for s in successors(by[lab].term):
                work.append(s)

    def subst(o: I.Operand, env: dict) -> I.Operand:
        while isinstance(o, I.Reg) and o.name in env:
            o = env[o.name]
        return o

    changed = False
    for b in fn.blocks:
        if b.label != entry and not any(p in out_env for p in preds[b.label]):
            continue
        env = meet(b.label)
        for ins in b.instrs:
            before = repr(ins)
            map_operands(ins, lambda o: subst(o, env))
            if repr(ins) != before:
                changed = True
            step(env, ins)
        before = repr(b.term)
        map_term_operands(b.term, lambda o: subst(o, env))
        if repr(b.term) != before:
            changed = True
    return changed


# ── pass: algebraic simplification (integers only, L49) ──

def algebraic(fn: I.IRFunction) -> bool:
    changed = False
    zero = I.Const(IT.I64, 0)
    for b in fn.blocks:
        for k, i in enumerate(b.instrs):
            if not (isinstance(i, I.BinOp) and i.dst.type == IT.I64):
                continue
            a, c = i.a, i.b
            new: I.Instr | None = None

            def is_c(o, v):
                return isinstance(o, I.Const) and o.value == v

            if i.op == "ADD":
                if is_c(c, 0):
                    new = I.Copy(i.dst, a)
                elif is_c(a, 0):
                    new = I.Copy(i.dst, c)
            elif i.op == "SUB" and is_c(c, 0):
                new = I.Copy(i.dst, a)
            elif i.op == "MUL":
                if is_c(c, 1):
                    new = I.Copy(i.dst, a)
                elif is_c(a, 1):
                    new = I.Copy(i.dst, c)
                elif is_c(c, 0) or is_c(a, 0):
                    new = I.Copy(i.dst, zero)
            elif i.op == "DIV" and is_c(c, 1):
                new = I.Copy(i.dst, a)
            elif i.op == "MOD" and is_c(c, 1):
                new = I.Copy(i.dst, zero)
            if new is not None:
                b.instrs[k] = new
                changed = True
    return changed


# ── pass: redundant conversion elimination ──

_ROUND_TRIP = {(IT.BOOL, IT.I64), (IT.CHAR, IT.I64)}


def redundant_convert(fn: I.IRFunction) -> bool:
    changed = False
    for b in fn.blocks:
        origin: dict[str, tuple[I.Reg, I.Operand]] = {}   # temp -> (temp reg, original src)
        for k, i in enumerate(b.instrs):
            d = defs(i)
            if isinstance(i, I.Convert):
                st = i.src.type if not isinstance(i.src, I.GlobalRef) else IT.ADDR
                if st == i.dst.type:
                    b.instrs[k] = I.Copy(i.dst, i.src)
                    changed = True
                    i = b.instrs[k]
                elif isinstance(i.src, I.Reg) and i.src.name in origin:
                    orig = origin[i.src.name][1]
                    ot = orig.type if not isinstance(orig, I.GlobalRef) else IT.ADDR
                    if (ot, i.src.type) in _ROUND_TRIP and i.dst.type == ot:
                        b.instrs[k] = I.Copy(i.dst, orig)
                        changed = True
                        i = b.instrs[k]
            # invalidate facts about anything redefined here
            if d is not None:
                origin.pop(d.name, None)
                for key in [key for key, (_, o) in origin.items()
                            if isinstance(o, I.Reg) and o.name == d.name]:
                    del origin[key]
                if isinstance(i, I.Convert) and isinstance(i.src, (I.Reg, I.Const)):
                    origin[d.name] = (d, i.src)
    return changed


# ── pass: CFG cleanup ──

def unreachable_blocks(fn: I.IRFunction) -> bool:
    live = reachable(fn)
    if len(live) == len(fn.blocks):
        return False
    fn.blocks = [b for b in fn.blocks if b.label in live]
    return True


def merge_blocks(fn: I.IRFunction) -> bool:
    """Merge ``A: ...; jump B`` with ``B`` when A is B's only predecessor (linear time)."""
    preds = predecessors(fn)
    by = {b.label: b for b in fn.blocks}
    entry = fn.blocks[0].label
    removed: set[str] = set()
    for b in fn.blocks:
        if b.label in removed:
            continue
        # absorb a whole chain of single-predecessor jump targets into ``b``
        while isinstance(b.term, I.Jump):
            t = b.term.target
            if t == b.label or t == entry or t in removed or len(preds[t]) != 1:
                break
            tb = by[t]
            b.instrs.extend(tb.instrs)
            b.term = tb.term
            removed.add(t)
            # successors of tb now have ``b`` as predecessor instead of ``tb``
            for succ in successors(tb.term):
                preds[succ] = [b.label if x == t else x for x in preds[succ]]
    if not removed:
        return False
    fn.blocks = [b for b in fn.blocks if b.label not in removed]
    return True


# ── pass: dead-code elimination ──

def _removable(i: I.Instr) -> bool:
    if isinstance(i, I.NewArray):
        # allocation can fail at run time ("invalid array size"): only small constant sizes are safe to drop
        return isinstance(i.count, I.Const) and 1 <= i.count.value <= 8192
    if isinstance(i, (I.Copy, I.UnOp, I.Cmp, I.Convert, I.Load, I.PtrAdd)):
        return True
    if isinstance(i, I.BinOp):
        if i.dst.type == IT.F64 or i.op in ("ADD", "SUB", "MUL"):
            return True
        return isinstance(i.b, I.Const) and i.b.value not in (0, -1)
    if isinstance(i, I.RtCall):
        return i.name in PURE
    return False


def dce(fn: I.IRFunction) -> bool:
    by = {b.label: b for b in fn.blocks}
    live_in: dict[str, set[str]] = {b.label: set() for b in fn.blocks}
    changed_any = True
    while changed_any:
        changed_any = False
        for b in reversed(fn.blocks):
            live: set[str] = set()
            for s in successors(b.term):
                live |= live_in[s]
            live |= {r.name for r in term_uses(b.term)}
            for i in reversed(b.instrs):
                d = defs(i)
                if d is not None and d.name in live and not isinstance(i, I.Store):
                    live.discard(d.name)
                live |= {r.name for r in uses(i)}
            if live != live_in[b.label]:
                live_in[b.label] = live
                changed_any = True
    changed = False
    for b in fn.blocks:
        live = set()
        for s in successors(b.term):
            live |= live_in[s]
        live |= {r.name for r in term_uses(b.term)}
        keep: list[I.Instr] = []
        for i in reversed(b.instrs):
            d = defs(i)
            dead = (
                d is not None and d.name not in live and _removable(i)
            ) or (isinstance(i, I.Copy) and isinstance(i.src, I.Reg) and i.src.name == i.dst.name)
            if dead:
                changed = True
                continue
            if d is not None:
                live.discard(d.name)
            live |= {r.name for r in uses(i)}
            keep.append(i)
        keep.reverse()
        b.instrs = keep
    return changed


PIPELINE = [
    ("const_prop", const_prop),
    ("copy_prop", copy_prop),
    ("algebraic", algebraic),
    ("redundant_convert", redundant_convert),
    ("unreachable_blocks", unreachable_blocks),
    ("merge_blocks", merge_blocks),
    ("dce", dce),
]


# ── module pass: drop string literals nobody loads any more ──

def prune_literals(module: I.IRModule) -> bool:
    """Remove the startup initialization (dv_rt_strlit + store) and the global of every
    string literal whose uses were all optimized away (e.g. in a dead branch)."""
    lits = {g.name for g in module.globals if g.name.startswith("lit.") and g.kind == "scalar"}
    if not lits:
        return False

    def is_init(i: I.Instr) -> bool:
        return (isinstance(i, I.Store) and isinstance(i.addr, I.GlobalRef)
                and i.addr.name in lits and isinstance(i.value, I.Reg)
                and i.value.name.startswith("lit.t"))

    used: set[str] = set()
    for f in module.functions:
        for b in f.blocks:
            for i in b.instrs:
                if is_init(i):
                    continue                      # the initialization itself is not a use
                for name in ("addr", "base", "src", "value"):
                    o = getattr(i, name, None)
                    if isinstance(o, I.GlobalRef) and o.name in lits:
                        used.add(o.name)
                for a in getattr(i, "args", []):
                    if isinstance(a, I.GlobalRef) and a.name in lits:
                        used.add(a.name)
    dead = lits - used
    if not dead:
        return False
    dead_regs: set[str] = set()
    for f in module.functions:
        for b in f.blocks:
            for i in b.instrs:
                if is_init(i) and i.addr.name in dead:          # type: ignore[union-attr]
                    dead_regs.add(i.value.name)                 # type: ignore[union-attr]
    for f in module.functions:
        for b in f.blocks:
            b.instrs = [
                i for i in b.instrs
                if not (is_init(i) and i.addr.name in dead)     # type: ignore[union-attr]
                and not (isinstance(i, I.RtCall) and i.name == "dv_rt_strlit"
                         and i.dst is not None and i.dst.name in dead_regs)
            ]
    module.globals = [g for g in module.globals if g.name not in dead]
    return True
