"""Program builders for the register-pressure attacks (shared by the regalloc and Windows suites).

All programs are well-typed, terminating and (unless a builder says so) trap-free.  Inputs that must not be constant
folded are read from stdin into globals (top-level declarations are globals, P19) and passed to functions, because only
function locals/parameters can live in registers.
"""
from __future__ import annotations

import random

BASIC = """\
int gtr
int mixi charya (int a, int b) { (a * 31 + b * 17 + 7) % 1000003 ivvu }
float mixf charya (float a, float b) { a * 0.5 + b * 0.25 + 0.125 ivvu }
void ping charya (int k) { gtr lo gtr * 3 + k pettu }
int id charya (int a) { a ivvu }
"""

IMIN = "(-9223372036854775807 - 1)"


def prog(*parts: str) -> str:
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------------------------- many live values
def many_live(seed: int, ni: int, nf: int, rounds: int, extra_types: bool = False) -> tuple[str, bytes]:
    """`run(seed)` keeps `ni` ints and `nf` floats (plus optionally chars/bools/strings) live across user calls."""
    r = random.Random(seed)
    L = [BASIC, "int run charya (int seed) {"]
    for i in range(ni):
        L.append(f"  int v{i}")
    for i in range(nf):
        L.append(f"  float f{i}")
    if extra_types:
        L += ["  char c0", "  char c1", "  bool b0", "  bool b1", "  padham s0", "  padham s1"]
    for i in range(ni):
        L.append(f"  v{i} lo mixi(seed, {i}) pettu")
    for i in range(nf):
        L.append(f"  f{i} lo mixf((float) seed, {i}.5) pettu")
    if extra_types:
        L += ["  c0 lo (char) (seed + 100) pettu", "  c1 lo (char) (seed * 7) pettu", "  b0 lo seed > 3 pettu", "  b1 lo !b0 pettu",
              "  s0 lo \"ab\" pettu", "  s1 lo \"xyz\" pettu"]
    for _ in range(rounds):
        a, b, c = (r.randrange(ni) for _ in range(3))
        x, y = r.randrange(nf), r.randrange(nf)
        k = r.randrange(9 if extra_types else 7)
        if k == 0:
            L.append(f"  v{a} lo mixi(v{b}, v{c}) pettu")
        elif k == 1:
            L.append(f"  v{a} lo v{a} + mixi(v{b}, v{c}) * v{b} pettu")
        elif k == 2:
            L.append(f"  f{x} lo mixf(f{y}, (float) v{b}) pettu")
        elif k == 3:
            L += [f"  ping(v{a})", f"  v{a} lo v{a} + gtr pettu"]
        elif k == 4:
            L.append(f"  v{a} lo (int) (f{x} * 3.0) + v{c} pettu")
        elif k == 5:
            L.append(f"  f{x} lo f{x} * 0.5 + (float) mixi(v{a}, 3) pettu")
        elif k == 6:
            L.append(f"  v{a} lo id(v{b}) - id(v{c}) + id(v{a}) pettu")
        elif k == 7:
            L += ["  s0 lo s0 + s1 pettu", "  s1 lo (padham) c0 + \"!\" pettu", f"  v{a} lo v{a} + podavu(s0) pettu"]
        else:
            L += [f"  c0 lo (char) (c1 + v{a}) pettu", f"  b0 lo b0 == (v{b} > v{c}) pettu", f"  c1 lo c0 pettu"]
    for i in range(ni):
        L.append(f"  v{i} ni chupi")
    for i in range(nf):
        L.append(f"  f{i} ni chupi")
    if extra_types:
        L += ["  c0 ni chupi", "  c1 ni chupi", "  b0 ni chupi", "  b1 ni chupi", "  s0 ni chupi", "  s1 ni chupi"]
    L.append("  (" + " + ".join(f"v{i}" for i in range(ni)) + ") ni chupi")
    L.append("  (" + " + ".join(f"f{i}" for i in range(nf)) + ") ni chupi")
    L.append("  v0 ivvu")
    L.append("}")
    L += ["int s", "s ni chaduvu", "run(s) ni chupi", "run(s + 5) ni chupi", "gtr ni chupi"]
    return prog(*L), f"{r.randrange(-50, 50)}\n".encode()


# --------------------------------------------------------------------------------------------- deep expression trees
def _tree(r: random.Random, d: int, shape: str, leaf, node):
    if d <= 0:
        return leaf()
    if shape == "left":
        return node(_tree(r, d - 1, shape, leaf, node), leaf())
    if shape == "right":
        return node(leaf(), _tree(r, d - 1, shape, leaf, node))
    if shape == "bal":
        return node(_tree(r, d - 1, shape, leaf, node), _tree(r, d - 1, shape, leaf, node))
    s = r.choice(["left", "right", "bal"])
    return node(_tree(r, d - 1, "rand", leaf, node), _tree(r, d - 1, "rand", leaf, node)) if s == "bal" else \
        (node(_tree(r, d - 1, "rand", leaf, node), leaf()) if s == "left" else node(leaf(), _tree(r, d - 1, "rand", leaf, node)))


