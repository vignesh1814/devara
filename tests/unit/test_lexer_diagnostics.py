"""Phase 2: lexical diagnostic categories, CRLF handling, token end columns."""

import pytest

from compiler.diagnostics import LexCategory
from compiler.lexer import Lexer, TokenType


def lex(src):
    lx = Lexer(src, filename="t.tel")
    toks = lx.tokenize()
    return toks, lx.errors


@pytest.mark.parametrize("src,cat", [
    ("@", LexCategory.INVALID_CHARACTER),
    ("a \r b", LexCategory.INVALID_CHARACTER),          # lone CR
    ('"abc', LexCategory.UNTERMINATED_STRING),
    ('"abc\ndef"', LexCategory.UNTERMINATED_STRING),
    ("'a", LexCategory.UNTERMINATED_CHAR),
    ("''", LexCategory.INVALID_CHAR_LITERAL),
    ("'ab'", LexCategory.INVALID_CHAR_LITERAL),
    (r"'\q'", LexCategory.INVALID_ESCAPE),
    (r'"\q"', LexCategory.INVALID_ESCAPE),
    (r"'\x4'", LexCategory.INVALID_ESCAPE),
    (r'"\xZZ"', LexCategory.INVALID_ESCAPE),
    ("089", LexCategory.INVALID_NUMBER),
])
def test_error_categories(src, cat):
    _, errs = lex(src)
    assert errs and errs[0].category == cat
    assert errs[0].stage == "lexical"
    assert errs[0].filename == "t.tel"


def test_all_errors_collected_and_tokenization_continues():
    toks, errs = lex("int @ x $ y")
    assert [e.category for e in errs] == [LexCategory.INVALID_CHARACTER] * 2
    assert [t.lexeme for t in toks if t.type == TokenType.IDENTIFIER] == ["x", "y"]


def test_error_span_is_half_open():
    _, errs = lex("int abc @")
    s = errs[0].span
    assert (s.start_line, s.start_column, s.end_line, s.end_column) == (1, 9, 1, 10)


def test_crlf_is_a_newline():
    toks, errs = lex("int a\r\nint b\r\n")
    assert not errs
    assert [(t.line, t.column) for t in toks if t.type == TokenType.INT] == [(1, 1), (2, 1)]
    assert toks[-1].type == TokenType.EOF and toks[-1].line == 3


def test_crlf_after_comment_and_unterminated_string():
    toks, errs = lex("# c\r\nint\r\n")
    assert not errs and toks[0].line == 2
    _, errs = lex('"abc\r\nint')
    assert errs[0].category == LexCategory.UNTERMINATED_STRING


def test_token_end_column_is_half_open():
    toks, _ = lex('abc 12 "hi" nijam')
    assert [(t.column, t.end_column) for t in toks[:-1]] == [(1, 4), (5, 7), (8, 12), (13, 18)]


def test_unicode_digits_are_not_digits():
    _, errs = lex("١٢")
    assert errs and all(e.category == LexCategory.INVALID_CHARACTER for e in errs)


def test_eof_token_position():
    toks, _ = lex("int")
    assert toks[-1].type == TokenType.EOF and (toks[-1].line, toks[-1].column) == (1, 4)
    toks, _ = lex("")
    assert (toks[-1].line, toks[-1].column) == (1, 1)
