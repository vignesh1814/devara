"""Register-allocating x86-64 function generator (-O1).

Register conventions (both ABIs):

* scratch, never allocated:  rax, rcx, rdx, r10   and   xmm0, xmm1
  (r10 is the temporary of the move helpers; rax/rcx/rdx are for instruction expansion and rax also
  parks a source to break a cycle of parallel moves)
* allocatable: the target's callee-saved registers plus its caller-saved registers outside the
  scratch set (:mod:`compiler.codegen.target`); see :mod:`compiler.codegen.regalloc` for the policy.

Every value occupies a full 64-bit register/slot exactly as in the stack-slot generator
(bool 0/1, char sign-extended, f64 in an xmm register or as its bit pattern in a slot), so the
two generators produce observably identical programs.
"""

from __future__ import annotations

from compiler.codegen import lir, regalloc
from compiler.codegen.target import Target
from compiler.codegen.x86_64 import (
    _Strings, assign_args, f64_bits, mangle_function, mangle_global,
)
from compiler.ir import ir as I

IT = I.IRType

# bool and char occupy one byte in memory (loaded zero-/sign-extended, stored from the low byte)
_BYTE_TYPES = frozenset({IT.BOOL, IT.CHAR})

Loc = tuple   # ("r", reg) | ("x", xmm) | ("m", rbp displacement) | ("i", int) | ("a", "rip + sym")

_BYTE = {"rax": "al", "rbx": "bl", "rcx": "cl", "rdx": "dl", "rsi": "sil", "rdi": "dil",
         **{f"r{n}": f"r{n}b" for n in range(8, 16)}}
_DWORD = {"rax": "eax", "rbx": "ebx", "rcx": "ecx", "rdx": "edx", "rsi": "esi", "rdi": "edi",
          **{f"r{n}": f"r{n}d" for n in range(8, 16)}}

_MIRROR = {"LT": "GT", "LE": "GE", "GT": "LT", "GE": "LE", "EQ": "EQ", "NE": "NE"}
_CC = {"LT": "l", "LE": "le", "GT": "g", "GE": "ge", "EQ": "e", "NE": "ne"}
_CC_INV = {"LT": "ge", "LE": "g", "GT": "le", "GE": "l", "EQ": "ne", "NE": "e"}
_SD = {"ADD": "addsd", "SUB": "subsd", "MUL": "mulsd", "DIV": "divsd"}

INT_MIN = -(1 << 63)


def _fits32(v: int) -> bool:
    return -(1 << 31) <= v < (1 << 31)


def mem(disp: int) -> str:
    return f"QWORD PTR [rbp {'-' if disp < 0 else '+'} {abs(disp)}]"


def reg_sets(target: Target) -> regalloc.RegSets:
    return regalloc.RegSets(
        int_caller=target.alloc_caller_int,
        int_callee=target.callee_saved_int,
        flt_caller=target.alloc_caller_xmm,
        flt_callee=target.callee_saved_xmm,
    )


