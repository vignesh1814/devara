"""x86-64 System V code generator (GNU as, ``.intel_syntax noprefix``).

Stack-slot strategy (plan §D): every IR register has a fixed 8-byte slot
``[rbp - k]``; each instruction loads operands into scratch registers
(``rax``, ``rcx``, ``rdx``, ``xmm0``, ``xmm1``), computes, and stores the result.
All values occupy a full 64-bit slot (bool 0/1, char sign-extended, f64 bit
pattern, str/addr pointer), so copies/loads/stores are plain 64-bit moves.
"""

from __future__ import annotations

import struct

from compiler.codegen.target import Target, get_target
from compiler.ir import ir as I

IT = I.IRType

FRAME_ARRAY_LIMIT = 64 * 1024     # bytes; larger constant-size arrays use the heap


def operand_type(o: I.Operand) -> IT:
    """IR type of an operand (a global's address is an ``addr``)."""
    return IT.ADDR if isinstance(o, I.GlobalRef) else o.type

_SETCC = {"LT": "l", "LE": "le", "GT": "g", "GE": "ge", "EQ": "e", "NE": "ne"}


def mangle_function(name: str) -> str:
    return "dv_entry" if name == I.ENTRY_FUNCTION else f"dv_f_{name}"


def mangle_global(name: str) -> str:
    return f"dv_g_{name}"


def f64_bits(v: float) -> int:
    return struct.unpack("<q", struct.pack("<d", v))[0]


def assign_args(target: Target, types: list[IT]) -> list[tuple[str, str | int]]:
    """ABI argument assignment: per argument ``("reg", name)`` or ``("stack", slot_index)``.

    SysV classifies integer and float arguments separately; Win64 assigns by
    position (argument ``i`` takes register ``i`` of its class, whichever class).
    Stack slots are 8 bytes each, in argument order.
    """
    out: list[tuple[str, str | int]] = []
    ni = nf = ns = 0
    for pos, t in enumerate(types):
        flt = t == IT.F64
        if target.positional:
            if pos < len(target.int_args):
                out.append(("reg", (target.float_args if flt else target.int_args)[pos]))
                continue
        elif flt and nf < len(target.float_args):
            out.append(("reg", target.float_args[nf]))
            nf += 1
            continue
        elif not flt and ni < len(target.int_args):
            out.append(("reg", target.int_args[ni]))
            ni += 1
            continue
        out.append(("stack", ns))
        ns += 1
    return out


class _Strings:
    def __init__(self, target: Target) -> None:
        self.table: dict[bytes, str] = {}
        self.target = target

    def label(self, b: bytes) -> str:
        if b not in self.table:
            self.table[b] = f".Lstr{len(self.table)}"
        return self.table[b]

    def emit(self) -> list[str]:
        out = self.target.rodata()
        for b, lab in self.table.items():
            out.append(f"{lab}:")
            out.append(f"    .quad {len(b)}")
            for i in range(0, len(b), 16):
                out.append("    .byte " + ", ".join(str(x) for x in b[i:i + 16]))
            out.append("    .byte 0")
            out.append("    .balign 8")
        return out