def deep_expr(seed: int, depth: int, shape: str, kind: str = "int", calls: bool = False) -> tuple[str, bytes]:
    """`f(a0..a7, x0..x5)` whose body is one expression tree of the given depth/shape. kind: int | float | mixed | bool."""
    r = random.Random(seed)
    ints = [f"a{i}" for i in range(8)]
    flts = [f"x{i}" for i in range(6)]

    def ileaf():
        c = r.random()
        if c < 0.75:
            return r.choice(ints)
        if c < 0.9:
            return r.choice(["1", "2", "3", "7", "255", "65537", "1000000007"])
        return "(-" + r.choice(["5", "9", "300"]) + ")"

    def fleaf():
        c = r.random()
        return r.choice(flts) if c < 0.8 else r.choice(["0.5", "1.5", "2.25", "(-0.75)", "3.0"])

    def inode(a, b):
        k = r.randrange(9 if calls else 7)
        if k == 0:
            return f"({a} + {b})"
        if k == 1:
            return f"({a} - {b})"
        if k == 2:
            return f"({a} * {b})"
        if k == 3:
            return f"(({a}) / {r.choice(['7', '-3', '1000', '9'])} + {b})"
        if k == 4:
            return f"(({a}) % {r.choice(['7', '-5', '13'])} - {b})"
        if k == 5:
            return f"(-{a} + {b})"
        if k == 6 and kind == "mixed":
            return f"((int) ({fnode(fleaf(), fleaf())}) + {a} - {b})"
        if k == 7:
            return f"mixi({a}, {b})"
        if k == 8:
            return f"(id({a}) - id({b}))"
        return f"({a} * 3 + {b})"

    def fnode(a, b):
        k = r.randrange(6)
        if k == 0:
            return f"({a} + {b})"
        if k == 1:
            return f"({a} - {b})"
        if k == 2:
            return f"({a} * 0.5 + {b})"
        if k == 3:
            return f"({a} / 2.0 - {b})"
        if k == 4 and kind == "mixed":
            return f"((float) ({inode(ileaf(), ileaf())}) * 0.001 + {a} - {b})"
        if k == 5 and calls:
            return f"mixf({a}, {b})"
        return f"({a} * 0.25 + {b} * 0.75)"

    def bnode(a, b):
        k = r.randrange(6)
        return [f"({a} && {b})", f"({a} || {b})", f"({a} == {b})", f"({a} != {b})", f"(!{a} && {b})", f"({a} || !{b})"][k]

    if kind == "int":
        body, ret = _tree(r, depth, shape, ileaf, inode), "int"
    elif kind == "float":
        body, ret = _tree(r, depth, shape, fleaf, fnode), "float"
    elif kind == "mixed":
        body, ret = _tree(r, depth, shape, ileaf, inode), "int"
    else:
        def bleaf():
            c = r.random()
            if c < 0.5:
                return f"({ileaf()} < {ileaf()})"
            if c < 0.8:
                return f"({fleaf()} >= {fleaf()})"
            return r.choice(["nijam", "abaddham"])
        body, ret = _tree(r, depth, shape, bleaf, bnode), "bool"
    params = ", ".join([f"int a{i}" for i in range(8)] + [f"float x{i}" for i in range(6)])
    L = [BASIC, f"{ret} f charya ({params}) {{", f"  {body} ivvu", "}"]
    for i in range(8):
        L.append(f"int g{i}")
    for i in range(6):
        L.append(f"float h{i}")
    for i in range(8):
        L.append(f"g{i} ni chaduvu")
    for i in range(6):
        L.append(f"h{i} ni chaduvu")
    L.append(f"f({', '.join([f'g{i}' for i in range(8)] + [f'h{i}' for i in range(6)])}) ni chupi")
    L.append(f"f({', '.join([f'g{(i + 3) % 8}' for i in range(8)] + [f'h{(i + 2) % 6}' for i in range(6)])}) ni chupi")
    stdin = (" ".join(str(r.randrange(-1000, 1000)) for _ in range(8)) + "\n" +
             " ".join(["%.2f" % r.uniform(-4, 4) for _ in range(6)]) + "\n").encode()
    return prog(*L), stdin


def wide_sum_tree(n: int, calls: bool) -> tuple[str, bytes]:
    """Right-nested sum/product over `n` distinct live variables: forces ~n simultaneously live temporaries."""
    L = [BASIC, "int f charya (int s) {"]
    for i in range(n):
        L.append(f"  int w{i}")
        L.append(f"  w{i} lo s * {i + 2} + {i} pettu")
    e = f"w{n - 1}"
    for i in range(n - 2, -1, -1):
        leaf = f"mixi(w{i}, {i})" if calls and i % 3 == 0 else f"w{i}"
        e = f"({leaf} {['+', '*', '-'][i % 3]} {e})"
    L += [f"  {e} ivvu", "}", "int q", "q ni chaduvu", "f(q) ni chupi", "f(q + 1) ni chupi"]
    return prog(*L), b"3\n"


# --------------------------------------------------------------------------------------------- many parameters
TYPES5 = ["int", "float", "char", "bool", "padham"]