class RAFunctionGen:
    def __init__(self, fn: I.IRFunction, index: int, strings: _Strings, target: Target) -> None:
        self.target = target
        self.fn = fn
        self.idx = index
        self.strings = strings
        self.lines: list[str] = []
        self.nlabel = 0
        self.need_div0 = self.need_rem0 = self.need_ovf = False
        self.alloc = regalloc.allocate(fn, reg_sets(target), lambda ts: assign_args(target, ts))
        self.loc: dict[str, Loc] = {
            name: (("m", -l[1]) if l[0] == "m" else l) for name, l in self.alloc.loc.items()
        }
        # frame: spill slots, then callee-saved save area, then constant-size local arrays
        self.next_off = 8 * self.alloc.nslots
        self.saved: list[tuple[str, int, bool]] = []          # (register, offset, is_xmm)
        for r in self.alloc.used_callee_int:
            self.next_off += 8
            self.saved.append((r, self.next_off, False))
        for r in self.alloc.used_callee_flt:
            self.next_off += 16
            self.saved.append((r, self.next_off, True))
        self.arrays: dict[int, int] = {}
        for b in fn.blocks:
            for i in b.instrs:
                if isinstance(i, I.NewArray) and lir.newarray_in_frame(i):
                    self.next_off += (i.count.value * i.elsize + 7) & ~7   # type: ignore[union-attr]
                    self.arrays[id(i)] = self.next_off
        # A leaf with an empty frame needs neither rbp nor a stack frame: no calls (so no alignment
        # requirement), no integer division (its trap stubs call into the runtime), no stack parameters
        # (they are addressed from rbp), nothing spilled or saved.
        self.frameless = (
            self.next_off == 0
            and all(kind == "reg" for kind, _ in assign_args(target, [p.type for p in fn.params]))
            and not any(lir.is_call(i) or (isinstance(i, I.BinOp) and i.dst.type != IT.F64 and i.op in ("DIV", "MOD"))
                        for b in fn.blocks for i in b.instrs)
        )

    # ── emit helpers ──

    def e(self, s: str) -> None:
        self.lines.append("    " + s)

    def lab(self, name: str) -> str:
        return f".L{self.idx}_{name}"

    def fresh(self, hint: str = "x") -> str:
        self.nlabel += 1
        return f".L{self.idx}_{hint}{self.nlabel}"

    def loc_of(self, o: I.Operand) -> Loc:
        if isinstance(o, I.Reg):
            return self.loc[o.name]
        if isinstance(o, I.GlobalRef):
            return ("a", f"rip + {mangle_global(o.name)}")
        if o.type == IT.STR:
            return ("a", f"rip + {self.strings.label(bytes(o.value))}")
        if o.type == IT.F64:
            return ("i", f64_bits(o.value))
        return ("i", int(o.value))

    @staticmethod
    def sstr(l: Loc) -> str:
        return l[1] if l[0] in ("r", "x") else mem(l[1])

    # ── moves ──

    def emit_move(self, d: Loc, s: Loc) -> None:
        """Copy a 64-bit value between any two locations (uses r10 as the only temporary)."""
        if d == s:
            return
        dk, sk = d[0], s[0]
        if dk == "r":
            D = d[1]
            if sk == "r":
                self.e(f"mov {D}, {s[1]}")
            elif sk == "x":
                self.e(f"movq {D}, {s[1]}")
            elif sk == "m":
                self.e(f"mov {D}, {mem(s[1])}")
            elif sk == "i":
                v = s[1]
                if v == 0:
                    self.e(f"xor {_DWORD[D]}, {_DWORD[D]}")
                else:
                    self.e(f"mov {D}, {v}")
            else:
                self.e(f"lea {D}, [{s[1]}]")
        elif dk == "x":
            D = d[1]
            if sk == "r":
                self.e(f"movq {D}, {s[1]}")
            elif sk == "x":
                self.e(f"movaps {D}, {s[1]}")
            elif sk == "m":
                self.e(f"movsd {D}, {mem(s[1])}")
            elif sk == "i":
                if s[1] == 0:
                    self.e(f"xorps {D}, {D}")
                else:
                    self.e(f"mov r10, {s[1]}")
                    self.e(f"movq {D}, r10")
            else:
                raise AssertionError("address into xmm")
        else:
            M = mem(d[1])
            if sk == "r":
                self.e(f"mov {M}, {s[1]}")
            elif sk == "x":
                self.e(f"movsd {M}, {s[1]}")
            elif sk == "m":
                self.e(f"mov r10, {mem(s[1])}")
                self.e(f"mov {M}, r10")
            elif sk == "i":
                if _fits32(s[1]):
                    self.e(f"mov {M}, {s[1]}")
                else:
                    self.e(f"mov r10, {s[1]}")
                    self.e(f"mov {M}, r10")
            else:
                self.e(f"lea r10, [{s[1]}]")
                self.e(f"mov {M}, r10")

    def parallel_move(self, moves: list[tuple[Loc, Loc]]) -> None:
        """Perform all moves as if simultaneously (destinations are registers or private slots)."""
        pending = [(d, s) for d, s in moves if d != s]
        while pending:
            progress = False
            for m in list(pending):
                d = m[0]
                if d[0] in ("r", "x") and any(o is not m and o[1] == d for o in pending):
                    continue                    # d is still needed as a source
                self.emit_move(*m)
                pending.remove(m)
                progress = True
            if not progress:
                # only register cycles remain: park one source in rax (scratch, never an operand of a
                # parallel move: these run only for call arguments and incoming parameters)
                d, s = pending[0]
                tmp: Loc = ("r", "rax")
                self.emit_move(tmp, s)
                pending = [(dd, tmp if ss == s else ss) for dd, ss in pending]

    # ── operand access ──

    def to_ireg(self, o: I.Operand, scratch: str) -> str:
        l = self.loc_of(o)
        if l[0] == "r":
            return l[1]
        self.emit_move(("r", scratch), l)
        return scratch

    def irm(self, o: I.Operand, scratch: str) -> str:
        l = self.loc_of(o)
        if l[0] == "r":
            return l[1]
        if l[0] == "m":
            return mem(l[1])
        self.emit_move(("r", scratch), l)
        return scratch

    def to_xreg(self, o: I.Operand, scratch: str) -> str:
        l = self.loc_of(o)
        if l[0] == "x":
            return l[1]
        self.emit_move(("x", scratch), l)
        return scratch

    def xrm(self, o: I.Operand, scratch: str) -> str:
        l = self.loc_of(o)
        if l[0] == "x":
            return l[1]
        if l[0] == "m":
            return mem(l[1])
        self.emit_move(("x", scratch), l)
        return scratch

    def address(self, base: I.Operand, index: I.Operand | None, scale: int = 8, ty: IT = IT.I64) -> str:
        """Memory operand for ``[base (+ index*scale)]`` of a value of type ``ty`` (scratch: rax, rcx).
        A bool or char is one byte in memory, everything else eight."""
        ptr = "BYTE PTR" if ty in _BYTE_TYPES else "QWORD PTR"
        bl = self.loc_of(base)
        if bl[0] == "a":
            if index is None:
                return f"{ptr} [{bl[1]}]"
            self.e(f"lea rax, [{bl[1]}]")
            B = "rax"
        elif bl[0] == "r":
            B = bl[1]
        else:
            self.emit_move(("r", "rax"), bl)
            B = "rax"
        if index is None:
            return f"{ptr} [{B}]"
        il = self.loc_of(index)
        if il[0] == "i" and _fits32(il[1] * scale):
            d = il[1] * scale
            return f"{ptr} [{B}]" if d == 0 else f"{ptr} [{B} {'-' if d < 0 else '+'} {abs(d)}]"
        if il[0] == "r":
            I_ = il[1]
        else:
            self.emit_move(("r", "rcx"), il)
            I_ = "rcx"
        return f"{ptr} [{B} + {I_}*{scale}]"

    def load_from(self, ld: Loc, addr: str, ty: IT = IT.I64) -> None:
        if ty in _BYTE_TYPES:                      # zero-extend a bool, sign-extend a char
            ext = "movzx" if ty == IT.BOOL else "movsx"
            if ld[0] == "r":
                self.e(f"{ext} {ld[1]}, {addr}")
            else:
                self.e(f"{ext} rdx, {addr}")
                self.e(f"mov {mem(ld[1])}, rdx")
        elif ld[0] == "r":
            self.e(f"mov {ld[1]}, {addr}")
        elif ld[0] == "x":
            self.e(f"movsd {ld[1]}, {addr}")
        else:
            self.e(f"mov rdx, {addr}")
            self.e(f"mov {mem(ld[1])}, rdx")

    def store_to(self, addr: str, vl: Loc, ty: IT = IT.I64) -> None:
        k = vl[0]
        if ty in _BYTE_TYPES:
            if k == "r":
                self.e(f"mov {addr}, {_BYTE[vl[1]]}")
            elif k == "i":
                self.e(f"mov {addr}, {vl[1] & 0xFF}")
            else:
                self.emit_move(("r", "rdx"), vl)
                self.e(f"mov {addr}, dl")
        elif k == "r":
            self.e(f"mov {addr}, {vl[1]}")
        elif k == "x":
            self.e(f"movsd {addr}, {vl[1]}")
        elif k == "i" and _fits32(vl[1]):
            self.e(f"mov {addr}, {vl[1]}")
        else:
            self.emit_move(("r", "rdx"), vl)
            self.e(f"mov {addr}, rdx")

    # ── function ──

    def generate(self) -> list[str]:
        fn = self.fn
        tg = self.target
        name = mangle_function(fn.name)
        self.index = {b.label: k for k, b in enumerate(fn.blocks)}
        for k, b in enumerate(fn.blocks):
            self.cur = k
            self.lines.append(f"{self.lab(b.label)}:")
            for ins in b.instrs:
                self.instr(ins)
            nxt = fn.blocks[k + 1].label if k + 1 < len(fn.blocks) else None
            self.terminator(b.term, nxt)
        body = self.lines
        stubs: list[str] = []
        for need, label, helper in ((self.need_div0, "trap_div0", "dv_rt_trap_div0"),
                                    (self.need_rem0, "trap_rem0", "dv_rt_trap_rem0"),
                                    (self.need_ovf, "trap_ovf", "dv_rt_trap_divovf")):
            if need:
                stubs.append(f"{self.lab(label)}:")
                if tg.shadow_space:
                    stubs.append(f"    sub rsp, {tg.shadow_space}")
                stubs.append(f"    call {helper}")

        frame = (self.next_off + 15) & ~15
        out = tg.function_header(name)
        if not self.frameless:
            out += ["    push rbp", "    mov rbp, rsp"]
        if frame:
            out += tg.probe_stack(frame)
            out.append(f"    sub rsp, {frame}")
        self.lines = []
        for r, off, is_x in self.saved:
            self.e(f"movups XMMWORD PTR [rbp - {off}], {r}" if is_x else f"mov QWORD PTR [rbp - {off}], {r}")
        moves: list[tuple[Loc, Loc]] = []
        for p, (kind, where) in zip(fn.params, assign_args(tg, [p.type for p in fn.params])):
            if p.name not in self.loc:
                continue
            if kind == "reg":
                src: Loc = ("x" if p.type == IT.F64 else "r", str(where))
            else:
                src = ("m", 16 + tg.shadow_space + 8 * int(where))
            moves.append((self.loc[p.name], src))
        self.parallel_move(moves)
        out += self.lines
        return out + body + stubs

    def epilogue(self) -> None:
        for r, off, is_x in self.saved:
            self.e(f"movups {r}, XMMWORD PTR [rbp - {off}]" if is_x else f"mov {r}, QWORD PTR [rbp - {off}]")
        if not self.frameless:
            self.e("leave")
        self.e("ret")

    # ── instructions ──

    def instr(self, i: I.Instr) -> None:
        if isinstance(i, I.Copy):
            self.emit_move(self.loc[i.dst.name], self.loc_of(i.src))
        elif isinstance(i, I.UnOp):
            self.unop(i)
        elif isinstance(i, I.BinOp):
            if i.dst.type == IT.F64:
                self.binop_f(i)
            elif i.op in ("DIV", "MOD"):
                self.divmod(i)
            else:
                self.binop_i(i)
        elif isinstance(i, I.Cmp):
            self.cmp_value(i)
        elif isinstance(i, I.Convert):
            self.convert(i)
        elif isinstance(i, I.Load):
            self.load_from(self.loc[i.dst.name], self.address(i.addr, None, 8, i.dst.type), i.dst.type)
        elif isinstance(i, lir.LoadIdx):
            self.load_from(self.loc[i.dst.name], self.address(i.base, i.index, i.scale, i.dst.type), i.dst.type)
        elif isinstance(i, I.Store):
            vt = lir.operand_type(i.value)
            self.store_to(self.address(i.addr, None, 8, vt), self.loc_of(i.value), vt)
        elif isinstance(i, lir.StoreIdx):
            vt = lir.operand_type(i.value)
            self.store_to(self.address(i.base, i.index, i.scale, vt), self.loc_of(i.value), vt)
        elif isinstance(i, I.PtrAdd):
            self.ptradd(i)
        elif isinstance(i, I.NewArray):
            off = self.arrays.get(id(i))
            if off is not None:
                n = (i.count.value * i.elsize + 7) // 8        # type: ignore[union-attr]  # qwords to clear
                self.e("mov rdx, rdi")          # rdi may hold a value (and is callee-saved on Win64)
                self.e(f"lea rdi, [rbp - {off}]")
                self.e(f"mov rcx, {n}")
                self.e("xor eax, eax")
                self.e("rep stosq")
                self.e("mov rdi, rdx")
                self.e(f"lea rax, [rbp - {off}]")
                self.emit_move(self.loc[i.dst.name], ("r", "rax"))
            else:
                self.call("dv_rt_newarray", [i.count, I.Const(IT.I64, i.elsize)], i.dst)
        elif isinstance(i, I.Call):
            self.call(mangle_function(i.callee), i.args, i.dst)
        elif isinstance(i, I.RtCall):
            self.call(i.name, i.args, i.dst)
        else:
            raise TypeError(type(i))

    def unop(self, i: I.UnOp) -> None:
        ld = self.loc[i.dst.name]
        ls = self.loc_of(i.src)
        if i.dst.type == IT.F64:                     # NEG on a double: flip the sign bit
            self.emit_move(("r", "rax"), ls)
            self.e("btc rax, 63")
            self.emit_move(ld, ("r", "rax"))
            return
        D = ld[1] if ld[0] == "r" else "rax"
        self.emit_move(("r", D), ls)
        self.e(f"xor {D}, 1" if i.op == "NOT" else f"neg {D}")
        self.emit_move(ld, ("r", D))

    def ptradd(self, i: I.PtrAdd) -> None:
        ld = self.loc[i.dst.name]
        D = ld[1] if ld[0] == "r" else "rax"
        bl, il = self.loc_of(i.base), self.loc_of(i.index)
        if bl[0] == "a":
            self.e(f"lea rax, [{bl[1]}]")
            B = "rax"
        else:
            B = self.to_ireg(i.base, "rax")
        if il[0] == "i" and _fits32(il[1] * i.scale):
            self.e(f"lea {D}, [{B} + {il[1] * i.scale}]")
        else:
            I_ = self.to_ireg(i.index, "rcx")
            self.e(f"lea {D}, [{B} + {I_}*{i.scale}]")
        self.emit_move(ld, ("r", D))

    def binop_i(self, i: I.BinOp) -> None:
        ld = self.loc[i.dst.name]
        op = i.op
        a, b = i.a, i.b
        la, lb = self.loc_of(a), self.loc_of(b)
        if ld[0] == "m" and la == ld and op in ("ADD", "SUB") and (
                lb[0] == "r" or (lb[0] == "i" and _fits32(lb[1]))):
            self.e(f"{'add' if op == 'ADD' else 'sub'} {mem(ld[1])}, {lb[1]}")
            return
        D = ld[1] if ld[0] == "r" else "rax"
        dreg: Loc = ("r", D)
        commut = op in ("ADD", "MUL")
        if commut and la != dreg and (lb == dreg or (la[0] != "r" and lb[0] == "r")):
            la, lb = lb, la
        elif op == "SUB" and lb == dreg and la != dreg:
            D = "rax"
            dreg = ("r", D)
        if op in ("ADD", "SUB") and la[0] == "r" and la != dreg:
            if lb[0] == "r" and op == "ADD":
                self.e(f"lea {D}, [{la[1]} + {lb[1]}]")
                self.emit_move(ld, dreg)
                return
            if lb[0] == "i":
                imm = lb[1] if op == "ADD" else -lb[1]
                if _fits32(imm):
                    self.e(f"lea {D}, [{la[1]} {'-' if imm < 0 else '+'} {abs(imm)}]")
                    self.emit_move(ld, dreg)
                    return
        self.emit_move(dreg, la)
        if lb[0] == "r":
            B = lb[1]
        elif lb[0] == "m":
            B = mem(lb[1])
        elif lb[0] == "i" and _fits32(lb[1]):
            B = str(lb[1])
        else:
            self.emit_move(("r", "rcx"), lb)
            B = "rcx"
        if op == "MUL":
            self.e(f"imul {D}, {D}, {B}" if lb[0] == "i" and _fits32(lb[1]) else f"imul {D}, {B}")
        else:
            self.e(f"{'add' if op == 'ADD' else 'sub'} {D}, {B}")
        self.emit_move(ld, dreg)

    def binop_f(self, i: I.BinOp) -> None:
        ld = self.loc[i.dst.name]
        la, lb = self.loc_of(i.a), self.loc_of(i.b)
        X = ld[1] if ld[0] == "x" else "xmm0"
        commut = i.op in ("ADD", "MUL")
        if lb == ("x", X) and la != lb:
            if commut:
                la, lb = lb, la
            else:
                X = "xmm0"
        self.emit_move(("x", X), la)
        if lb[0] == "x":
            B = lb[1]
        elif lb[0] == "m":
            B = mem(lb[1])
        else:
            self.emit_move(("x", "xmm1"), lb)
            B = "xmm1"
        self.e(f"{_SD[i.op]} {X}, {B}")
        self.emit_move(ld, ("x", X))

    def divmod(self, i: I.BinOp) -> None:
        ld = self.loc[i.dst.name]
        la, lb = self.loc_of(i.a), self.loc_of(i.b)
        div = i.op == "DIV"
        bval = lb[1] if lb[0] == "i" else None
        if bval is not None and bval > 0 and bval & (bval - 1) == 0 and bval < (1 << 31):
            k = bval.bit_length() - 1
            self.emit_move(("r", "rax"), la)
            if k == 0:
                if not div:
                    self.e("xor eax, eax")
            else:
                self.e("mov rdx, rax")
                self.e("sar rdx, 63")
                self.e(f"shr rdx, {64 - k}")
                if div:
                    self.e("add rax, rdx")
                    self.e(f"sar rax, {k}")
                else:
                    self.e("add rdx, rax")
                    self.e(f"and rdx, {-bval}")
                    self.e("sub rax, rdx")
            self.emit_move(ld, ("r", "rax"))
            return
        self.emit_move(("r", "rax"), la)
        if lb[0] == "r":
            B = lb[1]
        else:
            self.emit_move(("r", "rcx"), lb)
            B = "rcx"
        const_b = bval is not None
        safe = const_b and bval not in (0, -1)
        done = self.fresh("dv")
        if not safe:
            if not (const_b and bval == -1):
                self.e(f"test {B}, {B}")
                if div:
                    self.e(f"je {self.lab('trap_div0')}")
                    self.need_div0 = True
                else:
                    self.e(f"je {self.lab('trap_rem0')}")
                    self.need_rem0 = True
            normal = self.fresh("dn")
            self.e(f"cmp {B}, -1")
            self.e(f"jne {normal}")
            if div:
                self.e(f"mov rdx, {INT_MIN}")
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
        self.e(f"idiv {B}")
        if not div:
            self.e("mov rax, rdx")
        self.lines.append(f"{done}:")
        self.emit_move(ld, ("r", "rax"))

    # ── comparisons ──

    def int_compare(self, cond: str, a: I.Operand, b: I.Operand) -> str:
        """Emit ``cmp``/``test`` for an integer comparison; returns the (possibly mirrored) condition."""
        la, lb = self.loc_of(a), self.loc_of(b)
        if la[0] in ("i", "a") and lb[0] not in ("i", "a"):
            la, lb = lb, la
            cond = _MIRROR[cond]
        if la[0] in ("i", "a"):
            self.emit_move(("r", "rax"), la)
            la = ("r", "rax")
        A = la[1] if la[0] == "r" else mem(la[1])
        if lb[0] == "r":
            B = lb[1]
        elif lb[0] == "i" and _fits32(lb[1]):
            B = str(lb[1])
        elif lb[0] == "m" and la[0] == "r":
            B = mem(lb[1])
        else:
            self.emit_move(("r", "rcx"), lb)
            B = "rcx"
        if B == "0" and la[0] == "r":
            self.e(f"test {A}, {A}")
        else:
            self.e(f"cmp {A}, {B}")
        return cond

    def float_compare(self, cond: str, a: I.Operand, b: I.Operand) -> str | None:
        """Emit ``ucomisd``; returns the carry-style condition (``a``/``ae``) or None for EQ/NE."""
        if cond in ("LT", "LE"):
            first, second, cc = b, a, ("a" if cond == "LT" else "ae")
        elif cond in ("GT", "GE"):
            first, second, cc = a, b, ("a" if cond == "GT" else "ae")
        else:
            first, second, cc = a, b, None
        X = self.to_xreg(first, "xmm0")
        Y = self.xrm(second, "xmm1")
        self.e(f"ucomisd {X}, {Y}")
        return cc

    def cmp_value(self, i: I.Cmp) -> None:
        ld = self.loc[i.dst.name]
        t = lir.operand_type(i.a)
        if t == IT.STR:
            self.call("dv_rt_streq", [i.a, i.b], None)
            if i.cond == "NE":
                self.e("xor rax, 1")
            self.emit_move(ld, ("r", "rax"))
            return
        D = ld[1] if ld[0] == "r" else "rax"
        if t == IT.F64:
            cc = self.float_compare(i.cond, i.a, i.b)
            if cc is not None:
                self.e(f"set{cc} {_BYTE[D]}")
            elif i.cond == "EQ":
                self.e("sete al")
                self.e("setnp cl")
                self.e("and al, cl")
                D = "rax"
            else:
                self.e("setne al")
                self.e("setp cl")
                self.e("or al, cl")
                D = "rax"
        else:
            cond = self.int_compare(i.cond, i.a, i.b)
            self.e(f"set{_CC[cond]} {_BYTE[D]}")
        self.e(f"movzx {_DWORD[D]}, {_BYTE[D]}")
        self.emit_move(ld, ("r", D))

    def convert(self, i: I.Convert) -> None:
        ld = self.loc[i.dst.name]
        src_t = lir.operand_type(i.src)
        dst_t = i.dst.type
        if dst_t == IT.F64:
            X = ld[1] if ld[0] == "x" else "xmm0"
            S = self.irm(i.src, "rax")
            self.e(f"xorps {X}, {X}")
            self.e(f"cvtsi2sd {X}, {S}")
            self.emit_move(ld, ("x", X))
        elif src_t == IT.F64:
            if dst_t == IT.BOOL:
                X = self.to_xreg(i.src, "xmm0")
                self.e("xorps xmm1, xmm1")
                self.e(f"ucomisd {X}, xmm1")
                self.e("setne al")
                self.e("setp cl")
                self.e("or al, cl")
                self.e("movzx eax, al")
                self.emit_move(ld, ("r", "rax"))
            else:
                D = ld[1] if ld[0] == "r" else "rax"
                S = self.xrm(i.src, "xmm0")
                self.e(f"cvttsd2si {D}, {S}")
                if dst_t == IT.CHAR:
                    self.e(f"movsx {D}, {_BYTE[D]}")
                self.emit_move(ld, ("r", D))
        else:
            ls = self.loc_of(i.src)
            D = ld[1] if ld[0] == "r" else "rax"
            if dst_t == IT.BOOL and src_t != IT.BOOL:
                R = self.to_ireg(i.src, "rax")
                self.e(f"test {R}, {R}")
                self.e(f"setne {_BYTE[D]}")
                self.e(f"movzx {_DWORD[D]}, {_BYTE[D]}")
                self.emit_move(ld, ("r", D))
            elif dst_t == IT.CHAR:
                if ls[0] == "r":
                    S8 = _BYTE[ls[1]]
                elif ls[0] == "m":
                    S8 = mem(ls[1]).replace("QWORD", "BYTE")
                else:
                    self.emit_move(("r", "rax"), ls)
                    S8 = "al"
                self.e(f"movsx {D}, {S8}")
                self.emit_move(ld, ("r", D))
            else:
                self.emit_move(ld, ls)

    # ── calls ──

    def call(self, symbol: str, args: list[I.Operand], dst: I.Reg | None) -> None:
        tg = self.target
        types = [lir.operand_type(a) for a in args]
        assign = assign_args(tg, types)
        stack = [a for a, (kind, _) in zip(args, assign) if kind == "stack"]
        pad = 8 if len(stack) % 2 else 0
        if pad:
            self.e("sub rsp, 8")
        for a in reversed(stack):
            l = self.loc_of(a)
            if l[0] == "r":
                self.e(f"push {l[1]}")
            elif l[0] == "m":
                self.e(f"push {mem(l[1])}")
            elif l[0] == "i" and _fits32(l[1]):
                self.e(f"push {l[1]}")
            elif l[0] == "x":
                self.e("sub rsp, 8")
                self.e(f"movsd QWORD PTR [rsp], {l[1]}")
            else:
                self.emit_move(("r", "rax"), l)
                self.e("push rax")
        if tg.shadow_space:
            self.e(f"sub rsp, {tg.shadow_space}")
        moves: list[tuple[Loc, Loc]] = []
        for a, t, (kind, where) in zip(args, types, assign):
            if kind == "reg":
                moves.append((("x" if t == IT.F64 else "r", str(where)), self.loc_of(a)))
        self.parallel_move(moves)
        self.e(f"call {symbol}")
        cleanup = 8 * len(stack) + pad + tg.shadow_space
        if cleanup:
            self.e(f"add rsp, {cleanup}")
        if dst is not None:
            self.emit_move(self.loc[dst.name], ("x", "xmm0") if dst.type == IT.F64 else ("r", "rax"))

    # ── terminators ──

    def jumps(self, cc_true: str, cc_false: str, then: str, els: str, nxt: str | None) -> None:
        if then == els:
            if then != nxt:
                self.e(f"jmp {self.lab(then)}")
        elif then == nxt:
            self.e(f"j{cc_false} {self.lab(els)}")
        elif els == nxt:
            self.e(f"j{cc_true} {self.lab(then)}")
        else:
            self.e(f"j{cc_true} {self.lab(then)}")
            self.e(f"jmp {self.lab(els)}")

    def terminator(self, t: I.Terminator, nxt: str | None) -> None:
        if isinstance(t, I.Jump):
            if t.target != nxt and not self.rotate_loop(t.target, nxt):
                self.e(f"jmp {self.lab(t.target)}")
        elif isinstance(t, I.Branch):
            l = self.loc_of(t.cond)
            if l[0] == "i":
                target = t.then_target if l[1] else t.else_target
                if target != nxt:
                    self.e(f"jmp {self.lab(target)}")
                return
            if l[0] == "r":
                self.e(f"test {l[1]}, {l[1]}")
            else:
                self.e(f"cmp {mem(l[1])}, 0")
            self.jumps("ne", "e", t.then_target, t.else_target, nxt)
        elif isinstance(t, lir.CmpBranch):
            self.cmp_branch(t, nxt)
        elif isinstance(t, I.Return):
            if t.value is not None:
                l = self.loc_of(t.value)
                if lir.operand_type(t.value) == IT.F64:
                    self.emit_move(("x", "xmm0"), l)
                else:
                    self.emit_move(("r", "rax"), l)
            self.epilogue()
        else:
            raise TypeError(type(t))

    def rotate_loop(self, target: str, nxt: str | None) -> bool:
        """Back edge to a tiny condition block: duplicate it here instead of jumping to it."""
        k = self.index[target]
        if k >= self.cur:
            return False
        b = self.fn.blocks[k]
        if len(b.instrs) > 2 or not isinstance(b.term, (I.Branch, lir.CmpBranch)):
            return False
        for i in b.instrs:
            if lir.is_call(i) or isinstance(i, I.NewArray) or (
                    isinstance(i, I.BinOp) and i.op in ("DIV", "MOD") and i.dst.type != IT.F64):
                return False
        for i in b.instrs:
            self.instr(i)
        self.terminator(b.term, nxt)
        return True

    def cmp_branch(self, t: lir.CmpBranch, nxt: str | None) -> None:
        then, els = t.then_target, t.else_target
        if lir.operand_type(t.a) != IT.F64:
            cond = self.int_compare(t.cond, t.a, t.b)
            self.jumps(_CC[cond], _CC_INV[cond], then, els, nxt)
            return
        cc = self.float_compare(t.cond, t.a, t.b)
        if cc is not None:
            inv = {"a": "be", "ae": "b"}[cc]
            self.jumps(cc, inv, then, els, nxt)
        elif t.cond == "EQ":              # true iff ZF=1 and PF=0
            if then == els:
                if then != nxt:
                    self.e(f"jmp {self.lab(then)}")
            elif then == nxt:
                self.e(f"jp {self.lab(els)}")
                self.e(f"jne {self.lab(els)}")
            else:
                self.e(f"jp {self.lab(els)}")
                self.e(f"je {self.lab(then)}")
                if els != nxt:
                    self.e(f"jmp {self.lab(els)}")
        else:                             # NE: true iff ZF=0 or PF=1
            if then == els:
                if then != nxt:
                    self.e(f"jmp {self.lab(then)}")
            elif els == nxt:
                self.e(f"jp {self.lab(then)}")
                self.e(f"jne {self.lab(then)}")
            else:
                self.e(f"jp {self.lab(then)}")
                self.e(f"je {self.lab(els)}")
                if then != nxt:
                    self.e(f"jmp {self.lab(then)}")
