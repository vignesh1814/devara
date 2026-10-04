"""Shared diagnostics infrastructure: source spans, diagnostics, error types.

Every stage reports user-program errors as :class:`Diagnostic` values. A
diagnostic carries a *stage* (``lexical``, ``syntax`` or ``semantic``), a
category from the closed per-stage vocabulary (plan §E), a message and a
half-open source span.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Span:
    """Half-open source range ``[start, end)``; lines and columns are 1-based."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int

    @staticmethod
    def join(first: "Span", last: "Span") -> "Span":
        return Span(first.start_line, first.start_column, last.end_line, last.end_column)

    def contains(self, other: "Span") -> bool:
        return (
            (self.start_line, self.start_column) <= (other.start_line, other.start_column)
            and (other.end_line, other.end_column) <= (self.end_line, self.end_column)
        )

    def __str__(self) -> str:
        return (
            f"{self.start_line}:{self.start_column}-"
            f"{self.end_line}:{self.end_column}"
        )


class LexCategory(StrEnum):
    INVALID_CHARACTER = "INVALID_CHARACTER"
    UNTERMINATED_STRING = "UNTERMINATED_STRING"
    UNTERMINATED_CHAR = "UNTERMINATED_CHAR"
    INVALID_ESCAPE = "INVALID_ESCAPE"
    INVALID_CHAR_LITERAL = "INVALID_CHAR_LITERAL"
    INVALID_NUMBER = "INVALID_NUMBER"


class SyntaxCategory(StrEnum):
    UNEXPECTED_TOKEN = "UNEXPECTED_TOKEN"
    UNEXPECTED_EOF = "UNEXPECTED_EOF"
    MISSING_TOKEN = "MISSING_TOKEN"
    INVALID_EXPRESSION = "INVALID_EXPRESSION"
    INVALID_STATEMENT = "INVALID_STATEMENT"
    INVALID_DECLARATION = "INVALID_DECLARATION"


class SemCategory(StrEnum):
    UNDECLARED = "UNDECLARED"
    REDECLARATION = "REDECLARATION"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    INVALID_CONVERSION = "INVALID_CONVERSION"
    INVALID_OPERAND = "INVALID_OPERAND"
    NOT_ASSIGNABLE = "NOT_ASSIGNABLE"
    NOT_CALLABLE = "NOT_CALLABLE"
    NOT_INDEXABLE = "NOT_INDEXABLE"
    TOO_MANY_INDICES = "TOO_MANY_INDICES"
    ARGUMENT_COUNT = "ARGUMENT_COUNT"
    INVALID_RETURN = "INVALID_RETURN"
    MISSING_RETURN = "MISSING_RETURN"
    BREAK_OUTSIDE_LOOP = "BREAK_OUTSIDE_LOOP"
    CONTINUE_OUTSIDE_LOOP = "CONTINUE_OUTSIDE_LOOP"
    UNINITIALIZED = "UNINITIALIZED"
    VOID_MISUSE = "VOID_MISUSE"
    INVALID_ARRAY_SIZE = "INVALID_ARRAY_SIZE"
    LITERAL_OUT_OF_RANGE = "LITERAL_OUT_OF_RANGE"
    INVALID_CONDITION = "INVALID_CONDITION"


STAGES = ("lexical", "syntax", "semantic")


@dataclass(frozen=True)
class Diagnostic:
    """A user-program error with a category and a source span."""

    stage: str
    category: str
    message: str
    span: Span
    filename: str = "<stdin>"
    expected: tuple[str, ...] | None = None
    related: tuple[Span, ...] | None = None

    @property
    def line(self) -> int:
        return self.span.start_line

    @property
    def column(self) -> int:
        return self.span.start_column

    def format(self) -> str:
        return (
            f"{self.filename}:{self.line}:{self.column}: "
            f"{self.stage} error [{self.category}]: {self.message}"
        )

    def __str__(self) -> str:
        return self.format()


class DiagnosticError(Exception):
    """Raised by drivers when a stage finished with diagnostics."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__("\n".join(str(d) for d in diagnostics))


class InternalCompilerError(Exception):
    """A compiler bug (invariant violation, verifier failure, toolchain failure)."""
