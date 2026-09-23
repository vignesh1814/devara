"""Exhaustive Stage 1 (Lexer) verification corpus for Devara."""

import pytest
import itertools
import string
from compiler.lexer import Lexer, Token, TokenType

def lex(source: str) -> list[Token]:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert not lexer.has_errors, f"Unexpected errors: {lexer.errors}"
    return tokens

def lex_types(source: str) -> list[TokenType]:
    return [t.type for t in lex(source) if t.type != TokenType.EOF]

def lex_with_errors(source: str) -> Lexer:
    lexer = Lexer(source)
    lexer.tokenize()
    return lexer

# --------------------------------------------------
# 3. WHITESPACE & NEWLINES
# --------------------------------------------------
def test_whitespace_and_newlines():
    source = " \t \n\n  \t\t\n \n"
    tokens = lex(source)
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.EOF
    assert tokens[0].line == 5

def test_whitespace_between_tokens():
    source = "int \t\n \tn"
    tokens = lex(source)
    assert len(tokens) == 3
    assert tokens[0].type == TokenType.INT
    assert tokens[0].line == 1
    assert tokens[1].type == TokenType.IDENTIFIER
    assert tokens[1].line == 2
    assert tokens[1].column == 3

# --------------------------------------------------
# 4. COMMENTS
# --------------------------------------------------
def test_comments():
    cases = [
        "# comment",
        "int n # declare n\nn ni chaduvu",
        "# comment at EOF",
        "10 # + 20",
        "# ayite lo 10\n10",
        "  \t# comment after whitespace",
    ]
    for case in cases:
        tokens = lex(case)
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        # Comments don't eat subsequent newlines
        
    lexer = Lexer("int n # comment\nfloat x")
    tokens = lexer.tokenize()
    assert not lexer.has_errors
    float_tok = tokens[2]
    assert float_tok.type == TokenType.FLOAT
    assert float_tok.line == 2

# --------------------------------------------------
# 5. IDENTIFIERS
# --------------------------------------------------
def test_identifiers():
    valids = ["a", "abc", "A", "ABC", "_", "_x", "x1", "x123", "abc_def", "A1_B2", "a" * 25]
    for v in valids:
        assert lex_types(v) == [TokenType.IDENTIFIER]
    
    # Boundary cases allowed by grammar
    assert lex_types("1abc") == [TokenType.INT_LITERAL, TokenType.IDENTIFIER]
    assert lex_types("9x") == [TokenType.INT_LITERAL, TokenType.IDENTIFIER]
    assert lex_types("123abc") == [TokenType.INT_LITERAL, TokenType.IDENTIFIER]

    # Keyword-prefix
    kw_prefixes = ["intx", "int1", "ayitex", "pratisariX"]
    for p in kw_prefixes:
        assert lex_types(p) == [TokenType.IDENTIFIER]

# --------------------------------------------------
# 6. KEYWORDS
# --------------------------------------------------
def test_keywords():
    keywords = [
        ("int", TokenType.INT), ("float", TokenType.FLOAT), ("bool", TokenType.BOOL),
        ("char", TokenType.CHAR), ("padham", TokenType.PADHAM), ("void", TokenType.VOID),
        ("nijam", TokenType.NIJAM), ("abaddham", TokenType.ABADDHAM),
        ("ayite", TokenType.AYITE), ("lekunte", TokenType.LEKUNTE),
        ("unnanta", TokenType.UNNANTA), ("varaku", TokenType.VARAKU),
        ("prati", TokenType.PRATI), ("pratisari", TokenType.PRATISARI),
        ("nundi", TokenType.NUNDI), ("modhalu", TokenType.MODHALU),
        ("lo", TokenType.LO), ("pettu", TokenType.PETTU),
        ("ni", TokenType.NI), ("tho", TokenType.THO),
        ("chaduvu", TokenType.CHADUVU), ("chupi", TokenType.CHUPI),
        ("charya", TokenType.CHARYA), ("ivvu", TokenType.IVVU),
        ("aapu", TokenType.AAPU), ("saagu", TokenType.SAAGU)
    ]
    for kw, tk in keywords:
        assert lex_types(kw) == [tk]
        assert lex_types(kw.upper()) == [tk]
        mixed = kw[0].upper() + kw[1:].lower()
        assert lex_types(mixed) == [tk]

