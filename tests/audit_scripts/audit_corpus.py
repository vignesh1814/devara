import os
from compiler.lexer.lexer import Lexer
import glob

files = glob.glob('tests/programs/**/*.tel', recursive=True) + \
        glob.glob('tests/programs/**/*.txt', recursive=True) + \
        glob.glob('*.tel')

for path in files:
    try:
        lexer = Lexer(open(path, encoding='utf-8').read(), path)
        tokens = lexer.tokenize()
        if lexer.has_errors:
            print(f"FAIL: {path} - {lexer.errors[0]}")
        else:
            print(f"PASS: {path} - {len(tokens)} tokens")
    except Exception as e:
        print(f"ERROR: {path} - {e}")
