from compiler.lexer.lexer import Lexer

inputs = [
    "unnanta x <= 10 pettu;",
    "\"unterminated string",
    "'\\x'",
    "123abc456",
    "!@#$%^&*()_+",
    "x_lo_10_pettu",
    "/* block */",
    "// single",
    "unnantasomething",
    "  \t \n \r ",
    "",
    "0xGG",
    "099",
    "'\n'",
    "'a",
    "\"valid string\\n\"",
    "\"invalid\\escape\"",
    "0b1010",
    "nijamx",
    "0.0.1",
]

for i, inp in enumerate(inputs):
    lexer = Lexer(inp)
    tokens = lexer.tokenize()
    if lexer.has_errors:
        print(f"Fuzz {i}: {inp!r} - ERROR {lexer.errors[0]}")
    else:
        print(f"Fuzz {i}: {inp!r} - PASS {len(tokens)} tokens")
