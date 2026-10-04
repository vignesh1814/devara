"""Every bundled .tel program lexes, parses and satisfies the AST invariants."""

import glob
from pathlib import Path

import pytest

from compiler import serialize
from compiler.ast import nodes as ast_nodes
from compiler.ast.invariants import check_program
from compiler.ast.nodes import Program
from compiler.lexer import Lexer
from compiler.lexer import tokens as tokens_mod
from compiler.parser import Parser

ROOT_DIR = Path(__file__).parent.parent.parent
PROGRAM_FILES = sorted(
    glob.glob(str(ROOT_DIR / "tests" / "**" / "*.tel"), recursive=True)
    + glob.glob(str(ROOT_DIR / "examples" / "**" / "*.tel"), recursive=True)
)

serialize.register(tokens_mod, ast_nodes)


def parse_file(path: Path):
    source = path.read_bytes().decode("latin-1")
    lexer = Lexer(source, filename=path.name)
    tokens = lexer.tokenize()
    assert not lexer.has_errors, [str(e) for e in lexer.errors]
    parser = Parser(tokens, filename=path.name)
    return tokens, parser.parse(), parser.errors


@pytest.mark.parametrize("filepath", PROGRAM_FILES, ids=lambda p: Path(p).name)
def test_program_lex_parse_and_ast_invariants(filepath: str):
    path = Path(filepath)
    tokens, ast, errors = parse_file(path)
    assert len(tokens) > 1
    assert not errors, [str(e) for e in errors]
    assert isinstance(ast, Program) and ast.items
    assert check_program(ast) == []


@pytest.mark.parametrize("filepath", PROGRAM_FILES, ids=lambda p: Path(p).name)
def test_token_and_ast_json_round_trip(filepath: str):
    tokens, ast, _ = parse_file(Path(filepath))
    assert serialize.loads(serialize.dumps(tokens)) == tokens
    assert serialize.loads(serialize.dumps(ast)) == ast
    # a second round trip is byte-identical (deterministic output)
    assert serialize.dumps(ast) == serialize.dumps(serialize.loads(serialize.dumps(ast)))
