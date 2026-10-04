"""End-to-end integration tests for all Devara test programs."""

import glob
from pathlib import Path
import pytest

from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast.nodes import Program

ROOT_DIR = Path(__file__).parent.parent
PROGRAM_FILES = sorted(
    glob.glob(str(ROOT_DIR / "tests" / "programs" / "**" / "*.tel"), recursive=True)
    + glob.glob(str(ROOT_DIR / "examples" / "**" / "*.tel"), recursive=True)
)


@pytest.mark.parametrize("filepath", PROGRAM_FILES, ids=lambda p: Path(p).name)
def test_program_lex_and_parse_e2e(filepath: str):
    """Every test program must tokenize and parse with zero errors."""
    path = Path(filepath)
    source = path.read_text(encoding="utf-8")
    
    # 1. Lexer pass
    lexer = Lexer(source, filename=path.name)
    tokens = lexer.tokenize()
    assert not lexer.has_errors, f"Lexer errors in {path.name}: {[str(e) for e in lexer.errors]}"
    assert len(tokens) > 1, f"Expected non-empty token stream in {path.name}"
    
    # 2. Parser pass
    parser = Parser(tokens, filename=path.name)
    ast = parser.parse()
    assert not parser.errors, f"Parser errors in {path.name}: {[str(e) for e in parser.errors]}"
    assert isinstance(ast, Program), f"Expected Program AST root in {path.name}"
    assert len(ast.items) > 0, f"Expected non-empty AST in {path.name}"
