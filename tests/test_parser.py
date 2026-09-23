"""Comprehensive unit tests for the Devara parser."""

import pytest  # type: ignore
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast.nodes import (
    ArrayAccess,
    Assignment,
    AssignmentUpdate,
    BinaryExpression,
    BinaryOp,
    Block,
    BreakStatement,
    ContinueStatement,
    Declaration,
    DecrementUpdate,
    Identifier,
    IfStatement,
    IncrementUpdate,
    Input,
    Literal,
    LiteralType,
    Output,
    Parameter,
    PrimitiveType,
    Program,
    RangeLoop,
    ReturnStatement,
    Type,
    UnaryExpression,
    UnaryOp,
    UnaryPosition,
    WhileLoop,
    ForInit,
    ForLoop,
    FunctionCall,
    FunctionDeclaration,
)


def parse(source: str) -> Program:
    """Helper — lex, parse, assert no errors, return AST."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert not lexer.has_errors, f"Lexer errors: {lexer.errors}"

    parser = Parser(tokens)
    ast = parser.parse()
    assert not parser.errors, f"Parser errors: {parser.errors}"
    return ast


def parse_with_errors(source: str) -> Parser:
    """Helper — lex, parse, return parser (errors expected)."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.parse()
    return parser


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Declarations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDeclarations:
    def test_scalar_declaration(self):
        ast = parse("int n")
        assert len(ast.items) == 1
        decl = ast.items[0]
        assert isinstance(decl, Declaration)
        assert decl.name == "n"
        assert decl.type.name == PrimitiveType.INT
        assert decl.type.array_dimensions == []

    def test_1d_array_declaration(self):
        ast = parse("bool prime[10]")
        decl = ast.items[0]
        assert isinstance(decl, Declaration)
        assert decl.name == "prime"
        assert decl.type.name == PrimitiveType.BOOL
        assert len(decl.type.array_dimensions) == 1
        dim = decl.type.array_dimensions[0]
        assert isinstance(dim, Literal)
        assert dim.value == "10"

    def test_2d_array_declaration(self):
        ast = parse("float matrix[10][20]")
        decl = ast.items[0]
        assert isinstance(decl, Declaration)
        assert len(decl.type.array_dimensions) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Assignments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAssignment:
    def test_simple_assignment(self):
        ast = parse("x lo 10 pettu")
        stmt = ast.items[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.target, Identifier)
        assert stmt.target.name == "x"
        assert isinstance(stmt.value, Literal)
        assert stmt.value.value == "10"

    def test_array_assignment(self):
        ast = parse("a[i] lo 0 pettu")
        stmt = ast.items[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.target, ArrayAccess)
        assert isinstance(stmt.target.array, Identifier)
        assert stmt.target.array.name == "a"
        assert isinstance(stmt.target.index, Identifier)
        assert stmt.target.index.name == "i"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestIO:
    def test_input(self):
        ast = parse("n ni chaduvu")
        stmt = ast.items[0]
        assert isinstance(stmt, Input)
        assert isinstance(stmt.target, Identifier)
        assert stmt.target.name == "n"

    def test_output(self):
        ast = parse("n ni chupi")
        stmt = ast.items[0]
        assert isinstance(stmt, Output)
        assert isinstance(stmt.value, Identifier)
        assert stmt.value.name == "n"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Control Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestIfStatement:
    def test_simple_if(self):
        ast = parse("nijam ayite { x lo 1 pettu }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.condition, Literal)
        assert len(stmt.then_block.statements) == 1
        assert stmt.else_block is None

    def test_if_else(self):
        ast = parse("nijam ayite { } lekunte { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_block, Block)

    def test_chained_else_if(self):
        ast = parse("a ayite { } lekunte b ayite { } lekunte { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_block, IfStatement)
        assert isinstance(stmt.else_block.else_block, Block)


class TestWhileLoop:
    def test_while_loop(self):
        ast = parse("i < n unnanta varaku { }")
        stmt = ast.items[0]
        assert isinstance(stmt, WhileLoop)
        assert isinstance(stmt.condition, BinaryExpression)
        assert isinstance(stmt.body, Block)


class TestRangeLoop:
    def test_range_loop(self):
        ast = parse("prati i 1 nundi n varaku { }")
        stmt = ast.items[0]
        assert isinstance(stmt, RangeLoop)
        assert stmt.target == "i"
        assert isinstance(stmt.start, Literal)
        assert isinstance(stmt.end, Identifier)
        assert isinstance(stmt.body, Block)


class TestForLoop:
    def test_for_loop_increment(self):
        ast = parse("pratisari (i 0 tho modhalu; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForInit)
        assert stmt.init.target.name == "i"
        assert stmt.init.value.value == "0"
        assert isinstance(stmt.condition, BinaryExpression)
        assert isinstance(stmt.update, IncrementUpdate)
        assert not stmt.update.prefix

    def test_for_loop_assignment_update(self):
        ast = parse("pratisari (i 0 tho modhalu; i < 10; i lo i + 1 pettu) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.update, AssignmentUpdate)
        assert isinstance(stmt.update.target, Identifier)
        assert isinstance(stmt.update.value, BinaryExpression)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Expressions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExpressions:
    def test_binary_precedence(self):
        # a + b * c -> a + (b * c)
        ast = parse("a + b * c ni chupi")
        stmt = ast.items[0]
        assert isinstance(stmt, Output)
        expr = stmt.value
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOp.ADD
        assert isinstance(expr.right, BinaryExpression)
        assert expr.right.operator == BinaryOp.MUL

    def test_parentheses(self):
        # (a + b) * c
        ast = parse("(a + b) * c ni chupi")
        expr = ast.items[0].value
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOp.MUL
        assert isinstance(expr.left, BinaryExpression)
        assert expr.left.operator == BinaryOp.ADD

    def test_unary(self):
        ast = parse("!nijam ni chupi")
        expr = ast.items[0].value
        assert isinstance(expr, UnaryExpression)
        assert expr.operator == UnaryOp.NOT


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestFunctions:
    def test_function_declaration(self):
        ast = parse("int add charya(int a, int b) { a + b ivvu }")
        decl = ast.items[0]
        assert isinstance(decl, FunctionDeclaration)
        assert decl.name == "add"
        assert decl.return_type.name == PrimitiveType.INT
        assert len(decl.parameters) == 2
        assert decl.parameters[0].name == "a"
        assert decl.parameters[1].name == "b"
        assert len(decl.body.statements) == 1
        assert isinstance(decl.body.statements[0], ReturnStatement)

    def test_function_call(self):
        ast = parse("add(10, 20) ni chupi")
        expr = ast.items[0].value
        assert isinstance(expr, FunctionCall)
        assert isinstance(expr.callee, Identifier)
        assert expr.callee.name == "add"
        assert len(expr.arguments) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Errors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestErrors:
    def test_invalid_pratisari_condition(self):
        parser = parse_with_errors("pratisari (i 2 tho modhalu; i <= n unnanta varaku; i++) { }")
        assert len(parser.errors) > 0
        assert "unnanta varaku" in parser.errors[0].message

    def test_standalone_increment_fails(self):
        parser = parse_with_errors("i++")
        assert len(parser.errors) > 0
        assert "Expected statement keyword" in parser.errors[0].message
