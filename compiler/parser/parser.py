"""Recursive-descent parser for Devara (Stage 2 design + design §3.5–§3.7).

The parser follows the canonical grammar exactly (spec §11): it accepts no
bare ``{...}`` statements, no call/index chaining and no parenthesized
assignment/input/update targets. Syntax errors are recorded as structured
diagnostics (closed category set §3.6) and parsing continues through the
context-sensitive panic-mode recovery of §3.7. Any recorded error means parse
failure; the driver then discards the (partial) AST.
"""

from __future__ import annotations

from compiler.ast.nodes import (
    ArrayAccess, Assignment, AssignmentUpdate, BinaryExpression, BinaryOp, Block,
    BreakStatement, CastExpression, ContinueStatement, Declaration,
    DecrementUpdate, Expression, ExpressionStatement, ForAssignmentInit,
    ForDeclarationInit, ForInit, ForLoop, ForThoModhaluInit, ForUpdate,
    FunctionCall, FunctionDeclaration, Identifier, IfStatement, IncrementUpdate,
    Input, Literal, LiteralKind, Output, Parameter, PrimitiveType, Program,
    RangeLoop, ReturnStatement, Statement, TypeSyntax, UnaryExpression, UnaryOp,
    WhileLoop,
)
from compiler.diagnostics import Diagnostic, Span, SyntaxCategory
from compiler.lexer.tokens import Token, TokenType

T = TokenType
C = SyntaxCategory

_TYPE_MAP = {
    T.INT: PrimitiveType.INT,
    T.FLOAT: PrimitiveType.FLOAT,
    T.BOOL: PrimitiveType.BOOL,
    T.CHAR: PrimitiveType.CHAR,
    T.PADHAM: PrimitiveType.PADHAM,
    T.VOID: PrimitiveType.VOID,
}

# Frozen token sets (design §3.7.1).
FIRST_DECLARATION = frozenset(_TYPE_MAP)
FIRST_STATEMENT = frozenset({
    T.IDENTIFIER, T.INT_LITERAL, T.FLOAT_LITERAL, T.CHAR_LITERAL, T.STRING_LITERAL,
    T.NIJAM, T.ABADDHAM, T.LPAREN, T.NOT, T.PLUS, T.MINUS,
    T.AAPU, T.SAAGU, T.PRATI, T.PRATISARI, T.IVVU,
})
_SYNC_STATEMENT = FIRST_STATEMENT | FIRST_DECLARATION
_EXPR_START = frozenset({
    T.IDENTIFIER, T.INT_LITERAL, T.FLOAT_LITERAL, T.CHAR_LITERAL, T.STRING_LITERAL,
    T.NIJAM, T.ABADDHAM, T.LPAREN, T.NOT, T.PLUS, T.MINUS,
})
_HEADER_SYNC = frozenset({T.SEMICOLON, T.RPAREN, T.RBRACE})            # §3.7.2
_LIST_SYNC = frozenset({T.COMMA, T.RPAREN})                            # §3.7.3
_INDEX_SYNC = frozenset({T.RBRACKET, T.RPAREN, T.COMMA, T.RBRACE})     # §3.7.3

_OPEN = {T.LPAREN, T.LBRACKET, T.LBRACE}
_CLOSE = {T.RPAREN, T.RBRACKET, T.RBRACE}

_LITERAL_KINDS = {
    T.INT_LITERAL: LiteralKind.INTEGER,
    T.FLOAT_LITERAL: LiteralKind.FLOAT,
    T.CHAR_LITERAL: LiteralKind.CHAR,
    T.STRING_LITERAL: LiteralKind.STRING,
    T.NIJAM: LiteralKind.BOOL,
    T.ABADDHAM: LiteralKind.BOOL,
}

_EQUALITY = {T.EQEQ: BinaryOp.EQ, T.NEQ: BinaryOp.NE}
_RELATIONAL = {T.LT: BinaryOp.LT, T.GT: BinaryOp.GT, T.LTE: BinaryOp.LE, T.GTE: BinaryOp.GE}
_ADDITIVE = {T.PLUS: BinaryOp.ADD, T.MINUS: BinaryOp.SUB}
_MULTIPLICATIVE = {T.STAR: BinaryOp.MUL, T.SLASH: BinaryOp.DIV, T.PERCENT: BinaryOp.MOD}
_UNARY = {T.NOT: UnaryOp.NOT, T.PLUS: UnaryOp.POSITIVE, T.MINUS: UnaryOp.NEGATE}


