"""AST invariant checker (design §3.5.12 plus structural/span invariants).

``check_program(program)`` returns a list of human-readable violations (empty
when the AST is well formed). It is run on every parsed program in the tests.
"""

from __future__ import annotations

from compiler.ast.nodes import (
    ASTNode, ArrayAccess, Assignment, AssignmentUpdate, BinaryExpression, Block,
    CastExpression, Declaration, DecrementUpdate, Expression, ExpressionStatement,
    ForAssignmentInit, ForDeclarationInit, ForInit, ForLoop, ForThoModhaluInit,
    ForUpdate, FunctionCall, FunctionDeclaration, Identifier, IfStatement,
    IncrementUpdate, Input, Literal, LiteralKind, Output, Parameter, Program,
    RangeLoop, ReturnStatement, Statement, TypeSyntax, UnaryExpression, WhileLoop,
    BreakStatement, ContinueStatement, children,
)
from compiler.diagnostics import Span

_TARGET = (Identifier, ArrayAccess)
_INIT_VARIANTS = (ForThoModhaluInit, ForAssignmentInit, ForDeclarationInit)
_UPDATE_VARIANTS = (AssignmentUpdate, IncrementUpdate, DecrementUpdate)
_STATEMENT_NODES = (
    Declaration, Assignment, Input, Output, IfStatement, WhileLoop, RangeLoop,
    ForLoop, ReturnStatement, BreakStatement, ContinueStatement, ExpressionStatement,
)
_EXPRESSION_NODES = (
    Identifier, Literal, ArrayAccess, FunctionCall, UnaryExpression,
    CastExpression, BinaryExpression,
)