def _arg(t: str, i: int, r: random.Random) -> str:
    if t == "int":
        return r.choice([f"gi + {i}", f"mixi(gi, {i})", f"(-{i + 1})", "9223372036854775807", f"{i} * 1000003"])
    if t == "float":
        return r.choice([f"gf * {i + 1}.5", f"{i}.25", f"(-{i}.5)", f"mixf(gf, {i}.0)"])
    if t == "char":
        return r.choice([f"(char) (gi + {i + 120})", "'z'", "(char) 200", f"(char) {i}"])
    if t == "bool":
        return r.choice([f"gi > {i}", "nijam", "abaddham", f"gf < {i}.5"])
    return r.choice(['"s" + (padham) (char) (65 + gi % 20)', '"abc"', '""', '"x\\ty"'])


def _mod(t: str, name: str) -> str:
    return {"int": f"{name} + 1", "float": f"{name} * 2.0", "char": f"(char) ({name} + 1)", "bool": f"!{name}",
            "padham": f"{name} + \"!\""}[t]


def many_params(seed: int, n: int, types: list[str] | None = None) -> tuple[str, bytes]:
    """`cb` takes n mixed params, prints and checksums them; `cb2` forwards (modified) params twice; main calls both."""
    r = random.Random(seed)
    ts = types or [r.choice(TYPES5) for _ in range(n)]
    n = len(ts)
    sig = ", ".join(f"{t} p{i}" for i, t in enumerate(ts))
    L = [BASIC, "int gi", "float gf", "int tick charya () { gtr lo gtr + 1 pettu\n gtr ivvu }", f"int cb charya ({sig}) {{", "  int s", "  s lo 17 pettu"]
    for i, t in enumerate(ts):
        L.append(f"  p{i} ni chupi")
        add = {"int": f"p{i}", "float": f"(int) (p{i} * 100.0)", "char": f"(int) p{i}", "bool": f"(int) p{i}", "padham": f"podavu(p{i})"}[t]
        L.append(f"  s lo s * 31 + {add} pettu")
    L += ["  s ivvu", "}"]
    L.append(f"int cb2 charya ({sig}) {{")
    L.append("  int r")
    L.append("  r lo cb(" + ", ".join(_mod(t, f"p{i}") for i, t in enumerate(ts)) + ") pettu")
    L.append("  r lo r + cb(" + ", ".join(f"p{i}" for i in range(n)) + ") pettu")
    # parameters stay live across the calls above and are used again afterwards
    L.append("  r + (" + " + ".join({"int": f"p{i}", "float": f"(int) p{i}", "char": f"(int) p{i}", "bool": f"(int) p{i}",
                                      "padham": f"podavu(p{i})"}[t] for i, t in enumerate(ts)) + ") ivvu")
    L.append("}")
    L += ["gi ni chaduvu", "gf ni chaduvu"]
    args = [_arg(t, i, r) for i, t in enumerate(ts)]
    L.append(f"cb({', '.join(args)}) ni chupi")
    L.append(f"cb2({', '.join(args)}) ni chupi")
    L.append(f"cb2({', '.join(_arg(t, i + 3, r) for i, t in enumerate(ts))}) ni chupi")
    return prog(*L), f"{r.randrange(-30, 30)} {r.randrange(1, 30)}.5\n".encode()


def float_positions(npar: int, floats: set[int], seed: int = 0) -> tuple[str, bytes]:
    """Function with `npar` params where the (0-based) positions in `floats` are float and the rest int."""
    r = random.Random(seed)
    ts = ["float" if i in floats else "int" for i in range(npar)]
    sig = ", ".join(f"{t} p{i}" for i, t in enumerate(ts))
    L = [BASIC, f"float fn charya ({sig}) {{", "  float acc", "  acc lo 0.0 pettu"]
    for i, t in enumerate(ts):
        L.append(f"  acc lo acc * 1.5 + (float) p{i} * {i + 1}.0 pettu")
        L.append(f"  p{i} ni chupi")
    L += ["  acc ivvu", "}", "int gi", "float gf", "gi ni chaduvu", "gf ni chaduvu"]
    args = []
    for i, t in enumerate(ts):
        args.append(f"gf + {i}.25" if t == "float" else f"gi * {i + 1} + {r.randrange(-9, 9)}")
    L.append(f"fn({', '.join(args)}) ni chupi")
    L.append(f"fn({', '.join(args)}) + fn({', '.join(args)}) ni chupi")
    return prog(*L), b"7 2.5\n"


