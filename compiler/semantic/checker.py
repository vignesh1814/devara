"""Semantic analysis: scopes, symbols, type checking, conversions (P19–P40).

Produces a :class:`TypedProgram` or a list of semantic diagnostics. Definite
initialization and return-path analysis live in :mod:`compiler.semantic.flow`.
"""

from __future__ import annotations

from compiler import arith
from compiler.ast import nodes as A
from compiler.diagnostics import Diagnostic, SemCategory as S, Span
from compiler.semantic import typed as T
from compiler.semantic.types import (
    ARITHMETIC, BOOL, CHAR, ERROR, FLOAT, INT, INTEGRAL, PADHAM, VOID,
    ArrayType, FuncType, PrimType, is_arithmetic, is_integral, promote, prim,
)

_ESCAPES = {
    "n": 10, "t": 9, "r": 13, "b": 8, "f": 12, "0": 0, "\\": 92, "'": 39, '"': 34,
}

_PRIM_OF = {
    A.PrimitiveType.INT: INT, A.PrimitiveType.FLOAT: FLOAT, A.PrimitiveType.BOOL: BOOL,
    A.PrimitiveType.CHAR: CHAR, A.PrimitiveType.PADHAM: PADHAM, A.PrimitiveType.VOID: VOID,
}

PODAVU = "podavu"


class Scope:
    def __init__(self, parent: "Scope | None", depth: int) -> None:
        self.parent = parent
        self.depth = depth
        self.names: dict[str, T.Symbol] = {}

    def lookup(self, name: str) -> T.Symbol | None:
        s: Scope | None = self
        while s is not None:
            if name in s.names:
                return s.names[name]
            s = s.parent
        return None


def decode_escapes(body: str, span: Span) -> bytes:
    """Decode the interior of a char/string literal into bytes (lexer already validated)."""
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            e = body[i + 1]
            if e == "x":
                out.append(int(body[i + 2:i + 4], 16))
                i += 4
            else:
                out.append(_ESCAPES[e])
                i += 2
        else:
            try:
                out += c.encode("latin-1")
            except UnicodeEncodeError:
                out += c.encode("utf-8")
            i += 1
    return bytes(out)


def parse_int_lexeme(lx: str) -> int:
    if lx[:2] in ("0x", "0X"):
        return int(lx[2:], 16)
    if len(lx) > 1 and lx[0] == "0":
        return int(lx[1:], 8)
    return int(lx)


