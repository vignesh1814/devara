"""Stable human-readable text form of the IR."""

from __future__ import annotations

from compiler.ir import ir as I


def fmt_operand(o: I.Operand) -> str:
    if isinstance(o, I.Reg):
        return o.name
    if isinstance(o, I.GlobalRef):
        return f"@{o.name}"
    v = o.value
    if o.type == I.IRType.BOOL:
        return "true" if v else "false"
    if o.type == I.IRType.STR:
        return "str" + repr(bytes(v))[1:]
    if o.type == I.IRType.CHAR:
        return f"char({v})"
    if o.type == I.IRType.F64:
        return f"{float(v)!r}f"
    return str(v)


def _dst(r: I.Reg | None) -> str:
    return f"{r.name}:{r.type.value} = " if r is not None else ""


def fmt_instr(i: I.Instr) -> str:
    f = fmt_operand
    if isinstance(i, I.Copy):
        return f"{_dst(i.dst)}copy {f(i.src)}"
    if isinstance(i, I.UnOp):
        return f"{_dst(i.dst)}{i.op.lower()} {f(i.src)}"
    if isinstance(i, I.BinOp):
        return f"{_dst(i.dst)}{i.op.lower()} {f(i.a)}, {f(i.b)}"
    if isinstance(i, I.Cmp):
        return f"{_dst(i.dst)}cmp {i.cond.lower()} {f(i.a)}, {f(i.b)}"
    if isinstance(i, I.Convert):
        src_t = i.src.type.value if not isinstance(i.src, I.GlobalRef) else "addr"
        return f"{_dst(i.dst)}convert {src_t}->{i.dst.type.value} {f(i.src)}"
    if isinstance(i, I.Load):
        return f"{_dst(i.dst)}load [{f(i.addr)}]"
    if isinstance(i, I.Store):
        return f"store [{f(i.addr)}], {f(i.value)}"
    if isinstance(i, I.PtrAdd):
        return f"{_dst(i.dst)}ptradd {f(i.base)}, {f(i.index)}"
    if isinstance(i, I.NewArray):
        return f"{_dst(i.dst)}newarray {f(i.count)}"
    if isinstance(i, I.Call):
        return f"{_dst(i.dst)}call {i.callee}({', '.join(f(a) for a in i.args)})"
    if isinstance(i, I.RtCall):
        return f"{_dst(i.dst)}rtcall {i.name}({', '.join(f(a) for a in i.args)})"
    raise TypeError(type(i))


def fmt_term(t: I.Terminator) -> str:
    if isinstance(t, I.Jump):
        return f"jump {t.target}"
    if isinstance(t, I.Branch):
        return f"branch {fmt_operand(t.cond)}, {t.then_target}, {t.else_target}"
    if isinstance(t, I.Return):
        return "ret" if t.value is None else f"ret {fmt_operand(t.value)}"
    raise TypeError(type(t))


def format_function(fn: I.IRFunction) -> str:
    params = ", ".join(f"{p.name}:{p.type.value}" for p in fn.params)
    out = [f"function {fn.name}({params}) -> {fn.ret.value} {{"]
    for b in fn.blocks:
        out.append(f"  {b.label}:")
        for i in b.instrs:
            out.append(f"    {fmt_instr(i)}")
        out.append(f"    {fmt_term(b.term)}")
    out.append("}")
    return "\n".join(out)


def format_module(m: I.IRModule) -> str:
    out = []
    for g in m.globals:
        extra = f"[{g.count}]" if g.kind == "array_static" else ""
        out.append(f"global {g.name}: {g.type.value} {g.kind}{extra}")
    if m.globals:
        out.append("")
    out.append("\n\n".join(format_function(f) for f in m.functions))
    return "\n".join(out)
