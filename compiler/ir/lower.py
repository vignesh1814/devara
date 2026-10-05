"""Lowering of the typed tree to three-address IR + CFG (design §5.10–§5.25)."""

from __future__ import annotations

from compiler.ast.nodes import BinaryOp
from compiler.ir import ir as I
from compiler.ir.verify import verify_module
from compiler.semantic import typed as T
from compiler.semantic.checker import const_eval
from compiler.semantic.types import ArrayType, PrimType

try:                                  # constant-size arrays up to this size live in the stack frame
    from compiler.codegen.x86_64 import FRAME_ARRAY_LIMIT
except ImportError:                   # pragma: no cover - back end without a frame policy
    FRAME_ARRAY_LIMIT = 64 * 1024

IT = I.IRType

_CMP = {
    BinaryOp.LT: "LT", BinaryOp.LE: "LE", BinaryOp.GT: "GT", BinaryOp.GE: "GE",
    BinaryOp.EQ: "EQ", BinaryOp.NE: "NE",
}
_ARITH = {
    BinaryOp.ADD: "ADD", BinaryOp.SUB: "SUB", BinaryOp.MUL: "MUL",
    BinaryOp.DIV: "DIV", BinaryOp.MOD: "MOD",
}
_SUFFIX = {IT.I64: "i64", IT.F64: "f64", IT.BOOL: "bool", IT.CHAR: "char", IT.STR: "str"}


def irtype(t) -> IT:
    if isinstance(t, ArrayType):
        return IT.ADDR
    assert isinstance(t, PrimType), t
    return {"int": IT.I64, "float": IT.F64, "bool": IT.BOOL, "char": IT.CHAR,
            "padham": IT.STR, "void": IT.VOID}[t.name]


def zero(t: IT) -> I.Const:
    if t == IT.F64:
        return I.Const(t, 0.0)
    if t == IT.BOOL:
        return I.Const(t, False)
    if t == IT.STR:
        return I.Const(t, b"")
    return I.Const(IT.I64 if t == IT.ADDR else t, 0)


class ArrInfo:
    """How to reach an array variable: base operand source and dimension operands."""

    def __init__(self, kind: str, name: str, base: I.Reg | None, dims: list[I.Operand]) -> None:
        self.kind = kind          # local | static | ptr
        self.name = name
        self.base = base
        self.dims = dims


