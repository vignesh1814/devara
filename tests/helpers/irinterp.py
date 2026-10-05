"""A small IR interpreter used as the developer-side oracle for lowering and the optimizer.

It implements the runtime contract P1–P11 directly in Python so IR can be executed
and compared (O0 vs O1) before/independently of the x86-64 back end.
"""

from __future__ import annotations

import math
import sys

from compiler import arith
from compiler.ir import ir as I
from compiler.opt.passes import convert_const

IT = I.IRType


class RuntimeFailure(Exception):
    pass


class Addr:
    __slots__ = ("mem", "idx")

    def __init__(self, mem: list, idx: int = 0) -> None:
        self.mem = mem
        self.idx = idx

    def __add__(self, n: int) -> "Addr":
        return Addr(self.mem, self.idx + n)


def zero(t: IT):
    return {IT.I64: 0, IT.CHAR: 0, IT.F64: 0.0, IT.BOOL: False, IT.STR: b"", IT.ADDR: None}[t]


def fmt_g(x: float) -> str:
    if math.isnan(x):
        return "-nan" if math.copysign(1.0, x) < 0 else "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return "%g" % x


class Input:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.after_token = False

    def token(self) -> bytes:
        d = self.data
        while self.pos < len(d) and d[self.pos] in b" \t\n\r\v\f":
            self.pos += 1
        start = self.pos
        while self.pos < len(d) and d[self.pos] not in b" \t\n\r\v\f":
            self.pos += 1
        if start == self.pos:
            raise RuntimeFailure("invalid input")
        self.after_token = True
        return d[start:self.pos]

    def line(self) -> bytes:
        d = self.data
        if self.after_token:
            p = self.pos
            while p < len(d) and d[p] in b" \t\r\v\f":
                p += 1
            if p < len(d) and d[p] == ord("\n"):
                self.pos = p + 1
            elif p >= len(d):
                self.pos = p
            self.after_token = False
        if self.pos >= len(d):
            raise RuntimeFailure("invalid input")
        end = d.find(b"\n", self.pos)
        if end < 0:
            s, self.pos = d[self.pos:], len(d)
        else:
            s, self.pos = d[self.pos:end], end + 1
        return s


