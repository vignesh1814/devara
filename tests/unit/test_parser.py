"""Comprehensive unit tests for the Devara parser."""

import pytest  # type: ignore
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast.invariants import check_program
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
    LiteralKind,
    Output,
    Parameter,
    PrimitiveType,
    Program,
    RangeLoop,
    ReturnStatement,
    Span,
    TypeSyntax,
    UnaryExpression,
    UnaryOp,
    WhileLoop,
    ForAssignmentInit,
    ForDeclarationInit,
    ForInit,
    ForLoop,
    ForThoModhaluInit,
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
    assert check_program(ast) == []
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
        assert decl.name.name == "n"
        assert decl.type.primitive == PrimitiveType.INT
        assert decl.type.array_dimensions == []

    def test_1d_array_declaration(self):
        ast = parse("bool prime[10]")
        decl = ast.items[0]
        assert isinstance(decl, Declaration)
        assert decl.name.name == "prime"
        assert decl.type.primitive == PrimitiveType.BOOL
        assert len(decl.type.array_dimensions) == 1
        dim = decl.type.array_dimensions[0]
        assert isinstance(dim, Literal)
        assert dim.lexeme == "10"

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
        assert stmt.value.lexeme == "10"

    def test_array_assignment(self):
        ast = parse("a[i] lo 0 pettu")
        stmt = ast.items[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.target, ArrayAccess)
        assert isinstance(stmt.target.base, Identifier)
        assert stmt.target.base.name == "a"
        assert len(stmt.target.indices) == 1
        assert isinstance(stmt.target.indices[0], Identifier)
        assert stmt.target.indices[0].name == "i"


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
        assert stmt.else_branch is None

    def test_if_else(self):
        ast = parse("nijam ayite { } lekunte { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_branch, Block)

    def test_chained_else_if(self):
        ast = parse("a ayite { } lekunte b ayite { } lekunte { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_branch, IfStatement)
        assert isinstance(stmt.else_branch.else_branch, Block)


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
        assert stmt.variable.name == "i"
        assert isinstance(stmt.start, Literal)
        assert isinstance(stmt.end, Identifier)
        assert isinstance(stmt.body, Block)


class TestForLoop:
    def test_for_loop_increment(self):
        ast = parse("pratisari (i 0 tho modhalu; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForThoModhaluInit)
        assert stmt.init.target.name == "i"
        assert stmt.init.value.lexeme == "0"
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
        assert decl.name.name == "add"
        assert decl.return_type.primitive == PrimitiveType.INT
        assert len(decl.parameters) == 2
        assert decl.parameters[0].name.name == "a"
        assert decl.parameters[1].name.name == "b"
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
        assert "after expression" in parser.errors[0].message


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stage 2 Finalization Regression Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLekunteRegression:
    def test_lekunte_valid_block(self):
        ast = parse("x ayite { } lekunte { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_branch, Block)

    def test_lekunte_valid_else_if(self):
        ast = parse("x ayite { } lekunte y ayite { }")
        stmt = ast.items[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.else_branch, IfStatement)

    def test_lekunte_invalid_assignment(self):
        parser = parse_with_errors("x ayite { } lekunte y lo 10 pettu")
        assert len(parser.errors) > 0
        assert "Expected '{' or if-statement after 'lekunte'" in parser.errors[0].message

    def test_lekunte_invalid_input(self):
        parser = parse_with_errors("x ayite { } lekunte x ni chaduvu")
        assert len(parser.errors) > 0
        assert "Expected '{' or if-statement after 'lekunte'" in parser.errors[0].message


class TestPratisariRegression:
    def test_pratisari_tho_modhalu_init(self):
        ast = parse("pratisari (i 0 tho modhalu; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForThoModhaluInit)
        assert stmt.init.target.name == "i"
        assert stmt.init.value is not None

    def test_pratisari_assignment_init(self):
        ast = parse("pratisari (i lo 0 pettu; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForAssignmentInit)
        assert stmt.init.target.name == "i"
        assert stmt.init.value is not None

    def test_pratisari_declaration_init_without_value(self):
        ast = parse("pratisari (int i; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForDeclarationInit)
        assert stmt.init.name.name == "i"
        assert stmt.init.initializer is None
        assert stmt.init.type.primitive == PrimitiveType.INT

    def test_pratisari_declaration_init_with_value(self):
        ast = parse("pratisari (int i lo 0 pettu; i < 10; i++) { }")
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert isinstance(stmt.init, ForDeclarationInit)
        assert stmt.init.name.name == "i"
        assert stmt.init.initializer is not None
        assert stmt.init.type.primitive == PrimitiveType.INT

    @pytest.mark.parametrize(
        "init_str",
        [
            "i 0 tho modhalu",
            "i lo 0 pettu",
            "int i",
            "int i lo 0 pettu",
        ],
    )
    @pytest.mark.parametrize(
        "update_str",
        [
            "i lo i + 1 pettu",
            "++i",
            "i++",
            "--i",
            "i--",
        ],
    )
    def test_pratisari_all_init_update_combinations(self, init_str, update_str):
        code = f"pratisari ({init_str}; i < 10; {update_str}) {{ }}"
        ast = parse(code)
        assert len(ast.items) == 1
        stmt = ast.items[0]
        assert isinstance(stmt, ForLoop)
        assert stmt.init is not None
        assert stmt.condition is not None
        assert stmt.update is not None

    def test_pratisari_empty_rejected(self):
        parser = parse_with_errors("pratisari (;;) { }")
        assert len(parser.errors) > 0
        assert "Expected loop initialization in pratisari" in parser.errors[0].message


class TestBooleanLiteralsRegression:
    def test_nijam_raw_lexeme(self):
        ast = parse("nijam ni chupi")
        stmt = ast.items[0]
        assert isinstance(stmt, Output)
        assert isinstance(stmt.value, Literal)
        assert stmt.value.kind == LiteralKind.BOOL
        assert stmt.value.lexeme == "nijam"

    def test_abaddham_raw_lexeme(self):
        ast = parse("abaddham ni chupi")
        stmt = ast.items[0]
        assert isinstance(stmt, Output)
        assert isinstance(stmt.value, Literal)
        assert stmt.value.kind == LiteralKind.BOOL
        assert stmt.value.lexeme == "abaddham"


class TestSourceSpansRegression:
    """Spans are half-open [start, end): end is the first column after the construct."""

    def test_declaration_spans(self):
        decl = parse("int x").items[0]
        assert decl.span == Span(1, 1, 1, 6)
        assert (decl.line, decl.column, decl.end_line, decl.end_column) == (1, 1, 1, 6)

    def test_assignment_spans(self):
        assert parse("x lo 10 pettu").items[0].span == Span(1, 1, 1, 14)

    def test_binary_expression_spans(self):
        expr = parse("a + b ni chupi").items[0].value
        assert isinstance(expr, BinaryExpression)
        assert expr.span == Span(1, 1, 1, 6)

    def test_block_spans(self):
        block = parse("x ayite { x lo 1 pettu }").items[0].then_block
        assert isinstance(block, Block)
        assert block.span == Span(1, 9, 1, 25)

    def test_parenthesized_operand_is_included_in_parent_span(self):
        expr = parse("(a + b) * c ni chupi").items[0].value
        assert expr.span == Span(1, 1, 1, 12)
        assert expr.left.span == Span(1, 2, 1, 7)  # grouping creates no node

    def test_multiline_span(self):
        stmt = parse("x ayite {\n  y lo 1 pettu\n}\n").items[0]
        assert stmt.span == Span(1, 1, 3, 2)

    def test_program_span_covers_source_to_eof(self):
        assert parse("int x\n").span == Span(1, 1, 2, 1)
        assert parse("").span == Span(1, 1, 1, 1)
