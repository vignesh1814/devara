from compiler.lexer.lexer import Lexer
l = Lexer('"hello\nworld"\nint n')
for t in l.tokenize():
    print(t)
