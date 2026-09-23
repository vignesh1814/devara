"""Comprehensive unit tests for the Devara lexer."""

import pytest  # type: ignore
from compiler.lexer import Lexer, Token, TokenType


def lex(source: str) -> list[Token]:
    """Helper — tokenize source, assert no errors, return tokens."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert not lexer.has_errors, f"Unexpected errors: {lexer.errors}"
    return tokens


def lex_types(source: str) -> list[TokenType]:
    """Helper — return just the token types (excluding EOF)."""
    return [t.type for t in lex(source) if t.type != TokenType.EOF]


def lex_with_errors(source: str) -> Lexer:
    """Helper — tokenize and return the lexer (errors expected)."""
    lexer = Lexer(source)
    lexer.tokenize()
    return lexer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keywords
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestKeywords:
    """All 26 keywords must be recognized."""

    @pytest.mark.parametrize(
        "keyword, expected_type",
        [
            ("int", TokenType.INT),
            ("float", TokenType.FLOAT),
            ("bool", TokenType.BOOL),
            ("char", TokenType.CHAR),
            ("padham", TokenType.PADHAM),
            ("void", TokenType.VOID),
            ("nijam", TokenType.NIJAM),
            ("abaddham", TokenType.ABADDHAM),
            ("ayite", TokenType.AYITE),
            ("lekunte", TokenType.LEKUNTE),
            ("unnanta", TokenType.UNNANTA),
            ("varaku", TokenType.VARAKU),
            ("prati", TokenType.PRATI),
            ("pratisari", TokenType.PRATISARI),
            ("nundi", TokenType.NUNDI),
            ("modhalu", TokenType.MODHALU),
            ("lo", TokenType.LO),
            ("pettu", TokenType.PETTU),
            ("ni", TokenType.NI),
            ("tho", TokenType.THO),
            ("chaduvu", TokenType.CHADUVU),
            ("chupi", TokenType.CHUPI),
            ("charya", TokenType.CHARYA),
            ("ivvu", TokenType.IVVU),
            ("aapu", TokenType.AAPU),
            ("saagu", TokenType.SAAGU),
        ],
    )
    def test_keyword(self, keyword: str, expected_type: TokenType):
        tokens = lex(keyword)
        assert tokens[0].type == expected_type
        assert tokens[0].lexeme == keyword

    @pytest.mark.parametrize(
        "variant",
        ["Int", "INT", "iNt", "Ayite", "AYITE", "Pettu", "PETTU"],
    )
    def test_case_insensitive(self, variant: str):
        """Keywords are case-insensitive."""
        tokens = lex(variant)
        assert tokens[0].type != TokenType.IDENTIFIER

    def test_all_keywords_on_one_line(self):
        source = "int float bool char padham void nijam abaddham ayite lekunte unnanta varaku prati pratisari nundi modhalu lo pettu ni tho chaduvu chupi charya ivvu aapu saagu"
        types = lex_types(source)
        assert len(types) == 26
        assert TokenType.IDENTIFIER not in types


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Identifiers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestIdentifiers:
    @pytest.mark.parametrize(
        "name",
        ["n", "prime", "student1", "total_sum", "matrix", "i", "j"],
    )
    def test_identifier(self, name: str):
        tokens = lex(name)
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].lexeme == name

    def test_keyword_prefix_is_identifier(self):
        """'integer' is an identifier, not keyword 'int'."""
        tokens = lex("integer")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].lexeme == "integer"

    def test_keyword_suffix_is_identifier(self):
        """'floating' is an identifier, not keyword 'float'."""
        tokens = lex("floating")
        assert tokens[0].type == TokenType.IDENTIFIER

    def test_underscore_start(self):
        tokens = lex("_private")
        assert tokens[0].type == TokenType.IDENTIFIER


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Integer Literals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestIntLiterals:
    @pytest.mark.parametrize("value", ["0", "1", "42", "100", "999"])
    def test_decimal(self, value: str):
        tokens = lex(value)
        assert tokens[0].type == TokenType.INT_LITERAL
        assert tokens[0].lexeme == value

    def test_hex_literal(self):
        tokens = lex("0xFF")
        assert tokens[0].type == TokenType.INT_LITERAL
        assert tokens[0].lexeme == "0xFF"

    def test_hex_uppercase(self):
        tokens = lex("0XAB")
        assert tokens[0].type == TokenType.INT_LITERAL

    def test_octal_literal(self):
        tokens = lex("077")
        assert tokens[0].type == TokenType.INT_LITERAL
        assert tokens[0].lexeme == "077"

    @pytest.mark.parametrize("bad_val", ["089", "09"])
    def test_bad_octal_error(self, bad_val: str):
        lexer = lex_with_errors(bad_val)
        assert lexer.has_errors
        assert "octal" in lexer.errors[0].message.lower()

    @pytest.mark.parametrize("val", ["00", "012", "077"])
    def test_octal_literals(self, val: str):
        tokens = lex(val)
        assert tokens[0].type == TokenType.INT_LITERAL
        assert tokens[0].lexeme == val


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Float Literals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFloatLiterals:
    @pytest.mark.parametrize("value", ["3.14", "0.5", "10.0"])
    def test_float(self, value: str):
        tokens = lex(value)
        assert tokens[0].type == TokenType.FLOAT_LITERAL
        assert tokens[0].lexeme == value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Character Literals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCharLiterals:
    def test_simple_char(self):
        tokens = lex("'A'")
        assert tokens[0].type == TokenType.CHAR_LITERAL
        assert tokens[0].lexeme == "'A'"

    def test_digit_char(self):
        tokens = lex("'7'")
        assert tokens[0].type == TokenType.CHAR_LITERAL

    def test_escape_newline(self):
        tokens = lex(r"'\n'")
        assert tokens[0].type == TokenType.CHAR_LITERAL

    def test_escape_tab(self):
        tokens = lex(r"'\t'")
        assert tokens[0].type == TokenType.CHAR_LITERAL

    def test_hex_escape(self):
        tokens = lex(r"'\x41'")
        assert tokens[0].type == TokenType.CHAR_LITERAL

    def test_unterminated_char_error(self):
        lexer = lex_with_errors("'A")
        assert lexer.has_errors
        assert "unterminated" in lexer.errors[0].message.lower()

    def test_empty_char_error(self):
        lexer = lex_with_errors("''")
        assert lexer.has_errors
        assert "empty" in lexer.errors[0].message.lower()

    def test_multi_char_error(self):
        lexer = lex_with_errors("'ab'")
        assert lexer.has_errors
        assert "multi" in lexer.errors[0].message.lower()

    def test_physical_newline_in_char_rejected(self):
        lexer = lex_with_errors("'\n'")
        assert lexer.has_errors
        assert "unterminated" in lexer.errors[0].message.lower() or "invalid" in lexer.errors[0].message.lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# String Literals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStringLiterals:
    def test_simple_string(self):
        tokens = lex('"Hello"')
        assert tokens[0].type == TokenType.STRING_LITERAL
        assert tokens[0].lexeme == '"Hello"'

    def test_string_with_spaces(self):
        tokens = lex('"Hello World"')
        assert tokens[0].type == TokenType.STRING_LITERAL

    def test_escape_newline(self):
        tokens = lex(r'"\n"')
        assert tokens[0].type == TokenType.STRING_LITERAL

    def test_escape_tab(self):
        tokens = lex(r'"\t"')
        assert tokens[0].type == TokenType.STRING_LITERAL

    def test_hex_escape(self):
        tokens = lex(r'"\x41"')
        assert tokens[0].type == TokenType.STRING_LITERAL

    def test_unterminated_string_error(self):
        lexer = lex_with_errors('"hello')
        assert lexer.has_errors
        assert "unterminated" in lexer.errors[0].message.lower()

    def test_unknown_escape_error(self):
        lexer = lex_with_errors(r'"\q"')
        assert lexer.has_errors
        assert "escape" in lexer.errors[0].message.lower()

    def test_physical_newline_in_string_rejected(self):
        lexer = lex_with_errors('"hello\nworld"')
        assert lexer.has_errors
        assert "unterminated" in lexer.errors[0].message.lower()

    def test_unterminated_string_before_newline_rejected(self):
        lexer = lex_with_errors('"hello\n')
        assert lexer.has_errors
        assert "unterminated" in lexer.errors[0].message.lower()

    def test_location_tracking_after_bad_string(self):
        # A bad string shouldn't break location tracking for the next line
        lexer = Lexer('"hello\nint n')
        tokens = lexer.tokenize()
        assert lexer.has_errors
        # The 'int' should be on line 2
        int_tok = tokens[1] if tokens[0].type == TokenType.STRING_LITERAL else tokens[0]
        # In our implementation BAD_STRING emits no token or emits something, wait, BAD_STRING actually emits nothing, just an error!
        # Actually it doesn't append a token. So the first token should be 'int'
        assert int_tok.type == TokenType.INT
        assert int_tok.line == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Operators
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestOperators:
    @pytest.mark.parametrize(
        "op, expected_type",
        [
            ("+", TokenType.PLUS),
            ("-", TokenType.MINUS),
            ("*", TokenType.STAR),
            ("/", TokenType.SLASH),
            ("%", TokenType.PERCENT),
            ("<", TokenType.LT),
            (">", TokenType.GT),
            ("<=", TokenType.LTE),
            (">=", TokenType.GTE),
            ("==", TokenType.EQEQ),
            ("!=", TokenType.NEQ),
            ("&&", TokenType.AND),
            ("||", TokenType.OR),
            ("!", TokenType.NOT),
        ],
    )
    def test_operator(self, op: str, expected_type: TokenType):
        tokens = lex(op)
        assert tokens[0].type == expected_type
        assert tokens[0].lexeme == op

    def test_multichar_before_single(self):
        """<= should be one LTE token, not LT + EQEQ."""
        types = lex_types("<=")
        assert types == [TokenType.LTE]

    def test_less_than_then_equals(self):
        """< == should be LT then EQEQ (with space)."""
        types = lex_types("< ==")
        assert types == [TokenType.LT, TokenType.EQEQ]

    @pytest.mark.parametrize("bad_op", ["=<", "=>", "=+", "=-", "="])
    def test_negative_operators_rejected(self, bad_op: str):
        """Ensure invalid operator sequences are rejected (e.g., MISMATCH on first char)."""
        lexer = lex_with_errors(bad_op)
        assert lexer.has_errors
        # The first character '=' or '!' should cause an unexpected character error
        # or similar, since they don't form valid operators on their own (except '!' which is valid, but '!+' might parse as NOT, then PLUS, which is fine).
        # But `=>` parses as '=' (error) then '>'.
        # We just want to ensure it doesn't parse as a single LTE or GTE token.
        types = [t.type for t in lexer._tokens if t.type != TokenType.EOF]
        assert TokenType.LTE not in types
        assert TokenType.GTE not in types
        assert TokenType.EQEQ not in types


class TestIncrementDecrement:
    def test_increment(self):
        types = lex_types("i++")
        assert types == [TokenType.IDENTIFIER, TokenType.INCREMENT]
        
    def test_prefix_increment(self):
        types = lex_types("++i")
        assert types == [TokenType.INCREMENT, TokenType.IDENTIFIER]
        
    def test_decrement(self):
        types = lex_types("i--")
        assert types == [TokenType.IDENTIFIER, TokenType.DECREMENT]
        
    def test_prefix_decrement(self):
        types = lex_types("--i")
        assert types == [TokenType.DECREMENT, TokenType.IDENTIFIER]
        
    def test_in_for_loop(self):
        types = lex_types("pratisari (i 2 tho modhalu; i <= n; i++) {")
        assert types == [
            TokenType.PRATISARI,
            TokenType.LPAREN,
            TokenType.IDENTIFIER,
            TokenType.INT_LITERAL,
            TokenType.THO,
            TokenType.MODHALU,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,
            TokenType.LTE,
            TokenType.IDENTIFIER,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,
            TokenType.INCREMENT,
            TokenType.RPAREN,
            TokenType.LBRACE,
        ]
        
    def test_regression_plus_minus(self):
        types = lex_types("i + 1; i - 1")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.PLUS,
            TokenType.INT_LITERAL,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,
            TokenType.MINUS,
            TokenType.INT_LITERAL,
        ]

    def test_regression_minus_minus_spaced(self):
        types = lex_types("a - -b")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.MINUS,
            TokenType.MINUS,
            TokenType.IDENTIFIER,
        ]



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Punctuation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPunctuation:
    @pytest.mark.parametrize(
        "punct, expected_type",
        [
            ("(", TokenType.LPAREN),
            (")", TokenType.RPAREN),
            ("[", TokenType.LBRACKET),
            ("]", TokenType.RBRACKET),
            ("{", TokenType.LBRACE),
            ("}", TokenType.RBRACE),
            (";", TokenType.SEMICOLON),
            (",", TokenType.COMMA),
        ],
    )
    def test_punctuation(self, punct: str, expected_type: TokenType):
        tokens = lex(punct)
        assert tokens[0].type == expected_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Comments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestComments:
    def test_full_line_comment(self):
        types = lex_types("# this is a comment")
        assert types == []

    def test_inline_comment(self):
        types = lex_types("int n # declare n")
        assert types == [TokenType.INT, TokenType.IDENTIFIER]

    def test_comment_does_not_eat_next_line(self):
        types = lex_types("# comment\nint n")
        assert types == [TokenType.INT, TokenType.IDENTIFIER]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Language constructs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAssignment:
    def test_x_lo_10_pettu(self):
        types = lex_types("x lo 10 pettu")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.LO,
            TokenType.INT_LITERAL,
            TokenType.PETTU,
        ]


class TestIO:
    def test_input(self):
        types = lex_types("n ni chaduvu")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.NI,
            TokenType.CHADUVU,
        ]

    def test_output(self):
        types = lex_types("n ni chupi")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.NI,
            TokenType.CHUPI,
        ]


class TestArrayAccess:
    def test_array_assignment(self):
        types = lex_types("prime[i] lo abaddham pettu")
        assert types == [
            TokenType.IDENTIFIER,
            TokenType.LBRACKET,
            TokenType.IDENTIFIER,
            TokenType.RBRACKET,
            TokenType.LO,
            TokenType.ABADDHAM,
            TokenType.PETTU,
        ]


class TestPratisari:
    def test_for_loop_header(self):
        source = "pratisari (i 2 tho modhalu; i <= n; i lo i + 1 pettu)"
        types = lex_types(source)
        assert types == [
            TokenType.PRATISARI,
            TokenType.LPAREN,
            TokenType.IDENTIFIER,       # i
            TokenType.INT_LITERAL,       # 2
            TokenType.THO,
            TokenType.MODHALU,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,       # i
            TokenType.LTE,
            TokenType.IDENTIFIER,       # n
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,       # i
            TokenType.LO,
            TokenType.IDENTIFIER,       # i
            TokenType.PLUS,
            TokenType.INT_LITERAL,       # 1
            TokenType.PETTU,
            TokenType.RPAREN,
        ]

    def test_tho_modhalu_separate_tokens(self):
        """'tho modhalu' must remain two separate tokens."""
        types = lex_types("tho modhalu")
        assert types == [TokenType.THO, TokenType.MODHALU]

    def test_unnanta_varaku_separate_tokens(self):
        """'unnanta varaku' must remain two separate tokens."""
        types = lex_types("unnanta varaku")
        assert types == [TokenType.UNNANTA, TokenType.VARAKU]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Line & Column tracking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestLineColumn:
    def test_first_token_position(self):
        tokens = lex("int")
        assert tokens[0].line == 1
        assert tokens[0].column == 1

    def test_second_token_column(self):
        tokens = lex("int n")
        assert tokens[1].column == 5

    def test_multiline(self):
        tokens = lex("int n\nn ni chaduvu")
        # "n" on line 1
        assert tokens[1].line == 1
        # "n" on line 2
        assert tokens[2].line == 2
        assert tokens[2].column == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Error handling
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestErrors:
    def test_unexpected_character(self):
        lexer = lex_with_errors("@")
        assert lexer.has_errors
        assert "unexpected" in lexer.errors[0].message.lower()

    def test_error_recovery_multiple(self):
        """Multiple errors should all be collected."""
        lexer = lex_with_errors("@ $ ~")
        assert len(lexer.errors) == 3

    def test_error_line_column(self):
        lexer = lex_with_errors("int @")
        err = lexer.errors[0]
        assert err.line == 1
        assert err.column == 5


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Whitespace and EOF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWhitespace:
    def test_tabs_and_spaces(self):
        types = lex_types("int\t\tn")
        assert types == [TokenType.INT, TokenType.IDENTIFIER]

    def test_blank_lines(self):
        types = lex_types("int\n\n\nn")
        assert types == [TokenType.INT, TokenType.IDENTIFIER]


class TestEOF:
    def test_eof_always_emitted(self):
        tokens = lex("int")
        assert tokens[-1].type == TokenType.EOF

    def test_empty_input(self):
        tokens = lex("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF
