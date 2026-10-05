"""IR verifier (design §5.26): a correctness barrier before/after every pass."""

from __future__ import annotations

from compiler.diagnostics import InternalCompilerError
from compiler.ir import ir as I
from compiler.ir.runtime import RUNTIME
from compiler.ir.util import operand_fields, term_uses as _term_uses, uses as _uses

T = I.IRType
_ARITH = (T.I64, T.F64)
_VALUE = (T.I64, T.F64, T.BOOL, T.CHAR)
_NUMERIC_CONV = (T.I64, T.F64, T.BOOL, T.CHAR)


def check_module(m: I.IRModule) -> list[str]:
    errs: list[str] = []
    gnames = {g.name for g in m.globals}
    if len(gnames) != len(m.globals):
        errs.append("duplicate global names")
    sigs = {f.name: ([p.type for p in f.params], f.ret) for f in m.functions}
    if len(sigs) != len(m.functions):
        errs.append("duplicate function names")
    if I.ENTRY_FUNCTION not in sigs:
        errs.append(f"missing entry function {I.ENTRY_FUNCTION}")
    for f in m.functions:
        _check_function(f, sigs, gnames, errs)
    return errs


def verify_module(m: I.IRModule) -> None:
    errs = check_module(m)
    if errs:
        raise InternalCompilerError("IR verification failed:\n  " + "\n  ".join(errs))