# --------------------------------------------------------------------------------------------- recursion with many live values
def recursion_live(n: int, nlive: int = 12) -> tuple[str, bytes]:
    ps = ", ".join(["int n"] + [f"int a{i}" for i in range(4)] + [f"float x{i}" for i in range(3)])
    L = [BASIC, f"float rec charya ({ps}) {{"]
    for i in range(nlive):
        L.append(f"  int l{i}")
        L.append(f"  l{i} lo (a{i % 4} * {i + 3} + {i}) % 100003 pettu")
    for i in range(3):
        L.append(f"  float y{i}")
        L.append(f"  y{i} lo x{i} * 0.5 + (float) l{i} pettu")
    L.append("  n <= 0 ayite { (float) (" + " + ".join(f"l{i}" for i in range(nlive)) + ") + y0 + y1 + y2 ivvu }")
    L.append("  float r1")
    L.append(f"  r1 lo rec(n - 1, {', '.join(f'l{i}' for i in range(4))}, y0, y1, y2) pettu")
    L.append("  float r2")
    L.append(f"  r2 lo rec(n - 2, {', '.join(f'l{i + 4}' for i in range(4))}, y2, y0, y1) pettu")
    L.append("  float r3")
    L.append(f"  r3 lo rec(n - 3, {', '.join(f'l{i + 8}' for i in range(4))}, y1, y1, y0) pettu")
    # every live local is read again after the recursive calls
    L.append("  r1 * 0.001 + r2 * 0.002 + r3 * 0.003 + (float) (" + " + ".join(f"l{i}" for i in range(nlive)) + ") + y0 + y1 + y2 ivvu")
    L.append("}")
    # mutual recursion with strings
    L += ["padham ms charya (int n, padham a, padham b) { n <= 0 ayite { a + b ivvu }\n ms2(n - 1, b, a + \"1\") + a ivvu }",
          "padham ms2 charya (int n, padham a, padham b) { n <= 0 ayite { b ivvu }\n ms(n - 1, a + b, \"z\") ivvu }"]
    L += ["int q", "q ni chaduvu", f"rec({n}, q, q + 1, q + 2, q + 3, 1.5, 2.5, 3.5) ni chupi", "ms(q, \"a\", \"b\") ni chupi"]
    return prog(*L), b"5\n"


# --------------------------------------------------------------------------------------------- loops / aapu / saagu with live values
def loops_live(seed: int, nlive: int = 22) -> tuple[str, bytes]:
    r = random.Random(seed)
    L = [BASIC, "int work charya (int n) {"]
    for i in range(nlive):
        L += [f"  int v{i}", f"  v{i} lo n + {i * 7} pettu"]
    for i in range(10):
        L += [f"  float f{i}", f"  f{i} lo (float) n * {i + 1}.25 pettu"]
    L.append("  int total")
    L.append("  total lo 0 pettu")

    def upd():
        a, b, c = (r.randrange(nlive) for _ in range(3))
        x = r.randrange(10)
        return r.choice([f"v{a} lo (v{a} + v{b} * 3 - v{c}) % 10007 pettu", f"f{x} lo f{x} * 0.5 + (float) v{b} pettu",
                         f"v{a} lo v{a} + mixi(v{b}, v{c}) pettu", f"total lo total + v{a} - v{c} pettu"])

    L += ["  prati i 0 nundi 9 varaku {"]
    for _ in range(5):
        L.append("    " + upd())
    L += ["    i % 3 == 0 ayite { saagu }", "    " + upd(), f"    v0 > {r.randrange(3000, 9000)} ayite {{ aapu }}", "    " + upd(), "  }"]
    L += ["  int k", "  k lo 0 pettu", "  k < 40 unnanta varaku {", "    k lo k + 1 pettu", "    k % 4 == 1 ayite { saagu }"]
    for _ in range(4):
        L.append("    " + upd())
    L += ["    prati j 0 nundi 5 varaku {", "      j == k % 5 ayite { saagu }", "      " + upd(), "      total > 100000 ayite { aapu }", "      " + upd(), "    }",
          "    k > 33 ayite { aapu }", "    " + upd(), "  }"]
    L += ["  pratisari (int m lo 0 pettu; m < 12; m++) {", "    " + upd(), "    m == 7 ayite { saagu }", "    " + upd(), "    m == 10 ayite { aapu }", "  }"]
    for i in range(nlive):
        L.append(f"  v{i} ni chupi")
    for i in range(10):
        L.append(f"  f{i} ni chupi")
    L += ["  total + " + " + ".join(f"v{i}" for i in range(nlive)) + " ivvu", "}"]
    L += ["int q", "q ni chaduvu", "work(q) ni chupi", "work(q * 2 + 1) ni chupi"]
    return prog(*L), f"{r.randrange(0, 40)}\n".encode()


