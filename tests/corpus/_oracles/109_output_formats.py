from _rt import *
for v in (-17, 0, INT_MIN): out(v)
for f in (3.14159265358979, 2.5, 1.0/3.0, 123456789.0, 0.000123456789): out(g(f))
out("inf"); out("-inf"); out(g(100.0**6)); out(g(0.1*3))
out(b(True)); out(b(False)); out(b(1 < 2))
for c in ("x", "\t", "\\", "'", '"'): out(c)
sys.stdout.write("plain text\n\ntab\there\nquote\"inside\nback\\slash\nline1\nline2\nsingle'quote\n")
sys.stdout.write("a\0b\n3\nABC\n\n")
