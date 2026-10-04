"""Lexer error types: lexical errors are structured diagnostics."""

from compiler.diagnostics import Diagnostic, LexCategory

# Backwards-compatible name: a lexer error *is* a diagnostic (stage "lexical").
LexerError = Diagnostic

__all__ = ["LexerError", "LexCategory"]