def _check_function(f: I.IRFunction, sigs, gnames, errs: list[str]) -> None:
    def bad(msg: str) -> None:
        errs.append(f"{f.name}: {msg}")

    if not f.blocks:
        bad("function has no blocks")
        return
    labels = [b.label for b in f.blocks]
    if len(set(labels)) != len(labels):
        bad("duplicate block labels")
    lset = set(labels)

    regtypes: dict[str, T] = {}
    defined: set[str] = set()

    def see(r: I.Reg) -> None:
        old = regtypes.setdefault(r.name, r.type)
        if old != r.type:
            bad(f"register {r.name} used with types {old} and {r.type}")

    for p in f.params:
        see(p)
        defined.add(p.name)
    if any(p.type == T.VOID for p in f.params):
        bad("void parameter")

    def ty(o) -> T:
        if isinstance(o, I.Reg):
            see(o)
            return o.type
        if isinstance(o, I.GlobalRef):
            if o.name not in gnames:
                bad(f"unknown global @{o.name}")
            return T.ADDR
        if isinstance(o, I.Const):
            v = o.value
            ok = (
                (o.type in (T.I64, T.CHAR) and isinstance(v, int) and not isinstance(v, bool))
                or (o.type == T.F64 and isinstance(v, float))
                or (o.type == T.BOOL and isinstance(v, bool))
                or (o.type == T.STR and isinstance(v, bytes))
            )
            if not ok:
                bad(f"malformed constant {o}")
            if o.type == T.I64 and isinstance(v, int) and not (-(1 << 63) <= v < (1 << 63)):
                bad("i64 constant out of range")
            if o.type == T.CHAR and isinstance(v, int) and not (-128 <= v <= 127):
                bad("char constant out of range")
            return o.type
        bad(f"bad operand {o!r}")
        return T.VOID

    def defreg(r: I.Reg | None) -> None:
        if r is not None:
            see(r)
            defined.add(r.name)

    used: list[str] = []
    for b in f.blocks:
        for i in b.instrs:
            # a str constant has no refcount header: it may only be handed to dv_rt_strlit,
            # which returns the immortal runtime string (padham values are always loaded)
            ops = [getattr(i, n) for n in operand_fields(i)] + list(getattr(i, "args", []))
            if not (isinstance(i, I.RtCall) and i.name == "dv_rt_strlit"):
                if any(isinstance(o, I.Const) and o.type == T.STR for o in ops):
                    bad("str constant used outside dv_rt_strlit")
            if isinstance(i, I.Copy):
                st = ty(i.src)
                if st != i.dst.type or st == T.VOID:
                    bad(f"copy type mismatch {st} -> {i.dst.type}")
                defreg(i.dst)
            elif isinstance(i, I.UnOp):
                st = ty(i.src)
                if i.op == "NEG" and not (st in _ARITH and i.dst.type == st):
                    bad("neg needs i64/f64 with same dst type")
                elif i.op == "NOT" and not (st == T.BOOL and i.dst.type == T.BOOL):
                    bad("not needs bool")
                elif i.op not in ("NEG", "NOT"):
                    bad(f"unknown unop {i.op}")
                defreg(i.dst)
            elif isinstance(i, I.BinOp):
                at, bt = ty(i.a), ty(i.b)
                if i.op not in ("ADD", "SUB", "MUL", "DIV", "MOD"):
                    bad(f"unknown binop {i.op}")
                if not (at == bt == i.dst.type and at in _ARITH):
                    bad(f"binop {i.op} operand/result types differ: {at},{bt}->{i.dst.type}")
                if i.op == "MOD" and i.dst.type != T.I64:
                    bad("mod requires i64")
                defreg(i.dst)
            elif isinstance(i, I.Cmp):
                at, bt = ty(i.a), ty(i.b)
                if i.cond not in ("LT", "LE", "GT", "GE", "EQ", "NE"):
                    bad(f"unknown cmp {i.cond}")
                if at != bt or at not in (T.I64, T.F64, T.STR):
                    bad(f"cmp operand types {at},{bt}")
                if at == T.STR and i.cond not in ("EQ", "NE"):
                    bad("str supports only EQ/NE")
                if i.dst.type != T.BOOL:
                    bad("cmp result must be bool")
                defreg(i.dst)
            elif isinstance(i, I.Convert):
                st = ty(i.src)
                if st not in _NUMERIC_CONV or i.dst.type not in _NUMERIC_CONV:
                    bad(f"convert {st}->{i.dst.type} unsupported")
                defreg(i.dst)
            elif isinstance(i, I.Load):
                if ty(i.addr) != T.ADDR:
                    bad("load address must be addr")
                if i.dst.type in (T.VOID, T.ADDR) and False:
                    pass
                defreg(i.dst)
            elif isinstance(i, I.Store):
                if ty(i.addr) != T.ADDR:
                    bad("store address must be addr")
                if ty(i.value) == T.VOID:
                    bad("store of void")
            elif isinstance(i, I.PtrAdd):
                if ty(i.base) != T.ADDR or ty(i.index) != T.I64 or i.dst.type != T.ADDR:
                    bad("ptradd needs addr, i64 -> addr")
                defreg(i.dst)
            elif isinstance(i, I.NewArray):
                if ty(i.count) != T.I64 or i.dst.type != T.ADDR:
                    bad("newarray needs i64 -> addr")
                defreg(i.dst)
            elif isinstance(i, I.Call):
                sig = sigs.get(i.callee)
                if sig is None:
                    bad(f"call to unknown function {i.callee}")
                    for a in i.args:
                        ty(a)
                else:
                    ptypes, ret = sig
                    if len(i.args) != len(ptypes):
                        bad(f"call {i.callee}: expected {len(ptypes)} args, got {len(i.args)}")
                    for a, pt in zip(i.args, ptypes):
                        if ty(a) != pt:
                            bad(f"call {i.callee}: argument type {ty(a)} != {pt}")
                    if i.dst is None and ret != T.VOID:
                        pass  # result ignored
                    if i.dst is not None and i.dst.type != ret:
                        bad(f"call {i.callee}: result type {i.dst.type} != {ret}")
                defreg(i.dst)
            elif isinstance(i, I.RtCall):
                sig = RUNTIME.get(i.name)
                if sig is None:
                    bad(f"unknown runtime function {i.name}")
                else:
                    ptypes, ret = sig
                    if len(i.args) != len(ptypes):
                        bad(f"rtcall {i.name}: expected {len(ptypes)} args")
                    for a, pt in zip(i.args, ptypes):
                        if ty(a) != pt:
                            bad(f"rtcall {i.name}: argument type {ty(a)} != {pt}")
                    if (i.dst is None) != (ret == T.VOID) and i.dst is not None:
                        bad(f"rtcall {i.name}: void result assigned")
                    if i.dst is not None and i.dst.type != ret:
                        bad(f"rtcall {i.name}: result type mismatch")
                defreg(i.dst)
            else:
                bad(f"unknown instruction {type(i).__name__}")

        t = b.term
        if isinstance(t, I.Jump):
            if t.target not in lset:
                bad(f"{b.label}: jump to unknown label {t.target}")
        elif isinstance(t, I.Branch):
            if ty(t.cond) != T.BOOL:
                bad(f"{b.label}: branch condition must be bool")
            for tg in (t.then_target, t.else_target):
                if tg not in lset:
                    bad(f"{b.label}: branch to unknown label {tg}")
        elif isinstance(t, I.Return):
            if t.value is None:
                if f.ret != T.VOID:
                    bad(f"{b.label}: bare return in non-void function")
            else:
                if f.ret == T.VOID:
                    bad(f"{b.label}: value return in void function")
                elif ty(t.value) != f.ret:
                    bad(f"{b.label}: return type {ty(t.value)} != {f.ret}")
        else:
            bad(f"{b.label}: missing/unknown terminator")

    # every register that is read must be written somewhere (or be a parameter)
    for b in f.blocks:
        for i in b.instrs:
            for r in _uses(i):
                if r.name not in defined:
                    bad(f"register {r.name} is read but never defined")
        for r in _term_uses(b.term):
            if r.name not in defined:
                bad(f"register {r.name} is read but never defined")