def _pos_lt(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a < b


def check_program(program: Program) -> list[str]:
    problems: list[str] = []

    def bad(node: ASTNode, msg: str) -> None:
        problems.append(f"{type(node).__name__}@{node.span}: {msg}")

    def is_expr(x) -> bool:
        return isinstance(x, _EXPRESSION_NODES)

    def need_expr(node: ASTNode, name: str, x) -> None:
        if not is_expr(x):
            bad(node, f"field '{name}' must be an Expression, got {type(x).__name__}")

    def check_type(node: ASTNode, t, *, allow_unsized: bool, allow_dims: bool, what: str) -> None:
        if not isinstance(t, TypeSyntax):
            bad(node, f"{what} must be TypeSyntax")
            return
        dims = t.array_dimensions
        if not allow_dims and dims:
            bad(t, f"{what} must not have array dimensions")
        for d in dims:
            if d is None:
                if not allow_unsized:
                    bad(t, f"{what} has an unsized dimension")
                elif dims != [None]:
                    bad(t, "unsized parameter dimension must be exactly [None]")
            else:
                need_expr(t, "array_dimensions[]", d)

    def check_span(node: ASTNode, parent: ASTNode | None) -> None:
        sp = node.span
        if not isinstance(sp, Span):
            bad(node, "missing span")
            return
        start = (sp.start_line, sp.start_column)
        end = (sp.end_line, sp.end_column)
        if start[0] < 1 or start[1] < 1:
            bad(node, "span start is not 1-based")
        if isinstance(node, Program):
            if end < start:
                bad(node, "Program span is inverted")
        elif not _pos_lt(start, end):
            bad(node, "span must be non-empty half-open [start,end)")
        if parent is not None and isinstance(parent.span, Span) and not parent.span.contains(sp):
            bad(node, f"span not contained in parent {type(parent).__name__}@{parent.span}")

    def ordered(node: ASTNode, kids: list[ASTNode], name: str) -> None:
        prev_end = (0, 0)
        for k in kids:
            s = (k.span.start_line, k.span.start_column)
            if s < prev_end:
                bad(node, f"items of '{name}' overlap or are out of source order")
                return
            prev_end = (k.span.end_line, k.span.end_column)

    def visit(node: ASTNode, parent: ASTNode | None) -> None:
        check_span(node, parent)

        if isinstance(node, Program):
            for it in node.items:
                if not isinstance(it, (FunctionDeclaration, *_STATEMENT_NODES)):
                    bad(node, f"invalid top-level item {type(it).__name__}")
            ordered(node, node.items, "items")
        elif isinstance(node, Block):
            for st in node.statements:
                if not isinstance(st, _STATEMENT_NODES):
                    bad(node, f"invalid statement {type(st).__name__} in block")
            ordered(node, node.statements, "statements")
        elif isinstance(node, FunctionDeclaration):
            check_type(node, node.return_type, allow_unsized=False, allow_dims=False, what="return type")
            if not isinstance(node.name, Identifier):
                bad(node, "name must be Identifier")
            if not isinstance(node.body, Block):
                bad(node, "body must be Block")
            for p in node.parameters:
                if not isinstance(p, Parameter):
                    bad(node, "parameters must be Parameter nodes")
        elif isinstance(node, Parameter):
            check_type(node, node.type, allow_unsized=True, allow_dims=True, what="parameter type")
            if not isinstance(node.name, Identifier):
                bad(node, "name must be Identifier")
        elif isinstance(node, Declaration):
            check_type(node, node.type, allow_unsized=False, allow_dims=True, what="declaration type")
            if not isinstance(node.name, Identifier):
                bad(node, "name must be Identifier")
        elif isinstance(node, Assignment):
            if not isinstance(node.target, _TARGET):
                bad(node, "target must be Identifier or ArrayAccess")
            need_expr(node, "value", node.value)
        elif isinstance(node, Input):
            if not isinstance(node.target, _TARGET):
                bad(node, "target must be Identifier or ArrayAccess")
        elif isinstance(node, Output):
            need_expr(node, "value", node.value)
        elif isinstance(node, IfStatement):
            need_expr(node, "condition", node.condition)
            if not isinstance(node.then_block, Block):
                bad(node, "then_block must be Block")
            if node.else_branch is not None and not isinstance(node.else_branch, (Block, IfStatement)):
                bad(node, "else_branch must be None, Block or IfStatement")
        elif isinstance(node, WhileLoop):
            need_expr(node, "condition", node.condition)
            if not isinstance(node.body, Block):
                bad(node, "body must be Block")
        elif isinstance(node, RangeLoop):
            if not isinstance(node.variable, Identifier):
                bad(node, "variable must be Identifier")
            need_expr(node, "start", node.start)
            need_expr(node, "end", node.end)
            if not isinstance(node.body, Block):
                bad(node, "body must be Block")
        elif isinstance(node, ForLoop):
            if not isinstance(node.init, _INIT_VARIANTS):
                bad(node, f"init must be one of the three ForInit variants, got {type(node.init).__name__}")
            need_expr(node, "condition", node.condition)
            if not isinstance(node.update, _UPDATE_VARIANTS):
                bad(node, f"update must be one of the update variants, got {type(node.update).__name__}")
            if not isinstance(node.body, Block):
                bad(node, "body must be Block")
        elif isinstance(node, (ForThoModhaluInit, ForAssignmentInit)):
            if not isinstance(node.target, Identifier):
                bad(node, "target must be Identifier")
            need_expr(node, "value", node.value)
        elif isinstance(node, ForDeclarationInit):
            check_type(node, node.type, allow_unsized=False, allow_dims=False, what="for-declaration type")
            if not isinstance(node.name, Identifier):
                bad(node, "name must be Identifier")
            if node.initializer is not None:
                need_expr(node, "initializer", node.initializer)
        elif isinstance(node, AssignmentUpdate):
            if not isinstance(node.target, _TARGET):
                bad(node, "target must be Identifier or ArrayAccess")
            need_expr(node, "value", node.value)
        elif isinstance(node, (IncrementUpdate, DecrementUpdate)):
            if not isinstance(node.target, _TARGET):
                bad(node, "target must be Identifier or ArrayAccess")
            if not isinstance(node.prefix, bool):
                bad(node, "prefix must be bool")
        elif isinstance(node, ReturnStatement):
            need_expr(node, "value", node.value)
        elif isinstance(node, ExpressionStatement):
            if not isinstance(node.expression, FunctionCall):
                bad(node, "expression must be a FunctionCall")
        elif isinstance(node, FunctionCall):
            if not isinstance(node.callee, Identifier):
                bad(node, "callee must be Identifier")
            for a in node.arguments:
                need_expr(node, "arguments[]", a)
        elif isinstance(node, ArrayAccess):
            if not isinstance(node.base, Identifier):
                bad(node, "base must be Identifier")
            if not node.indices:
                bad(node, "ArrayAccess needs at least one index")
            for i in node.indices:
                need_expr(node, "indices[]", i)
        elif isinstance(node, BinaryExpression):
            need_expr(node, "left", node.left)
            need_expr(node, "right", node.right)
        elif isinstance(node, UnaryExpression):
            need_expr(node, "operand", node.operand)
        elif isinstance(node, CastExpression):
            check_type(node, node.target_type, allow_unsized=False, allow_dims=False, what="cast type")
            need_expr(node, "expression", node.expression)
        elif isinstance(node, Literal):
            lx = node.lexeme
            if node.kind == LiteralKind.BOOL and lx.lower() not in ("nijam", "abaddham"):
                bad(node, f"bool literal has invalid lexeme {lx!r}")
            if node.kind == LiteralKind.STRING and not (len(lx) >= 2 and lx[0] == lx[-1] == '"'):
                bad(node, "string literal lexeme must keep its quotes")
            if node.kind == LiteralKind.CHAR and not (len(lx) >= 3 and lx[0] == lx[-1] == "'"):
                bad(node, "char literal lexeme must keep its quotes")
            if node.kind == LiteralKind.INTEGER and not lx[:1].isdigit():
                bad(node, "integer literal lexeme must start with a digit")
            if node.kind == LiteralKind.FLOAT and "." not in lx:
                bad(node, "float literal lexeme must contain '.'")
        elif isinstance(node, (BreakStatement, ContinueStatement, Identifier, TypeSyntax)):
            pass
        elif type(node) in (ASTNode, Statement, Expression, ForInit, ForUpdate):
            bad(node, f"abstract node {type(node).__name__} instantiated")
        else:
            bad(node, f"unknown node type {type(node).__name__}")

        for child in children(node):
            visit(child, node)

    visit(program, None)
    return problems
