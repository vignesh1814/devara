from _rt import *
def steps(n):
    c = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3*n + 1
        c += 1
    return c
t = tokens(); q = int(t[0])
for k in range(q): out(steps(int(t[1+k])))
best = 0; arg = 1
for n in range(1, 3000):
    if steps(n) > best: best = steps(n); arg = n
out(arg); out(best)
