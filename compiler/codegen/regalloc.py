"""Linear-scan register allocation over IR virtual registers.

* Liveness is computed on the CFG (backward data flow over the linear block order); every virtual
  register gets one conservative live interval ``[start, end]`` over the linear instruction
  numbering. A register live into a loop header and out of its latch therefore covers the whole
  loop (the interval is extended across the back edge).
* Numbering: an instruction ``k`` sits at an even position ``p``; its operands are read at ``p`` and
  its result is written at ``p + 1``, so a source whose last use is ``p`` may share a register with
  the result.
* Intervals that are live across a call (``start < call < end``) may only use callee-saved
  registers; others may also use caller-saved registers outside the scratch set. Whatever does not
  fit is spilled to a stack slot for its whole lifetime.
* Heuristic: when no register is free, the interval with the lowest (loop-depth weighted) access
  count per unit of length is spilled.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

from compiler.codegen import lir
from compiler.ir import ir as I

IT = I.IRType


def reg_class(t: IT) -> str:
    return "f" if t == IT.F64 else "i"


@dataclass
class Interval:
    name: str
    cls: str
    start: int
    end: int
    weight: float = 0.0
    crosses: bool = False
    reg: str | None = None
    slot: int | None = None
    hint: str | None = None          # vreg whose register would make this interval's defining move free
    pref: str | None = None          # register that makes a parameter / call-argument move free

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass
class RegSets:
    """Allocatable registers per class, in preference order."""

    int_caller: tuple[str, ...]
    int_callee: tuple[str, ...]
    flt_caller: tuple[str, ...]
    flt_callee: tuple[str, ...]


@dataclass
class Allocation:
    loc: dict[str, tuple]                    # vreg -> ("r", reg) | ("x", xmm) | ("m", rbp offset)
    nslots: int                              # 8-byte spill slots
    used_callee_int: list[str] = field(default_factory=list)
    used_callee_flt: list[str] = field(default_factory=list)


def loop_depths(fn: I.IRFunction) -> list[int]:
    """Loop nesting depth per block, from back edges of the linear order."""
    idx = {b.label: k for k, b in enumerate(fn.blocks)}
    depth = [0] * len(fn.blocks)
    for j, b in enumerate(fn.blocks):
        for s in lir.successors(b.term):
            i = idx[s]
            if i <= j:
                for k in range(i, j + 1):
                    depth[k] += 1
    return depth


def build_intervals(fn: I.IRFunction, assign=None) -> tuple[dict[str, Interval], list[int], dict]:
    """Number the function, compute liveness and one interval per virtual register.

    Returns ``(intervals, call_positions, positions)`` where ``positions`` maps ``(block, k)`` to
    the instruction position (``k == len(instrs)`` is the terminator).
    """
    blocks = fn.blocks
    nb = len(blocks)
    idx = {b.label: k for k, b in enumerate(blocks)}
    types: dict[str, IT] = {}

    def see(r: I.Reg) -> None:
        types.setdefault(r.name, r.type)

    gen: list[set[str]] = []
    kill: list[set[str]] = []
    for p in fn.params:
        see(p)
    for b in blocks:
        g: set[str] = set()
        k: set[str] = set()
        for i in b.instrs:
            for r in lir.uses(i):
                see(r)
                if r.name not in k:
                    g.add(r.name)
            d = lir.defs(i)
            if d is not None:
                see(d)
                k.add(d.name)
        for r in lir.term_uses(b.term):
            see(r)
            if r.name not in k:
                g.add(r.name)
        gen.append(g)
        kill.append(k)

    succ = [[idx[s] for s in lir.successors(b.term)] for b in blocks]
    live_in = [set() for _ in range(nb)]
    live_out = [set() for _ in range(nb)]
    changed = True
    while changed:
        changed = False
        for n in range(nb - 1, -1, -1):
            out: set[str] = set()
            for s in succ[n]:
                out |= live_in[s]
            inn = gen[n] | (out - kill[n])
            if out != live_out[n] or inn != live_in[n]:
                live_out[n], live_in[n] = out, inn
                changed = True

    depth = loop_depths(fn)
    ivs: dict[str, Interval] = {}
    calls: list[int] = []
    positions: dict[tuple[int, int], int] = {}

    def touch(name: str, pos: int, w: float = 0.0) -> Interval:
        iv = ivs.get(name)
        if iv is None:
            iv = ivs[name] = Interval(name, reg_class(types[name]), pos, pos)
        else:
            if pos < iv.start:
                iv.start = pos
            if pos > iv.end:
                iv.end = pos
        iv.weight += w
        return iv

    pos = 0
    for p in fn.params:
        touch(p.name, 0)
    if assign is not None:
        for p, (kind, where) in zip(fn.params, assign([p.type for p in fn.params])):
            if kind == "reg":
                ivs[p.name].pref = str(where)
    for n, b in enumerate(blocks):
        w = 10.0 ** min(depth[n], 5)
        start = pos
        pos += 2
        for name in live_in[n]:
            touch(name, start)
        for k, i in enumerate(b.instrs):
            positions[(n, k)] = pos
            if lir.is_call(i):
                calls.append(pos)
            for r in lir.uses(i):
                touch(r.name, pos, w)
            if assign is not None and isinstance(i, (I.Call, I.RtCall)):
                for a, (kind, where) in zip(i.args, assign([lir.operand_type(a) for a in i.args])):
                    if kind == "reg" and isinstance(a, I.Reg) and ivs[a.name].pref is None:
                        ivs[a.name].pref = str(where)
            d = lir.defs(i)
            if d is not None:
                iv = touch(d.name, pos + 1, w)
                src = _hint_source(i)
                if src is not None and iv.hint is None:
                    iv.hint = src
            pos += 2
        positions[(n, len(b.instrs))] = pos
        for r in lir.term_uses(b.term):
            touch(r.name, pos, w)
        for name in live_out[n]:
            touch(name, pos + 1)
        pos += 2

    for iv in ivs.values():
        a = bisect_right(calls, iv.start)           # first call position > start
        iv.crosses = a < len(calls) and calls[a] < iv.end
    # a parameter that is never read needs no location at all
    for p in fn.params:
        iv = ivs[p.name]
        if iv.start == 0 and iv.end == 0 and iv.weight == 0.0:
            del ivs[p.name]
    return ivs, calls, positions


def _hint_source(i: I.Instr) -> str | None:
    """Register worth sharing with the result of ``i`` (two-address friendly)."""
    srcs: list[I.Operand] = []
    if isinstance(i, (I.Copy, I.UnOp, I.Convert)):
        srcs = [i.src]
    elif isinstance(i, I.BinOp):
        srcs = [i.a] if i.op == "SUB" or i.op in ("DIV", "MOD") else [i.a, i.b]
    for s in srcs:
        if isinstance(s, I.Reg):
            return s.name
    return None


def allocate(fn: I.IRFunction, regs: RegSets, assign=None) -> Allocation:
    """``assign`` maps a list of argument types to the ABI's per-argument locations (for preferences)."""
    ivs, _calls, _pos = build_intervals(fn, assign)
    by_start = sorted(ivs.values(), key=lambda v: (v.start, v.end, v.name))
    for cls, caller, callee in (("i", regs.int_caller, regs.int_callee),
                                ("f", regs.flt_caller, regs.flt_callee)):
        _scan([v for v in by_start if v.cls == cls], ivs, caller, callee)

    # spill slots, reused once an interval has ended
    nslots = 0
    free_slots: list[int] = []
    busy: list[tuple[int, int]] = []          # (end, slot)
    for v in by_start:
        if v.reg is not None:
            continue
        still = []
        for end, slot in busy:
            if end < v.start:
                free_slots.append(slot)
            else:
                still.append((end, slot))
        busy = still
        if free_slots:
            v.slot = free_slots.pop()
        else:
            nslots += 1
            v.slot = nslots
        busy.append((v.end, v.slot))

    loc: dict[str, tuple] = {}
    used_i: set[str] = set()
    used_f: set[str] = set()
    for v in ivs.values():
        if v.reg is not None:
            loc[v.name] = ("x" if v.cls == "f" else "r", v.reg)
            if v.reg in regs.int_callee:
                used_i.add(v.reg)
            if v.reg in regs.flt_callee:
                used_f.add(v.reg)
        else:
            loc[v.name] = ("m", v.slot * 8)
    return Allocation(
        loc, nslots,
        [r for r in regs.int_callee if r in used_i],
        [r for r in regs.flt_callee if r in used_f],
    )


