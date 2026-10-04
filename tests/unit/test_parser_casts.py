import pytest
from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.ast.nodes import (
    CastExpression, ExpressionStatement, TypeSyntax, Identifier, PrimitiveType, BinaryExpression, FunctionCall, Literal
)

def parse_expr(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    expr = parser.parse_expression()
    assert not parser.errors
    return expr

def parse_with_errors(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    return parser.errors

def test_cast_expression_basic():
    expr = parse_expr("(int) x")
    assert isinstance(expr, CastExpression)
    assert expr.target_type.primitive == PrimitiveType.INT
    assert isinstance(expr.expression, Identifier)
    assert expr.expression.name == "x"

def test_cast_all_primitive_types():
    types = ["int", "float", "bool", "char", "padham", "void"]
    for t in types:
        expr = parse_expr(f"({t}) x")
        assert isinstance(expr, CastExpression)
        assert expr.target_type.primitive.value == t.upper()

def test_cast_used_as_subexpression():
    expr = parse_expr("(int) x + 1")
    assert isinstance(expr, BinaryExpression)
    assert isinstance(expr.left, CastExpression)
    assert expr.left.target_type.primitive == PrimitiveType.INT

def test_cast_precedence():
    expr = parse_expr("(int) x + 1")
    assert isinstance(expr, BinaryExpression)
    assert isinstance(expr.left, CastExpression)

def test_disambiguation():
    # Plain grouping
    expr = parse_expr("(x)")
    assert isinstance(expr, Identifier)
    assert expr.name == "x"

    # Cast of grouped expression
    expr = parse_expr("(int)(x)")
    assert isinstance(expr, CastExpression)
    assert expr.target_type.primitive == PrimitiveType.INT
    assert isinstance(expr.expression, Identifier)

    # Nested casts
    expr = parse_expr("(int)(float) x")
    assert isinstance(expr, CastExpression)
    assert expr.target_type.primitive == PrimitiveType.INT
    assert isinstance(expr.expression, CastExpression)
    assert expr.expression.target_type.primitive == PrimitiveType.FLOAT

def test_malformed_casts():
    # Unterminated
    errors = parse_with_errors("(int x;")
    assert len(errors) > 0

    # Not a type keyword
    errors = parse_with_errors("(nonexistenttype) x;")
    assert len(errors) > 0

    # Empty parens
    errors = parse_with_errors("() x;")
    assert len(errors) > 0

def test_cast_ast_shape():
    expr = parse_expr("(int) x")
    assert isinstance(expr, CastExpression)
    assert expr.target_type
    assert expr.expression
    # Check span: '(' should be start, 'x' should be end
    assert expr.line > 0
    assert expr.column > 0
    assert expr.end_line >= expr.line
    assert expr.span.start_column == 1 and expr.span.end_column == 8  # '(int) x' = [1,8)

def test_cast_assignment():
    lexer = Lexer("y lo (int) x pettu")
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    assert not parser.errors
    stmt = prog.items[0]
    assert isinstance(stmt.value, CastExpression)
