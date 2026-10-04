"""Phase 3: grammar conformance — constructs the canonical grammar rejects (plan §A)."""

import pytest

from compiler.ast.invariants import check_program
from compiler.ast.nodes import (
    ArrayAccess, Assignment, BinaryExpression, BinaryOp, Block, ExpressionStatement,
    FunctionCall, FunctionDeclaration, Identifier, IfStatement, Literal, LiteralKind,
    Output, ReturnStatement, UnaryExpression, UnaryOp, WhileLoop, CastExpression,
    Declaration, Input,
)
from compiler.diagnostics import SyntaxCategory as C
from compiler.lexer import Lexer
from compiler.parser import Parser


def run(src):
    lx = Lexer(src, "t.tel")
    toks = lx.tokenize()
    assert not lx.errors
    p = Parser(toks, "t.tel")
    prog = p.parse()
    return prog, p.errors


def ok(src):
    prog, errs = run(src)
    assert not errs, [str(e) for e in errs]
    assert check_program(prog) == []
    return prog


def bad(src, category=None):
    _, errs = run(src)
    assert errs, f"expected a syntax error for: {src!r}"
    assert all(e.stage == "syntax" for e in errs)
    if category is not None:
        assert errs[0].category == category, (errs[0].category, errs[0].message)
    return errs


# ── constructs removed because the grammar does not admit them ──

@pytest.mark.parametrize("src", [
    "{ x lo 1 pettu }",                         # bare block statement
    "x ayite { { y lo 1 pettu } }",             # nested bare block
    "int f charya() { { 1 ivvu } }",
])
def test_bare_block_statement_rejected(src):
    bad(src)


@pytest.mark.parametrize("src", [
    "x lo f(1)(2) pettu",       # call chaining
    "x lo a[1](2) pettu",       # index then call
    "x lo f(1)[0] pettu",       # call then index
    "x lo f(1)(2)(3) pettu",
])
def test_no_postfix_chaining_in_expressions(src):
    bad(src)


def test_call_followed_by_parenthesized_expression_is_two_statements():
    # f(1) (2) ni chupi  ==  call statement, then output statement (no terminators exist)
    prog = ok("f(1) (2) ni chupi")
    assert isinstance(prog.items[0], ExpressionStatement)
    assert isinstance(prog.items[1], Output)


@pytest.mark.parametrize("src", [
    "(x) lo 1 pettu",
    "((x)) lo 1 pettu",
    "(x) ni chaduvu",
    "(a[1]) lo 1 pettu",
    "5 lo 1 pettu",
    "f(x) lo 1 pettu",
    "a + b lo 1 pettu",
    "5 ni chaduvu",
    "f(x) ni chaduvu",
])
def test_parenthesized_or_non_lvalue_targets_rejected(src):
    bad(src, C.INVALID_STATEMENT)


@pytest.mark.parametrize("update", ["++(i)", "--(i)", "(i)++", "(i)--", "(i) lo 1 pettu", "5++", "++5"])
def test_parenthesized_update_targets_rejected(update):
    bad(f"pratisari (int i; i < 3; {update}) {{ }}")


def test_parenthesized_call_is_not_an_expression_statement():
    bad("(f(1))\nint y", C.INVALID_STATEMENT)
    bad("(f(1))", C.UNEXPECTED_EOF)


def test_standalone_increment_is_not_a_statement():
    bad("i++")
    bad("++i")


def test_call_arguments_may_be_parenthesized_and_calls_nest():
    ok("f((a), (b + 1), g(h(2))) ni chupi")


# ── valid forms ──

def test_function_vs_declaration_lookahead_is_type_ident_charya():
    prog = ok("int f charya() { 1 ivvu }\nint f\nint a[3][f(1)]")
    assert isinstance(prog.items[0], FunctionDeclaration)
    assert isinstance(prog.items[1], Declaration)
    assert isinstance(prog.items[2], Declaration)
    assert len(prog.items[2].type.array_dimensions) == 2


def test_array_parameter_and_multi_index_access():
    prog = ok("int f charya(int a[], float b) { a[1][2] lo b pettu\n0 ivvu }")
    fn = prog.items[0]
    assert fn.parameters[0].type.array_dimensions == [None]
    assert fn.parameters[1].type.array_dimensions == []
    asg = fn.body.statements[0]
    assert isinstance(asg.target, ArrayAccess) and len(asg.target.indices) == 2


