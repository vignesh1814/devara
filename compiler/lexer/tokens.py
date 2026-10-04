"""Token type definitions and Token dataclass for the Devara lexer."""

from dataclasses import dataclass
from enum import StrEnum


class TokenType(StrEnum):
    """All token types recognized by the Devara lexer."""

    # ── Type keywords ──
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    CHAR = "CHAR"
    PADHAM = "PADHAM"
    VOID = "VOID"

    # ── Boolean literal keywords ──
    NIJAM = "NIJAM"
    ABADDHAM = "ABADDHAM"

    # ── Control flow ──
    AYITE = "AYITE"
    LEKUNTE = "LEKUNTE"

    # ── Loops ──
    UNNANTA = "UNNANTA"
    VARAKU = "VARAKU"
    PRATI = "PRATI"
    PRATISARI = "PRATISARI"
    NUNDI = "NUNDI"
    MODHALU = "MODHALU"

    # ── Postpositions ──
    LO = "LO"
    PETTU = "PETTU"
    NI = "NI"
    THO = "THO"

    # ── I/O ──
    CHADUVU = "CHADUVU"
    CHUPI = "CHUPI"

    # ── Functions ──
    CHARYA = "CHARYA"
    IVVU = "IVVU"

    # ── Flow control ──
    AAPU = "AAPU"
    SAAGU = "SAAGU"

    # ── Literals ──
    INT_LITERAL = "INT_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    CHAR_LITERAL = "CHAR_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"

    # ── Identifier ──
    IDENTIFIER = "IDENTIFIER"

    # ── Arithmetic operators ──
    PLUS = "PLUS"
    MINUS = "MINUS"
    INCREMENT = "INCREMENT"
    DECREMENT = "DECREMENT"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"

    # ── Comparison operators ──
    LT = "LT"
    GT = "GT"
    LTE = "LTE"
    GTE = "GTE"
    EQEQ = "EQEQ"
    NEQ = "NEQ"

    # ── Logical operators ──
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # ── Punctuation ──
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    SEMICOLON = "SEMICOLON"
    COMMA = "COMMA"

    # ── Special ──
    EOF = "EOF"


# Case-insensitive keyword lookup table (all keys are lowercase)
KEYWORDS: dict[str, TokenType] = {
    "int": TokenType.INT,
    "float": TokenType.FLOAT,
    "bool": TokenType.BOOL,
    "char": TokenType.CHAR,
    "padham": TokenType.PADHAM,
    "void": TokenType.VOID,
    "nijam": TokenType.NIJAM,
    "abaddham": TokenType.ABADDHAM,
    "ayite": TokenType.AYITE,
    "lekunte": TokenType.LEKUNTE,
    "unnanta": TokenType.UNNANTA,
    "varaku": TokenType.VARAKU,
    "prati": TokenType.PRATI,
    "pratisari": TokenType.PRATISARI,
    "nundi": TokenType.NUNDI,
    "modhalu": TokenType.MODHALU,
    "lo": TokenType.LO,
    "pettu": TokenType.PETTU,
    "ni": TokenType.NI,
    "tho": TokenType.THO,
    "chaduvu": TokenType.CHADUVU,
    "chupi": TokenType.CHUPI,
    "charya": TokenType.CHARYA,
    "ivvu": TokenType.IVVU,
    "aapu": TokenType.AAPU,
    "saagu": TokenType.SAAGU,
}


@dataclass(frozen=True, slots=True)
class Token:
    """A single lexical token produced by the Devara lexer."""

    type: TokenType
    lexeme: str
    line: int
    column: int

    @property
    def end_column(self) -> int:
        """Half-open end column (tokens never span lines)."""
        return self.column + len(self.lexeme)

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.lexeme!r}, {self.line}:{self.column})"