def nested_call_args(depth: int) -> tuple[str, bytes]:
    """f(g(a,b), h(c), a+b*c) shaped calls with order-recording side effects and many live locals."""
    L = [BASIC, "int tr",
         "int g charya (int a, int b) { tr lo tr * 10 + 1 pettu\n a * 3 + b ivvu }",
         "int h charya (int a) { tr lo tr * 10 + 2 pettu\n a - 5 ivvu }",
         "int f charya (int a, int b, int c) { tr lo tr * 10 + 3 pettu\n a * 100 + b * 10 + c ivvu }",
         "float ff charya (float a, float b, float c) { tr lo tr * 10 + 4 pettu\n a + b * 2.0 + c * 3.0 ivvu }",
         "int k charya (int a, int b, int c, int d, int e, int f2, int g2, int h2) { tr lo tr * 10 + 5 pettu\n a + b * 2 + c * 3 + d * 4 + e * 5 + f2 * 6 + g2 * 7 + h2 * 8 ivvu }",
         "int run charya (int a, int b, int c) {"]
    for i in range(14):
        L += [f"  int l{i}", f"  l{i} lo a * {i + 1} - b + c pettu"]
    L += ["  tr lo 0 pettu", "  int r1", "  r1 lo f(g(a, b), h(c), a + b * c) pettu", "  r1 ni chupi", "  tr ni chupi", "  tr lo 0 pettu"]
    e = "a"
    for d in range(depth):
        e = f"f(g({e}, l{d % 14}), h({['a', 'b', 'c'][d % 3]}), {e} + b * c)"
    L += [f"  int r2", f"  r2 lo {e} pettu", "  r2 ni chupi", "  tr ni chupi", "  tr lo 0 pettu"]
    L += ["  float r3", "  r3 lo ff(g(a, b), h(c), mixf(g(b, c), (float) h(a))) pettu", "  r3 ni chupi", "  tr ni chupi", "  tr lo 0 pettu"]
    L += ["  int r4", "  r4 lo k(g(a, b), h(c), g(h(a), h(b)), a + b, g(c, c), h(h(h(a))), f(a, b, c), id(l0)) pettu", "  r4 ni chupi", "  tr ni chupi"]
    L += ["  r1 + r2 + r4 + " + " + ".join(f"l{i}" for i in range(14)) + " ivvu", "}"]
    L += ["int x", "int y", "int z", "x ni chaduvu", "y ni chaduvu", "z ni chaduvu", "run(x, y, z) ni chupi"]
    return prog(*L), b"4 5 6\n"


# --------------------------------------------------------------------------------------------- short-circuit with side effects
def short_circuit(seed: int, nterms: int = 12, depth: int = 4) -> tuple[str, bytes]:
    r = random.Random(seed)
    cnt = [0]

    def term():
        cnt[0] += 1
        k = r.randrange(5)
        i = cnt[0]
        if k == 0:
            return f"t({i}, a)"
        if k == 1:
            return f"t({i}, !a)"
        if k == 2:
            return f"(u({i}) > b)"
        if k == 3:
            return f"(vf({i}) < 1.5 + x)"
        return f"(t({i}, a) == t({i + 100}, b > 0))"

    def tree(d):
        if d == 0:
            return term()
        c = r.randrange(4)
        if c == 0:
            return f"({tree(d - 1)} && {tree(d - 1)})"
        if c == 1:
            return f"({tree(d - 1)} || {tree(d - 1)})"
        if c == 2:
            return f"(!{tree(d - 1)})"
        return f"({tree(d - 1)} && ({tree(d - 1)} || {tree(d - 1)}))"

    L = [BASIC, "int tr",
         "bool t charya (int id, bool v) { tr lo tr * 7 + id pettu\n tr lo tr % 1000000007 pettu\n v ivvu }",
         "int u charya (int id) { tr lo tr * 7 + id pettu\n tr lo tr % 1000000007 pettu\n id % 3 ivvu }",
         "float vf charya (int id) { tr lo tr * 7 + id pettu\n tr lo tr % 1000000007 pettu\n (float) (id % 4) ivvu }",
         "int run charya (bool a, int b, float x) {"]
    for i in range(16):
        L += [f"  int l{i}", f"  l{i} lo b * {i + 1} + {i} pettu"]
    for ex in range(nterms):
        L += [f"  bool r{ex}", f"  r{ex} lo {tree(depth)} pettu", f"  r{ex} ni chupi", "  tr ni chupi", "  tr lo 0 pettu"]
    L += ["  int cnt", "  cnt lo 0 pettu"]
    L += [f"  {tree(3)} ayite {{ cnt lo cnt + 1 pettu }} lekunte {{ cnt lo cnt + 10 pettu }}", "  tr ni chupi", "  tr lo 0 pettu"]
    L += [f"  int w", "  w lo 0 pettu", f"  (w < 5 && {tree(2)}) unnanta varaku {{ w lo w + 1 pettu }}", "  tr ni chupi", "  w ni chupi"]
    L += ["  cnt + " + " + ".join(f"l{i}" for i in range(16)) + " ivvu", "}"]
    L += ["run(nijam, 2, 0.5) ni chupi", "run(abaddham, -1, 1.25) ni chupi", "run(nijam, 0, -3.0) ni chupi"]
    return prog(*L), b""


# --------------------------------------------------------------------------------------------- edge values / char / NaN
EDGE_VALUES = ["9223372036854775807", IMIN, "0", "1", "(-1)", "4611686018427387904", "(-4611686018427387904)", "3037000500", "(-3037000500)"]


