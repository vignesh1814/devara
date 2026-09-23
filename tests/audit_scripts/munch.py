from compiler.lexer.lexer import Lexer
inputs = [
    ("<= 1", "LTE"),
    ("< = 1", "LT EQ"),
    ("unnanta", "Keyword"),
    ("unnantasomething", "Identifier prefix"),
    ("nijamx", "Keyword suffix")
]
for inp, desc in inputs:
    l = Lexer(inp)
    toks = l.tokenize()
    print(f"Munch {desc}: {[t.type.value for t in toks[:-1]]}")
