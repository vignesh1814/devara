"""Pre-allocation rewrites for the register-allocating back end (-O1).

* :func:`promote_globals` -- global scalars (and array base pointers) that only the generated
  ``$entry`` function touches, and only through direct ``load``/``store``, become virtual
  registers of ``$entry``. Top-level programs keep all their variables in globals; without this
  every access would be a memory operation.
* :func:`hoist_array_bases` -- keep the address of a static global array in a register (audit F10).
* :func:`prepare_function` -- on a private copy: merge ``t = op ...; x = copy t`` into
  ``x = op ...``, fold ``ptradd`` into the addressing mode of its single load/store, and fuse a
  trailing ``cmp`` into its ``branch``.
"""

from __future__ import annotations

from compiler.codegen import lir
from compiler.ir import ir as I
from compiler.ir import util

IT = I.IRType

_ZERO = {IT.I64: 0, IT.F64: 0.0, IT.BOOL: False, IT.CHAR: 0}      # str/addr start as a null pointer


# ── global promotion ──

def _global_refs(fn: I.IRFunction):
    """Yield (instr, role) for every instruction mentioning a GlobalRef; role is 'addr' when the
    global is only the address operand of a load/store, else 'other'."""
    for b in fn.blocks:
        for i in b.instrs:
            if isinstance(i, I.Load) and isinstance(i.addr, I.GlobalRef):
                yield i, "load"
                continue
            if isinstance(i, I.Store) and isinstance(i.addr, I.GlobalRef):
                if isinstance(i.value, I.GlobalRef):
                    yield i, "other"
                else:
                    yield i, "store"
                continue
            ops = []
            for name in ("src", "a", "b", "addr", "value", "base", "index", "count"):
                if hasattr(i, name):
                    ops.append(getattr(i, name))
            ops += getattr(i, "args", [])
            if any(isinstance(o, I.GlobalRef) for o in ops):
                yield i, "other"
        t = b.term
        if isinstance(t, I.Branch) and isinstance(t.cond, I.GlobalRef):
            yield t, "other"
        if isinstance(t, I.Return) and isinstance(t.value, I.GlobalRef):
            yield t, "other"


def promote_globals(module: I.IRModule) -> I.IRModule:
    """Return ``module`` with entry-only global scalars turned into registers (or ``module`` itself)."""
    entry = next((f for f in module.functions if f.name == I.ENTRY_FUNCTION), None)
    if entry is None:
        return module
    scalars = {g.name: g for g in module.globals if g.kind in ("scalar", "array_ptr")}
    if not scalars:
        return module
    blocked: set[str] = set()
    types: dict[str, set[IT]] = {}
    stored: set[str] = set()

    for f in module.functions:
        for i, role in _global_refs(f):
            if role == "other":
                for name in ("src", "a", "b", "addr", "value", "base", "index", "count", "cond"):
                    o = getattr(i, name, None)
                    if isinstance(o, I.GlobalRef):
                        blocked.add(o.name)
                for o in getattr(i, "args", []):
                    if isinstance(o, I.GlobalRef):
                        blocked.add(o.name)
                continue
            g = i.addr.name
            if f.name != I.ENTRY_FUNCTION:
                blocked.add(g)
            else:
                types.setdefault(g, set()).add(i.dst.type if role == "load" else i.value.type)
                if role == "store":
                    stored.add(g)
    chosen = {n: g for n, g in scalars.items()
              if n not in blocked and n in types and len(types[n]) == 1
              and next(iter(types[n])) != IT.STR            # keeps interned literals reachable (LSan)
              and (next(iter(types[n])) in _ZERO or n in stored)}
    if not chosen:
        return module

    while True:
        out, fn, regs = _rewrite(module, chosen, types)
        # a str/addr global may start as a null pointer, which an IR constant cannot express (the
        # verifier only admits string constants as dv_rt_strlit arguments): keep in memory those that
        # can be read before being written
        bad = {r.name for r in regs.values() if r.type not in _ZERO} & _live_into_entry(fn)
        offenders = [n for n, r in regs.items() if r.name in bad]
        if not offenders:
            break
        for n in offenders:
            del chosen[n]
        if not chosen:
            return module
    # numeric globals start zeroed: explicit initializers (dce drops those overwritten before any read)
    fn.blocks[0].instrs[0:0] = [I.Copy(r, I.Const(r.type, _ZERO[r.type]))
                                for r in regs.values() if r.type in _ZERO]
    # tidy up with the regular -O1 passes (copy propagation removes the load/store shims)
    from compiler.opt import optimize

    return optimize(out, 1)