def int_edges() -> tuple[str, bytes]:
    """Binary ops on INT64 edge values passed through registers (non-constant) incl. wrap-around, never trapping."""
    L = [BASIC, "int pw charya (int a, int b, int c, int d) {",
         "  a + b ni chupi", "  a - b ni chupi", "  a * b ni chupi", "  -a ni chupi", "  c * d ni chupi", "  (a + b) * (c - d) ni chupi",
         "  a < b ni chupi", "  a >= b ni chupi", "  a == b ni chupi", "  a != c ni chupi", "  (a + 1) < a ni chupi", "  (b - 1) > b ni chupi",
         "  (float) a ni chupi", "  (float) b ni chupi", "  (bool) a ni chupi", "  (char) a ni chupi", "  (char) b ni chupi", "  (char) c ni chupi",
         "  a / 3 ni chupi", "  b / 7 ni chupi", "  a % 10 ni chupi", "  b % 10 ni chupi", "  b / 1 ni chupi", "  b % 1 ni chupi",
         "  (a / 2) / (-1) ni chupi", "  d % 2 ni chupi", "  a * a * a ni chupi",
         "  int s", "  s lo a pettu", "  s lo s + 1 pettu", "  s lo s - 1 - 1 pettu", "  s lo s * 3 pettu", "  s ivvu", "}"]
    for i in range(4):
        L.append(f"int e{i}")
    for i in range(4):
        L.append(f"e{i} ni chaduvu")
    L.append("pw(e0, e1, e2, e3) ni chupi")
    L.append("pw(e1, e0, e3, e2) ni chupi")
    L.append("pw(e2, e3, e0, e1) ni chupi")
    L.append("pw(e3, e2, e1, e0) ni chupi")
    stdin = "\n".join(f"{a} {b} {c} {d}" for a, b, c, d in [("9223372036854775807", "-9223372036854775808", "3037000500", "-3037000500")]) + "\n"
    return prog(*L), stdin.encode()


def char_signext() -> tuple[str, bytes]:
    L = [BASIC, "char cc charya (char a, char b, int k) {",
         "  char c", "  char d", "  c lo (char) (k + 200) pettu", "  d lo (char) (k * 3 - 300) pettu",
         "  (int) a ni chupi", "  (int) b ni chupi", "  (int) c ni chupi", "  (int) d ni chupi",
         "  a + b ni chupi", "  c + d ni chupi", "  a < 0 ni chupi", "  c < 0 ni chupi", "  d > 50 ni chupi", "  a < b ni chupi", "  c == d ni chupi",
         "  (a == 'a') ni chupi", "  (int) (char) (a + 100) ni chupi", "  (int) (char) (c * 2) ni chupi", "  (float) a ni chupi", "  (float) c ni chupi",
         "  (a + 0) * 1000 ni chupi", "  (a - 200) ni chupi", "  (bool) c ni chupi", "  (int) (char) (c + d + a + b) ni chupi",
         "  (padham) a + (padham) b + (padham) c ni chupi",
         "  char arr[4]", "  arr[0] lo a pettu", "  arr[1] lo c pettu", "  arr[2] lo (char) (a + c) pettu", "  arr[3] lo (char) 255 pettu",
         "  (int) arr[0] ni chupi", "  (int) arr[1] ni chupi", "  (int) arr[2] ni chupi", "  (int) arr[3] ni chupi", "  arr[3] < arr[0] ni chupi",
         "  (int) arr[0] + (int) arr[1] + (int) arr[2] + (int) arr[3] ni chupi",
         "  c ivvu", "}",
         "char x", "char y", "int kk", "x ni chaduvu", "y ni chaduvu", "kk ni chaduvu",
         "(int) cc(x, y, kk) ni chupi", "(int) cc(y, x, kk + 1) ni chupi", "cc('a', (char) 128, 7) ni chupi",
         "(int) cc((char) 200, (char) 127, 0) ni chupi", "cc((char) (-128), (char) 129, 1000) ni chupi"]
    return prog(*L), b"\xe9 \xff 5\n"


def float_specials() -> tuple[str, bytes]:
    L = [BASIC, "float fs charya (float z, float one, int k) {",
         "  float nan", "  float inf", "  float nz", "  float a", "  float b", "  float c", "  float d", "  float e",
         "  nan lo z / z pettu", "  inf lo one / z pettu", "  nz lo -z pettu", "  a lo mixf(nan, one) pettu", "  b lo mixf(nz, inf) pettu",
         "  c lo (float) k * nz pettu", "  d lo nz - z pettu", "  e lo one / nz pettu",
         "  nan ni chupi", "  inf ni chupi", "  nz ni chupi", "  a ni chupi", "  b ni chupi", "  c ni chupi", "  d ni chupi", "  e ni chupi",
         "  nan == nan ni chupi", "  nan != nan ni chupi", "  nan < one ni chupi", "  nan >= one ni chupi", "  nz == z ni chupi", "  nz < z ni chupi", "  nz > z ni chupi",
         "  (bool) nan ni chupi", "  (bool) nz ni chupi", "  (bool) z ni chupi", "  (int) nan ni chupi", "  (int) inf ni chupi", "  (int) nz ni chupi",
         "  (int) (-inf) ni chupi", "  (int) (char) nan ni chupi",
         "  !nan ni chupi", "  nan && nijam ni chupi", "  nz || abaddham ni chupi", "  nz ni chupi",
         "  float acc", "  acc lo 0.0 pettu", "  acc lo acc + nan pettu", "  acc lo acc * nz pettu", "  acc ni chupi",
         "  float f0", "  float f1", "  float f2", "  float f3", "  float f4", "  float f5", "  float f6", "  float f7", "  float f8", "  float f9", "  float f10", "  float f11",
         "  f0 lo nan pettu", "  f1 lo nz pettu", "  f2 lo inf pettu", "  f3 lo -inf pettu", "  f4 lo one pettu", "  f5 lo z pettu", "  f6 lo mixf(f1, f2) pettu",
         "  f7 lo f0 + f1 pettu", "  f8 lo f1 * f4 pettu", "  f9 lo f5 * f1 pettu", "  f10 lo f2 + f3 pettu", "  f11 lo f1 / f2 pettu",
         "  f0 ni chupi", "  f1 ni chupi", "  f2 ni chupi", "  f3 ni chupi", "  f4 ni chupi", "  f5 ni chupi", "  f6 ni chupi", "  f7 ni chupi", "  f8 ni chupi", "  f9 ni chupi",
         "  f10 ni chupi", "  f11 ni chupi", "  (f1 == f5) ni chupi", "  (f8 < f9) ni chupi", "  (f11 == f5) ni chupi", "  one / f11 ni chupi",
         "  f1 ivvu", "}",
         "float zz", "float oo", "int kk", "zz ni chaduvu", "oo ni chaduvu", "kk ni chaduvu", "fs(zz, oo, kk) ni chupi", "fs(-zz, -oo, kk) ni chupi"]
    return prog(*L), b"0.0 1.0 3\n"


