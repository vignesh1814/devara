"""Syntax AST for the Devara compiler (design §3.5 field-level contract).

The AST is syntax only: no resolved symbols, semantic types or conversions.
Every node carries a half-open :class:`Span`. Parenthesized grouping creates no
node (D9); the grouped expression's child is returned directly.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterator

from compiler.diagnostics import Span

__all__ = [
    "Span", "PrimitiveType", "BinaryOp", "UnaryOp", "LiteralKind", "LiteralType",
    "ASTNode", "Statement", "Expression", "TypeSyntax", "Identifier", "Literal",
    "ArrayAccess", "FunctionCall", "UnaryExpression", "CastExpression",
    "BinaryExpression", "Block", "Declaration", "Assignment", "Input", "Output",
    "IfStatement", "WhileLoop", "RangeLoop", "ForInit", "ForThoModhaluInit",
    "ForAssignmentInit", "ForDeclarationInit", "ForUpdate", "AssignmentUpdate",
    "IncrementUpdate", "DecrementUpdate", "ForLoop", "ReturnStatement",
    "BreakStatement", "ContinueStatement", "ExpressionStatement", "Parameter",
    "FunctionDeclaration", "Program", "children",
]


# ── Enums ──

class PrimitiveType(StrEnum):
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    CHAR = "CHAR"
    PADHAM = "PADHAM"
    VOID = "VOID"


class BinaryOp(StrEnum):
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    MOD = "MOD"
    LT = "LT"
    GT = "GT"
    LE = "LE"
    GE = "GE"
    EQ = "EQ"
    NE = "NE"
    AND = "AND"
    OR = "OR"


class UnaryOp(StrEnum):
    NOT = "NOT"
    NEGATE = "NEGATE"
    POSITIVE = "POSITIVE"


class LiteralKind(StrEnum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    CHAR = "CHAR"
    STRING = "STRING"


LiteralType = LiteralKind  # backwards-compatible alias


# ── Bases ──

@dataclass
class ASTNode:
    """Base class for every AST node; ``span`` is half-open ``[start, end)``."""

    span: Span

    @property
    def line(self) -> int:
        return self.span.start_line

    @property
    def column(self) -> int:
        return self.span.start_column

    @property
    def end_line(self) -> int:
        return self.span.end_line

    @property
    def end_column(self) -> int:
        return self.span.end_column


@dataclass
class Statement(ASTNode):
    pass


@dataclass
class Expression(ASTNode):
    pass


# ── Type syntax ──

@dataclass
class TypeSyntax(ASTNode):
    """``primitive`` plus array dimensions (``None`` = unsized parameter dim)."""

    primitive: PrimitiveType
    array_dimensions: list[Expression | None]


# ── Names, literals, expressions ──

@dataclass
class Identifier(Expression):
    name: str


@dataclass
class Literal(Expression):
    kind: LiteralKind
    lexeme: str


@dataclass
class ArrayAccess(Expression):
    base: Identifier
    indices: list[Expression]


@dataclass
class FunctionCall(Expression):
    callee: Identifier
    arguments: list[Expression]


@dataclass
class UnaryExpression(Expression):
    operator: UnaryOp
    operand: Expression


@dataclass
class CastExpression(Expression):
    target_type: TypeSyntax
    expression: Expression


@dataclass
class BinaryExpression(Expression):
    operator: BinaryOp
    left: Expression
    right: Expression


# ── Statements ──

@dataclass
class Block(ASTNode):
    statements: list[Statement]


@dataclass
class Declaration(Statement):
    type: TypeSyntax
    name: Identifier


@dataclass
class Assignment(Statement):
    target: Identifier | ArrayAccess
    value: Expression


@dataclass
class Input(Statement):
    target: Identifier | ArrayAccess


@dataclass
class Output(Statement):
    value: Expression


@dataclass
class IfStatement(Statement):
    condition: Expression
    then_block: Block
    else_branch: Block | IfStatement | None


@dataclass
class WhileLoop(Statement):
    condition: Expression
    body: Block


@dataclass
class RangeLoop(Statement):
    variable: Identifier
    start: Expression
    end: Expression
    body: Block


# ── Three-part loop ──

@dataclass
class ForInit(ASTNode):
    """Tagged union base: ForThoModhaluInit | ForAssignmentInit | ForDeclarationInit."""


@dataclass
class ForThoModhaluInit(ForInit):
    target: Identifier
    value: Expression


@dataclass
class ForAssignmentInit(ForInit):
    target: Identifier
    value: Expression


@dataclass
class ForDeclarationInit(ForInit):
    type: TypeSyntax
    name: Identifier
    initializer: Expression | None


@dataclass
class ForUpdate(ASTNode):
    """Tagged union base: AssignmentUpdate | IncrementUpdate | DecrementUpdate."""


@dataclass
class AssignmentUpdate(ForUpdate):
    target: Identifier | ArrayAccess
    value: Expression


@dataclass
class IncrementUpdate(ForUpdate):
    target: Identifier | ArrayAccess
    prefix: bool


@dataclass
class DecrementUpdate(ForUpdate):
    target: Identifier | ArrayAccess
    prefix: bool


@dataclass
class ForLoop(Statement):
    init: ForInit
    condition: Expression
    update: ForUpdate
    body: Block


# ── Control transfer / expression statements ──

@dataclass
class ReturnStatement(Statement):
    value: Expression


@dataclass
class BreakStatement(Statement):
    pass


@dataclass
class ContinueStatement(Statement):
    pass


@dataclass
class ExpressionStatement(Statement):
    expression: FunctionCall


# ── Top level ──

@dataclass
class Parameter(ASTNode):
    type: TypeSyntax
    name: Identifier


@dataclass
class FunctionDeclaration(ASTNode):
    return_type: TypeSyntax
    name: Identifier
    parameters: list[Parameter]
    body: Block


@dataclass
class Program(ASTNode):
    items: list[FunctionDeclaration | Declaration | Statement]


# ── Traversal ──

def children(node: ASTNode) -> Iterator[ASTNode]:
    """Yield the direct child nodes of ``node`` in field order."""
    for f in dataclasses.fields(node):
        if f.name == "span":
            continue
        v = getattr(node, f.name)
        if isinstance(v, ASTNode):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, ASTNode):
                    yield x
