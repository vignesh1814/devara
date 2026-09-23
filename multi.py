from compiler.lexer.lexer import Lexer
l = Lexer('"hello\nworld"')
print(l.tokenize())
print(l.errors)