class FunctionGen:
    def __init__(self, fn: I.IRFunction, index: int, strings: _Strings, target: Target) -> None:
        self.target = target
        self.fn = fn
        self.idx = index
        self.strings = strings
        self.lines: list[str] = []
        self.slots: dict[str, int] = {}
        self.next_off = 0
        self.nlabel = 0
        self.arrays: dict[int, int] = {}      # id(instr) -> frame offset of its region
        self.need_div0 = self.need_rem0 = self.need_ovf = False
        self.collect()

    # ── frame ──

    def slot(self, name: str) -> str:
        return f"QWORD PTR [rbp - {self.slots[name]}]"

    def alloc(self, nbytes: int) -> int:
        self.next_off += (nbytes + 7) & ~7
        return self.next_off

    def collect(self) -> None:
        def see(o) -> None:
            if isinstance(o, I.Reg) and o.name not in self.slots:
                self.slots[o.name] = self.alloc(8)

        for p in self.fn.params:
            see(p)
        for b in self.fn.blocks:
            for i in b.instrs:
                for name in ("dst", "src", "a", "b", "addr", "value", "base", "index", "count"):
                    if hasattr(i, name):
                        see(getattr(i, name))
                for a in getattr(i, "args", []):
                    see(a)
                if isinstance(i, I.NewArray) and isinstance(i.count, I.Const) \
                        and 1 <= i.count.value and i.count.value * i.elsize <= FRAME_ARRAY_LIMIT:
                    self.arrays[id(i)] = self.alloc(i.count.value * i.elsize)
            t = b.term
            if isinstance(t, I.Branch):
                see(t.cond)
            elif isinstance(t, I.Return) and t.value is not None:
                see(t.value)

    # ── emit helpers ──

    def e(self, s: str) -> None:
        self.lines.append("    " + s)

    def lab(self, name: str) -> str:
        return f".L{self.idx}_{name}"

    def fresh(self, hint: str = "x") -> str:
        self.nlabel += 1
        return f".L{self.idx}_{hint}{self.nlabel}"

    def load(self, reg: str, o: I.Operand) -> None:
        """Load a 64-bit operand into integer register ``reg``."""
        if isinstance(o, I.Reg):
            self.e(f"mov {reg}, {self.slot(o.name)}")
        elif isinstance(o, I.GlobalRef):
            self.e(f"lea {reg}, [rip + {mangle_global(o.name)}]")
        elif o.type == IT.STR:
            self.e(f"lea {reg}, [rip + {self.strings.label(bytes(o.value))}]")
        elif o.type == IT.F64:
            self.e(f"mov {reg}, {f64_bits(o.value)}")
        else:
            self.e(f"mov {reg}, {int(o.value)}")

    def loadf(self, xmm: str, o: I.Operand) -> None:
        if isinstance(o, I.Reg):
            self.e(f"movsd {xmm}, {self.slot(o.name)}")
        else:
            self.load("rax", o)
            self.e(f"movq {xmm}, rax")

    def store(self, dst: I.Reg, reg: str = "rax") -> None:
        self.e(f"mov {self.slot(dst.name)}, {reg}")

    def storef(self, dst: I.Reg, xmm: str = "xmm0") -> None:
        self.e(f"movsd {self.slot(dst.name)}, {xmm}")

    # ── function ──

    def generate(self) -> list[str]:
        fn = self.fn
        tg = self.target
        name = mangle_function(fn.name)
        out = tg.function_header(name)
        # body first (to know the frame size), then assemble
        for k, b in enumerate(fn.blocks):
            self.lines.append(f"{self.lab(b.label)}:")
            for ins in b.instrs:
                self.instr(ins)
            nxt = fn.blocks[k + 1].label if k + 1 < len(fn.blocks) else None
            self.terminator(b.term, nxt)
        stubs = []
        for need, label, helper in ((self.need_div0, "trap_div0", "dv_rt_trap_div0"),
                                    (self.need_rem0, "trap_rem0", "dv_rt_trap_rem0"),
                                    (self.need_ovf, "trap_ovf", "dv_rt_trap_divovf")):
            if need:
                stubs.append(f"{self.lab(label)}:")
                if tg.shadow_space:
                    stubs.append(f"    sub rsp, {tg.shadow_space}")
                stubs.append(f"    call {helper}")
        frame = (self.next_off + 15) & ~15
        out += ["    push rbp", "    mov rbp, rsp"]
        if frame:
            out += tg.probe_stack(frame)
            out.append(f"    sub rsp, {frame}")
        # move parameters from ABI locations into their slots
        shadow = tg.shadow_space
        for p, (kind, loc) in zip(fn.params, assign_args(tg, [p.type for p in fn.params])):
            if kind == "reg":
                if p.type == IT.F64:
                    out.append(f"    movsd {self.slot(p.name)}, {loc}")
                else:
                    out.append(f"    mov {self.slot(p.name)}, {loc}")
            else:
                out.append(f"    mov rax, QWORD PTR [rbp + {16 + shadow + 8 * int(loc)}]")
                out.append(f"    mov {self.slot(p.name)}, rax")
        out += self.lines + stubs
        return out

    # ── instructions ──

    def instr(self, i: I.Instr) -> None:
        if isinstance(i, I.Copy):
            self.load("rax", i.src)
            self.store(i.dst)
        elif isinstance(i, I.UnOp):
            self.load("rax", i.src)
            if i.op == "NOT":
                self.e("xor rax, 1")
            elif i.dst.type == IT.I64:
                self.e("neg rax")
            else:
                self.e("btc rax, 63")
            self.store(i.dst)
        elif isinstance(i, I.BinOp):
            self.binop(i)
        elif isinstance(i, I.Cmp):
            self.cmp(i)
        elif isinstance(i, I.Convert):
            self.convert(i)
        elif isinstance(i, I.Load):
            self.load("rax", i.addr)
            if i.dst.type == IT.BOOL:                  # bool and char occupy one byte in memory
                self.e("movzx eax, BYTE PTR [rax]")
            elif i.dst.type == IT.CHAR:
                self.e("movsx rax, BYTE PTR [rax]")
            else:
                self.e("mov rax, QWORD PTR [rax]")
            self.store(i.dst)
        elif isinstance(i, I.Store):
            self.load("rax", i.addr)
            self.load("rcx", i.value)
            if operand_type(i.value) in (IT.BOOL, IT.CHAR):
                self.e("mov BYTE PTR [rax], cl")
            else:
                self.e("mov QWORD PTR [rax], rcx")
        elif isinstance(i, I.PtrAdd):
            self.load("rax", i.base)
            self.load("rcx", i.index)
            self.e(f"lea rax, [rax + rcx*{i.scale}]")
            self.store(i.dst)
        elif isinstance(i, I.NewArray):
            off = self.arrays.get(id(i))
            if off is not None:
                n = (i.count.value * i.elsize + 7) // 8  # type: ignore[union-attr]  # qwords to clear
                self.e("mov r11, rdi")          # rdi is callee-saved on Win64
                self.e(f"lea rdi, [rbp - {off}]")
                self.e(f"mov rcx, {n}")
                self.e("xor eax, eax")
                self.e("rep stosq")
                self.e("mov rdi, r11")
                self.e(f"lea rax, [rbp - {off}]")
                self.store(i.dst)
            else:
                self.call("dv_rt_newarray", [i.count, I.Const(IT.I64, i.elsize)], i.dst)
        elif isinstance(i, I.Call):
            self.call(mangle_function(i.callee), i.args, i.dst)
        elif isinstance(i, I.RtCall):
            self.call(i.name, i.args, i.dst)
        else:
            raise TypeError(type(i))

    def binop(self, i: I.BinOp) -> None:
        if i.dst.type == IT.F64:
            self.loadf("xmm0", i.a)
            self.loadf("xmm1", i.b)
            self.e({"ADD": "addsd", "SUB": "subsd", "MUL": "mulsd", "DIV": "divsd"}[i.op] + " xmm0, xmm1")
            self.storef(i.dst)
            return
        self.load("rax", i.a)
        self.load("rcx", i.b)
        if i.op in ("ADD", "SUB", "MUL"):
            self.e({"ADD": "add", "SUB": "sub", "MUL": "imul"}[i.op] + " rax, rcx")
            self.store(i.dst)
            return
        b = i.b
        const_b = isinstance(b, I.Const)
        safe = const_b and b.value not in (0, -1)
        done = self.fresh("dv")
        if not safe:
            if not (const_b and b.value == -1):
                self.e("test rcx, rcx")
                if i.op == "DIV":
                    self.e(f"je {self.lab('trap_div0')}")
                    self.need_div0 = True
                else:
                    self.e(f"je {self.lab('trap_rem0')}")
                    self.need_rem0 = True
            normal = self.fresh("dn")
            self.e("cmp rcx, -1")
            self.e(f"jne {normal}")
            if i.op == "DIV":
                self.e("mov rdx, -9223372036854775808")
                self.e("cmp rax, rdx")
                self.e(f"je {self.lab('trap_ovf')}")
                self.need_ovf = True
                self.e("neg rax")
                self.e(f"jmp {done}")
            else:
                self.e("xor eax, eax")          # x % -1 == 0 (and avoids the idiv trap)
                self.e(f"jmp {done}")
            self.lines.append(f"{normal}:")
        self.e("cqo")
        self.e("idiv rcx")
        if i.op == "MOD":
            self.e("mov rax, rdx")
        self.lines.append(f"{done}:")
        self.store(i.dst)

    def cmp(self, i: I.Cmp) -> None:
        t = i.a.type if not isinstance(i.a, I.GlobalRef) else IT.ADDR
        if t == IT.STR:
            self.call("dv_rt_streq", [i.a, i.b], None, keep_rax=True)
            if i.cond == "NE":
                self.e("xor rax, 1")
            self.store(i.dst)
            return
        if t == IT.F64:
            self.loadf("xmm0", i.a)
            self.loadf("xmm1", i.b)
            c = i.cond
            if c == "LT":
                self.e("ucomisd xmm1, xmm0"); self.e("seta al")
            elif c == "LE":
                self.e("ucomisd xmm1, xmm0"); self.e("setae al")
            elif c == "GT":
                self.e("ucomisd xmm0, xmm1"); self.e("seta al")
            elif c == "GE":
                self.e("ucomisd xmm0, xmm1"); self.e("setae al")
            elif c == "EQ":
                self.e("ucomisd xmm0, xmm1"); self.e("sete al"); self.e("setnp cl"); self.e("and al, cl")
            else:
                self.e("ucomisd xmm0, xmm1"); self.e("setne al"); self.e("setp cl"); self.e("or al, cl")
            self.e("movzx eax, al")
            self.store(i.dst)
            return
        self.load("rax", i.a)
        self.load("rcx", i.b)
        self.e("cmp rax, rcx")
        self.e(f"set{_SETCC[i.cond]} al")
        self.e("movzx eax, al")
        self.store(i.dst)

    def convert(self, i: I.Convert) -> None:
        src_t = i.src.type if not isinstance(i.src, I.GlobalRef) else IT.ADDR
        dst_t = i.dst.type
        if dst_t == IT.F64:
            self.load("rax", i.src)
            self.e("cvtsi2sd xmm0, rax")
            self.storef(i.dst)
        elif src_t == IT.F64:
            self.loadf("xmm0", i.src)
            if dst_t == IT.BOOL:
                self.e("xorpd xmm1, xmm1")
                self.e("ucomisd xmm0, xmm1")
                self.e("setne al"); self.e("setp cl"); self.e("or al, cl")
                self.e("movzx eax, al")
            else:
                self.e("cvttsd2si rax, xmm0")
                if dst_t == IT.CHAR:
                    self.e("movsx rax, al")
            self.store(i.dst)
        else:
            self.load("rax", i.src)
            if dst_t == IT.BOOL:
                if src_t != IT.BOOL:
                    self.e("test rax, rax")
                    self.e("setne al")
                    self.e("movzx eax, al")
            elif dst_t == IT.CHAR:
                self.e("movsx rax, al")
            self.store(i.dst)

    def call(self, symbol: str, args: list[I.Operand], dst: I.Reg | None, keep_rax: bool = False) -> None:
        tg = self.target
        types = [a.type if not isinstance(a, I.GlobalRef) else IT.ADDR for a in args]
        assign = assign_args(tg, types)
        stack = [a for a, (kind, _) in zip(args, assign) if kind == "stack"]
        pad = 8 if len(stack) % 2 else 0
        if pad:
            self.e("sub rsp, 8")
        for a in reversed(stack):
            self.load("rax", a)
            self.e("push rax")
        if tg.shadow_space:
            self.e(f"sub rsp, {tg.shadow_space}")
        for a, t, (kind, loc) in zip(args, types, assign):
            if kind == "reg" and t == IT.F64:
                self.loadf(str(loc), a)
        for a, t, (kind, loc) in zip(args, types, assign):
            if kind == "reg" and t != IT.F64:
                self.load(str(loc), a)
        self.e(f"call {symbol}")
        cleanup = 8 * len(stack) + pad + tg.shadow_space
        if cleanup:
            self.e(f"add rsp, {cleanup}")
        if dst is not None:
            if dst.type == IT.F64:
                self.storef(dst)
            else:
                self.store(dst)

    def terminator(self, t: I.Terminator, nxt: str | None) -> None:
        if isinstance(t, I.Jump):
            if t.target != nxt:
                self.e(f"jmp {self.lab(t.target)}")
        elif isinstance(t, I.Branch):
            self.load("rax", t.cond)
            self.e("test rax, rax")
            if t.then_target == nxt:
                self.e(f"je {self.lab(t.else_target)}")
            elif t.else_target == nxt:
                self.e(f"jne {self.lab(t.then_target)}")
            else:
                self.e(f"jne {self.lab(t.then_target)}")
                self.e(f"jmp {self.lab(t.else_target)}")
        elif isinstance(t, I.Return):
            if t.value is not None:
                if t.value.type == IT.F64:
                    self.loadf("xmm0", t.value)
                else:
                    self.load("rax", t.value)
            self.e("mov rsp, rbp")
            self.e("pop rbp")
            self.e("ret")
        else:
            raise TypeError(type(t))