# --------------------------------------------------------------------------------------------- aliasing
def array_aliasing() -> tuple[str, bytes]:
    L = [BASIC,
         "void al charya (int x[], int y[], int z[], int n) {",
         "  int t", "  int u",
         "  prati i 0 nundi n varaku {",
         "    t lo y[i] pettu", "    x[i] lo t + 1 pettu", "    u lo y[i] pettu", "    z[i] lo u * 2 + t pettu", "    t lo x[i] + z[i] pettu", "    y[i] lo t pettu",
         "    t ni chupi", "    u ni chupi",
         "  }", "}",
         "void al2 charya (int a[], int b[], int c[], int d[], int e[], int f[], int g[], int h[]) {",
         "  int s0", "  int s1", "  int s2", "  int s3", "  int s4", "  int s5", "  int s6", "  int s7",
         "  s0 lo a[0] pettu", "  s1 lo b[0] pettu", "  s2 lo c[0] pettu", "  s3 lo d[0] pettu", "  s4 lo e[0] pettu", "  s5 lo f[0] pettu", "  s6 lo g[0] pettu", "  s7 lo h[0] pettu",
         "  a[0] lo 100 pettu", "  s0 + s1 + s2 + s3 + s4 + s5 + s6 + s7 ni chupi", "  b[0] + c[0] + d[0] + e[0] + f[0] + g[0] + h[0] ni chupi",
         "  b[0] lo b[0] + a[0] pettu", "  c[0] lo c[0] * 2 pettu", "  h[0] lo h[0] - 1 pettu", "  a[0] ni chupi", "  d[0] ni chupi", "  g[0] ni chupi", "}",
         "float falias charya (float p[], float q[], int n) {", "  float s", "  s lo 0.0 pettu",
         "  prati i 0 nundi n varaku { p[i] lo p[i] + 1.5 pettu\n s lo s + q[i] * 2.0 pettu\n q[i] lo q[i] - 0.25 pettu\n s lo s + p[i] pettu }", "  s ivvu", "}",
         "int gar[6]", "int ga[8]", "int m[3][4]", "float fa[5]", "int c3[2][3][4]",
         "void bump charya (int p[]) { gar[1] lo gar[1] + 10 pettu\n p[1] lo p[1] * 2 pettu\n gar[1] lo gar[1] + p[1] pettu }",
         "int n", "n ni chaduvu", "int loc[8]",
         "prati i 0 nundi 6 varaku { gar[i] lo i + 1 pettu }",
         "al(gar, gar, gar, 6)", "prati i 0 nundi 6 varaku { gar[i] ni chupi }",
         "prati i 0 nundi 6 varaku { ga[i] lo i * 3 pettu }", "al(ga, ga, gar, 6)", "al(gar, ga, ga, 6)", "al(ga, gar, gar, 6)",
         "prati i 0 nundi 6 varaku { gar[i] ni chupi\n ga[i] ni chupi }",
         "prati i 0 nundi 4 varaku { m[0][i] lo i pettu\n m[1][i] lo i * 10 pettu }",
         "al(m[0], m[0], m[1], 4)", "al(m[1], m[0], m[0], 4)", "al(m[0], m[1], m[1], 4)", "prati i 0 nundi 4 varaku { m[0][i] ni chupi\n m[1][i] ni chupi }",
         "al2(gar, gar, gar, gar, gar, gar, gar, gar)", "al2(ga, ga, gar, gar, ga, gar, m[0], m[0])", "al2(m[2], m[2], m[2], m[2], m[2], m[2], m[2], m[2])",
         "al2(c3[1][1], c3[1][1], c3[1][2], c3[1][1], c3[0][0], c3[0][0], c3[1][1], c3[1][2])", "c3[1][1][0] ni chupi", "c3[1][2][0] ni chupi",
         "prati i 0 nundi 5 varaku { fa[i] lo (float) i pettu }", "falias(fa, fa, 5) ni chupi", "prati i 0 nundi 5 varaku { fa[i] ni chupi }",
         "bump(gar)", "gar[1] ni chupi", "prati i 0 nundi 8 varaku { loc[i] lo n + i pettu }", "al(loc, loc, loc, 8)", "al(loc, gar, loc, 6)", "bump(loc)", "loc[1] ni chupi"]
    return prog(*L), b"3\n"