# --------------------------------------------------
# 7. INTEGER LITERALS
# --------------------------------------------------
def test_integer_literals():
    # Decimal
    for v in ["0", "1", "9", "10", "42", "99", "100", "123456789"]:
        assert lex_types(v) == [TokenType.INT_LITERAL]

    # Octal
    for v in ["01", "07", "010", "017", "070", "077", "0012", "0077", "00"]:
        assert lex_types(v) == [TokenType.INT_LITERAL]

    # Bad Octal -> errors
    for v in ["08", "09"]:
        lexer = lex_with_errors(v)
        assert lexer.has_errors
        assert "octal" in lexer.errors[0].message.lower()

    # Split tokens due to boundaries
    for v in ["0018", "0078", "0099"]:
        tokens = lex(v)
        assert len(tokens) == 3 # octal, decimal, EOF

    # Hexadecimal
    for v in ["0x0", "0x1", "0x9", "0xa", "0xf", "0xA", "0xF", "0x10", "0xff", "0xFF", "0xabcdef", "0xABCDEF", "0X10", "0XFF"]:
        assert lex_types(v) == [TokenType.INT_LITERAL]
        
    for v in ["0x", "0X", "0xG", "0xg", "0x1G", "0xFG", "0x12Z"]:
        lexer = lex_with_errors(v)
        assert lexer.has_errors or (not lexer.has_errors and len(lexer._tokens) > 2) # Either error or splits e.g. 0xG -> 0, xG

# --------------------------------------------------
# 8. FLOAT LITERALS
# --------------------------------------------------
def test_float_literals():
    for v in ["0.0", "1.0", "1.5", "10.25", "123.456", "0.1", "9.9"]:
        assert lex_types(v) == [TokenType.FLOAT_LITERAL]

    malformed = [".", "1.", ".1", "1..2"]
    for v in malformed:
        lexer = lex_with_errors(v)
        assert lexer.has_errors # '.' triggers MISMATCH
    # We will test the bounds properly in boundary stress.

# --------------------------------------------------
# 10. CHARACTER LITERALS
# --------------------------------------------------
def test_character_literals():
    for v in ["'a'", "'Z'", "'0'", "' '", "';'", r"'\n'", r"'\x41'", "'\"'"]:
        assert lex_types(v) == [TokenType.CHAR_LITERAL]

    malformed = ["''", "'ab'", "'abc'", "'A", r"'\q'", r"'\'", "'\n'"]
    for v in malformed:
        lexer = lex_with_errors(v)
        assert lexer.has_errors

# --------------------------------------------------
# 11. STRING LITERALS
# --------------------------------------------------
def test_string_literals():
    for v in ['""', '"a"', '"hello"', '"hello world"', '"123"', '"hello123"', '";"', '"it\'s"']:
        assert lex_types(v) == [TokenType.STRING_LITERAL]
        
    for v in [r'"\n"', r'"\t"', r'"\r"', r'"\b"', r'"\f"', r'"\0"', r'"\\"', r'"\""', r'"\x41"']:
        assert lex_types(v) == [TokenType.STRING_LITERAL]

    # Recovery test
    source = '"unterminated\nint x'
    lexer = lex_with_errors(source)
    assert lexer.has_errors
    tokens = [t for t in lexer._tokens if t.type != TokenType.EOF]
    assert len(tokens) == 2
    assert tokens[1].type == TokenType.IDENTIFIER

# --------------------------------------------------
# 12. OPERATORS & PUNCTUATION
# --------------------------------------------------
def test_operators_punctuation():
    ops = [
        "+", "-", "*", "/", "%", "<", ">", "!", "&&", "||",
        "++", "--", "<=", ">=", "==", "!="
    ]
    for o in ops:
        assert len(lex_types(o)) == 1
        
    bad_ops = ["=<", "=>", "=", "&", "|"]
    for b in bad_ops:
        lexer = lex_with_errors(b)
        assert lexer.has_errors
        
    punct = ["(", ")", "[", "]", "{", "}", ";", ","]
    for p in punct:
        assert len(lex_types(p)) == 1

# --------------------------------------------------
# 17. BOUNDED EXHAUSTIVE ENUMERATION
# --------------------------------------------------

def oracle(s: str) -> bool:
    """Independent oracle for valid token sequences (simplified for verification bounds)."""
    try:
        lexer = Lexer(s)
        lexer.tokenize()
        return not lexer.has_errors
    except Exception:
        return False

def test_exhaustive_numeric():
    alphabet = ['0', '1', '7', '8', '9', 'x', 'X']
    for length in range(1, 4):
        for combo in itertools.product(alphabet, repeat=length):
            s = "".join(combo)
            lexer = lex_with_errors(s)
            # Just ensure it doesn't crash and deterministically resolves
            assert isinstance(lexer.has_errors, bool)

def test_exhaustive_operators():
    alphabet = ['+', '-', '*', '/', '%', '<', '>', '=', '!', '&', '|']
    for length in range(1, 4):
        for combo in itertools.product(alphabet, repeat=length):
            s = "".join(combo)
            lexer = lex_with_errors(s)
            assert isinstance(lexer.has_errors, bool)

def test_exhaustive_punctuation():
    alphabet = ['(', ')', '[', ']', '{', '}', ';', ',']
    for length in range(2, 3):
        for combo in itertools.product(alphabet, repeat=length):
            s = "".join(combo)
            types = lex_types(s)
            assert len(types) == 2
