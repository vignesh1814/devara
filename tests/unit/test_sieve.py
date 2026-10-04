"""Integration test — tokenize the canonical Sieve of Eratosthenes program."""

from pathlib import Path

import pytest
from compiler.lexer import Lexer, TokenType

SIEVE_PATH = Path(__file__).parent / "programs" / "sieve.tel"

@pytest.fixture
def sieve_tokens():
    source = SIEVE_PATH.read_text(encoding="utf-8")
    lexer = Lexer(source, filename="sieve.tel")
    tokens = lexer.tokenize()
    return lexer, tokens


class TestSieveIntegration:
    """The canonical Sieve program must tokenize with zero errors."""

    def test_no_errors(self, sieve_tokens):
        lexer, _ = sieve_tokens
        assert not lexer.has_errors, (
            f"Lexer errors: {[str(e) for e in lexer.errors]}"
        )

    def test_ends_with_eof(self, sieve_tokens):
        _, tokens = sieve_tokens
        assert tokens[-1].type == TokenType.EOF

    def test_token_count(self, sieve_tokens):
        """Sanity check — Sieve program should produce a reasonable number of tokens."""
        _, tokens = sieve_tokens
        non_eof = [t for t in tokens if t.type != TokenType.EOF]
        # The sieve program has ~130-170 tokens depending on exact counting
        assert len(non_eof) > 80, f"Only {len(non_eof)} tokens — too few"

    def test_first_line_tokens(self, sieve_tokens):
        """Line 1: 'int n' → INT IDENTIFIER."""
        _, tokens = sieve_tokens
        assert tokens[0].type == TokenType.INT
        assert tokens[0].lexeme == "int"
        assert tokens[1].type == TokenType.IDENTIFIER
        assert tokens[1].lexeme == "n"

    def test_second_line_io(self, sieve_tokens):
        """Line 2: 'n ni chaduvu' → IDENTIFIER NI CHADUVU."""
        _, tokens = sieve_tokens
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].lexeme == "n"
        assert tokens[3].type == TokenType.NI
        assert tokens[4].type == TokenType.CHADUVU

    def test_pratisari_keyword_present(self, sieve_tokens):
        """Sieve contains 'pratisari' keywords."""
        _, tokens = sieve_tokens
        pratisari_tokens = [
            t for t in tokens if t.type == TokenType.PRATISARI
        ]
        assert len(pratisari_tokens) >= 3  # three for-loops in sieve

    def test_tho_and_modhalu_separate(self, sieve_tokens):
        """'tho modhalu' must always be two separate tokens."""
        _, tokens = sieve_tokens
        for i, t in enumerate(tokens):
            if t.type == TokenType.THO:
                assert tokens[i + 1].type == TokenType.MODHALU

    def test_unnanta_and_varaku_separate(self, sieve_tokens):
        """'unnanta varaku' must always be two separate tokens."""
        _, tokens = sieve_tokens
        unnanta_count = 0
        for i, t in enumerate(tokens):
            if t.type == TokenType.UNNANTA:
                unnanta_count += 1
                assert tokens[i + 1].type == TokenType.VARAKU
        assert unnanta_count == 1  # only in the standalone while loop

    def test_increment_token_present(self, sieve_tokens):
        """Sieve contains '++' tokens in pratisari updates."""
        _, tokens = sieve_tokens
        incr_tokens = [t for t in tokens if t.type == TokenType.INCREMENT]
        assert len(incr_tokens) == 2  # two i++ loops

    def test_no_combined_tokens(self, sieve_tokens):
        """Verify no accidental combined tokens leaked in."""
        _, tokens = sieve_tokens
        type_names = {t.type.value for t in tokens}
        # These should NOT exist as token types
        for forbidden in ["WHILE", "INPUT", "OUTPUT", "ASSIGN"]:
            assert forbidden not in type_names

    def test_full_token_type_sequence(self, sieve_tokens):
        """Verify the complete token type sequence for the first statement block."""
        _, tokens = sieve_tokens
        # First 5 tokens: int n \n n ni chaduvu
        expected_start = [
            TokenType.INT,          # int
            TokenType.IDENTIFIER,   # n
            TokenType.IDENTIFIER,   # n
            TokenType.NI,           # ni
            TokenType.CHADUVU,      # chaduvu
        ]
        actual = [t.type for t in tokens[:5]]
        assert actual == expected_start
