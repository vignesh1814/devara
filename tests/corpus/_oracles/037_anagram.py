from _rt import *
lines = sys.stdin.read().split("\n"); q = int(lines[0])
for k in range(q):
    x, y = lines[1+2*k], lines[2+2*k]
    out(b(sorted(x) == sorted(y)))
