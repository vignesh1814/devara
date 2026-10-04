"""Random generator of well-typed, terminating, trap-free Devara programs for differential testing.

The generator only needs the language *rules* (spec §8-§10 + P27/P28): it knows the static type of every
expression it builds, so the output is accepted by any conforming semantic analyser.  Division/remainder go
through guarded helper functions so the programs never raise runtime errors; floats are kept in ranges that cannot
overflow to inf/nan in the bounded loops that are generated.
"""
from __future__ import annotations

import random

INT_LITS = ["0", "1", "2", "3", "7", "10", "255", "1000", "65536", "1000000007", "9223372036854775807",
            "4611686018427387904", "0x7F", "0xFF", "017", "99999"]
FLOAT_LITS = ["0.0", "0.5", "1.0", "1.5", "2.25", "3.0", "10.0", "0.1", "100.5", "7.75"]
CHAR_LITS = ["'a'", "'z'", "'A'", "'0'", "' '", "'\\n'", "'\\x41'", "'~'", "'\\t'"]
STR_LITS = ['"abc"', '"hello"', '"x"', '"Devara"', '"a b"', '"\\x41\\x42"', '"q\\"q"']

PRELUDE = """\
int sdiv charya (int a, int b) {
    b == 0 ayite { 0 ivvu }
    b == -1 ayite { 0 - a ivvu }
    a / b ivvu
}
int srem charya (int a, int b) {
    b == 0 ayite { 0 ivvu }
    b == -1 ayite { 0 ivvu }
    a % b ivvu
}
int sidx charya (int i, int n) {
    int r
    r lo i % n pettu
    r < 0 ayite { r lo r + n pettu }
    r ivvu
}
int g0
int g1
float gf
bool gb
char gc
padham gs
int garr[8]
float gfa[4]
padham gsa[3]
int gm[3][4]
int se0 charya (int a) {
    g1 lo g1 * 3 + a pettu
    g1 ivvu
}
int se1 charya (int a) {
    g0 lo g0 - a pettu
    garr[sidx(a, 8)] lo garr[sidx(a, 8)] + 1 pettu
    g0 ivvu
}
void vd0 charya (int a) {
    g0 lo g0 + a pettu
    gm[sidx(a, 3)][sidx(g0, 4)] lo a pettu
}
void ap0 charya (int arr[], int n) {
    prati i 0 nundi 4 varaku { arr[i] lo arr[i] + n * i pettu }
}
int ap1 charya (int arr[], int i) {
    arr[sidx(i, 4)] ivvu
}
"""


