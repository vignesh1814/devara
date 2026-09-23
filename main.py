"""Devara compiler CLI entry point."""

import sys
from pathlib import Path

from compiler.lexer import Lexer


def cmd_lex(filepath: str) -> int:
    """Tokenize a source file and print the token stream."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return 1

    source = path.read_text(encoding="utf-8")
    lexer = Lexer(source, filename=str(path))
    tokens = lexer.tokenize()

    if lexer.has_errors:
        for err in lexer.errors:
            print(err, file=sys.stderr)
        print(
            f"\n{len(lexer.errors)} lexer error(s) found.", file=sys.stderr
        )
        return 1

    for tok in tokens:
        print(tok)

    # Summary (excluding EOF)
    count = len(tokens) - 1
    print(f"\n--- {count} token(s) + EOF ---")
    return 0


def cmd_parse(filepath: str) -> int:
    """Parse a source file and print the AST."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return 1

    source = path.read_text(encoding="utf-8")
    lexer = Lexer(source, filename=str(path))
    tokens = lexer.tokenize()

    if lexer.has_errors:
        print("Lexer errors must be fixed before parsing:", file=sys.stderr)
        for err in lexer.errors:
            print(err, file=sys.stderr)
        return 1

    from compiler.parser import Parser
    import pprint
    from dataclasses import asdict

    parser = Parser(tokens, filename=str(path))
    ast = parser.parse()

    if parser.errors:
        for err in parser.errors:
            print(err, file=sys.stderr)
        print(
            f"\n{len(parser.errors)} parser error(s) found.", file=sys.stderr
        )
        return 1

    pprint.pprint(asdict(ast), indent=2)
    return 0


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python main.py <command> <filename>", file=sys.stderr)
        print("Commands: lex, parse", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    if command == "lex":
        sys.exit(cmd_lex(sys.argv[2]))
    elif command == "parse":
        sys.exit(cmd_parse(sys.argv[2]))
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Available commands: lex, parse", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
