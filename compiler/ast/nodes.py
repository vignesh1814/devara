"""AST nodes and enums for the Devara compiler."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum


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


class UnaryPosition(StrEnum):
    PREFIX = "PREFIX"
    POSTFIX = "POSTFIX"


class LiteralType(StrEnum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    CHAR = "CHAR"
    STRING = "STRING"


# ── Base Nodes ──

@dataclass(frozen=True, slots=True)
class ASTNode:
    """Base class for all AST nodes."""
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Statement(ASTNode):
    """Base class for all statement nodes."""
    pass


@dataclass(frozen=True, slots=True)
class Expression(ASTNode):
    """Base class for all expression nodes."""
    pass


# ── Types and Parameters ──

@dataclass(frozen=True, slots=True)
class Type(ASTNode):
    name: PrimitiveType
    array_dimensions: list[Expression]


@dataclass(frozen=True, slots=True)
class Parameter(ASTNode):
    type: Type
    name: str


# ── Expressions ──

@dataclass(frozen=True, slots=True)
class Identifier(Expression):
    name: str


@dataclass(frozen=True, slots=True)
class Literal(Expression):
    value: str
    literal_type: LiteralType


@dataclass(frozen=True, slots=True)
class ArrayAccess(Expression):
    array: Expression
    index: Expression


@dataclass(frozen=True, slots=True)
class FunctionCall(Expression):
    callee: Expression
    arguments: list[Expression]


@dataclass(frozen=True, slots=True)
class UnaryExpression(Expression):
    operator: UnaryOp
    operand: Expression
    position: UnaryPosition


@dataclass(frozen=True, slots=True)
class BinaryExpression(Expression):
    operator: BinaryOp
    left: Expression
    right: Expression


# ── Statements ──

@dataclass(frozen=True, slots=True)
class Block(ASTNode):
    statements: list[Statement]


@dataclass(frozen=True, slots=True)
class Declaration(Statement):
    type: Type
    name: str


@dataclass(frozen=True, slots=True)
class Assignment(Statement):
    target: Expression
    value: Expression


@dataclass(frozen=True, slots=True)
class Input(Statement):
    target: Expression


@dataclass(frozen=True, slots=True)
class Output(Statement):
    value: Expression


@dataclass(frozen=True, slots=True)
class IfStatement(Statement):
    condition: Expression
    then_block: Block
    else_block: Block | IfStatement | None


@dataclass(frozen=True, slots=True)
class WhileLoop(Statement):
    condition: Expression
    body: Block


@dataclass(frozen=True, slots=True)
class RangeLoop(Statement):
    target: str
    start: Expression
    end: Expression
    body: Block


# ── For Loop Constructs ──

@dataclass(frozen=True, slots=True)
class ForInit(ASTNode):
    target: Identifier
    value: Expression


@dataclass(frozen=True, slots=True)
class ForUpdate(ASTNode):
    """Base class for for-loop updates."""
    pass


@dataclass(frozen=True, slots=True)
class AssignmentUpdate(ForUpdate):
    target: Expression
    value: Expression


@dataclass(frozen=True, slots=True)
class IncrementUpdate(ForUpdate):
    target: Expression
    prefix: bool


@dataclass(frozen=True, slots=True)
class DecrementUpdate(ForUpdate):
    target: Expression
    prefix: bool


@dataclass(frozen=True, slots=True)
class ForLoop(Statement):
    init: ForInit | None
    condition: Expression | None
    update: ForUpdate | None
    body: Block


# ── Control Flow Statements ──

@dataclass(frozen=True, slots=True)
class ReturnStatement(Statement):
    value: Expression


@dataclass(frozen=True, slots=True)
class BreakStatement(Statement):
    pass


@dataclass(frozen=True, slots=True)
class ContinueStatement(Statement):
    pass


@dataclass(frozen=True, slots=True)
class ExpressionStatement(Statement):
    """For extensibility. Not currently produced by the parser."""
    expression: Expression


# ── Top-Level ──

@dataclass(frozen=True, slots=True)
class FunctionDeclaration(ASTNode):
    return_type: Type
    name: str
    parameters: list[Parameter]
    body: Block


@dataclass(frozen=True, slots=True)
class Program(ASTNode):
    items: list[FunctionDeclaration | Statement]