def _rewrite(module: I.IRModule, chosen, types):
    out = I.clone_module(module)
    fn = next(f for f in out.functions if f.name == I.ENTRY_FUNCTION)
    regs = {n: I.Reg(f"@g.{n}", next(iter(types[n]))) for n in chosen}
    for b in fn.blocks:
        new: list[I.Instr] = []
        for i in b.instrs:
            if isinstance(i, I.Load) and isinstance(i.addr, I.GlobalRef) and i.addr.name in regs:
                new.append(I.at(I.Copy(i.dst, regs[i.addr.name]), i))
            elif isinstance(i, I.Store) and isinstance(i.addr, I.GlobalRef) and i.addr.name in regs:
                new.append(I.at(I.Copy(regs[i.addr.name], i.value), i))
            else:
                new.append(i)
        b.instrs = new
    return out, fn, regs


def _live_into_entry(fn: I.IRFunction) -> set[str]:
    """Registers that may be read before being written on some path from the entry."""
    idx = {b.label: k for k, b in enumerate(fn.blocks)}
    gen, kill = [], []
    for b in fn.blocks:
        g: set[str] = set()
        k: set[str] = set()
        for i in b.instrs:
            g |= {r.name for r in lir.uses(i)} - k
            d = lir.defs(i)
            if d is not None:
                k.add(d.name)
        g |= {r.name for r in lir.term_uses(b.term)} - k
        gen.append(g)
        kill.append(k)
    live_in = [set() for _ in fn.blocks]
    changed = True
    while changed:
        changed = False
        for n in range(len(fn.blocks) - 1, -1, -1):
            out: set[str] = set()
            for s in lir.successors(fn.blocks[n].term):
                out |= live_in[idx[s]]
            inn = gen[n] | (out - kill[n])
            if inn != live_in[n]:
                live_in[n] = inn
                changed = True
    return live_in[0]


# ── per-function rewrites ──

def _use_def_counts(fn: I.IRFunction):
    nuse: dict[str, int] = {}
    ndef: dict[str, int] = {}
    for p in fn.params:
        ndef[p.name] = ndef.get(p.name, 0) + 1
    for b in fn.blocks:
        for i in b.instrs:
            for r in lir.uses(i):
                nuse[r.name] = nuse.get(r.name, 0) + 1
            d = lir.defs(i)
            if d is not None:
                ndef[d.name] = ndef.get(d.name, 0) + 1
        for r in lir.term_uses(b.term):
            nuse[r.name] = nuse.get(r.name, 0) + 1
    return nuse, ndef


def _coalesce_copies(fn: I.IRFunction) -> None:
    nuse, ndef = _use_def_counts(fn)
    for b in fn.blocks:
        out: list[I.Instr] = []
        for i in b.instrs:
            if (isinstance(i, I.Copy) and isinstance(i.src, I.Reg) and out
                    and nuse.get(i.src.name) == 1 and ndef.get(i.src.name) == 1):
                prev = out[-1]
                d = lir.defs(prev)
                if d is not None and d.name == i.src.name and d.type == i.dst.type:
                    prev.dst = i.dst            # type: ignore[union-attr]
                    continue
            out.append(i)
        b.instrs = out