class Gen:
    def __init__(self, rnd: random.Random, size: int = 20):
        self.r = rnd
        self.size = size
        self.nvar = 0
        self.funcs: list[tuple[str, str, list[str]]] = []  # name, ret, param types
        self.lines: list[str] = []
        self.loop_depth = 0
        self.scopes: list[dict[str, list[str]]] = []
        self.in_func = False
        self.readonly: set[str] = set()

    # ------------------------------------------------------------------ scopes
    def push(self):
        self.scopes.append({"int": [], "float": [], "bool": [], "char": [], "padham": []})

    def pop(self):
        self.scopes.pop()

    def declare(self, t: str, init: str) -> str:
        n = f"v{self.nvar}"
        self.nvar += 1
        self.emit(f"{t} {n}")
        self.emit(f"{n} lo {init} pettu")
        self.scopes[-1][t].append(n)
        return n

    def names(self, t: str) -> list[str]:
        res = []
        for sc in self.scopes:
            res += sc[t]
        return res

    def emit(self, s: str):
        self.lines.append(s)

    # ------------------------------------------------------------------ expressions
    def ex(self, t: str, d: int) -> str:
        r = self.r
        if d <= 0 or r.random() < 0.2:
            return self.leaf(t)
        return getattr(self, "ex_" + t)(d - 1)

    def leaf(self, t):
        r = self.r
        pool = self.names(t)
        if t == "int":
            c = r.random()
            if pool and c < 0.5:
                return r.choice(pool)
            if c < 0.6:
                return r.choice(["g0", "g1"])
            lit = r.choice(INT_LITS)
            return f"({'-' + lit})" if r.random() < 0.3 else lit
        if t == "float":
            if pool and r.random() < 0.5:
                return r.choice(pool)
            if r.random() < 0.15:
                return "gf"
            lit = r.choice(FLOAT_LITS)
            return f"(-{lit})" if r.random() < 0.3 else lit
        if t == "bool":
            if pool and r.random() < 0.5:
                return r.choice(pool)
            return r.choice(["nijam", "abaddham", "gb"])
        if t == "char":
            if pool and r.random() < 0.5:
                return r.choice(pool)
            return r.choice(CHAR_LITS + ["gc"])
        if pool and r.random() < 0.5:
            return r.choice(pool)
        return r.choice(STR_LITS + ["gs"])

    def ex_int(self, d):
        r = self.r
        k = r.randrange(14)
        a = lambda: self.ex("int", d)
        if k == 0:
            return f"({a()} + {a()})"
        if k == 1:
            return f"({a()} - {a()})"
        if k == 2:
            return f"({a()} * {a()})"
        if k == 3:
            return f"sdiv({a()}, {a()})"
        if k == 4:
            return f"srem({a()}, {a()})"
        if k == 5:
            return f"({a()} / {r.choice(['7', '-3', '2', '1000', '-1', '9'])})"
        if k == 6:
            return f"({a()} % {r.choice(['7', '-3', '2', '1000', '-1', '10'])})"
        if k == 7:
            return f"(-{a()})"
        if k == 8:
            return f"((int) {self.ex(r.choice(['float', 'char', 'bool']), d)})"
        if k == 9:
            return f"garr[sidx({a()}, 8)]"
        if k == 10:
            return f"podavu({self.ex('padham', d)})"
        if k == 11 and self.funcs and r.random() < 0.5:
            return self.call("int", d)
        if k == 11:
            c = r.randrange(3)
            if c == 0:
                return f"se0({a()})"
            if c == 1:
                return f"se1({a()})"
            return f"ap1(gm[sidx({a()}, 3)], {a()})"
        if k == 12:
            return f"({self.ex('char', d)} - {self.ex('char', d)})"
        return f"(+{a()})"

    def ex_float(self, d):
        r = self.r
        k = r.randrange(9)
        a = lambda: self.ex("float", d)
        if k == 0:
            return f"({a()} + {a()})"
        if k == 1:
            return f"({a()} - {a()})"
        if k == 2:
            return f"({a()} * {r.choice(['0.5', '2.0', '1.5', '0.25', '3.0'])})"
        if k == 3:
            return f"({a()} / {r.choice(['2.0', '4.0', '3.0', '8', '0.5'])})"
        if k == 4:
            return f"((float) {self.ex(r.choice(['int', 'char', 'bool']), d)})"
        if k == 5:
            return f"(-{a()})"
        if k == 6:
            return f"gfa[sidx({self.ex('int', d)}, 4)]"
        if k == 7 and self.funcs:
            return self.call("float", d)
        return f"({a()} + {self.ex('int', d)})" if False else f"({a()} * 1.0)" if False else f"({a()} + 0.25)"

    def ex_bool(self, d):
        r = self.r
        k = r.randrange(10)
        if k == 0:
            return f"({self.ex('int', d)} {r.choice(['<', '>', '<=', '>=', '==', '!='])} {self.ex('int', d)})"
        if k == 1:
            return f"({self.ex('float', d)} {r.choice(['<', '>', '<=', '>=', '==', '!='])} {self.ex('float', d)})"
        if k == 2:
            return f"({self.ex('bool', d)} && {self.ex('bool', d)})"
        if k == 3:
            return f"({self.ex('bool', d)} || {self.ex('bool', d)})"
        if k == 4:
            return f"(!{self.ex('bool', d)})"
        if k == 5:
            return f"((bool) {self.ex(r.choice(['int', 'float', 'char']), d)})"
        if k == 6:
            return f"({self.ex('char', d)} {r.choice(['<', '==', '!='])} {self.ex('char', d)})"
        if k == 7:
            return f"({self.ex('padham', d)} {r.choice(['==', '!='])} {self.ex('padham', d)})"
        if k == 8 and self.funcs:
            return self.call("bool", d)
        return f"({self.ex('bool', d)} == {self.ex('bool', d)})"

    def ex_char(self, d):
        r = self.r
        k = r.randrange(5)
        if k == 0:
            return f"((char) {self.ex('int', d)})"
        if k == 1:
            return f"((char) {self.ex('float', d)})"
        if k == 2:
            s = self.ex("padham", d)
            return f"{self.safe_str(s)}[sidx({self.ex('int', d)}, podavu({self.safe_str(s)}))]" if False else f"gs[sidx({self.ex('int', d)}, podavu(gs))]"
        if k == 3:
            return f"((char) {self.ex('bool', d)})"
        return self.leaf("char")

    def ex_padham(self, d):
        r = self.r
        k = r.randrange(5)
        if k == 0 or k == 1:
            return f"({self.ex('padham', d)} + {self.ex('padham', d)})"
        if k == 2:
            return f"((padham) {self.ex('char', d)})"
        if k == 3:
            return f"gsa[sidx({self.ex('int', d)}, 3)]"
        return self.leaf("padham")

    def call(self, ret, d):
        c = [f for f in self.funcs if f[1] == ret]
        if not c:
            return self.leaf(ret)
        name, _, ps = self.r.choice(c)
        return f"{name}({', '.join(self.ex(p, d) for p in ps)})"

    # ------------------------------------------------------------------ statements
    def stmt(self, depth: int):
        r = self.r
        k = r.randrange(16)
        types = ["int", "float", "bool", "char", "padham"]
        if k <= 2:
            t = r.choice(types)
            self.declare(t, self.ex(t, 3))
        elif k <= 5:
            t = r.choice(types)
            pool = [x for x in self.names(t) if x not in self.readonly]
            if pool:
                self.emit(f"{r.choice(pool)} lo {self.ex(t, 3)} pettu")
            else:
                self.declare(t, self.ex(t, 3))
        elif k <= 8:
            t = r.choice(types)
            self.emit(f"{self.ex(t, 3)} ni chupi")
        elif k == 9:
            self.emit(f"garr[sidx({self.ex('int', 2)}, 8)] lo {self.ex('int', 3)} pettu")
        elif k == 10:
            self.emit(f"gfa[sidx({self.ex('int', 2)}, 4)] lo {self.ex('float', 3)} pettu")
        elif k == 11:
            self.emit(f"{r.choice(['g0', 'g1'])} lo {self.ex('int', 3)} pettu")
        elif k == 12 and depth > 0:
            self.if_stmt(depth)
        elif k == 13 and depth > 0 and not self.in_func and self.loop_depth < 2:
            self.loop_stmt(depth)
        elif k == 14 and self.loop_depth > 0:
            self.emit(f"{self.ex('bool', 2)} ayite {{ {r.choice(['aapu', 'saagu'])} }}")
        elif k == 15 and r.random() < 0.5:
            c = r.randrange(3)
            if c == 0:
                self.emit(f"vd0({self.ex('int', 3)})")
            elif c == 1:
                self.emit(f"ap0(gm[sidx({self.ex('int', 2)}, 3)], {self.ex('int', 3)})")
            else:
                self.emit(f"gm[sidx({self.ex('int', 2)}, 3)][sidx({self.ex('int', 2)}, 4)] lo {self.ex('int', 3)} pettu")
        else:
            self.emit(f"gsa[sidx({self.ex('int', 2)}, 3)] lo {self.ex('padham', 2)} pettu")

    def block(self, depth: int, n: int):
        self.push()
        for _ in range(n):
            self.stmt(depth - 1)
        self.pop()

    def if_stmt(self, depth):
        r = self.r
        self.emit(f"{self.ex('bool', 3)} ayite {{")
        self.block(depth, r.randrange(1, 4))
        if r.random() < 0.5:
            self.emit("} lekunte {")
            self.block(depth, r.randrange(1, 3))
        self.emit("}")

    def loop_stmt(self, depth):
        r = self.r
        k = r.randrange(4)
        n = r.randrange(1, 4)
        v = f"v{self.nvar}"
        self.nvar += 1
        self.loop_depth += 1
        self.push()
        if k == 0:
            self.emit(f"prati {v} {r.randrange(0, 2)} nundi {n + 2} varaku {{")
            self.scopes[-1]["int"].append(v)
            self.readonly.add(v)
            for _ in range(r.randrange(1, 4)):
                self.stmt(depth - 1)
            self.emit("}")
        elif k == 1:
            upd = r.choice([f"{v}++", f"++{v}", f"{v} lo {v} + 1 pettu"])
            self.emit(f"pratisari (int {v} lo 0 pettu; {v} < {n}; {upd}) {{")
            self.scopes[-1]["int"].append(v)
            self.readonly.add(v)
            for _ in range(r.randrange(1, 4)):
                self.stmt(depth - 1)
            self.emit("}")
        elif k == 2:
            self.emit(f"int {v}")
            upd = r.choice([f"{v}--", f"--{v}", f"{v} lo {v} - 1 pettu"])
            self.emit(f"pratisari ({v} {n} tho modhalu; {v} > 0; {upd}) {{")
            self.scopes[-1]["int"].append(v)
            self.readonly.add(v)
            for _ in range(r.randrange(1, 4)):
                self.stmt(depth - 1)
            self.emit("}")
        else:
            self.emit(f"int {v}")
            self.emit(f"{v} lo 0 pettu")
            self.emit(f"{v} < {n} unnanta varaku {{")
            self.emit(f"{v} lo {v} + 1 pettu")
            self.scopes[-1]["int"].append(v)
            self.readonly.add(v)
            for _ in range(r.randrange(1, 4)):
                self.stmt(depth - 1)
            self.emit("}")
        self.pop()
        self.loop_depth -= 1

    # ------------------------------------------------------------------ functions & whole program
    def make_function(self, idx: int, ret: str, ps: list[str]):
        r = self.r
        name = f"fn{idx}"
        params = [f"{t} p{i}" for i, t in enumerate(ps)]
        out = self.lines
        self.lines = []
        saved_scopes = self.scopes
        self.scopes = [{"int": [], "float": [], "bool": [], "char": [], "padham": []}]
        for i, t in enumerate(ps):
            self.scopes[0][t].append(f"p{i}")
        self.emit(f"{ret} {name} charya ({', '.join(params)}) {{")
        self.in_func = True
        for _ in range(r.randrange(1, 5)):
            self.stmt(2)
        self.emit(f"{self.ex(ret, 3)} ivvu")
        self.emit("}")
        self.in_func = False
        body = self.lines
        self.lines = out
        self.scopes = saved_scopes
        self.lines += body
        self.funcs.append((name, ret, ps))

    def program(self) -> str:
        r = self.r
        self.lines = []
        self.push()
        idx = 0
        for ret, ps in [("int", ["int", "int"]), ("float", ["float", "int"]), ("bool", ["int"]), ("int", ["char", "padham"]),
                        ("padham", ["padham", "int"])][: r.randrange(2, 6)]:
            self.make_function(idx, ret, ps)
            idx += 1
        self.emit("gs lo \"hello\" pettu")
        self.emit("gsa[0] lo \"p\" pettu")
        self.emit("gsa[1] lo \"qq\" pettu")
        self.emit("gsa[2] lo \"r\" pettu")
        self.emit("g0 ni chaduvu")
        self.emit("g1 ni chaduvu")
        for _ in range(self.size):
            self.stmt(3)
        for n in ["g0", "g1", "gf", "gb", "gs"]:
            self.emit(f"{n} ni chupi")
        self.emit("prati i 0 nundi 8 varaku { garr[i] ni chupi }")
        self.emit("prati i 0 nundi 4 varaku { gfa[i] ni chupi }")
        self.emit("prati i 0 nundi 3 varaku { gsa[i] ni chupi }")
        self.emit("prati i 0 nundi 3 varaku { prati j 0 nundi 4 varaku { gm[i][j] ni chupi } }")
        return PRELUDE + "\n".join(self.lines) + "\n"


def generate(seed: int, size: int = 20) -> tuple[str, bytes]:
    rnd = random.Random(seed)
    g = Gen(rnd, size)
    src = g.program()
    stdin = f"{rnd.randrange(-1000, 1000)} {rnd.choice([7, -3, 1000000007, 2 ** 62, -2 ** 62])}\n".encode()
    return src, stdin