def _scan(intervals: list[Interval], ivs: dict[str, Interval],
          caller: tuple[str, ...], callee: tuple[str, ...]) -> None:
    active: list[Interval] = []
    free_caller = list(caller)
    free_callee = list(callee)
    callee_set = set(callee)
    caller_set = set(caller)

    def release(reg: str) -> None:
        if reg in callee_set:
            free_callee.append(reg)
        else:
            free_caller.append(reg)

    for cur in intervals:
        still = []
        for a in active:
            if a.end < cur.start:
                release(a.reg)       # type: ignore[arg-type]
            else:
                still.append(a)
        active = still

        pools = [free_callee] if cur.crosses else [free_caller, free_callee]
        chosen: str | None = None
        if cur.hint is not None:
            h = ivs.get(cur.hint)
            if h is not None and h.reg is not None and h.cls == cur.cls:
                for pool in pools:
                    if h.reg in pool:
                        chosen = h.reg
                        pool.remove(h.reg)
                        break
        if chosen is None and cur.pref is not None:
            for pool in pools:
                if cur.pref in pool:
                    chosen = cur.pref
                    pool.remove(cur.pref)
                    break
        if chosen is None:
            for pool in pools:
                if pool:
                    # keep the declared preference order
                    order = (callee if pool is free_callee else caller)
                    best = min(pool, key=order.index)
                    pool.remove(best)
                    chosen = best
                    break
        if chosen is not None:
            cur.reg = chosen
            active.append(cur)
            continue

        # no register free: spill the cheapest eligible interval (possibly ``cur``)
        allowed = callee_set if cur.crosses else (callee_set | caller_set)
        elig = [a for a in active if a.reg in allowed]
        victim = cur
        vkey = cur.weight / cur.length
        for a in elig:
            k = a.weight / a.length
            if k < vkey:
                victim, vkey = a, k
        if victim is not cur:
            cur.reg = victim.reg
            victim.reg = None
            active.remove(victim)
            active.append(cur)