def generate(module: I.IRModule, target: "Target | str | None" = None, regalloc: bool = False) -> str:
    """Emit GNU assembler text for a verified module (``target`` defaults to the host).

    ``regalloc=False`` is the reference stack-slot generator (-O0); ``True`` runs the
    register-allocating generator plus the peephole pass (-O1).
    """
    tg = get_target(target)
    strings = _Strings(tg)
    out = tg.preamble()
    if regalloc:
        from compiler.codegen.peephole import peephole
        from compiler.codegen.prep import prepare_function, promote_globals
        from compiler.codegen.x86_64_ra import RAFunctionGen

        module = promote_globals(module)
        for k, fn in enumerate(module.functions):
            out += peephole(RAFunctionGen(prepare_function(fn), k, strings, tg).generate())
            out.append("")
    else:
        for k, fn in enumerate(module.functions):
            out += FunctionGen(fn, k, strings, tg).generate()
            out.append("")
    out += tg.function_header("main")
    out += ["    push rbp", "    mov rbp, rsp"]
    if tg.shadow_space:
        out.append(f"    sub rsp, {tg.shadow_space}")
    out += ["    call dv_rt_init", "    call dv_entry", "    xor eax, eax", "    leave", "    ret", ""]
    if module.globals:
        out += ["    .bss", "    .balign 16"]
        for g in module.globals:
            elsize = 1 if g.type in (IT.BOOL, IT.CHAR) else 8
            size = (elsize * (g.count if g.kind == "array_static" else 1) + 7) & ~7   # keep globals 8-aligned
            out += [f"{mangle_global(g.name)}:", f"    .zero {size}"]
        out.append("")
    out += strings.emit()
    out += tg.footer()
    out.append("")
    return "\n".join(out)