MAX_NESTING = 20_000   # counted per grammar level (about 10 000 nested blocks/parentheses); implementation limit, see N-001


class ParseAbort(Exception):
    """Control-flow signal: a diagnostic was recorded; unwind to a recovery point."""


class Parser:
    """Hand-written recursive-descent parser producing the §3.5 AST."""

    def __init__(self, tokens: list[Token], filename: str = "<stdin>") -> None:
        toks = list(tokens)
        for i, t in enumerate(toks):
            if t.type == T.EOF:
                toks = toks[: i + 1]
                break
        else:
            if toks:
                last = toks[-1]
                toks.append(Token(T.EOF, "", last.line, last.column + len(last.lexeme)))
            else:
                toks.append(Token(T.EOF, "", 1, 1))
        self.tokens = toks
        self.filename = filename
        self.pos = 0
        self.errors: list[Diagnostic] = []
        self._header_depth = 0  # >0 while parsing a pratisari header
        self._depth = 0         # current syntactic nesting depth

    # ── Public API ──

    def parse(self) -> Program:
        """Parse the whole token stream (always returns a Program; see ``errors``)."""
        items = []
        while not self._at_end():
            start = self.pos
            item = self._recoverable(self.parse_top_level_item)
            if item is not None:
                items.append(item)
            elif self.pos == start and not self._at_end():
                self.pos += 1  # progress guard (§3.7.4)
        eof = self.tokens[-1]
        return Program(
            span=Span(1, 1, eof.line, eof.column),
            items=items,
        )

    def _enter(self) -> None:
        self._depth += 1
        if self._depth > MAX_NESTING:
            raise RecursionError("nesting too deep")   # reported by the driver as a syntax diagnostic

    # ── Token helpers ──

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, n: int) -> Token:
        i = self.pos + n
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def _at_end(self) -> bool:
        return self.cur.type == T.EOF

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != T.EOF:
            self.pos += 1
        return tok

    def _prev(self) -> Token:
        return self.tokens[self.pos - 1]

    def _span_from(self, start: Token) -> Span:
        end = self._prev()
        return Span(start.line, start.column, end.line, end.column + len(end.lexeme))

    @staticmethod
    def _tok_span(tok: Token) -> Span:
        return Span(tok.line, tok.column, tok.line, tok.column + len(tok.lexeme))

    # ── Diagnostics ──

    def _fail(
        self,
        category: SyntaxCategory,
        message: str,
        tok: Token | None = None,
        expected: list[T] | None = None,
    ) -> ParseAbort:
        tok = tok if tok is not None else self.cur
        if tok.type == T.EOF:
            category = C.UNEXPECTED_EOF
        span = Span(tok.line, tok.column, tok.line, tok.column + max(len(tok.lexeme), 1))
        exp = tuple(str(e) for e in expected) if expected else None
        self.errors.append(
            Diagnostic("syntax", category, message, span, self.filename, expected=exp)
        )
        return ParseAbort()

    def _expect(self, kind: T, message: str) -> Token:
        if self.cur.type == kind:
            return self._advance()
        raise self._fail(C.MISSING_TOKEN, message, expected=[kind])

    # ── Recovery (design §3.7) ──

    def _recoverable(self, fn):
        """Run a statement-level production; on failure record-and-synchronize."""
        try:
            return fn()
        except ParseAbort:
            self._sync_statement()
            return None

    def _skip_with_depth(self, stop_at: frozenset[T], *, statement: bool) -> None:
        """Consume tokens until a sync token at nesting depth 0 (or EOF).

        ``(``, ``[`` and ``{`` opened during the skip are matched, so tokens of
        nested constructs never act as the current construct's boundary.
        """
        paren = 0
        brace = 0
        while True:
            t = self.cur.type
            if t == T.EOF:
                return
            if t == T.RBRACE and brace == 0:
                return  # closes the enclosing block: never consumed by recovery
            if paren == 0 and brace == 0:
                if t in stop_at or (statement and t in _SYNC_STATEMENT):
                    return
            if t == T.LBRACE:
                brace += 1
            elif t == T.LPAREN or t == T.LBRACKET:
                paren += 1
            elif t == T.RBRACE:
                brace -= 1
            elif t == T.RPAREN or t == T.RBRACKET:
                if paren > 0:
                    paren -= 1
            self.pos += 1

    def _sync_statement(self) -> None:
        """§3.7.1: consume ≥1 token unless at a sync token; stop at RBRACE/EOF/FIRST sets."""
        t = self.cur.type
        if t == T.EOF or t == T.RBRACE or t in _SYNC_STATEMENT:
            return
        stop = frozenset({T.RBRACE})
        # consume the offending token (tracking nesting), then skip to a sync token
        first = self.cur.type
        self.pos += 1
        if first == T.LBRACE:
            self._skip_nested_after_open(T.LBRACE)
        elif first in (T.LPAREN, T.LBRACKET):
            self._skip_nested_after_open(first)
        self._skip_with_depth(stop, statement=True)

    def _skip_nested_after_open(self, opener: T) -> None:
        """Skip to just past the delimiter matching an already-consumed opener."""
        depth = 1
        while depth > 0 and self.cur.type != T.EOF:
            t = self.cur.type
            if t in _OPEN:
                depth += 1
            elif t in _CLOSE:
                depth -= 1
            self.pos += 1

    def _sync_header(self) -> None:
        """§3.7.2: delimiter-aware recovery inside a pratisari header."""
        self._skip_with_depth(_HEADER_SYNC, statement=False)

    def _sync_delimited(self, stops: frozenset[T]) -> None:
        """§3.7.3: delimiter-aware recovery in argument/parameter/index lists."""
        if self._header_depth > 0 and stops is _INDEX_SYNC:
            stops = stops | {T.SEMICOLON}
        self._skip_with_depth(stops, statement=False)

    # ── Top level ──

    def parse_top_level_item(self) -> FunctionDeclaration | Statement:
        if self.cur.type in FIRST_DECLARATION:
            if self._peek(1).type == T.IDENTIFIER and self._peek(2).type == T.CHARYA:
                return self.parse_function_declaration()
            return self.parse_declaration()
        return self.parse_statement()

    def parse_type(self) -> TypeSyntax:
        tok = self.cur
        if tok.type not in _TYPE_MAP:
            raise self._fail(C.INVALID_DECLARATION, "Expected type keyword.", expected=list(_TYPE_MAP))
        self._advance()
        return TypeSyntax(
            span=self._tok_span(tok), primitive=_TYPE_MAP[tok.type], array_dimensions=[]
        )

    def _identifier(self, tok: Token) -> Identifier:
        return Identifier(span=self._tok_span(tok), name=tok.lexeme)

    def parse_function_declaration(self) -> FunctionDeclaration:
        start = self.cur
        ret_type = self.parse_type()
        name = self._identifier(self._expect(T.IDENTIFIER, "Expected function name."))
        self._expect(T.CHARYA, "Expected 'charya' after function name.")
        self._expect(T.LPAREN, "Expected '(' after 'charya'.")
        parameters: list[Parameter] = []
        failed = False
        if self.cur.type != T.RPAREN:
            while True:
                try:
                    parameters.append(self._parse_parameter())
                except ParseAbort:
                    failed = True
                    self._sync_delimited(_LIST_SYNC)
                if self.cur.type == T.COMMA:
                    self._advance()
                    continue
                break
        if self.cur.type == T.RPAREN:
            self._advance()
        elif failed:
            raise ParseAbort()
        else:
            raise self._fail(C.MISSING_TOKEN, "Expected ')' after parameters.",
                             expected=[T.RPAREN, T.COMMA])
        if failed:
            # still parse the body so its own errors are reported
            if self.cur.type == T.LBRACE:
                try:
                    self.parse_block()
                except ParseAbort:
                    pass
            raise ParseAbort()
        body = self.parse_block()
        return FunctionDeclaration(
            span=self._span_from(start),
            return_type=ret_type, name=name, parameters=parameters, body=body,
        )

    def _parse_parameter(self) -> Parameter:
        start = self.cur
        if start.type not in _TYPE_MAP:
            raise self._fail(C.INVALID_DECLARATION, "Expected parameter type.",
                             expected=list(_TYPE_MAP))
        ptype = self.parse_type()
        name = self._identifier(self._expect(T.IDENTIFIER, "Expected parameter name."))
        if self.cur.type == T.LBRACKET:
            self._advance()
            self._expect(T.RBRACKET, "Expected ']' after '[' in array parameter.")
            ptype.array_dimensions = [None]
            ptype.span = self._span_from(start)
        return Parameter(span=self._span_from(start), type=ptype, name=name)

    # ── Statements ──

    def parse_statement(self) -> Statement:
        tok = self.cur
        t = tok.type
        if t in FIRST_DECLARATION:
            return self.parse_declaration()
        if t == T.PRATISARI:
            return self.parse_for_loop()
        if t == T.PRATI:
            return self.parse_range_loop()
        if t == T.AAPU:
            self._advance()
            return BreakStatement(span=self._tok_span(tok))
        if t == T.SAAGU:
            self._advance()
            return ContinueStatement(span=self._tok_span(tok))
        if t not in FIRST_STATEMENT:
            raise self._fail(C.UNEXPECTED_TOKEN, f"Unexpected {self._describe(tok)}; expected a statement.")
        return self.parse_expression_statement()

    @staticmethod
    def _describe(tok: Token) -> str:
        if tok.type == T.EOF:
            return "end of input"
        return f"'{tok.lexeme}'"

    def parse_declaration(self) -> Declaration:
        start = self.cur
        dtype = self.parse_type()
        name_tok = self.cur
        if name_tok.type != T.IDENTIFIER:
            raise self._fail(C.INVALID_DECLARATION, "Expected variable name after type.",
                             expected=[T.IDENTIFIER])
        self._advance()
        name = self._identifier(name_tok)
        dims: list[Expression | None] = []
        while self.cur.type == T.LBRACKET:
            self._advance()
            dims.append(self._parse_bracketed_expression("Expected ']' after array dimension."))
        if self.cur.type == T.CHARYA:
            raise self._fail(C.INVALID_DECLARATION,
                             "Function declarations are only allowed at top level.")
        if self.cur.type == T.LO:
            raise self._fail(C.INVALID_DECLARATION,
                             "Declarations cannot have an initializer; use a separate assignment.")
        if dims:
            dtype.array_dimensions = dims
            dtype.span = self._span_from(start)
        return Declaration(span=self._span_from(start), type=dtype, name=name)

    def parse_block(self) -> Block:
        self._enter()
        try:
            return self._parse_block()
        finally:
            self._depth -= 1

    def _parse_block(self) -> Block:
        lbrace = self._expect(T.LBRACE, "Expected '{'.")
        statements: list[Statement] = []
        while self.cur.type not in (T.RBRACE, T.EOF):
            start = self.pos
            stmt = self._recoverable(self.parse_statement)
            if stmt is not None:
                statements.append(stmt)
            elif self.pos == start and self.cur.type not in (T.RBRACE, T.EOF):
                self.pos += 1  # progress guard (§3.7.4)
        self._expect(T.RBRACE, "Expected '}' after block.")
        return Block(span=self._span_from(lbrace), statements=statements)

    def _as_target(self, expr: Expression, start_idx: int, what: str) -> Identifier | ArrayAccess:
        """An assignment/input target must be a bare identifier or array access."""
        start = self.tokens[start_idx]
        if isinstance(expr, (Identifier, ArrayAccess)) and start.type == T.IDENTIFIER:
            return expr
        raise self._fail(
            C.INVALID_STATEMENT,
            f"Expected identifier or array access as {what} target.",
            tok=start,
        )

    def parse_expression_statement(self) -> Statement:
        start = self.cur
        start_idx = self.pos
        expr = self.parse_expression()
        t = self.cur.type

        if t == T.LO:
            target = self._as_target(expr, start_idx, "assignment")
            self._advance()
            value = self.parse_expression()
            self._expect(T.PETTU, "Expected 'pettu' after assignment value.")
            return Assignment(span=self._span_from(start), target=target, value=value)

        if t == T.NI:
            self._advance()
            if self.cur.type == T.CHADUVU:
                target = self._as_target(expr, start_idx, "input")
                self._advance()
                return Input(span=self._span_from(start), target=target)
            if self.cur.type == T.CHUPI:
                self._advance()
                return Output(span=self._span_from(start), value=expr)
            raise self._fail(C.MISSING_TOKEN, "Expected 'chaduvu' or 'chupi' after 'ni'.",
                             expected=[T.CHADUVU, T.CHUPI])

        if t == T.AYITE:
            return self._finish_if(expr, start)

        if t == T.UNNANTA:
            self._advance()
            self._expect(T.VARAKU, "Expected 'varaku' after 'unnanta'.")
            body = self.parse_block()
            return WhileLoop(span=self._span_from(start), condition=expr, body=body)

        if t == T.IVVU:
            self._advance()
            return ReturnStatement(span=self._span_from(start), value=expr)

        if isinstance(expr, FunctionCall) and start.type == T.IDENTIFIER:
            return ExpressionStatement(span=self._span_from(start), expression=expr)

        raise self._fail(
            C.INVALID_STATEMENT, "Expected statement keyword after expression.",
            expected=[T.LO, T.NI, T.AYITE, T.UNNANTA, T.IVVU],
        )

    def _finish_if(self, condition: Expression, start: Token) -> IfStatement:
        self._enter()
        try:
            return self._finish_if_inner(condition, start)
        finally:
            self._depth -= 1

    def _finish_if_inner(self, condition: Expression, start: Token) -> IfStatement:
        self._expect(T.AYITE, "Expected 'ayite'.")
        then_block = self.parse_block()
        else_branch: Block | IfStatement | None = None
        if self.cur.type == T.LEKUNTE:
            self._advance()
            else_branch = self._parse_else_branch()
        return IfStatement(
            span=self._span_from(start),
            condition=condition, then_block=then_block, else_branch=else_branch,
        )

    def _parse_else_branch(self) -> Block | IfStatement:
        msg = "Expected '{' or if-statement after 'lekunte'."
        if self.cur.type == T.LBRACE:
            return self.parse_block()
        if self.cur.type in _EXPR_START:
            start = self.cur
            cond = self.parse_expression()
            if self.cur.type != T.AYITE:
                raise self._fail(C.INVALID_STATEMENT, msg, tok=start, expected=[T.LBRACE])
            return self._finish_if(cond, start)
        raise self._fail(C.UNEXPECTED_TOKEN, msg, expected=[T.LBRACE])

    def parse_range_loop(self) -> RangeLoop:
        start = self._advance()  # 'prati'
        var_tok = self.cur
        if var_tok.type != T.IDENTIFIER:
            raise self._fail(C.INVALID_STATEMENT, "Expected variable name after 'prati'.",
                             expected=[T.IDENTIFIER])
        self._advance()
        variable = self._identifier(var_tok)
        start_expr = self.parse_expression()
        self._expect(T.NUNDI, "Expected 'nundi' after start expression.")
        end_expr = self.parse_expression()
        self._expect(T.VARAKU, "Expected 'varaku' after end expression.")
        body = self.parse_block()
        return RangeLoop(span=self._span_from(start), variable=variable,
                         start=start_expr, end=end_expr, body=body)

    # ── pratisari ──

    def parse_for_loop(self) -> ForLoop:
        start = self._advance()  # 'pratisari'
        self._header_depth += 1
        try:
            return self._parse_for_loop_rest(start)
        finally:
            self._header_depth -= 1

    def _parse_for_loop_rest(self, start: Token) -> ForLoop:
        self._expect(T.LPAREN, "Expected '(' after 'pratisari'.")
        steps = [
            (self.parse_for_init, T.SEMICOLON, "Expected ';' after pratisari init."),
            (self._parse_for_condition, T.SEMICOLON, "Expected ';' after pratisari condition."),
            (self.parse_for_update, T.RPAREN, "Expected ')' after pratisari."),
        ]
        parts: list = []
        ok = True
        closed = False
        for fn, closer, msg in steps:
            if closed:
                break
            try:
                value = fn()
                self._expect(closer, msg)
                parts.append(value)
            except ParseAbort:
                ok = False
                self._sync_header()
                while self.cur.type == T.SEMICOLON and closer == T.RPAREN:
                    self._advance()
                    self._sync_header()
                t = self.cur.type
                if t == T.SEMICOLON:
                    self._advance()
                elif t == T.RPAREN:
                    self._advance()
                    closed = True
                else:  # RBRACE / EOF: leave for the enclosing recovery
                    raise ParseAbort()
        if not ok:
            if self.cur.type == T.LBRACE:  # report errors in the body too
                try:
                    self.parse_block()
                except ParseAbort:
                    pass
            raise ParseAbort()
        body = self.parse_block()
        init, cond, update = parts
        return ForLoop(span=self._span_from(start), init=init, condition=cond,
                       update=update, body=body)

    def parse_for_init(self) -> ForInit:
        start = self.cur
        t = start.type
        if t in FIRST_DECLARATION:
            ftype = self.parse_type()
            name_tok = self.cur
            if name_tok.type != T.IDENTIFIER:
                raise self._fail(C.INVALID_STATEMENT, "Expected loop variable in pratisari.",
                                 expected=[T.IDENTIFIER])
            self._advance()
            name = self._identifier(name_tok)
            initializer = None
            if self.cur.type == T.LO:
                self._advance()
                initializer = self.parse_expression()
                self._expect(T.PETTU, "Expected 'pettu' in pratisari init.")
            return ForDeclarationInit(span=self._span_from(start), type=ftype,
                                      name=name, initializer=initializer)
        if t == T.IDENTIFIER:
            self._advance()
            target = self._identifier(start)
            if self.cur.type == T.LO:
                self._advance()
                value = self.parse_expression()
                self._expect(T.PETTU, "Expected 'pettu' in pratisari init.")
                return ForAssignmentInit(span=self._span_from(start), target=target, value=value)
            value = self.parse_expression()
            self._expect(T.THO, "Expected 'tho' in pratisari init.")
            self._expect(T.MODHALU, "Expected 'modhalu' in pratisari init.")
            return ForThoModhaluInit(span=self._span_from(start), target=target, value=value)
        raise self._fail(C.INVALID_STATEMENT, "Expected loop initialization in pratisari.")

    def _parse_for_condition(self) -> Expression:
        if self.cur.type not in _EXPR_START:
            raise self._fail(C.INVALID_EXPRESSION, "Expected condition in pratisari.")
        cond = self.parse_expression()
        if self.cur.type == T.UNNANTA:
            raise self._fail(C.UNEXPECTED_TOKEN,
                             "'unnanta varaku' is not allowed in a pratisari loop condition.")
        return cond

    def parse_target(self) -> Identifier | ArrayAccess:
        """``identifier | array-access`` (no parentheses, no other expressions)."""
        tok = self.cur
        if tok.type != T.IDENTIFIER:
            raise self._fail(C.INVALID_STATEMENT,
                             "Expected identifier or array access as target.",
                             expected=[T.IDENTIFIER])
        self._advance()
        if self.cur.type == T.LBRACKET:
            return self._finish_array_access(tok)
        return self._identifier(tok)

    def parse_for_update(self) -> ForUpdate:
        start = self.cur
        t = start.type
        if t in (T.INCREMENT, T.DECREMENT):
            self._advance()
            target = self.parse_target()
            cls = IncrementUpdate if t == T.INCREMENT else DecrementUpdate
            return cls(span=self._span_from(start), target=target, prefix=True)
        if t == T.IDENTIFIER:
            target = self.parse_target()
            nt = self.cur.type
            if nt == T.LO:
                self._advance()
                value = self.parse_expression()
                self._expect(T.PETTU, "Expected 'pettu' in pratisari update.")
                return AssignmentUpdate(span=self._span_from(start), target=target, value=value)
            if nt in (T.INCREMENT, T.DECREMENT):
                self._advance()
                cls = IncrementUpdate if nt == T.INCREMENT else DecrementUpdate
                return cls(span=self._span_from(start), target=target, prefix=False)
            raise self._fail(C.INVALID_STATEMENT,
                             "Expected 'lo', '++' or '--' in pratisari update.",
                             expected=[T.LO, T.INCREMENT, T.DECREMENT])
        raise self._fail(C.INVALID_STATEMENT, "Expected update in pratisari.")

    # ── Expressions ──

    def parse_expression(self) -> Expression:
        self._enter()
        try:
            return self._binary(self._parse_and, {T.OR: BinaryOp.OR})
        finally:
            self._depth -= 1

    def _parse_and(self) -> Expression:
        return self._binary(self._parse_equality, {T.AND: BinaryOp.AND})

    def _parse_equality(self) -> Expression:
        return self._binary(self._parse_relational, _EQUALITY)

    def _parse_relational(self) -> Expression:
        return self._binary(self._parse_additive, _RELATIONAL)

    def _parse_additive(self) -> Expression:
        return self._binary(self._parse_multiplicative, _ADDITIVE)

    def _parse_multiplicative(self) -> Expression:
        return self._binary(self.parse_unary, _MULTIPLICATIVE)

    def _binary(self, sub, ops: dict) -> Expression:
        start = self.cur
        left = sub()
        while self.cur.type in ops:
            op = ops[self._advance().type]
            right = sub()
            left = BinaryExpression(
                span=self._span_from(start), operator=op, left=left, right=right
            )
        return left

    def parse_unary(self) -> Expression:
        self._enter()
        try:
            return self._parse_unary()
        finally:
            self._depth -= 1

    def _parse_unary(self) -> Expression:
        start = self.cur
        t = start.type
        if t == T.LPAREN and self._peek(1).type in FIRST_DECLARATION:
            self._advance()
            ctype = self.parse_type()
            self._expect(T.RPAREN, "Expected ')' after type in cast.")
            operand = self.parse_unary()
            return CastExpression(span=self._span_from(start), target_type=ctype,
                                  expression=operand)
        if t in _UNARY:
            self._advance()
            operand = self.parse_unary()
            return UnaryExpression(span=self._span_from(start), operator=_UNARY[t],
                                   operand=operand)
        return self.parse_primary()

    def parse_primary(self) -> Expression:
        tok = self.cur
        t = tok.type
        if t in _LITERAL_KINDS:
            self._advance()
            return Literal(span=self._tok_span(tok), kind=_LITERAL_KINDS[t], lexeme=tok.lexeme)
        if t == T.LPAREN:
            self._advance()
            expr = self.parse_expression()
            self._expect(T.RPAREN, "Expected ')' after expression.")
            return expr  # grouping creates no node (D9)
        if t == T.IDENTIFIER:
            self._advance()
            if self.cur.type == T.LPAREN:
                return self._finish_call(tok)
            if self.cur.type == T.LBRACKET:
                return self._finish_array_access(tok)
            return self._identifier(tok)
        raise self._fail(C.INVALID_EXPRESSION, "Expected expression.")

    def _finish_call(self, name_tok: Token) -> FunctionCall:
        callee = self._identifier(name_tok)
        self._advance()  # '('
        args: list[Expression] = []
        failed = False
        if self.cur.type != T.RPAREN:
            while True:
                try:
                    args.append(self.parse_expression())
                except ParseAbort:
                    failed = True
                    self._sync_delimited(_LIST_SYNC)
                if self.cur.type == T.COMMA:
                    self._advance()
                    continue
                break
        if self.cur.type == T.RPAREN:
            self._advance()
        elif failed:
            raise ParseAbort()
        else:
            raise self._fail(C.MISSING_TOKEN, "Expected ')' after arguments.",
                             expected=[T.RPAREN, T.COMMA])
        if failed:
            raise ParseAbort()
        return FunctionCall(span=self._span_from(name_tok), callee=callee, arguments=args)

    def _finish_array_access(self, name_tok: Token) -> ArrayAccess:
        base = self._identifier(name_tok)
        indices: list[Expression] = []
        while self.cur.type == T.LBRACKET:
            self._advance()
            indices.append(self._parse_bracketed_expression("Expected ']' after array index."))
        return ArrayAccess(span=self._span_from(name_tok), base=base, indices=indices)

    def _parse_bracketed_expression(self, close_msg: str) -> Expression:
        """Expression + ']' after '[' was consumed, with §3.7.3 index recovery."""
        try:
            expr = self.parse_expression()
        except ParseAbort:
            self._sync_delimited(_INDEX_SYNC)
            if self.cur.type == T.RBRACKET:
                self._advance()
            raise
        self._expect(T.RBRACKET, close_msg)
        return expr
