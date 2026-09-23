"""Deterministic regex-based lexer for the Devara language."""

from __future__ import annotations

import re
from compiler.lexer.errors import LexerError
from compiler.lexer.tokens import KEYWORDS, Token, TokenType

# ── Escape sequence map ──
_ESCAPE_MAP: dict[str, str] = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "0": "\0",
    "\\": "\\",
    "'": "'",
    '"': '"',
}

# ── Master regex (order matters — longest match first) ──
_TOKEN_SPEC: list[tuple[str, str]] = [
    ("COMMENT",     r"#[^\n]*"),
    ("WHITESPACE",  r"[ \t]+"),
    ("NEWLINE",     r"\n"),
    ("FLOAT_LIT",   r"\d+\.\d+"),
    ("HEX_INT",     r"0[xX][0-9a-fA-F]+"),
    ("OCT_INT",     r"0[0-7]+"),
    ("BAD_OCT",     r"0[0-9]+"),
    ("DEC_INT",     r"0|[1-9][0-9]*"),
    ("STRING",      r'"[^"\n\\]*(?:\\.[^"\n\\]*)*"'),
    ("BAD_STRING",  r'"[^"\n]*'),
    ("CHARLIT",     r"'[^'\n\\]'|'\\.[^'\n]*'|'\\x[0-9a-fA-F]{2}'"),
    ("BAD_CHAR",    r"'[^'\n]*'?"),
    ("IDENT",       r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("LTE",         r"<="),
    ("GTE",         r">="),
    ("EQEQ",        r"=="),
    ("NEQ",         r"!="),
    ("ANDAND",      r"&&"),
    ("OROR",        r"\|\|"),
    ("INCR",        r"\+\+"),
    ("DECR",        r"--"),
    ("PLUS",        r"\+"),
    ("MINUS",       r"-"),
    ("STAR",        r"\*"),
    ("SLASH",       r"/"),
    ("PERCENT",     r"%"),
    ("LT",          r"<"),
    ("GT",          r">"),
    ("NOT",         r"!"),
    ("LPAREN",      r"\("),
    ("RPAREN",      r"\)"),
    ("LBRACKET",    r"\["),
    ("RBRACKET",    r"\]"),
    ("LBRACE",      r"\{"),
    ("RBRACE",      r"\}"),
    ("SEMICOLON",   r";"),
    ("COMMA",       r","),
    ("MISMATCH",    r"."),
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC)
)

# ── Simple operator / punctuation map ──
_SIMPLE_TOKEN: dict[str, TokenType] = {
    "LTE": TokenType.LTE,
    "GTE": TokenType.GTE,
    "EQEQ": TokenType.EQEQ,
    "NEQ": TokenType.NEQ,
    "ANDAND": TokenType.AND,
    "OROR": TokenType.OR,
    "INCR": TokenType.INCREMENT,
    "DECR": TokenType.DECREMENT,
    "PLUS": TokenType.PLUS,
    "MINUS": TokenType.MINUS,
    "STAR": TokenType.STAR,
    "SLASH": TokenType.SLASH,
    "PERCENT": TokenType.PERCENT,
    "LT": TokenType.LT,
    "GT": TokenType.GT,
    "NOT": TokenType.NOT,
    "LPAREN": TokenType.LPAREN,
    "RPAREN": TokenType.RPAREN,
    "LBRACKET": TokenType.LBRACKET,
    "RBRACKET": TokenType.RBRACKET,
    "LBRACE": TokenType.LBRACE,
    "RBRACE": TokenType.RBRACE,
    "SEMICOLON": TokenType.SEMICOLON,
    "COMMA": TokenType.COMMA,
}


