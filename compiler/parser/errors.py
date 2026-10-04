"""Parser error types: syntax errors are structured diagnostics."""

from compiler.diagnostics import Diagnostic, SyntaxCategory

# Backwards-compatible name: a parser error *is* a diagnostic (stage "syntax").
ParserError = Diagnostic
ParserDiagnostic = Diagnostic

__all__ = ["ParserError", "ParserDiagnostic", "SyntaxCategory"]
