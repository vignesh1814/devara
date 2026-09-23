from compiler.lexer.lexer import Lexer

tests = [
    ("nundi", "keyword"),
    ("NUNDI", "different casing"),
    ("1abc", "starts with digit"),
    ("x", "single char"),
    ("x+1", "no spaces"),
    ("x+ 1", "space after"),
    ("x +1", "space before")
]

for name, desc in tests:
    l = Lexer(name)
    toks = l.tokenize()
    print(f"BCheck {desc}:")
    if l.has_errors:
        print(f"  ERR: {l.errors[0]}")
    else:
        print(f"  OK: {[t.type.value for t in toks[:-1]]}")