def _fold_addressing(fn: I.IRFunction) -> None:
    nuse, ndef = _use_def_counts(fn)
    for b in fn.blocks:
        pending: dict[str, int] = {}          # ptradd dst name -> index in b.instrs
        dead: set[int] = set()
        for k, i in enumerate(b.instrs):
            replaced = None
            if isinstance(i, I.Load) and isinstance(i.addr, I.Reg) and i.addr.name in pending:
                p = b.instrs[pending[i.addr.name]]
                replaced = lir.LoadIdx(i.dst, p.base, p.index, p.scale)  # type: ignore[union-attr]
                dead.add(pending[i.addr.name])
            elif isinstance(i, I.Store) and isinstance(i.addr, I.Reg) and i.addr.name in pending \
                    and not (isinstance(i.value, I.Reg) and i.value.name == i.addr.name):
                p = b.instrs[pending[i.addr.name]]
                replaced = lir.StoreIdx(p.base, p.index, i.value, p.scale)   # type: ignore[union-attr]
                dead.add(pending[i.addr.name])
            if replaced is not None:
                del pending[i.addr.name]        # type: ignore[union-attr]
                b.instrs[k] = I.at(replaced, i)
                i = b.instrs[k]
            d = lir.defs(i)
            if d is not None:
                # a redefinition invalidates ptradds that read (or produce) this register
                for t in [t for t, idx in pending.items()
                          if t == d.name
                          or any(isinstance(o, I.Reg) and o.name == d.name
                                 for o in (b.instrs[idx].base, b.instrs[idx].index))]:   # type: ignore[union-attr]
                    del pending[t]
            if isinstance(i, I.PtrAdd) and nuse.get(i.dst.name) == 1 and ndef.get(i.dst.name) == 1 \
                    and not (isinstance(i.base, I.Reg) and i.base.name == i.dst.name) \
                    and not (isinstance(i.index, I.Reg) and i.index.name == i.dst.name):
                pending[i.dst.name] = k
        if dead:
            b.instrs = [i for k, i in enumerate(b.instrs) if k not in dead]


def _fuse_cmp_branch(fn: I.IRFunction) -> None:
    nuse, ndef = _use_def_counts(fn)
    for b in fn.blocks:
        t = b.term
        if not (isinstance(t, I.Branch) and isinstance(t.cond, I.Reg) and b.instrs):
            continue
        last = b.instrs[-1]
        if isinstance(last, I.Cmp) and last.dst.name == t.cond.name \
                and nuse.get(t.cond.name) == 1 and ndef.get(t.cond.name) == 1 \
                and lir.operand_type(last.a) != IT.STR:
            b.instrs.pop()
            b.term = I.at(lir.CmpBranch(last.cond, last.a, last.b, t.then_target, t.else_target), t)


# ── hoisting of static-array base addresses (audit F10) ──
#
# The address of a static global array is a link-time constant that x86-64 can only materialise with
# ``lea reg, [rip + sym]`` (RIP-relative addressing takes no index register), so every element access
# in a loop re-did it. A function that uses such a base more than once, or inside a loop, now copies it
# into a register once at entry; the allocator keeps it there when the loop weights justify it, and
# spills it (a reload instead of the ``lea``) when registers run out.

def _hoist_bases(fn: I.IRFunction, static: frozenset[str]) -> I.IRFunction:
    succ, _ = _cfg(fn)
    in_cycle = {b.label for b in fn.blocks if b.label in _reachable_from_succs(b.label, succ)}
    uses: dict[str, int] = {}
    looped: set[str] = set()
    for b in fn.blocks:
        for i in b.instrs:
            if isinstance(i, I.PtrAdd) and isinstance(i.base, I.GlobalRef) and i.base.name in static:
                uses[i.base.name] = uses.get(i.base.name, 0) + 1
                if b.label in in_cycle:
                    looped.add(i.base.name)
    chosen = [n for n, k in uses.items() if k >= 2 or n in looped]
    if not chosen:
        return fn
    fn = I.clone_function(fn)
    regs = {n: I.Reg(f"{n}.base", IT.ADDR) for n in chosen}
    for b in fn.blocks:
        for i in b.instrs:
            if isinstance(i, I.PtrAdd) and isinstance(i.base, I.GlobalRef) and i.base.name in regs:
                i.base = regs[i.base.name]
    fn.blocks[0].instrs[:0] = [I.Copy(regs[n], I.GlobalRef(n)) for n in chosen]
    return fn


def hoist_array_bases(module: I.IRModule) -> I.IRModule:
    """Return ``module`` with static-array base addresses held in registers (or ``module`` itself)."""
    static = frozenset(g.name for g in module.globals if g.kind == "array_static")
    if not static:
        return module
    funcs = [_hoist_bases(f, static) for f in module.functions]
    if all(a is b for a, b in zip(funcs, module.functions)):
        return module
    return I.IRModule(module.globals, funcs)


# ── shrink-wrapping of call-crossing parameters (audit F7) ──
#
# A parameter that is live across a call must sit in a callee-saved register for its whole interval,
# which makes the prologue save that register on *every* path -- including the early return of a
# recursive function's base case. When all calls of a function lie in a single-entry region S that
# starts at block N (the nearest common dominator of the blocks containing calls), the parameters
# used after a call inside S are copied into fresh registers at the start of N and renamed inside S,
# and ``fn.wrap = (N, S)`` tells the code generator that callee-saved registers used only inside S
# may be saved at N and restored on the returns inside S instead of in the prologue and everywhere.

