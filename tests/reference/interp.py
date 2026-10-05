"""Independent tree-walking reference interpreter for Devara.

Written from docs/DEVARA_LANGUAGE_SPEC_v0.7.md, the AST contract in design §3.5 and the
semantic decisions L1-L49 / P1-P40.  It never looks at the compiler's semantic, IR or
code-generation stages: its only input is the *parser's* AST (as the JSON produced by
``devara parse --json`` or an equivalent dict tree) plus a stdin byte string.  It performs its
own typing dynamically (every value carries its Devara type), so it serves as a differential
oracle for sema/IR/optimizer/codegen/runtime.

Public API::

    result = run_ast(ast_data, stdin_bytes, max_steps=...)   # -> Result
    result = run_file("prog.tel", stdin_bytes)                # shells out to ./devara parse --json
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MASK = (1 << 64) - 1
INT_MIN = -(1 << 63)
INT_MAX = (1 << 63) - 1

ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- results / errors
@dataclass
class Result:
    stdout: bytes
    status: int  # 0 normal, 1 runtime error
    error: str = ""  # runtime error message (without prefix)


class RuntimeErr(Exception):
    pass


class StepLimit(Exception):
    pass


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


# --------------------------------------------------------------------------- values
# A scalar value is a pair (type, python_value):
#   int -> signed 64 bit int, char -> signed 8 bit int, bool -> bool, float -> float,
#   padham -> str of code points 0..255 (one per byte)
def wrap(x: int) -> int:
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


def wrap8(x: int) -> int:
    x &= 0xFF
    return x - 256 if x >= 128 else x


ARITH = ("bool", "char", "int", "float")
ZERO = {"int": 0, "char": 0, "bool": False, "float": 0.0, "padham": ""}


class Arr:
    """A (possibly partial) view of a row-major array."""

    def __init__(self, elem, dims, data, offset=0):
        self.elem = elem
        self.dims = dims  # list[int] or [None] for unsized parameter
        self.data = data  # shared flat list
        self.offset = offset

    def stride(self, depth):
        s = 1
        for d in self.dims[depth + 1:]:
            s *= d
        return s


def conv(v, to, explicit=False):
    """Convert scalar ``v`` = (type, value) to type ``to`` (P27)."""
    ty, x = v
    if ty == to:
        return v
    if to == "padham":
        if explicit and ty == "char":
            return ("padham", chr(x & 0xFF))
        raise AssertionError("invalid conversion %s->%s" % (ty, to))
    if ty == "padham":
        if explicit and to == "char":
            if len(x) != 1:
                raise RuntimeErr("invalid char conversion")
            return ("char", wrap8(ord(x)))
        raise AssertionError("invalid conversion %s->%s" % (ty, to))
    # arithmetic -> arithmetic
    if to == "bool":
        return ("bool", bool(x) if ty != "float" else (x != 0.0))
    if to == "float":
        return ("float", float(int(x)) if ty != "float" else x)
    if ty == "float":
        if math.isnan(x) or math.isinf(x) or not (-(2.0 ** 63) <= x < 2.0 ** 63):
            iv = INT_MIN
        else:
            iv = int(x)  # truncation toward zero
    else:
        iv = int(x)
    if to == "int":
        return ("int", iv)
    if to == "char":
        return ("char", wrap8(iv))
    raise AssertionError(to)


def promote(v):
    """Integral promotion: bool/char -> int."""
    if v[0] in ("bool", "char"):
        return ("int", int(v[1]))
    return v


def usual(a, b):
    a, b = promote(a), promote(b)
    if a[0] == "float" or b[0] == "float":
        return conv(a, "float"), conv(b, "float")
    return a, b


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _strtod_token(tok) -> float:
    """C strtod over one whole token (Q-013): decimal, hex floats, inf/infinity, nan(...)."""
    t = tok.decode("latin-1") if isinstance(tok, (bytes, bytearray)) else tok
    if "_" in t or t[:1].isspace():
        raise ValueError(t)
    body = t.lstrip("+-")
    neg = t.startswith("-")
    if body[:2].lower() == "0x":
        m = body[2:]
        if not m or m.lower().count("p") > 1:
            raise ValueError(t)
        if "p" not in m.lower():
            m += "p0"
        v = float.fromhex("0x" + m)
        return -v if neg else v
    if body.lower().startswith("nan(") and body.endswith(")"):
        return float("-nan" if neg else "nan")
    return float(t)


def fmt_g(x: float) -> str:
    return "%g" % x


# --------------------------------------------------------------------------- literal decoding
_ESC = {"n": 10, "t": 9, "r": 13, "b": 8, "f": 12, "0": 0, "\\": 92, "'": 39, '"': 34}


def _unescape(body: str) -> list[int]:
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            n = body[i + 1]
            if n == "x":
                out.append(int(body[i + 2:i + 4], 16))
                i += 4
            else:
                out.append(_ESC[n])
                i += 2
        else:
            out.append(ord(c))
            i += 1
    return out


def literal_value(node):
    kind, lex = node["kind"], node["lexeme"]
    if kind == "INTEGER":
        if lex.lower().startswith("0x"):
            return ("int", wrap(int(lex, 16)))
        if len(lex) > 1 and lex[0] == "0":
            return ("int", wrap(int(lex, 8)))
        return ("int", wrap(int(lex)))
    if kind == "FLOAT":
        return ("float", float(lex))
    if kind == "BOOL":
        return ("bool", lex.lower() == "nijam")
    if kind == "CHAR":
        return ("char", wrap8(_unescape(lex[1:-1])[0]))
    if kind == "STRING":
        return ("padham", "".join(chr(b) for b in _unescape(lex[1:-1])))
    raise AssertionError(kind)


_PRIM = {"INT": "int", "FLOAT": "float", "BOOL": "bool", "CHAR": "char", "PADHAM": "padham", "VOID": "void"}


# --------------------------------------------------------------------------- the interpreter
class Interp:
    def __init__(self, stdin: bytes, max_steps: int | None, strict_tokens: bool = True):
        # strict_tokens=True: a numeric read consumes a whole whitespace-delimited token (any trailing junk is an
        # error); False: C++ `cin >>` prefix semantics. ruled strict by the design authority (plan §M, Q-010); default True.
        self.strict_tokens = strict_tokens
        self.inp = stdin
        self.pos = 0
        self.last_token = False
        self.out = bytearray()
        self.globals: dict = {}
        self.funcs: dict = {}
        self.stack: list[dict] = []
        self.steps = 0
        self.max_steps = max_steps

    # -- housekeeping
    def tick(self):
        self.steps += 1
        if self.max_steps is not None and self.steps > self.max_steps:
            raise StepLimit()

    def lookup(self, name):
        for sc in reversed(self.stack):
            if name in sc:
                return sc[name]
        return self.globals[name]

    def declare(self, name, cell):
        (self.stack[-1] if self.stack else self.globals)[name] = cell

    # -- input (P7-P10)
    def _skip_ws(self):
        while self.pos < len(self.inp) and self.inp[self.pos] in b" \t\r\n\v\f":
            self.pos += 1

    def _token(self):
        self._skip_ws()
        start = self.pos
        while self.pos < len(self.inp) and self.inp[self.pos] not in b" \t\r\n\v\f":
            self.pos += 1
        if start == self.pos:
            raise RuntimeErr("invalid input")
        return self.inp[start:self.pos].decode("latin-1")

    def read(self, ty):
        if ty == "padham":
            if self.last_token:
                p = self.pos
                while p < len(self.inp) and self.inp[p] in b" \t\r\v\f":
                    p += 1
                if p < len(self.inp) and self.inp[p] == 10:
                    self.pos = p + 1
                elif p >= len(self.inp):
                    self.pos = p
            self.last_token = False
            if self.pos >= len(self.inp):
                raise RuntimeErr("invalid input")
            end = self.inp.find(b"\n", self.pos)
            if end < 0:
                s, self.pos = self.inp[self.pos:], len(self.inp)
            else:
                s, self.pos = self.inp[self.pos:end], end + 1
                if s.endswith(b"\r"):          # CRLF line ending: strip the CR before the LF
                    s = s[:-1]
            return ("padham", s.decode("latin-1"))
        self.last_token = True
        if ty == "char":
            self._skip_ws()
            if self.pos >= len(self.inp):
                raise RuntimeErr("invalid input")
            c = self.inp[self.pos]
            self.pos += 1
            return ("char", wrap8(c))
        if ty == "int":
            self._skip_ws()
            p = self.pos
            q = p
            if q < len(self.inp) and self.inp[q] in b"+-":
                q += 1
            d = q
            while q < len(self.inp) and 48 <= self.inp[q] <= 57:
                q += 1
            if q == d:
                self.pos = max(self.pos, p)
                raise RuntimeErr("invalid input")
            v = int(self.inp[p:q])
            self.pos = q
            if self.strict_tokens and q < len(self.inp) and self.inp[q] not in b" \t\r\n\v\f":
                raise RuntimeErr("invalid input")
            if not INT_MIN <= v <= INT_MAX:
                raise RuntimeErr("invalid input")
            return ("int", v)
        tok = self._token()
        if ty == "float":
            try:
                return ("float", _strtod_token(tok))
            except ValueError:
                raise RuntimeErr("invalid input")
        if ty == "bool":
            t = tok.lower()
            if t in ("nijam", "1"):
                return ("bool", True)
            if t in ("abaddham", "0"):
                return ("bool", False)
            raise RuntimeErr("invalid input")
        raise AssertionError(ty)

    # -- output (P1-P6)
    def emit(self, v):
        ty, x = v
        if ty == "int":
            s = str(x).encode()
        elif ty == "float":
            s = fmt_g(x).encode()
        elif ty == "bool":
            s = b"nijam" if x else b"abaddham"
        elif ty == "char":
            s = bytes([x & 0xFF])
        else:
            s = x.encode("latin-1")
        self.out += s + b"\n"

    # -- program
    def run_program(self, prog):
        items = prog["items"]
        for it in items:
            if it["_node"] == "FunctionDeclaration":
                self.funcs[it["name"]["name"]] = it
        # globals with constant dimensions exist from program start (P22)
        for it in items:
            if it["_node"] == "Declaration":
                self.predeclare_global(it)
        for it in items:
            n = it["_node"]
            if n == "FunctionDeclaration":
                continue
            if n == "Declaration":
                self.exec_decl(it, top=True)
            else:
                self.exec_stmt(it)

    def const_dims(self, ty):
        """Return list of ints if every dimension is a constant expression, else None."""
        res = []
        for d in ty["array_dimensions"]:
            try:
                v = self.const_eval(d)
            except (KeyError, ZeroDivisionError, RuntimeErr, AssertionError):
                return None
            res.append(int(promote(v)[1]))
        return res

    def const_eval(self, e):
        n = e["_node"]
        if n == "Literal":
            return literal_value(e)
        if n == "UnaryExpression":
            return self.unary(e["operator"], self.const_eval(e["operand"]))
        if n == "BinaryExpression":
            if e["operator"] in ("AND", "OR"):
                raise KeyError()
            return self.binary(e["operator"], self.const_eval(e["left"]), self.const_eval(e["right"]))
        if n == "CastExpression":
            return conv(self.const_eval(e["expression"]), _PRIM[e["target_type"]["primitive"]], True)
        raise KeyError(n)

    def predeclare_global(self, d):
        ty = d["type"]
        if ty["array_dimensions"]:
            dims = self.const_dims(ty)
            if dims is not None:
                self.globals[d["name"]["name"]] = self.new_array(_PRIM[ty["primitive"]], dims)
        else:
            prim = _PRIM[ty["primitive"]]
            self.globals[d["name"]["name"]] = [prim, ZERO[prim]]

    def new_array(self, elem, dims):
        if any(x < 1 for x in dims):
            raise RuntimeErr("invalid array size")
        total = 1
        for x in dims:
            total *= x
        return Arr(elem, dims, [ZERO[elem]] * total)

    def exec_decl(self, d, top=False):
        name = d["name"]["name"]
        ty = d["type"]
        prim = _PRIM[ty["primitive"]]
        if ty["array_dimensions"]:
            if top and name in self.globals and not self.stack:
                return  # already allocated at program start
            dims = []
            for e in ty["array_dimensions"]:
                dims.append(int(conv(self.eval(e), "int")[1]))
            self.declare(name, self.new_array(prim, dims))
        else:
            if top and not self.stack and name in self.globals:
                return
            self.declare(name, [prim, ZERO[prim]])

    # -- statements
    def exec_block(self, block):
        self.stack.append({})
        try:
            for s in block["statements"]:
                self.exec_stmt(s)
        finally:
            self.stack.pop()

    def exec_stmt(self, s):
        self.tick()
        n = s["_node"]
        m = getattr(self, "s_" + n)
        m(s)

    def s_Block(self, s):
        self.exec_block(s)

    def s_Declaration(self, s):
        self.exec_decl(s)

    def target(self, t):
        """Evaluate a target to (setter, type, getter); indices evaluated now (P40)."""
        if t["_node"] == "Identifier":
            cell = self.lookup(t["name"])
            return cell, None
        cell = self.lookup(t["base"]["name"])
        idx = [int(conv(self.eval(i), "int")[1]) for i in t["indices"]]
        return cell, idx

    def elem_loc(self, arr: Arr, idx):
        off = arr.offset
        for k, i in enumerate(idx):
            off += i * arr.stride(k)
        return off

    def store(self, loc, v):
        cell, idx = loc
        if idx is None:
            cell[1] = conv(v, cell[0])[1]
        else:
            off = self.elem_loc(cell, idx)
            cell.data[off] = conv(v, cell.elem)[1]

    def load(self, loc):
        cell, idx = loc
        if idx is None:
            return (cell[0], cell[1])
        off = self.elem_loc(cell, idx)
        return (cell.elem, cell.data[off])

    def s_Assignment(self, s):
        loc = self.target(s["target"])
        v = self.eval(s["value"])
        self.store(loc, v)

    def s_Input(self, s):
        loc = self.target(s["target"])
        cell, idx = loc
        ty = cell[0] if idx is None else cell.elem
        self.store(loc, self.read(ty))

    def s_Output(self, s):
        self.emit(self.eval(s["value"]))

    def cond(self, e):
        v = self.eval(e)
        return conv(v, "bool")[1]

    def s_IfStatement(self, s):
        if self.cond(s["condition"]):
            self.exec_block(s["then_block"])
        elif s["else_branch"] is not None:
            eb = s["else_branch"]
            if eb["_node"] == "Block":
                self.exec_block(eb)
            else:
                self.exec_stmt(eb)

    def s_WhileLoop(self, s):
        while self.cond(s["condition"]):
            self.tick()
            try:
                self.exec_block(s["body"])
            except _Break:
                break
            except _Continue:
                continue

    def s_RangeLoop(self, s):
        start = conv(self.eval(s["start"]), "int")[1]
        end = conv(self.eval(s["end"]), "int")[1]
        self.stack.append({s["variable"]["name"]: ["int", start]})
        try:
            cell = self.stack[-1][s["variable"]["name"]]
            while cell[1] < end:
                self.tick()
                try:
                    self.exec_block(s["body"])
                except _Break:
                    break
                except _Continue:
                    pass
                cell[1] = wrap(cell[1] + 1)
        finally:
            self.stack.pop()

    def s_ForLoop(self, s):
        self.stack.append({})
        try:
            init = s["init"]
            k = init["_node"]
            if k == "ForDeclarationInit":
                prim = _PRIM[init["type"]["primitive"]]
                cell = [prim, ZERO[prim]]
                self.stack[-1][init["name"]["name"]] = cell
                if init["initializer"] is not None:
                    cell[1] = conv(self.eval(init["initializer"]), prim)[1]
            else:
                loc = self.target(init["target"])
                self.store(loc, self.eval(init["value"]))
            while self.cond(s["condition"]):
                self.tick()
                try:
                    self.exec_block(s["body"])
                except _Break:
                    break
                except _Continue:
                    pass
                self.update(s["update"])
        finally:
            self.stack.pop()

    def update(self, u):
        k = u["_node"]
        loc = self.target(u["target"])
        if k == "AssignmentUpdate":
            self.store(loc, self.eval(u["value"]))
            return
        cur = self.load(loc)
        delta = 1 if k == "IncrementUpdate" else -1
        if cur[0] == "float":
            new = ("float", cur[1] + delta)
        else:
            new = (cur[0], cur[1] + delta)
            new = conv(("int", wrap(cur[1] + delta)), cur[0])
        self.store(loc, new)

    def s_BreakStatement(self, s):
        raise _Break()

    def s_ContinueStatement(self, s):
        raise _Continue()

    def s_ReturnStatement(self, s):
        raise _Return(self.eval(s["value"]))

    def s_ExpressionStatement(self, s):
        self.eval(s["expression"])

    # -- expressions
    def eval(self, e):
        self.tick()
        return getattr(self, "e_" + e["_node"])(e)

    def e_Literal(self, e):
        return literal_value(e)

    def e_Identifier(self, e):
        cell = self.lookup(e["name"])
        if isinstance(cell, Arr):
            return ("array", cell)
        return (cell[0], cell[1])

    def e_ArrayAccess(self, e):
        cell = self.lookup(e["base"]["name"])
        idx = [int(conv(self.eval(i), "int")[1]) for i in e["indices"]]
        if isinstance(cell, list):  # padham indexing -> char rvalue, bounds checked
            assert cell[0] == "padham" and len(idx) == 1
            if not 0 <= idx[0] < len(cell[1]):
                raise RuntimeErr("string index out of range")
            return ("char", wrap8(ord(cell[1][idx[0]])))
        if len(idx) < len(cell.dims):
            off = self.elem_loc(cell, idx)
            return ("array", Arr(cell.elem, cell.dims[len(idx):], cell.data, off))
        off = self.elem_loc(cell, idx)
        return (cell.elem, cell.data[off])

    def e_FunctionCall(self, e):
        name = e["callee"]["name"]
        args = [self.eval(a) for a in e["arguments"]]
        # a local variable cannot be called; shadowing of podavu by a *user function* is rejected by sema
        if name == "podavu" and "podavu" not in self.funcs:
            return ("int", len(args[0][1]))
        f = self.funcs[name]
        saved = self.stack
        frame = {}
        for p, a in zip(f["parameters"], args):
            pt = p["type"]
            prim = _PRIM[pt["primitive"]]
            if pt["array_dimensions"]:
                frame[p["name"]["name"]] = a[1]
            else:
                frame[p["name"]["name"]] = [prim, conv(a, prim)[1]]
        self.stack = [frame]
        try:
            for s in f["body"]["statements"]:
                self.exec_stmt(s)
            ret = None
        except _Return as r:
            rt = _PRIM[f["return_type"]["primitive"]]
            ret = conv(r.value, rt)
        finally:
            self.stack = saved
        return ret

    def e_CastExpression(self, e):
        return conv(self.eval(e["expression"]), _PRIM[e["target_type"]["primitive"]], True)

    def e_UnaryExpression(self, e):
        return self.unary(e["operator"], self.eval(e["operand"]))

    def unary(self, op, v):
        if op == "NOT":
            return ("bool", not conv(v, "bool")[1])
        v = promote(v)
        if op == "POSITIVE":
            return v
        if v[0] == "float":
            return ("float", -v[1])
        return ("int", wrap(-v[1]))

    def e_BinaryExpression(self, e):
        op = e["operator"]
        if op == "AND":
            if not conv(self.eval(e["left"]), "bool")[1]:
                return ("bool", False)
            return ("bool", conv(self.eval(e["right"]), "bool")[1])
        if op == "OR":
            if conv(self.eval(e["left"]), "bool")[1]:
                return ("bool", True)
            return ("bool", conv(self.eval(e["right"]), "bool")[1])
        a = self.eval(e["left"])
        b = self.eval(e["right"])
        return self.binary(op, a, b)

    def binary(self, op, a, b):
        if a[0] == "padham":
            if op == "ADD":
                return ("padham", a[1] + b[1])
            if op == "EQ":
                return ("bool", a[1] == b[1])
            if op == "NE":
                return ("bool", a[1] != b[1])
            raise AssertionError("bad padham op " + op)
        a, b = usual(a, b)
        t = a[0]
        x, y = a[1], b[1]
        if op in ("LT", "GT", "LE", "GE", "EQ", "NE"):
            r = {"LT": x < y, "GT": x > y, "LE": x <= y, "GE": x >= y, "EQ": x == y, "NE": x != y}[op]
            return ("bool", r)
        if t == "float":
            if op == "ADD":
                return ("float", x + y)
            if op == "SUB":
                return ("float", x - y)
            if op == "MUL":
                return ("float", x * y)
            if op == "DIV":
                if y == 0.0:
                    if x == 0.0 or math.isnan(x):
                        return ("float", math.nan)
                    neg = (math.copysign(1.0, x) < 0) != (math.copysign(1.0, y) < 0)
                    return ("float", -math.inf if neg else math.inf)
                return ("float", x / y)
            raise AssertionError("bad float op " + op)
        if op == "ADD":
            return ("int", wrap(x + y))
        if op == "SUB":
            return ("int", wrap(x - y))
        if op == "MUL":
            return ("int", wrap(x * y))
        if op == "DIV":
            if y == 0:
                raise RuntimeErr("division by zero")
            if x == INT_MIN and y == -1:
                raise RuntimeErr("integer overflow in division")
            return ("int", tdiv(x, y))
        if op == "MOD":
            if y == 0:
                raise RuntimeErr("remainder by zero")
            if y == -1:
                return ("int", 0)
            return ("int", x - tdiv(x, y) * y)
        raise AssertionError(op)


# --------------------------------------------------------------------------- public API
def run_ast(ast_data, stdin: bytes = b"", max_steps: int | None = 5_000_000, strict_tokens: bool = True) -> Result:
    """Interpret ``ast_data`` (the ``data`` member of ``parse --json``).

    Runs in a thread with a large stack so that deep Devara recursion (>10^4 frames) works."""
    import threading

    box: list = []

    def target():
        it = Interp(stdin, max_steps, strict_tokens)
        try:
            it.run_program(ast_data)
            box.append(Result(bytes(it.out), 0, ""))
        except RuntimeErr as e:
            box.append(Result(bytes(it.out), 1, str(e)))
        except BaseException as e:  # StepLimit, RecursionError, ... propagate to the caller
            box.append(e)

    old_rec = sys.getrecursionlimit()
    old_stack = threading.stack_size()
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(1 << 29)
    try:
        t = threading.Thread(target=target)
        t.start()
        t.join()
    finally:
        sys.setrecursionlimit(old_rec)
        threading.stack_size(old_stack)
    if isinstance(box[0], BaseException):
        raise box[0]
    return box[0]


def parse_to_ast(path: str | Path):
    p = subprocess.run([str(ROOT / "devara"), "parse", "--json", str(path)], capture_output=True)
    if p.returncode != 0:
        raise ValueError("parse failed: " + p.stderr.decode(errors="replace"))
    return json.loads(p.stdout)["data"]


def run_file(path, stdin: bytes = b"", max_steps: int | None = 5_000_000) -> Result:
    return run_ast(parse_to_ast(path), stdin, max_steps)


if __name__ == "__main__":
    r = run_file(sys.argv[1], sys.stdin.buffer.read())
    sys.stdout.buffer.write(r.stdout)
    if r.status:
        sys.stderr.write("devara: runtime error: %s\n" % r.error)
    sys.exit(r.status)
