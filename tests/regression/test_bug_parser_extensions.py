"""Regression tests: parser accepted constructs the canonical grammar rejects (plan §A)."""

import pytest

from compiler.lexer import Lexer
from compiler.parser import Parser


def syntax_errors(src):
    p = Parser(Lexer(src).tokenize())
    p.parse()
    return p.errors


@pytest.mark.parametrize("src", ["{ x lo 1 pettu }", "{ }"])
def test_bug_bare_block_statement_was_accepted(src):
    assert syntax_errors(src)


@pytest.mark.parametrize("src", ["x lo f(1)(2) pettu", "x lo a[1](2) pettu", "x lo f(1)[0] pettu"])
def test_bug_call_and_index_chaining_was_accepted(src):
    assert syntax_errors(src)


@pytest.mark.parametrize("src", [
    "(x) lo 1 pettu", "(x) ni chaduvu", "pratisari (int i; i < 1; ++(i)) { }",
    "pratisari (int i; i < 1; (i)++) { }", "pratisari (int i; i < 1; (i) lo 1 pettu) { }",
])
def test_bug_parenthesized_targets_were_stripped_and_accepted(src):
    assert syntax_errors(src)


def test_bug_ast_end_column_was_start_of_last_token():
    from compiler.ast.nodes import Declaration
    prog = Parser(Lexer("int xyz").tokenize()).parse()
    decl = prog.items[0]
    assert isinstance(decl, Declaration)
    assert (decl.span.end_line, decl.span.end_column) == (1, 8)  # half-open end


def test_bug_lexer_cr_was_an_unexpected_character():
    lx = Lexer("int a\r\nint b\r\n")
    lx.tokenize()
    assert not lx.errors


def test_bug_lexer_unicode_digits_matched_as_numbers():
    lx = Lexer("٣")
    lx.tokenize()
    assert lx.errors