def _cfg(fn: I.IRFunction):
    succ = {b.label: lir.successors(b.term) for b in fn.blocks}
    pred: dict[str, list[str]] = {b.label: [] for b in fn.blocks}
    for label, ss in succ.items():
        for t in ss:
            pred[t].append(label)
    return succ, pred


def _reachable(start: str, succ: dict[str, list[str]]) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        for t in succ[stack.pop()]:
            if t not in seen:
                seen.add(t)
                stack.append(t)
    return seen


def _dominators(entry: str, succ: dict[str, list[str]], pred: dict[str, list[str]]) -> dict[str, set[str]]:
    live = _reachable(entry, succ)
    dom = {l: set(live) for l in live}
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for l in live:
            if l == entry:
                continue
            ps = [dom[q] for q in pred[l] if q in live]
            new = {l} | (set.intersection(*ps) if ps else set())
            if new != dom[l]:
                dom[l] = new
                changed = True
    return dom


def _call_region(fn: I.IRFunction):
    """(N, S) as described above, or None when the function has no such region."""
    entry = fn.blocks[0].label
    succ, pred = _cfg(fn)
    call_blocks = [b.label for b in fn.blocks if any(lir.is_call(i) for i in b.instrs)]
    if not call_blocks:
        return None
    dom = _dominators(entry, succ, pred)
    if any(c not in dom for c in call_blocks):
        return None
    common = set.intersection(*(dom[c] for c in call_blocks))
    n = max(common, key=lambda l: len(dom[l]))             # the deepest common dominator
    if n == entry:
        return None
    region = _reachable(n, succ)
    if entry in region or any(q in region for q in pred[n]):
        return None                                        # N must be entered from outside S only
    for l in region:
        if l != n and any(q not in region for q in pred[l]):
            return None                                    # S must be single-entry
    return n, region


def _rename_in_blocks(blocks: list[I.BasicBlock], old: str, new: I.Reg) -> None:
    def sub(o):
        return new if isinstance(o, I.Reg) and o.name == old else o

    for b in blocks:
        for i in b.instrs:
            util.map_operands(i, sub)
            d = util.defs(i)
            if d is not None and d.name == old:
                i.dst = new                                # type: ignore[union-attr]
        util.map_term_operands(b.term, sub)


def _used_after_call(blocks: list[I.BasicBlock], region: set[str], succ: dict[str, list[str]], name: str) -> bool:
    """Is parameter ``name`` read in S after a call (in its block, or in a block a call can reach)?"""
    by_label = {b.label: b for b in blocks}
    after: set[str] = set()                                # blocks entered after some call in S
    for l in region:
        if any(lir.is_call(i) for i in by_label[l].instrs):
            after |= _reachable_from_succs(l, succ)
    for l in region:
        b = by_label[l]
        seen_call = l in after
        for i in b.instrs:
            if seen_call and any(r.name == name for r in util.uses(i)):
                return True
            if lir.is_call(i):
                seen_call = True
        if seen_call and any(r.name == name for r in util.term_uses(b.term)):
            return True
    return False


def _reachable_from_succs(label: str, succ: dict[str, list[str]]) -> set[str]:
    out: set[str] = set()
    for t in succ[label]:
        out |= _reachable(t, succ)
    return out


def _wrap_calls(fn: I.IRFunction) -> None:
    found = _call_region(fn)
    if found is None:
        return
    n, region = found
    succ, _ = _cfg(fn)
    blocks = [b for b in fn.blocks if b.label in region]
    head = next(b for b in blocks if b.label == n)
    copies: list[I.Instr] = []
    for prm in fn.params:
        if prm.type == IT.VOID or not _used_after_call(fn.blocks, region, succ, prm.name):
            continue
        fresh = I.Reg(f"{prm.name}.w", prm.type)
        _rename_in_blocks(blocks, prm.name, fresh)
        copies.append(I.Copy(fresh, prm))
    head.instrs[:0] = copies
    fn.wrap = (n, frozenset(region))                       # type: ignore[attr-defined]


def prepare_function(fn: I.IRFunction) -> I.IRFunction:
    fn = I.clone_function(fn)
    _wrap_calls(fn)
    _coalesce_copies(fn)
    _fold_addressing(fn)
    _fuse_cmp_branch(fn)
    return fn