class Checker:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.diags: list[Diagnostic] = []
        self.symbols: list[T.Symbol] = []
        self.global_scope = Scope(None, 0)
        self.scope = self.global_scope
        self.owner = ""
        self.ret_type: PrimType | None = None   # None at top level
        self.loops: list[int] = []
        self.next_loop = 0
        self.globals: list[int] = []
        self.functions: list[T.TFunction] = []
        self.func_syms: dict[str, T.Symbol] = {}

    # ── diagnostics / symbols ──

    def err(self, cat: S, msg: str, span: Span) -> None:
        self.diags.append(Diagnostic("semantic", cat, msg, span, self.filename))

    def new_symbol(self, name, kind, typ, span, *, is_global=False) -> T.Symbol:
        sym = T.Symbol(
            id=len(self.symbols), name=name, kind=kind, type=typ,
            scope_depth=self.scope.depth, is_global=is_global,
            owner="" if is_global or kind in ("function", "builtin") else self.owner,
            span=span,
        )
        self.symbols.append(sym)
        return sym

    def declare(self, name: str, kind: str, typ, span: Span, *, is_global=False) -> T.Symbol | None:
        prev = self.scope.names.get(name)
        if prev is not None:
            self.err(S.REDECLARATION, f"'{name}' is already declared in this scope", span)
            return None
        sym = self.new_symbol(name, kind, typ, span, is_global=is_global)
        self.scope.names[name] = sym
        return sym

    def push(self) -> None:
        self.scope = Scope(self.scope, self.scope.depth + 1)

    def pop(self) -> None:
        assert self.scope.parent is not None
        self.scope = self.scope.parent

    # ── program ──

    def run(self, program: A.Program) -> T.TypedProgram:
        # builtin `podavu` is installed before user declarations (L48)
        b = self.new_symbol(PODAVU, "builtin", FuncType((PADHAM,), INT), None, is_global=False)
        self.global_scope.names[PODAVU] = b

        # collect function signatures first (L22)
        sigs: dict[int, T.Symbol] = {}
        for it in program.items:
            if isinstance(it, A.FunctionDeclaration):
                sym = self.collect_function(it)
                if sym is not None:
                    sigs[id(it)] = sym

        entry: list[T.TStmt] = []
        self.owner = T.ENTRY_OWNER
        for it in program.items:
            if isinstance(it, A.FunctionDeclaration):
                sym = sigs.get(id(it))
                if sym is not None:
                    self.check_function(it, sym)
                continue
            self.owner = T.ENTRY_OWNER
            self.ret_type = None
            st = self.check_statement(it, top_level=True)
            if st is not None:
                entry.append(st)

        self.diags.sort(key=lambda d: (d.line, d.column, str(d.category)))
        return T.TypedProgram(
            span=program.span, symbols=self.symbols, globals=self.globals,
            functions=self.functions, entry=T.TBlock(span=program.span, stmts=entry),
        )

    # ── functions ──

    def collect_function(self, fn: A.FunctionDeclaration) -> T.Symbol | None:
        params: list = []
        for p in fn.parameters:
            pt = self.param_type(p)
            params.append(pt)
        ret = _PRIM_OF[fn.return_type.primitive]
        ftype = FuncType(tuple(params), ret)
        name = fn.name.name
        prev = self.global_scope.names.get(name)
        if prev is not None:
            # report at the later declaration in source order
            self.err(S.REDECLARATION, f"'{name}' is already declared in this scope", fn.name.span)
            return None
        sym = self.new_symbol(name, "function", ftype, fn.name.span, is_global=False)
        self.global_scope.names[name] = sym
        self.func_syms[name] = sym
        return sym

    def param_type(self, p: A.Parameter):
        base = _PRIM_OF[p.type.primitive]
        if base == VOID:
            self.err(S.VOID_MISUSE, "parameter cannot have type 'void'", p.type.span)
            return ERROR
        if p.type.array_dimensions:
            return ArrayType(base, len(p.type.array_dimensions))
        return base

    def check_function(self, fn: A.FunctionDeclaration, sym: T.Symbol) -> None:
        ftype: FuncType = sym.type  # type: ignore[assignment]
        self.owner = fn.name.name
        self.ret_type = ftype.ret
        self.loops = []
        errs_before = len(self.diags)
        self.push()  # parameters + outermost block share one scope (P33)
        pids: list[int] = []
        for p, pt in zip(fn.parameters, ftype.params):
            ps = self.declare(p.name.name, "parameter", pt, p.name.span)
            if ps is not None:
                pids.append(ps.id)
        body = self.check_block_statements(fn.body)
        self.pop()
        tf = T.TFunction(span=fn.span, symbol=sym.id, name=fn.name.name,
                         params=pids, ret=ftype.ret, body=body)
        self.functions.append(tf)
        if len(self.diags) == errs_before:
            from compiler.semantic import flow
            for d in flow.analyze_function(tf, self.symbols, fn.name.span, self.filename):
                self.diags.append(d)
        self.owner = T.ENTRY_OWNER
        self.ret_type = None

    # ── statements ──

    def check_block_statements(self, block: A.Block) -> T.TBlock:
        stmts: list[T.TStmt] = []
        for st in block.statements:
            t = self.check_statement(st)
            if t is not None:
                stmts.append(t)
        return T.TBlock(span=block.span, stmts=stmts)

    def check_block(self, block: A.Block) -> T.TBlock:
        self.push()
        try:
            return self.check_block_statements(block)
        finally:
            self.pop()

    def check_statement(self, st: A.Statement, top_level: bool = False) -> T.TStmt | None:
        m = getattr(self, "st_" + type(st).__name__)
        return m(st, top_level) if type(st) is A.Declaration else m(st)

    def st_Declaration(self, d: A.Declaration, top_level: bool = False) -> T.TStmt | None:
        base = _PRIM_OF[d.type.primitive]
        dims: list[T.TExpr] = []
        bad = False
        if base == VOID:
            self.err(S.VOID_MISUSE, "variable cannot have type 'void'", d.type.span)
            bad = True
        consts: list[int | None] = []
        for de in d.type.array_dimensions:
            assert de is not None
            te = self.value(de)
            ce = self.convert_assign(te, INT, de.span, "array dimension")
            if ce.type == ERROR:
                bad = True
                continue
            dims.append(ce)
            consts.append(self.const_int(ce))
        if dims and consts and all(c is not None for c in consts) and len(dims) == len(d.type.array_dimensions):
            for c, de in zip(consts, d.type.array_dimensions):
                if c is not None and c < 1:
                    self.err(S.INVALID_ARRAY_SIZE, f"array dimension must be at least 1, got {c}", de.span)
                    bad = True
        typ = ArrayType(base, len(d.type.array_dimensions)) if d.type.array_dimensions else base
        if bad and base == VOID:
            typ = ERROR
        sym = self.declare(d.name.name, "variable", typ, d.name.span, is_global=top_level)
        if sym is None or bad:
            return None
        if top_level:
            self.globals.append(sym.id)
        return T.TDecl(span=d.span, symbol=sym.id, dims=dims)

    def st_Assignment(self, a: A.Assignment) -> T.TStmt | None:
        target = self.lvalue(a.target, "assignment")
        # P40: target address (indices) evaluated before the value
        value = self.value(a.value)
        if target is None or value.type == ERROR:
            return None
        v = self.convert_assign(value, target.type, a.value.span, "assignment")
        if v.type == ERROR:
            return None
        return T.TAssign(span=a.span, target=target, value=v)

    def st_Input(self, a: A.Input) -> T.TStmt | None:
        target = self.lvalue(a.target, "input")
        if target is None:
            return None
        return T.TInput(span=a.span, target=target)

    def st_Output(self, o: A.Output) -> T.TStmt | None:
        v = self.value(o.value)
        if v.type == ERROR:
            return None
        return T.TOutput(span=o.span, value=v)

    def st_IfStatement(self, s: A.IfStatement) -> T.TStmt | None:
        cond = self.condition(s.condition)
        then = self.check_block(s.then_block)
        els: T.TBlock | None = None
        if isinstance(s.else_branch, A.Block):
            els = self.check_block(s.else_branch)
        elif isinstance(s.else_branch, A.IfStatement):
            inner = self.st_IfStatement(s.else_branch)
            els = T.TBlock(span=s.else_branch.span, stmts=[inner] if inner else [])
        if cond is None:
            return None
        return T.TIf(span=s.span, condition=cond, then_block=then, else_block=els)

    def new_loop(self) -> int:
        self.next_loop += 1
        self.loops.append(self.next_loop)
        return self.next_loop

    def st_WhileLoop(self, s: A.WhileLoop) -> T.TStmt | None:
        cond = self.condition(s.condition)
        lid = self.new_loop()
        body = self.check_block(s.body)
        self.loops.pop()
        if cond is None:
            return None
        return T.TWhile(span=s.span, loop_id=lid, condition=cond, body=body)

    def st_RangeLoop(self, s: A.RangeLoop) -> T.TStmt | None:
        start = self.convert_assign(self.value(s.start), INT, s.start.span, "range start")
        end = self.convert_assign(self.value(s.end), INT, s.end.span, "range end")
        self.push()
        var = self.declare(s.variable.name, "variable", INT, s.variable.span)
        lid = self.new_loop()
        body = self.check_block(s.body)
        self.loops.pop()
        self.pop()
        if var is None or start.type == ERROR or end.type == ERROR:
            return None
        return T.TRange(span=s.span, loop_id=lid, variable=var.id, start=start, end=end, body=body)

    def st_ForLoop(self, s: A.ForLoop) -> T.TStmt | None:
        self.push()
        ok = True
        init: list[T.TStmt] = []
        init_node = s.init
        if isinstance(init_node, A.ForDeclarationInit):
            base = _PRIM_OF[init_node.type.primitive]
            val = None
            if init_node.initializer is not None:
                val = self.value(init_node.initializer)
            if base == VOID:
                self.err(S.VOID_MISUSE, "variable cannot have type 'void'", init_node.type.span)
                ok = False
            sym = self.declare(init_node.name.name, "variable", base, init_node.name.span)
            if sym is None or base == VOID:
                ok = False
            else:
                init.append(T.TDecl(span=init_node.span, symbol=sym.id, dims=[]))
                if val is not None:
                    cv = self.convert_assign(val, base, init_node.initializer.span, "initializer")
                    if cv.type == ERROR:
                        ok = False
                    else:
                        init.append(T.TAssign(
                            span=init_node.span,
                            target=T.TVar(span=init_node.name.span, type=base, symbol=sym.id),
                            value=cv))
        else:
            assert isinstance(init_node, (A.ForThoModhaluInit, A.ForAssignmentInit))
            target = self.lvalue(init_node.target, "loop initialization")
            val = self.value(init_node.value)
            if target is None or val.type == ERROR:
                ok = False
            else:
                cv = self.convert_assign(val, target.type, init_node.value.span, "assignment")
                if cv.type == ERROR:
                    ok = False
                else:
                    init.append(T.TAssign(span=init_node.span, target=target, value=cv))
        cond = self.condition(s.condition)
        if cond is None:
            ok = False
        lid = self.new_loop()
        upd = self.for_update(s.update)
        if upd is None:
            ok = False
        body = self.check_block(s.body)
        self.loops.pop()
        self.pop()
        if not ok:
            return None
        return T.TFor(span=s.span, loop_id=lid, init=init, condition=cond, update=upd, body=body)

    def for_update(self, u: A.ForUpdate) -> T.TStmt | None:
        if isinstance(u, A.AssignmentUpdate):
            target = self.lvalue(u.target, "assignment")
            val = self.value(u.value)
            if target is None or val.type == ERROR:
                return None
            cv = self.convert_assign(val, target.type, u.value.span, "assignment")
            if cv.type == ERROR:
                return None
            return T.TAssign(span=u.span, target=target, value=cv)
        assert isinstance(u, (A.IncrementUpdate, A.DecrementUpdate))
        target = self.lvalue(u.target, "increment/decrement")
        if target is None:
            return None
        if target.type not in (INT, CHAR, FLOAT):
            self.err(S.INVALID_OPERAND,
                     f"'++'/'--' require an int, char or float operand, got {target.type}", u.span)
            return None
        return T.TIncDec(span=u.span, target=target,
                         delta=1 if isinstance(u, A.IncrementUpdate) else -1, prefix=u.prefix)

    def st_BreakStatement(self, s: A.BreakStatement) -> T.TStmt | None:
        if not self.loops:
            self.err(S.BREAK_OUTSIDE_LOOP, "'aapu' outside of a loop", s.span)
            return None
        return T.TBreak(span=s.span, loop_id=self.loops[-1])

    def st_ContinueStatement(self, s: A.ContinueStatement) -> T.TStmt | None:
        if not self.loops:
            self.err(S.CONTINUE_OUTSIDE_LOOP, "'saagu' outside of a loop", s.span)
            return None
        return T.TContinue(span=s.span, loop_id=self.loops[-1])

    def st_ReturnStatement(self, s: A.ReturnStatement) -> T.TStmt | None:
        if self.ret_type is None:
            self.err(S.INVALID_RETURN, "'ivvu' outside of a function", s.span)
            self.value(s.value)
            return None
        if self.ret_type == VOID:
            self.err(S.INVALID_RETURN, "void function cannot return a value", s.span)
            self.value(s.value)
            return None
        v = self.value(s.value)
        if v.type == ERROR:
            return None
        cv = self.convert_assign(v, self.ret_type, s.value.span, "return")
        if cv.type == ERROR:
            return None
        return T.TReturn(span=s.span, value=cv)

    def st_ExpressionStatement(self, s: A.ExpressionStatement) -> T.TStmt | None:
        call = self.expr(s.expression)
        if isinstance(call, T.TCall):
            return T.TExprStmt(span=s.span, call=call)
        return None

    # ── lvalues ──

    def lvalue(self, node: A.Expression, what: str) -> T.TExpr | None:
        """Resolve an assignment/input/update target (Identifier | ArrayAccess)."""
        if isinstance(node, A.Identifier):
            sym = self.scope.lookup(node.name)
            if sym is None:
                self.err(S.UNDECLARED, f"undeclared identifier '{node.name}'", node.span)
                return None
            if sym.kind not in ("variable", "parameter"):
                self.err(S.NOT_ASSIGNABLE, f"'{node.name}' is a function, not assignable", node.span)
                return None
            if isinstance(sym.type, ArrayType):
                self.err(S.NOT_ASSIGNABLE, f"cannot use whole array '{node.name}' as {what} target", node.span)
                return None
            if sym.type == ERROR:
                return None
            return T.TVar(span=node.span, type=sym.type, symbol=sym.id)
        assert isinstance(node, A.ArrayAccess)
        r = self.array_access(node)
        if r is None:
            return None
        if isinstance(r, T.TStringIndex):
            self.err(S.NOT_ASSIGNABLE, "padham elements are not assignable", node.span)
            return None
        if isinstance(r.type, ArrayType):
            self.err(S.NOT_ASSIGNABLE, "cannot use a partially indexed array as a target", node.span)
            return None
        return r

    # ── expressions ──

    def err_expr(self, span: Span) -> T.TExpr:
        return T.TLiteral(span=span, type=ERROR, value=0)

    def expr(self, e: A.Expression) -> T.TExpr:
        """Check an expression; result may be void or array-typed."""
        m = getattr(self, "ex_" + type(e).__name__)
        return m(e)

    def value(self, e: A.Expression) -> T.TExpr:
        """Check an expression used as a scalar value (not void, not an array)."""
        r = self.expr(e)
        return self.require_scalar(r, e.span)

    def require_scalar(self, r: T.TExpr, span: Span) -> T.TExpr:
        if r.type == ERROR:
            return r
        if r.type == VOID:
            self.err(S.VOID_MISUSE, "void value used in an expression", span)
            return self.err_expr(span)
        if isinstance(r.type, ArrayType):
            self.err(S.INVALID_OPERAND, "array used where a scalar value is required", span)
            return self.err_expr(span)
        if isinstance(r.type, FuncType):
            self.err(S.INVALID_OPERAND, "function used as a value", span)
            return self.err_expr(span)
        return r

    def ex_Literal(self, e: A.Literal) -> T.TExpr:
        lx = e.lexeme
        k = e.kind
        if k == A.LiteralKind.INTEGER:
            v = parse_int_lexeme(lx)
            if v > arith.INT64_MAX:
                self.err(S.LITERAL_OUT_OF_RANGE, f"integer literal {lx} does not fit in a 64-bit int", e.span)
                return self.err_expr(e.span)
            return T.TLiteral(span=e.span, type=INT, value=v)
        if k == A.LiteralKind.FLOAT:
            return T.TLiteral(span=e.span, type=FLOAT, value=float(lx))
        if k == A.LiteralKind.BOOL:
            return T.TLiteral(span=e.span, type=BOOL, value=lx.lower() == "nijam")
        if k == A.LiteralKind.CHAR:
            b = decode_escapes(lx[1:-1], e.span)
            if len(b) != 1:
                self.err(S.LITERAL_OUT_OF_RANGE, "character literal does not fit in 8 bits", e.span)
                return self.err_expr(e.span)
            return T.TLiteral(span=e.span, type=CHAR, value=arith.wrap8(b[0]))
        return T.TLiteral(span=e.span, type=PADHAM, value=decode_escapes(lx[1:-1], e.span))

    def ex_Identifier(self, e: A.Identifier) -> T.TExpr:
        sym = self.scope.lookup(e.name)
        if sym is None:
            self.err(S.UNDECLARED, f"undeclared identifier '{e.name}'", e.span)
            return self.err_expr(e.span)
        if sym.type == ERROR:
            return self.err_expr(e.span)
        return T.TVar(span=e.span, type=sym.type, symbol=sym.id)

    def array_access(self, e: A.ArrayAccess) -> T.TExpr | None:
        name = e.base.name
        sym = self.scope.lookup(name)
        if sym is None:
            self.err(S.UNDECLARED, f"undeclared identifier '{name}'", e.base.span)
            for i in e.indices:
                self.expr(i)
            return None
        idx: list[T.TExpr] = []
        bad = False
        for i in e.indices:
            ti = self.value(i)
            ci = self.convert_assign(ti, INT, i.span, "array index")
            if ci.type == ERROR:
                bad = True
            idx.append(ci)
        if sym.type == ERROR:
            return None
        if sym.kind not in ("variable", "parameter"):
            self.err(S.NOT_INDEXABLE, f"'{name}' is a function and cannot be indexed", e.span)
            return None
        t = sym.type
        if t == PADHAM:
            if len(e.indices) > 1:
                self.err(S.TOO_MANY_INDICES, "a padham can be indexed only once", e.span)
                return None
            if bad:
                return None
            base = T.TVar(span=e.base.span, type=PADHAM, symbol=sym.id)
            return T.TStringIndex(span=e.span, type=CHAR, string=base, index=idx[0])
        if not isinstance(t, ArrayType):
            self.err(S.NOT_INDEXABLE, f"'{name}' of type {t} cannot be indexed", e.span)
            return None
        if len(e.indices) > t.rank:
            self.err(S.TOO_MANY_INDICES,
                     f"'{name}' has {t.rank} dimension(s) but {len(e.indices)} indices were given", e.span)
            return None
        if bad:
            return None
        rt = t.element if len(idx) == t.rank else ArrayType(t.element, t.rank - len(idx))
        return T.TIndex(span=e.span, type=rt, symbol=sym.id, indices=idx)

    def ex_ArrayAccess(self, e: A.ArrayAccess) -> T.TExpr:
        r = self.array_access(e)
        return r if r is not None else self.err_expr(e.span)

    def ex_FunctionCall(self, e: A.FunctionCall) -> T.TExpr:
        name = e.callee.name
        sym = self.scope.lookup(name)
        if sym is None:
            self.err(S.UNDECLARED, f"undeclared function '{name}'", e.callee.span)
            for a in e.arguments:
                self.expr(a)
            return self.err_expr(e.span)
        if sym.kind not in ("function", "builtin"):
            self.err(S.NOT_CALLABLE, f"'{name}' is not a function", e.callee.span)
            for a in e.arguments:
                self.expr(a)
            return self.err_expr(e.span)
        ft: FuncType = sym.type  # type: ignore[assignment]
        args = [self.expr(a) for a in e.arguments]
        if len(args) != len(ft.params):
            self.err(S.ARGUMENT_COUNT,
                     f"'{name}' expects {len(ft.params)} argument(s), got {len(args)}", e.span)
            return self.err_expr(e.span)
        out: list[T.TExpr] = []
        bad = False
        for a, node, pt in zip(args, e.arguments, ft.params):
            if a.type == ERROR or pt == ERROR:
                bad = True
                continue
            if isinstance(pt, ArrayType):
                if a.type != pt:
                    self.err(S.TYPE_MISMATCH,
                             f"argument of type {a.type} cannot be passed to array parameter of type {pt}",
                             node.span)
                    bad = True
                else:
                    out.append(a)
                continue
            a = self.require_scalar(a, node.span)
            ca = self.convert_assign(a, pt, node.span, "argument")
            if ca.type == ERROR:
                bad = True
            else:
                out.append(ca)
        if bad:
            return self.err_expr(e.span)
        return T.TCall(span=e.span, type=ft.ret, callee=sym.id, args=out)

    def ex_UnaryExpression(self, e: A.UnaryExpression) -> T.TExpr:
        o = self.value(e.operand)
        if o.type == ERROR:
            return o
        if o.type == PADHAM:
            self.err(S.INVALID_OPERAND, "operator cannot be applied to padham", e.span)
            return self.err_expr(e.span)
        if e.operator == A.UnaryOp.NOT:
            ob = self.to_type(o, BOOL, explicit=False)
            return T.TUnary(span=e.span, type=BOOL, op="NOT", operand=ob)
        pt = promote(o.type, o.type)  # bool/char/int -> int ; float -> float
        oc = self.to_type(o, pt, explicit=False)
        if e.operator == A.UnaryOp.POSITIVE:
            if oc is o:
                return oc
            oc.span = e.span
            return oc
        return T.TUnary(span=e.span, type=pt, op="NEG", operand=oc)

    def ex_CastExpression(self, e: A.CastExpression) -> T.TExpr:
        target = _PRIM_OF[e.target_type.primitive]
        o = self.value(e.expression)
        if target == VOID:
            self.err(S.VOID_MISUSE, "cannot cast to 'void'", e.target_type.span)
            return self.err_expr(e.span)
        if o.type == ERROR:
            return o
        if not self.can_convert(o.type, target, explicit=True):
            self.err(S.INVALID_CONVERSION, f"cannot convert {o.type} to {target}", e.span)
            return self.err_expr(e.span)
        r = self.to_type(o, target, explicit=True)
        if r is o:
            # same-type cast keeps an explicit node so the tree records the source cast
            return T.TConvert(span=e.span, type=target, operand=o, explicit=True)
        r.span = e.span
        return r

    def ex_BinaryExpression(self, e: A.BinaryExpression) -> T.TExpr:
        op = e.operator
        l = self.value(e.left)
        r = self.value(e.right)
        if l.type == ERROR or r.type == ERROR:
            return self.err_expr(e.span)
        lt, rt = l.type, r.type
        if op in (A.BinaryOp.AND, A.BinaryOp.OR):
            if PADHAM in (lt, rt):
                self.err(S.INVALID_OPERAND, "logical operators require arithmetic operands", e.span)
                return self.err_expr(e.span)
            return T.TBinary(span=e.span, type=BOOL, op=op,
                             left=self.to_type(l, BOOL, explicit=False),
                             right=self.to_type(r, BOOL, explicit=False))
        if lt == PADHAM or rt == PADHAM:
            if lt == PADHAM and rt == PADHAM and op in (A.BinaryOp.ADD, A.BinaryOp.EQ, A.BinaryOp.NE):
                return T.TBinary(span=e.span, type=PADHAM if op == A.BinaryOp.ADD else BOOL,
                                 op=op, left=l, right=r)
            self.err(S.INVALID_OPERAND, f"operator {op.value} cannot be applied to {lt} and {rt}", e.span)
            return self.err_expr(e.span)
        pt = promote(lt, rt)
        if op == A.BinaryOp.MOD and (not is_integral(lt) or not is_integral(rt)):
            self.err(S.INVALID_OPERAND, "'%' requires integral operands", e.span)
            return self.err_expr(e.span)
        lc = self.to_type(l, pt, explicit=False)
        rc = self.to_type(r, pt, explicit=False)
        if op in (A.BinaryOp.ADD, A.BinaryOp.SUB, A.BinaryOp.MUL, A.BinaryOp.DIV, A.BinaryOp.MOD):
            return T.TBinary(span=e.span, type=pt, op=op, left=lc, right=rc)
        return T.TBinary(span=e.span, type=BOOL, op=op, left=lc, right=rc)

    # ── conversions ──

    def can_convert(self, src, dst, *, explicit: bool) -> bool:
        if src == ERROR or dst == ERROR:
            return True
        if src in ARITHMETIC and dst in ARITHMETIC:
            return True
        if src == PADHAM and dst == PADHAM:
            return True
        if explicit and ((src == CHAR and dst == PADHAM) or (src == PADHAM and dst == CHAR)):
            return True
        return False

    def to_type(self, e: T.TExpr, dst: PrimType, *, explicit: bool) -> T.TExpr:
        """Wrap ``e`` in a conversion if its type differs (legality already checked)."""
        if e.type == dst:
            return e
        return T.TConvert(span=e.span, type=dst, operand=e, explicit=explicit)

    def convert_assign(self, e: T.TExpr, dst, span: Span, what: str) -> T.TExpr:
        """Implicit (assignment-style) conversion of a scalar value to ``dst``."""
        if e.type == ERROR or dst == ERROR:
            return self.err_expr(span)
        if not self.can_convert(e.type, dst, explicit=False):
            self.err(S.TYPE_MISMATCH, f"cannot convert {e.type} to {dst} in {what}", span)
            return self.err_expr(span)
        return self.to_type(e, dst, explicit=False)

    def condition(self, node: A.Expression) -> T.TExpr | None:
        r = self.expr(node)
        if r.type == ERROR:
            return None
        if r.type == VOID:
            self.err(S.VOID_MISUSE, "void value used as a condition", node.span)
            return None
        if isinstance(r.type, ArrayType):
            self.err(S.INVALID_OPERAND, "array used as a condition", node.span)
            return None
        if r.type not in ARITHMETIC:
            self.err(S.INVALID_CONDITION, f"condition must be arithmetic, got {r.type}", node.span)
            return None
        return self.to_type(r, BOOL, explicit=False)

    # ── constants (P21) ──

    def const_int(self, e: T.TExpr) -> int | None:
        v = const_eval(e)
        if v is None:
            return None
        return int(v)