class Lexer:
    """Regex-based deterministic scanner for Devara source code."""

    def __init__(self, source: str, filename: str = "<stdin>") -> None:
        self._source = source
        self._filename = filename
        self._tokens: list[Token] = []
        self._errors: list[LexerError] = []
        self._line = 1
        self._col_offset = 0  # index of the start of the current line

    # ── Public API ──

    def tokenize(self) -> list[Token]:
        """Scan the source and return all tokens (ending with EOF)."""
        self._tokens = []
        self._errors = []
        self._line = 1
        self._col_offset = 0

        for mo in _MASTER_RE.finditer(self._source):
            kind = mo.lastgroup
            value = mo.group()
            start = mo.start()
            col = start - self._col_offset + 1

            if kind == "NEWLINE":
                self._line += 1
                self._col_offset = mo.end()
                continue

            if kind == "WHITESPACE" or kind == "COMMENT":
                continue

            if kind == "IDENT":
                kw = KEYWORDS.get(value.lower())
                if kw is not None:
                    self._tokens.append(Token(kw, value, self._line, col))
                else:
                    self._tokens.append(
                        Token(TokenType.IDENTIFIER, value, self._line, col)
                    )

            elif kind == "FLOAT_LIT":
                self._tokens.append(
                    Token(TokenType.FLOAT_LITERAL, value, self._line, col)
                )

            elif kind == "HEX_INT":
                self._tokens.append(
                    Token(TokenType.INT_LITERAL, value, self._line, col)
                )

            elif kind == "OCT_INT":
                self._tokens.append(
                    Token(TokenType.INT_LITERAL, value, self._line, col)
                )

            elif kind == "BAD_OCT":
                self._error(f"Invalid octal literal '{value}'", self._line, col)

            elif kind == "DEC_INT":
                self._tokens.append(
                    Token(TokenType.INT_LITERAL, value, self._line, col)
                )

            elif kind == "STRING":
                # Validate escape sequences inside the matched string
                self._validate_string(value, self._line, col)

            elif kind == "BAD_STRING":
                self._error("Unterminated string literal", self._line, col)

            elif kind == "CHARLIT":
                # Validate the character literal
                self._validate_char(value, self._line, col)

            elif kind == "BAD_CHAR":
                self._handle_bad_char(value, self._line, col)

            elif kind in _SIMPLE_TOKEN:
                self._tokens.append(
                    Token(_SIMPLE_TOKEN[kind], value, self._line, col)
                )

            elif kind == "MISMATCH":
                self._error(
                    f"Unexpected character {value!r}", self._line, col
                )

        # Always end with EOF
        eof_col = (
            len(self._source) - self._col_offset + 1
            if self._source
            else 1
        )
        self._tokens.append(
            Token(TokenType.EOF, "", self._line, eof_col)
        )
        return self._tokens

    @property
    def errors(self) -> list[LexerError]:
        return self._errors

    @property
    def has_errors(self) -> bool:
        return len(self._errors) > 0

    # ── Private helpers ──

    def _error(self, message: str, line: int, col: int) -> None:
        self._errors.append(LexerError(message, line, col, self._filename))

    def _validate_string(self, lexeme: str, line: int, col: int) -> None:
        """Validate escape sequences in a fully-matched string literal."""
        inner = lexeme[1:-1]  # strip surrounding quotes
        i = 0
        has_error = False
        while i < len(inner):
            if inner[i] == "\\":
                i += 1
                if i >= len(inner):
                    break
                esc = inner[i]
                if esc == "x":
                    hex_str = inner[i + 1 : i + 3]
                    if len(hex_str) == 2 and all(
                        c in "0123456789abcdefABCDEF" for c in hex_str
                    ):
                        i += 2
                    else:
                        esc_col = col + i
                        self._error(
                            "Invalid hex escape sequence", line, esc_col
                        )
                        has_error = True
                elif esc not in _ESCAPE_MAP:
                    esc_col = col + i
                    self._error(
                        f"Unknown escape sequence '\\{esc}'", line, esc_col
                    )
                    has_error = True
            i += 1

        if not has_error:
            self._tokens.append(
                Token(TokenType.STRING_LITERAL, lexeme, line, col)
            )
        else:
            # Still emit the token even with escape errors
            self._tokens.append(
                Token(TokenType.STRING_LITERAL, lexeme, line, col)
            )

    def _validate_char(self, lexeme: str, line: int, col: int) -> None:
        """Validate a character literal that the regex already matched."""
        inner = lexeme[1:-1]  # strip surrounding quotes

        if len(inner) == 0:
            self._error("Empty character literal", line, col)
            return

        if inner[0] == "\\":
            esc = inner[1] if len(inner) > 1 else ""
            if esc == "x":
                hex_str = inner[2:]
                if len(hex_str) == 2 and all(
                    c in "0123456789abcdefABCDEF" for c in hex_str
                ):
                    self._tokens.append(
                        Token(TokenType.CHAR_LITERAL, lexeme, line, col)
                    )
                else:
                    self._error("Invalid hex escape sequence", line, col + 1)
            elif esc in _ESCAPE_MAP:
                self._tokens.append(
                    Token(TokenType.CHAR_LITERAL, lexeme, line, col)
                )
            else:
                self._error(
                    f"Unknown escape sequence '\\{esc}'", line, col + 1
                )
        elif len(inner) == 1:
            self._tokens.append(
                Token(TokenType.CHAR_LITERAL, lexeme, line, col)
            )
        else:
            self._error("Multi-character character literal", line, col)

    def _handle_bad_char(self, lexeme: str, line: int, col: int) -> None:
        """Handle character literals that didn't match the valid pattern."""
        if not lexeme.endswith("'"):
            self._error("Unterminated character literal", line, col)
        elif lexeme == "''":
            self._error("Empty character literal", line, col)
        else:
            inner = lexeme[1:-1]
            if len(inner) > 1 and inner[0] != "\\":
                self._error("Multi-character character literal", line, col)
            else:
                self._error("Invalid character literal", line, col)