# --------------------------------------------------------------------------------------------- runtime errors under pressure
def trap_under_pressure(kind: str) -> tuple[str, bytes]:
    bad = {"div": "q / z", "rem": "q % z", "ovf": "m / (z * 2 - 1)", "idx": "(int) s[z * 5 - 3]"}[kind]
    L = [BASIC, "int tr charya (int z, int m, padham s) {", "  int q", "  q lo 1000 pettu"]
    for i in range(18):
        L += [f"  int v{i}", f"  v{i} lo mixi(z + {i}, m) pettu"]
    L += ["  v0 ni chupi", "  v17 ni chupi", f"  int r", f"  r lo {bad} pettu", "  r ni chupi",
          "  " + " + ".join(f"v{i}" for i in range(18)) + " ivvu", "}",
          "int zz", "int mm", "zz ni chaduvu", "mm ni chaduvu", "tr(zz + 1, mm, \"abc\") ni chupi", "tr(zz, mm, \"abc\") ni chupi", "\"unreachable\" ni chupi"]
    return prog(*L), b"0 -9223372036854775808\n"


# --------------------------------------------------------------------------------------------- runtime calls with many live values
def rt_calls_live(seed: int, ni: int = 18, nf: int = 12, iters: int = 3) -> tuple[str, bytes]:
    """Values (ints, floats, chars, bools, strings) stay live across calls into the C runtime: output of every type,
    input of every type, string concatenation/comparison/indexing, podavu."""
    r = random.Random(seed)
    L = [BASIC, "int run charya (int n) {"]
    for i in range(ni):
        L += [f"  int v{i}", f"  v{i} lo n * {i + 3} - {i} pettu"]
    for i in range(nf):
        L += [f"  float f{i}", f"  f{i} lo (float) n / {i + 2}.0 pettu"]
    L += ["  char c", "  bool b", "  padham s", "  padham t", "  padham u", "  int w", "  float x",
          "  c lo (char) (n + 60) pettu", "  b lo n > 2 pettu", "  s lo \"s\" pettu", "  t lo \"\" pettu", "  u lo \"\" pettu", "  w lo 0 pettu", "  x lo 0.0 pettu"]
    L.append(f"  prati it 0 nundi {iters} varaku {{")
    for _ in range(14):
        a, b2 = r.randrange(ni), r.randrange(ni)
        x = r.randrange(nf)
        k = r.randrange(11)
        L.append("    " + [
            f"f{x} ni chupi", f"v{a} ni chupi", "c ni chupi", "b ni chupi", "s lo s + (padham) c pettu",
            "t lo s + \"-\" + s pettu", f"v{a} lo v{a} + podavu(t) pettu", "b lo s == t pettu",
            "w ni chaduvu\n    x ni chaduvu\n    u ni chaduvu\n    " + f"v{b2} lo v{b2} + w + podavu(u) pettu\n    f{x} lo f{x} + x pettu",
            f"c lo (char) (c + v{a} % 7) pettu", f"u ni chupi"][k])
    L.append("  }")
    for i in range(ni):
        L.append(f"  v{i} ni chupi")
    for i in range(nf):
        L.append(f"  f{i} ni chupi")
    L += ["  c ni chupi", "  b ni chupi", "  s ni chupi", "  t ni chupi", "  u ni chupi",
          "  (" + " + ".join(f"v{i}" for i in range(ni)) + ") ni chupi", "  (" + " + ".join(f"f{i}" for i in range(nf)) + ") ni chupi", "  v0 ivvu", "}",
          "int q", "q ni chaduvu", "run(q) ni chupi"]
    lines = "".join(f"{r.randrange(-99, 99)} {r.uniform(-9, 9):.3f}\nline number {k} \xe9x\n" for k in range(iters * 14))
    return prog(*L), (f"{r.randrange(1, 9)}\n" + lines).encode("latin-1")


def int_args(n: int) -> tuple[str, bytes]:
    """`n` int params weighted by distinct primes (a transposed/lost stack argument changes the sum)."""
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89]
    sig = ", ".join(f"int p{i}" for i in range(n))
    body = " + ".join(f"p{i} * {primes[i]}" for i in range(n))
    args = ", ".join(f"g + {i * 3 - 5}" for i in range(n))
    nested = ", ".join(f"g * {i + 1}" for i in range(n))
    L = [f"int fa charya ({sig}) {{", f"  p0 lo p0 + 0 pettu", f"  {body} ivvu", "}", "int g", "g ni chaduvu",
         f"fa({args}) ni chupi", f"fa({nested}) ni chupi", f"fa({args}) + fa({nested}) ni chupi"]
    if n >= 2:
        L.append("fa(" + ", ".join(f"fa({', '.join(['g'] * n)})" if i % 2 == 0 else f"g - {i}" for i in range(n)) + ") ni chupi")
    return prog(*L), b"13\n"