def const_eval(e: T.TExpr):
    """Evaluate a typed constant expression, or None if not constant / traps."""
    if isinstance(e, T.TLiteral):
        if isinstance(e.value, bytes):
            return None
        return e.value
    if isinstance(e, T.TConvert):
        v = const_eval(e.operand)
        if v is None:
            return None
        return convert_const(v, e.operand.type, e.type)
    if isinstance(e, T.TUnary):
        v = const_eval(e.operand)
        if v is None:
            return None
        if e.op == "NOT":
            return not v
        return arith.wrap64(-v) if e.type == INT else -v
    if isinstance(e, T.TBinary):
        a = const_eval(e.left)
        b = const_eval(e.right)
        if a is None or b is None:
            return None
        return binary_const(e.op, e.left.type, a, b)
    return None


def convert_const(v, src: PrimType, dst: PrimType):
    if src == dst:
        return v
    if dst == BOOL:
        return v != 0
    if dst == FLOAT:
        return float(v)
    if dst == INT:
        if src == FLOAT:
            return arith.float_to_int(v)
        return int(v)
    if dst == CHAR:
        iv = arith.float_to_int(v) if src == FLOAT else int(v)
        return arith.wrap8(iv)
    return None


def binary_const(op: A.BinaryOp, operand_type: PrimType, a, b):
    B = A.BinaryOp
    if op in (B.AND, B.OR):
        return (bool(a) and bool(b)) if op == B.AND else (bool(a) or bool(b))
    if operand_type == FLOAT:
        a, b = float(a), float(b)
        if op == B.ADD: return a + b
        if op == B.SUB: return a - b
        if op == B.MUL: return a * b
        if op == B.DIV: return arith.fdiv(a, b)
    else:
        a, b = int(a), int(b)
        if op == B.ADD: return arith.wrap64(a + b)
        if op == B.SUB: return arith.wrap64(a - b)
        if op == B.MUL: return arith.wrap64(a * b)
        if op in (B.DIV, B.MOD):
            if b == 0 or (a == arith.INT64_MIN and b == -1 and op == B.DIV):
                return None
            return arith.idiv(a, b) if op == B.DIV else arith.irem(a, b)
    if op == B.LT: return a < b
    if op == B.GT: return a > b
    if op == B.LE: return a <= b
    if op == B.GE: return a >= b
    if op == B.EQ: return a == b
    if op == B.NE: return a != b
    return None
