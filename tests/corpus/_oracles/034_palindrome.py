from _rt import *
lines = sys.stdin.read().split("\n")
q = int(lines[0])
for k in range(q):
    w = lines[1+k]
    out(b(w == w[::-1]))
