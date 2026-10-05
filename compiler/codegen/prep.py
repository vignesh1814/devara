"""Pre-allocation rewrites for the register-allocating back end (-O1).

* :func:`promote_globals` -- global scalars (and array base pointers) that only the generated
  ``$entry`` function touches, and only through direct ``load``/``store``, become virtual
  registers of ``$entry``. Top-level programs keep all their variables in globals; without this
  every access would be a memory operation.
* :func:`prepare_function` -- on a private copy: merge ``t = op ...; x = copy t`` into
  ``x = op ...``, fold ``ptradd`` into the addressing mode of its single load/store, and fuse a
  trailing ``cmp`` into its ``branch``.
"""

from __future__ import annotations

import copy

from compiler.codegen import lir
from compiler.ir import ir as I

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
    out = copy.deepcopy(module)
    fn = next(f for f in out.functions if f.name == I.ENTRY_FUNCTION)
    regs = {n: I.Reg(f"@g.{n}", next(iter(types[n]))) for n in chosen}
    for b in fn.blocks:
        new: list[I.Instr] = []
        for i in b.instrs:
            if isinstance(i, I.Load) and isinstance(i.addr, I.GlobalRef) and i.addr.name in regs:
                new.append(I.Copy(i.dst, regs[i.addr.name]))
            elif isinstance(i, I.Store) and isinstance(i.addr, I.GlobalRef) and i.addr.name in regs:
                new.append(I.Copy(regs[i.addr.name], i.value))
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
                replaced = lir.LoadIdx(i.dst, p.base, p.index)          # type: ignore[union-attr]
                dead.add(pending[i.addr.name])
            elif isinstance(i, I.Store) and isinstance(i.addr, I.Reg) and i.addr.name in pending \
                    and not (isinstance(i.value, I.Reg) and i.value.name == i.addr.name):
                p = b.instrs[pending[i.addr.name]]
                replaced = lir.StoreIdx(p.base, p.index, i.value)       # type: ignore[union-attr]
                dead.add(pending[i.addr.name])
            if replaced is not None:
                del pending[i.addr.name]        # type: ignore[union-attr]
                b.instrs[k] = replaced
                i = replaced
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
            b.term = lir.CmpBranch(last.cond, last.a, last.b, t.then_target, t.else_target)


def prepare_function(fn: I.IRFunction) -> I.IRFunction:
    fn = copy.deepcopy(fn)
    _coalesce_copies(fn)
    _fold_addressing(fn)
    _fuse_cmp_branch(fn)
    return fn