@pytest.mark.parametrize("src", [
    "int a[]",                      # unsized dimension outside parameters
    "int f charya(int m[][3]) { 0 ivvu }",   # multidimensional unsized parameter (not in grammar)
    "int f charya(int a, ) { 0 ivvu }",
    "int f charya(, int a) { 0 ivvu }",
    "x lo a[] pettu",
])
def test_unsized_and_malformed_dimensions_rejected(src):
    bad(src)


def test_function_declarations_only_at_top_level():
    errs = bad("x ayite { int f charya() { 1 ivvu } }")
    assert errs[0].category == C.INVALID_DECLARATION


def test_declaration_initializer_not_in_grammar():
    bad("int x lo 1 pettu", C.INVALID_DECLARATION)


def test_void_and_padham_types_parse():
    ok("void v\npadham s\nvoid f charya() { }")


def test_bare_ivvu_is_not_in_grammar():
    bad("int f charya() { ivvu }")


def test_unary_cast_and_precedence_shapes():
    prog = ok("-a * b ni chupi")
    e = prog.items[0].value
    assert isinstance(e, BinaryExpression) and e.operator == BinaryOp.MUL
    assert isinstance(e.left, UnaryExpression) and e.left.operator == UnaryOp.NEGATE
    prog = ok("(float) a / b ni chupi")
    e = prog.items[0].value
    assert e.operator == BinaryOp.DIV and isinstance(e.left, CastExpression)
    prog = ok("a < b == c ni chupi")          # relational binds tighter than equality
    e = prog.items[0].value
    assert e.operator == BinaryOp.EQ and e.left.operator == BinaryOp.LT
    prog = ok("a && b || c && d ni chupi")
    e = prog.items[0].value
    assert e.operator == BinaryOp.OR and e.left.operator == BinaryOp.AND


def test_binary_operators_are_left_associative():
    e = ok("a - b - c ni chupi").items[0].value
    assert e.operator == BinaryOp.SUB and isinstance(e.left, BinaryExpression) and isinstance(e.right, Identifier)
    e = ok("a / b % c ni chupi").items[0].value
    assert e.operator == BinaryOp.MOD and e.left.operator == BinaryOp.DIV


def test_longest_match_call_statement_then_minus_continues_expression():
    # P16: f(x) NEWLINE -y ni chupi  ==  output of  f(x) - y
    prog = ok("f(x)\n-y ni chupi")
    assert len(prog.items) == 1
    e = prog.items[0].value
    assert isinstance(e, BinaryExpression) and e.operator == BinaryOp.SUB
    assert isinstance(e.left, FunctionCall)


def test_bool_literals_keep_original_spelling():
    prog = ok("NIJAM ni chupi\nAbaddham ni chupi")
    assert [i.value.lexeme for i in prog.items] == ["NIJAM", "Abaddham"]
    assert all(i.value.kind == LiteralKind.BOOL for i in prog.items)


def test_keywords_case_insensitive_in_statements():
    ok("X AYITE { y NI CHUPI } LEKUNTE { y NI CHUPI }")


def test_statement_forms_all_parse():
    ok("""
int n
n ni chaduvu
n + 1 ni chupi
n > 0 ayite { } lekunte n < 0 ayite { } lekunte { }
n < 3 unnanta varaku { aapu\nsaagu }
prati i 0 nundi n varaku { i ni chupi }
pratisari (int j lo 0 pettu; j < n; ++j) { }
f(1, 2)
int g charya(int a) { a ivvu }
""")


def test_complete_token_consumption_trailing_garbage_is_error():
    bad("int x )")
    bad("int x }")
    bad("int x ]")


def test_empty_program_is_valid():
    prog = ok("")
    assert prog.items == []


def test_literal_kinds():
    prog = ok("1 ni chupi\n1.5 ni chupi\n'a' ni chupi\n\"s\" ni chupi\nnijam ni chupi")
    kinds = [i.value.kind for i in prog.items]
    assert kinds == [LiteralKind.INTEGER, LiteralKind.FLOAT, LiteralKind.CHAR,
                     LiteralKind.STRING, LiteralKind.BOOL]


def test_deeply_nested_expression_does_not_crash():
    n = 60
    prog = ok("(" * n + "1" + ")" * n + " ni chupi")
    assert isinstance(prog.items[0].value, Literal)
