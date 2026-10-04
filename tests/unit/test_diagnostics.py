from compiler.diagnostics import (
    Diagnostic, DiagnosticError, LexCategory, SemCategory, Span, SyntaxCategory,
)


def test_span_half_open_helpers():
    a = Span(1, 1, 1, 4)
    b = Span(1, 6, 2, 3)
    j = Span.join(a, b)
    assert j == Span(1, 1, 2, 3)
    assert j.contains(a) and j.contains(b) and not a.contains(j)


def test_diagnostic_format_matches_cli_contract():
    d = Diagnostic("syntax", SyntaxCategory.MISSING_TOKEN, "expected 'pettu'",
                   Span(4, 12, 4, 13), "f.tel")
    assert d.format() == "f.tel:4:12: syntax error [MISSING_TOKEN]: expected 'pettu'"
    assert (d.line, d.column) == (4, 12)


def test_category_vocabularies_are_closed_sets():
    assert {c.value for c in LexCategory} == {
        "INVALID_CHARACTER", "UNTERMINATED_STRING", "UNTERMINATED_CHAR",
        "INVALID_ESCAPE", "INVALID_CHAR_LITERAL", "INVALID_NUMBER"}
    assert {c.value for c in SyntaxCategory} == {
        "UNEXPECTED_TOKEN", "UNEXPECTED_EOF", "MISSING_TOKEN",
        "INVALID_EXPRESSION", "INVALID_STATEMENT", "INVALID_DECLARATION"}
    assert len(SemCategory) == 19


def test_diagnostic_error_carries_list():
    d = Diagnostic("semantic", SemCategory.UNDECLARED, "x", Span(1, 1, 1, 2))
    err = DiagnosticError([d])
    assert err.diagnostics == [d]
