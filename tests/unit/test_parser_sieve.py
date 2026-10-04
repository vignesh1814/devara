"""Integration test — parse the canonical Sieve of Eratosthenes program."""

from pathlib import Path
import pytest

from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast.nodes import (
    Program,
    Declaration,
    Assignment,
    ForLoop,
    WhileLoop,
    IfStatement,
    Output,
    IncrementUpdate,
    AssignmentUpdate,
)

SIEVE_PATH = Path(__file__).parent.parent / "programs" / "sieve.tel"


@pytest.fixture
def parsed_sieve():
    source = SIEVE_PATH.read_text(encoding="utf-8")
    lexer = Lexer(source, filename="sieve.tel")
    tokens = lexer.tokenize()
    assert not lexer.has_errors

    parser = Parser(tokens, filename="sieve.tel")
    ast = parser.parse()
    return parser, ast


class TestParserSieveIntegration:
    """The canonical Sieve program must parse with zero errors."""

    def test_no_errors(self, parsed_sieve):
        parser, _ = parsed_sieve
        assert not parser.errors, f"Parser errors: {[str(e) for e in parser.errors]}"

    def test_top_level_items(self, parsed_sieve):
        _, ast = parsed_sieve
        assert isinstance(ast, Program)
        # sieve.tel structure:
        # 1. int n
        # 2. n ni chaduvu
        # 3. bool prime[n + 1]
        # 4. int i
        # 5. pratisari (init array)
        # 6. prime[0] = False
        # 7. prime[1] = False
        # 8. int p
        # 9. p = 2
        # 10. int j
        # 11. p * p <= n unnanta varaku
        # 12. pratisari (print primes)
        
        assert len(ast.items) == 12

    def test_for_loop_with_increment(self, parsed_sieve):
        _, ast = parsed_sieve
        # The first for loop is item 4 (0-indexed)
        loop1 = ast.items[4]
        assert isinstance(loop1, ForLoop)
        assert isinstance(loop1.update, IncrementUpdate)
        assert not loop1.update.prefix

    def test_standalone_while_loop(self, parsed_sieve):
        _, ast = parsed_sieve
        # The while loop is item 10 (0-indexed)
        while_loop = ast.items[10]
        assert isinstance(while_loop, WhileLoop)
        
        # Inside while loop:
        # prime[p] ayite { pratisari ... }
        # p lo p + 1 pettu
        assert len(while_loop.body.statements) == 2
        if_stmt = while_loop.body.statements[0]
        assert isinstance(if_stmt, IfStatement)
        
        inner_for = if_stmt.then_block.statements[0]
        assert isinstance(inner_for, ForLoop)
        assert isinstance(inner_for.update, AssignmentUpdate)

    def test_output_statement(self, parsed_sieve):
        _, ast = parsed_sieve
        # The last loop prints primes
        loop3 = ast.items[11]
        assert isinstance(loop3, ForLoop)
        
        if_stmt = loop3.body.statements[0]
        assert isinstance(if_stmt, IfStatement)
        
        output = if_stmt.then_block.statements[0]
        assert isinstance(output, Output)