class Lowerer:
    def __init__(self, tp: T.TypedProgram) -> None:
        self.tp = tp
        self.syms = tp.symbols
        self.globals: list[I.IRGlobal] = []
        self.garrays: dict[int, ArrInfo] = {}
        self.gscalars: dict[int, str] = {}
        # per-function state
        self.blocks: list[I.BasicBlock] = []
        self.cur: I.BasicBlock | None = None
        self.ntemp = 0
        self.nlabel = 0
        self.locals: dict[int, I.Reg] = {}
        self.larrays: dict[int, ArrInfo] = {}
        # loop_id -> (break label, continue label, scope depth of the loop body)
        self.loops: dict[int, tuple[str, str, int]] = {}
        # lexical scopes of the function being lowered, innermost last; each holds the
        # cleanups (in declaration order) to run when the scope is left
        self.scopes: list[list[tuple]] = []
        self.ret = IT.VOID

    # ── module ──

    def run(self) -> I.IRModule:
        self.collect_globals()
        funcs = [self.lower_function(f) for f in self.tp.functions]
        funcs.append(self.lower_entry())
        mod = I.IRModule(globals=self.globals, functions=funcs)
        verify_module(mod)
        return mod

    def collect_globals(self) -> None:
        decls = {s.symbol: s for s in self.tp.entry.stmts if isinstance(s, T.TDecl)}
        for sid in self.tp.globals:
            sym = self.syms[sid]
            if isinstance(sym.type, ArrayType):
                d = decls[sid]
                consts = [const_eval(x) for x in d.dims]
                elem = irtype(sym.type.element)
                if all(c is not None for c in consts):
                    dims = [int(c) for c in consts]
                    count = 1
                    for x in dims:
                        count *= x
                    self.globals.append(I.IRGlobal(sym.name, elem, "array_static", count))
                    self.garrays[sid] = ArrInfo("static", sym.name, None,
                                                [I.Const(IT.I64, x) for x in dims])
                else:
                    self.globals.append(I.IRGlobal(sym.name, elem, "array_ptr", 1))
                    dim_ops: list[I.Operand] = []
                    for j in range(len(d.dims)):
                        gname = f"{sym.name}.d{j}"
                        self.globals.append(I.IRGlobal(gname, IT.I64, "scalar", 1))
                    self.garrays[sid] = ArrInfo("ptr", sym.name, None, dim_ops)
            else:
                self.globals.append(I.IRGlobal(sym.name, irtype(sym.type), "scalar", 1))
                self.gscalars[sid] = sym.name

    # ── function plumbing ──

    def begin_function(self) -> None:
        self.blocks = []
        self.cur = None
        self.ntemp = 0
        self.nlabel = 0
        self.locals = {}
        self.larrays = {}
        self.loops = {}
        self.scopes = []
        self.start(self.label("entry"))

    def finish_function(self, name: str, params: list[I.Reg], ret: IT) -> I.IRFunction:
        if self.cur is not None:
            self.terminate(I.Return(None if ret == IT.VOID else zero(ret)))
        for b in self.blocks:
            if b.term is None:
                b.term = I.Return(None if ret == IT.VOID else zero(ret))
        return I.IRFunction(name=name, params=params, ret=ret, blocks=self.blocks)

    def label(self, hint: str) -> str:
        self.nlabel += 1
        return f"{hint}{self.nlabel}"

    def start(self, label: str) -> None:
        assert self.cur is None, "previous block not terminated"
        blk = I.BasicBlock(label=label, instrs=[], term=None)  # type: ignore[arg-type]
        self.blocks.append(blk)
        self.cur = blk

    def terminate(self, term: I.Terminator) -> None:
        if self.cur is None:                  # unreachable code after ivvu/aapu/saagu
            self.start(self.label("dead"))
        assert self.cur is not None
        self.cur.term = term
        self.cur = None

    def jump(self, target: str) -> None:
        if self.cur is not None:
            self.terminate(I.Jump(target))

    def emit(self, ins: I.Instr) -> None:
        if self.cur is None:
            self.start(self.label("dead"))
        assert self.cur is not None
        self.cur.instrs.append(ins)

    def temp(self, t: IT) -> I.Reg:
        self.ntemp += 1
        return I.Reg(f"t{self.ntemp}", t)

    def varreg(self, sid: int) -> I.Reg:
        r = self.locals.get(sid)
        if r is None:
            sym = self.syms[sid]
            r = I.Reg(f"{sym.name}.{sid}", irtype(sym.type))
            self.locals[sid] = r
        return r

    def lower_function(self, f: T.TFunction) -> I.IRFunction:
        self.begin_function()
        self.ret = irtype(f.ret)
        params = []
        for pid in f.params:
            sym = self.syms[pid]
            r = self.varreg(pid)
            params.append(r)
            if isinstance(sym.type, ArrayType):
                self.larrays[pid] = ArrInfo("local", sym.name, r, [])
        self.block(f.body)
        return self.finish_function(f.name, params, self.ret)

    def lower_entry(self) -> I.IRFunction:
        self.begin_function()
        self.ret = IT.VOID
        self.block(self.tp.entry)
        if self.cur is not None:
            self.global_epilogue()
        return self.finish_function(I.ENTRY_FUNCTION, [], IT.VOID)

    # ── statements ──

    def block(self, b: T.TBlock) -> None:
        """Lower a block as one lexical scope; falling off its end runs the scope's cleanups."""
        self.scopes.append([])
        for s in b.stmts:
            self.stmt(s)
        self.pop_scope()

    # ── scope cleanups (P22) ──

    def pop_scope(self) -> None:
        """Leave the innermost scope on the fallthrough path (skipped when it is unreachable:
        the jump/return that ended the path already ran the cleanups)."""
        entries = self.scopes.pop()
        if self.cur is not None:
            for ent in reversed(entries):
                self.emit_cleanup(ent)

    def unwind(self, depth: int) -> None:
        """Run the cleanups of every scope above ``depth`` (innermost first) without leaving
        them lexically: used by ivvu (depth 0) and aapu/saagu (depth of the loop body)."""
        for entries in reversed(self.scopes[depth:]):
            for ent in reversed(entries):
                self.emit_cleanup(ent)

    def emit_cleanup(self, ent: tuple) -> None:
        kind = ent[0]
        if kind == "heap":                       # ("heap", base)
            self.emit(I.RtCall(None, "dv_rt_freearray", [ent[1]]))
        else:
            raise AssertionError(kind)

    def global_epilogue(self) -> None:
        """End of the program entry: release global storage, then the runtime shutdown hook."""
        for sid in reversed(self.tp.globals):
            sym = self.syms[sid]
            info = self.garrays.get(sid)
            if info is not None and info.kind == "ptr":
                p = self.temp(IT.ADDR)
                self.emit(I.Load(p, I.GlobalRef(info.name)))
                self.emit(I.RtCall(None, "dv_rt_freearray", [p]))
        self.emit(I.RtCall(None, "dv_rt_shutdown", []))

    def stmt(self, s: T.TStmt) -> None:
        getattr(self, "s_" + type(s).__name__)(s)

    def s_TBlock(self, s: T.TBlock) -> None:
        self.block(s)

    def s_TDecl(self, s: T.TDecl) -> None:
        sym = self.syms[s.symbol]
        if not isinstance(sym.type, ArrayType):
            if not sym.is_global:
                self.varreg(s.symbol)
            return
        info = self.garrays.get(s.symbol) if sym.is_global else None
        if info is not None and info.kind == "static":
            return
        dims: list[I.Operand] = [self.expr(d) for d in s.dims]
        for d in dims:
            if not (isinstance(d, I.Const) and d.value >= 1):
                self.emit(I.RtCall(None, "dv_rt_checkdim", [d]))
        total: I.Operand = dims[0]
        for d in dims[1:]:
            t = self.temp(IT.I64)
            self.emit(I.BinOp("MUL", t, total, d))
            total = t
        base = self.temp(IT.ADDR)
        # Small constant-size local arrays live in the stack frame (NewArray with a constant
        # count: the back end zero-fills them and they need no freeing). Everything else is
        # allocated explicitly on the heap and freed when its scope is left.
        frame = info is None and self.frame_size(dims) is not None
        if frame:
            self.emit(I.NewArray(base, I.Const(IT.I64, self.frame_size(dims))))
        else:
            self.emit(I.RtCall(base, "dv_rt_newarray", [total]))
        if info is not None:       # global array with run-time dimensions
            self.emit(I.Store(I.GlobalRef(sym.name), base))
            for j, d in enumerate(dims):
                self.emit(I.Store(I.GlobalRef(f"{sym.name}.d{j}"), d))
            return
        breg = I.Reg(f"{sym.name}.{s.symbol}", IT.ADDR)
        self.emit(I.Copy(breg, base))
        snap: list[I.Operand] = []
        for j, d in enumerate(dims):
            if isinstance(d, I.Const):
                snap.append(d)
            else:
                r = I.Reg(f"{sym.name}.{s.symbol}.d{j}", IT.I64)
                self.emit(I.Copy(r, d))
                snap.append(r)
        self.larrays[s.symbol] = ArrInfo("local", sym.name, breg, snap)
        if not frame:
            self.scopes[-1].append(("heap", breg))

    @staticmethod
    def frame_size(dims: list[I.Operand]) -> int | None:
        """Element count if every dimension is a positive constant and the array is small
        enough for the frame, else None."""
        n = 1
        for d in dims:
            if not (isinstance(d, I.Const) and d.value >= 1):
                return None
            n *= d.value
            if n * 8 > FRAME_ARRAY_LIMIT:
                return None
        return n

    def lvalue(self, target: T.TExpr):
        """Resolve an assignment target; address computed *before* the value (P40)."""
        if isinstance(target, T.TVar):
            if target.symbol in self.gscalars:
                return ("mem", I.GlobalRef(self.gscalars[target.symbol]))
            return ("reg", self.varreg(target.symbol))
        assert isinstance(target, T.TIndex)
        return ("mem", self.element_addr(target))

    def write(self, lv, value: I.Operand) -> None:
        kind, loc = lv
        if kind == "reg":
            self.emit(I.Copy(loc, value))
        else:
            self.emit(I.Store(loc, value))

    def read(self, lv, t: IT) -> I.Operand:
        kind, loc = lv
        if kind == "reg":
            return loc
        r = self.temp(t)
        self.emit(I.Load(r, loc))
        return r

    def s_TAssign(self, s: T.TAssign) -> None:
        lv = self.lvalue(s.target)
        v = self.expr(s.value)
        self.write(lv, v)

    def s_TInput(self, s: T.TInput) -> None:
        lv = self.lvalue(s.target)
        t = irtype(s.target.type)
        r = self.temp(t)
        self.emit(I.RtCall(r, f"dv_rt_input_{_SUFFIX[t]}", []))
        self.write(lv, r)

    def s_TOutput(self, s: T.TOutput) -> None:
        v = self.expr(s.value)
        t = irtype(s.value.type)
        self.emit(I.RtCall(None, f"dv_rt_output_{_SUFFIX[t]}", [v]))

    def s_TIncDec(self, s: T.TIncDec) -> None:
        lv = self.lvalue(s.target)
        t = irtype(s.target.type)
        cur = self.read(lv, t)
        op = "ADD" if s.delta > 0 else "SUB"
        if t == IT.F64:
            res = lv[1] if lv[0] == "reg" else self.temp(IT.F64)
            self.emit(I.BinOp(op, res, cur, I.Const(IT.F64, 1.0)))
            if lv[0] == "mem":
                self.write(lv, res)
        elif t == IT.I64:
            res = lv[1] if lv[0] == "reg" else self.temp(IT.I64)
            self.emit(I.BinOp(op, res, cur, I.Const(IT.I64, 1)))
            if lv[0] == "mem":
                self.write(lv, res)
        else:  # char: widen, step, wrap back to 8 bits
            wide = self.temp(IT.I64)
            self.emit(I.Convert(wide, cur))
            stepped = self.temp(IT.I64)
            self.emit(I.BinOp(op, stepped, wide, I.Const(IT.I64, 1)))
            res = lv[1] if lv[0] == "reg" else self.temp(IT.CHAR)
            self.emit(I.Convert(res, stepped))
            if lv[0] == "mem":
                self.write(lv, res)

    def s_TExprStmt(self, s: T.TExprStmt) -> None:
        self.call(s.call, want_value=False)

    def s_TReturn(self, s: T.TReturn) -> None:
        v = self.expr(s.value) if s.value is not None else None   # value first, then cleanups
        self.unwind(0)
        self.terminate(I.Return(v))

    def s_TBreak(self, s: T.TBreak) -> None:
        target, _, depth = self.loops[s.loop_id]
        self.unwind(depth)
        self.jump(target)

    def s_TContinue(self, s: T.TContinue) -> None:
        _, target, depth = self.loops[s.loop_id]
        self.unwind(depth)
        self.jump(target)

    def s_TIf(self, s: T.TIf) -> None:
        then_l = self.label("then")
        merge_l = self.label("endif")
        else_l = self.label("else") if s.else_block is not None else merge_l
        self.cond(s.condition, then_l, else_l)
        self.start(then_l)
        self.block(s.then_block)
        self.jump(merge_l)
        if s.else_block is not None:
            self.start(else_l)
            self.block(s.else_block)
            self.jump(merge_l)
        self.start(merge_l)

    def s_TWhile(self, s: T.TWhile) -> None:
        cond_l, body_l, exit_l = self.label("wcond"), self.label("wbody"), self.label("wexit")
        self.jump(cond_l)
        self.start(cond_l)
        self.cond(s.condition, body_l, exit_l)
        self.start(body_l)
        self.loops[s.loop_id] = (exit_l, cond_l, len(self.scopes))
        self.block(s.body)
        self.jump(cond_l)
        self.start(exit_l)

    def s_TRange(self, s: T.TRange) -> None:
        start = self.expr(s.start)
        end = self.expr(s.end)
        endr = self.temp(IT.I64)               # end evaluated exactly once
        self.emit(I.Copy(endr, end))
        var = self.varreg(s.variable)
        self.emit(I.Copy(var, start))
        cond_l, body_l = self.label("rcond"), self.label("rbody")
        incr_l, exit_l = self.label("rincr"), self.label("rexit")
        self.jump(cond_l)
        self.start(cond_l)
        c = self.temp(IT.BOOL)
        self.emit(I.Cmp("LT", c, var, endr))
        self.terminate(I.Branch(c, body_l, exit_l))
        self.start(body_l)
        self.loops[s.loop_id] = (exit_l, incr_l, len(self.scopes))
        self.block(s.body)
        self.jump(incr_l)
        self.start(incr_l)
        self.emit(I.BinOp("ADD", var, var, I.Const(IT.I64, 1)))
        self.jump(cond_l)
        self.start(exit_l)

    def s_TFor(self, s: T.TFor) -> None:
        self.scopes.append([])               # the loop scope holds the init declarations
        for i in s.init:
            self.stmt(i)
        cond_l, body_l = self.label("fcond"), self.label("fbody")
        upd_l, exit_l = self.label("fupd"), self.label("fexit")
        self.jump(cond_l)
        self.start(cond_l)
        self.cond(s.condition, body_l, exit_l)
        self.start(body_l)
        self.loops[s.loop_id] = (exit_l, upd_l, len(self.scopes))
        self.block(s.body)
        self.jump(upd_l)
        self.start(upd_l)
        self.stmt(s.update)
        self.jump(cond_l)
        self.start(exit_l)
        self.pop_scope()

    # ── conditions (short-circuit via branches) ──

    def cond(self, e: T.TExpr, tl: str, fl: str) -> None:
        if isinstance(e, T.TBinary) and e.op in (BinaryOp.AND, BinaryOp.OR):
            mid = self.label("sc")
            if e.op == BinaryOp.AND:
                self.cond(e.left, mid, fl)
            else:
                self.cond(e.left, tl, mid)
            self.start(mid)
            self.cond(e.right, tl, fl)
            return
        if isinstance(e, T.TUnary) and e.op == "NOT":
            self.cond(e.operand, fl, tl)
            return
        v = self.expr(e)
        self.terminate(I.Branch(v, tl, fl))

    # ── expressions ──

    def expr(self, e: T.TExpr) -> I.Operand:
        return getattr(self, "e_" + type(e).__name__)(e)

    def e_TLiteral(self, e: T.TLiteral) -> I.Operand:
        t = irtype(e.type)
        v = e.value
        if t == IT.F64:
            v = float(v)
        return I.Const(t, v)

    def array_base(self, sid: int) -> I.Operand:
        info = self.larrays.get(sid)
        if info is not None:
            return info.base  # type: ignore[return-value]
        ginfo = self.garrays[sid]
        if ginfo.kind == "static":
            return I.GlobalRef(ginfo.name)
        r = self.temp(IT.ADDR)
        self.emit(I.Load(r, I.GlobalRef(ginfo.name)))
        return r

    def array_dim(self, sid: int, j: int) -> I.Operand:
        info = self.larrays.get(sid)
        if info is not None:
            return info.dims[j]
        ginfo = self.garrays[sid]
        if ginfo.kind == "static":
            return ginfo.dims[j]
        r = self.temp(IT.I64)
        self.emit(I.Load(r, I.GlobalRef(f"{ginfo.name}.d{j}")))
        return r

    def e_TVar(self, e: T.TVar) -> I.Operand:
        if isinstance(e.type, ArrayType):
            return self.array_base(e.symbol)
        if e.symbol in self.gscalars:
            r = self.temp(irtype(e.type))
            self.emit(I.Load(r, I.GlobalRef(self.gscalars[e.symbol])))
            return r
        return self.varreg(e.symbol)

    def element_addr(self, e: T.TIndex) -> I.Operand:
        rank = self.syms[e.symbol].type.rank  # type: ignore[union-attr]
        base = self.array_base(e.symbol)
        idx = [self.expr(i) for i in e.indices]
        off: I.Operand = idx[0]
        for j in range(1, rank):
            d = self.array_dim(e.symbol, j)
            m = self.temp(IT.I64)
            self.emit(I.BinOp("MUL", m, off, d))
            off = m
            if j < len(idx):
                a = self.temp(IT.I64)
                self.emit(I.BinOp("ADD", a, off, idx[j]))
                off = a
        addr = self.temp(IT.ADDR)
        self.emit(I.PtrAdd(addr, base, off))
        return addr

    def e_TIndex(self, e: T.TIndex) -> I.Operand:
        addr = self.element_addr(e)
        if isinstance(e.type, ArrayType):
            return addr
        r = self.temp(irtype(e.type))
        self.emit(I.Load(r, addr))
        return r

    def e_TStringIndex(self, e: T.TStringIndex) -> I.Operand:
        s = self.expr(e.string)
        i = self.expr(e.index)
        r = self.temp(IT.CHAR)
        self.emit(I.RtCall(r, "dv_rt_strindex", [s, i]))
        return r

    def e_TUnary(self, e: T.TUnary) -> I.Operand:
        if e.op == "NOT":
            return self.bool_value(e)
        v = self.expr(e.operand)
        r = self.temp(irtype(e.type))
        self.emit(I.UnOp("NEG", r, v))
        return r

    def bool_value(self, e: T.TExpr) -> I.Operand:
        """Materialize a short-circuit/negation expression as a bool register."""
        tl, fl, join = self.label("btrue"), self.label("bfalse"), self.label("bjoin")
        r = self.temp(IT.BOOL)
        self.cond(e, tl, fl)
        self.start(tl)
        self.emit(I.Copy(r, I.Const(IT.BOOL, True)))
        self.jump(join)
        self.start(fl)
        self.emit(I.Copy(r, I.Const(IT.BOOL, False)))
        self.jump(join)
        self.start(join)
        return r

    def e_TBinary(self, e: T.TBinary) -> I.Operand:
        if e.op in (BinaryOp.AND, BinaryOp.OR):
            return self.bool_value(e)
        a = self.expr(e.left)
        b = self.expr(e.right)
        if e.op in _CMP:
            r = self.temp(IT.BOOL)
            self.emit(I.Cmp(_CMP[e.op], r, a, b))
            return r
        if e.type == PrimType("padham"):
            r = self.temp(IT.STR)
            self.emit(I.RtCall(r, "dv_rt_strcat", [a, b]))
            return r
        r = self.temp(irtype(e.type))
        self.emit(I.BinOp(_ARITH[e.op], r, a, b))
        return r

    def e_TConvert(self, e: T.TConvert) -> I.Operand:
        v = self.expr(e.operand)
        src, dst = irtype(e.operand.type), irtype(e.type)
        if src == dst:
            return v
        r = self.temp(dst)
        if src == IT.CHAR and dst == IT.STR:
            self.emit(I.RtCall(r, "dv_rt_char2str", [v]))
        elif src == IT.STR and dst == IT.CHAR:
            self.emit(I.RtCall(r, "dv_rt_str2char", [v]))
        else:
            self.emit(I.Convert(r, v))
        return r

    def e_TCall(self, e: T.TCall) -> I.Operand:
        r = self.call(e, want_value=True)
        assert r is not None
        return r

    def call(self, e: T.TCall, *, want_value: bool) -> I.Reg | None:
        args = [self.expr(a) for a in e.args]
        sym = self.syms[e.callee]
        ret = irtype(e.type)
        dst = self.temp(ret) if ret != IT.VOID and want_value else None
        if sym.kind == "builtin":
            assert sym.name == "podavu"
            if dst is None:
                dst = self.temp(IT.I64)
            self.emit(I.RtCall(dst, "dv_rt_strlen", args))
        else:
            self.emit(I.Call(dst, sym.name, args))
        return dst


def lower_program(typed: T.TypedProgram) -> I.IRModule:
    return Lowerer(typed).run()