class Interp:
    def __init__(self, module: I.IRModule, stdin: bytes = b"") -> None:
        self.m = module
        self.funcs = {f.name: f for f in module.functions}
        self.out = bytearray()
        self.inp = Input(stdin)
        self.gmem: dict[str, list] = {}
        for g in module.globals:
            if g.kind == "array_static":
                self.gmem[g.name] = [zero(g.type)] * g.count
            elif g.kind == "array_ptr":
                self.gmem[g.name] = [None]
            else:
                self.gmem[g.name] = [zero(g.type)]
        self.steps = 0

    def run(self, step_limit: int = 3_000_000) -> tuple[bytes, int, str]:
        self.limit = step_limit
        sys.setrecursionlimit(100000)
        try:
            self.call(I.ENTRY_FUNCTION, [])
            return bytes(self.out), 0, ""
        except RuntimeFailure as e:
            return bytes(self.out), 1, f"devara: runtime error: {e}"

    # ── operands ──

    def val(self, env: dict, o: I.Operand):
        if isinstance(o, I.Reg):
            return env[o.name]
        if isinstance(o, I.GlobalRef):
            return Addr(self.gmem[o.name], 0)
        return o.value

    def call(self, name: str, args: list):
        f = self.funcs[name]
        env = {p.name: a for p, a in zip(f.params, args)}
        by = {b.label: b for b in f.blocks}
        blk = f.blocks[0]
        while True:
            for ins in blk.instrs:
                self.steps += 1
                if self.steps > self.limit:
                    raise RuntimeFailure("step limit exceeded")
                self.exec(ins, env)
            t = blk.term
            if isinstance(t, I.Jump):
                blk = by[t.target]
            elif isinstance(t, I.Branch):
                blk = by[t.then_target if self.val(env, t.cond) else t.else_target]
            else:
                return None if t.value is None else self.val(env, t.value)

    def exec(self, i: I.Instr, env: dict) -> None:
        v = lambda o: self.val(env, o)
        if isinstance(i, I.Copy):
            env[i.dst.name] = v(i.src)
        elif isinstance(i, I.UnOp):
            x = v(i.src)
            if i.op == "NOT":
                env[i.dst.name] = not x
            elif i.dst.type == IT.I64:
                env[i.dst.name] = arith.wrap64(-x)
            else:
                env[i.dst.name] = -x
        elif isinstance(i, I.BinOp):
            env[i.dst.name] = self.binop(i, v(i.a), v(i.b))
        elif isinstance(i, I.Cmp):
            a, b = v(i.a), v(i.b)
            env[i.dst.name] = {"LT": a < b, "LE": a <= b, "GT": a > b,
                               "GE": a >= b, "EQ": a == b, "NE": a != b}[i.cond] \
                if not isinstance(a, bytes) else ((a == b) if i.cond == "EQ" else (a != b))
        elif isinstance(i, I.Convert):
            src_t = i.src.type if not isinstance(i.src, I.GlobalRef) else IT.ADDR
            env[i.dst.name] = convert_const(v(i.src), src_t, i.dst.type)
        elif isinstance(i, I.Load):
            a = v(i.addr)
            x = a.mem[a.idx]
            t = i.dst.type
            if x is None or (isinstance(x, int) and not isinstance(x, bool) and t in (IT.F64, IT.BOOL, IT.STR)):
                x = zero(t) if t != IT.ADDR else None
            env[i.dst.name] = x
        elif isinstance(i, I.Store):
            a = v(i.addr)
            a.mem[a.idx] = v(i.value)
        elif isinstance(i, I.PtrAdd):
            env[i.dst.name] = v(i.base) + v(i.index)
        elif isinstance(i, I.NewArray):
            n = v(i.count)
            if n < 1:
                raise RuntimeFailure("invalid array size")
            env[i.dst.name] = Addr([0] * n, 0)
        elif isinstance(i, I.Call):
            r = self.call(i.callee, [v(a) for a in i.args])
            if i.dst is not None:
                env[i.dst.name] = r
        elif isinstance(i, I.RtCall):
            r = self.rt(i.name, [v(a) for a in i.args])
            if i.dst is not None:
                env[i.dst.name] = r
        else:
            raise AssertionError(i)

    def binop(self, i: I.BinOp, a, b):
        if i.dst.type == IT.F64:
            if i.op == "ADD": return a + b
            if i.op == "SUB": return a - b
            if i.op == "MUL": return a * b
            return arith.fdiv(a, b)
        if i.op == "ADD": return arith.wrap64(a + b)
        if i.op == "SUB": return arith.wrap64(a - b)
        if i.op == "MUL": return arith.wrap64(a * b)
        if b == 0:
            raise RuntimeFailure("division by zero" if i.op == "DIV" else "remainder by zero")
        if i.op == "DIV":
            if a == arith.INT64_MIN and b == -1:
                raise RuntimeFailure("integer overflow in division")
            return arith.idiv(a, b)
        return arith.irem(a, b)

    # ── runtime library (P1–P11) ──

    def rt(self, name: str, a: list):
        out = self.out
        if name == "dv_rt_output_i64": out += b"%d\n" % a[0]
        elif name == "dv_rt_output_f64": out += fmt_g(a[0]).encode() + b"\n"
        elif name == "dv_rt_output_bool": out += (b"nijam" if a[0] else b"abaddham") + b"\n"
        elif name == "dv_rt_output_char": out += bytes([a[0] & 0xFF]) + b"\n"
        elif name == "dv_rt_output_str": out += bytes(a[0]) + b"\n"
        elif name == "dv_rt_input_i64":
            tok = self.inp.token()
            try:
                s = tok.decode()
                if not (s.lstrip("+-").isdigit() and s.count("+") + s.count("-") <= 1 and s[0] in "+-0123456789"):
                    raise ValueError
                x = int(s)
            except ValueError:
                raise RuntimeFailure("invalid input")
            if not (arith.INT64_MIN <= x <= arith.INT64_MAX):
                raise RuntimeFailure("invalid input")
            return x
        elif name == "dv_rt_input_f64":
            tok = self.inp.token()
            try:
                return float(tok.decode())
            except ValueError:
                raise RuntimeFailure("invalid input")
        elif name == "dv_rt_input_bool":
            tok = self.inp.token().lower()
            if tok in (b"nijam", b"1"): return True
            if tok in (b"abaddham", b"0"): return False
            raise RuntimeFailure("invalid input")
        elif name == "dv_rt_input_char":
            d = self.inp.data
            p = self.inp.pos
            while p < len(d) and d[p] in b" \t\n\r\v\f":
                p += 1
            if p >= len(d):
                raise RuntimeFailure("invalid input")
            self.inp.pos = p + 1
            self.inp.after_token = True
            return arith.wrap8(d[p])
        elif name == "dv_rt_input_str": return self.inp.line()
        elif name == "dv_rt_strcat": return bytes(a[0]) + bytes(a[1])
        elif name == "dv_rt_streq": return bytes(a[0]) == bytes(a[1])
        elif name == "dv_rt_strindex":
            s, k = bytes(a[0]), a[1]
            if k < 0 or k >= len(s):
                raise RuntimeFailure("string index out of range")
            return arith.wrap8(s[k])
        elif name == "dv_rt_strlen": return len(bytes(a[0]))
        elif name == "dv_rt_char2str": return bytes([a[0] & 0xFF])
        elif name == "dv_rt_str2char":
            s = bytes(a[0])
            if len(s) != 1:
                raise RuntimeFailure("invalid char conversion")
            return arith.wrap8(s[0])
        elif name == "dv_rt_checkdim":
            if a[0] < 1:
                raise RuntimeFailure("invalid array size")
        elif name == "dv_rt_newarray":
            if a[0] < 1:
                raise RuntimeFailure("invalid array size")
            return Addr([0] * a[0], 0)
        elif name == "dv_rt_strlit":
            return bytes(a[0])
        elif name in ("dv_rt_freearray", "dv_rt_freearray_str", "dv_rt_release_elems",
                      "dv_rt_retain", "dv_rt_release", "dv_rt_shutdown"):
            pass
        else:
            raise AssertionError(name)
        return None


def run_module(module: I.IRModule, stdin: bytes = b"") -> tuple[bytes, int, str]:
    return Interp(module, stdin).run()
