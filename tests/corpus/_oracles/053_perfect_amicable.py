from _rt import *
def ds(n):
    if n == 1: return 0
    s = 1; i = 2
    while i*i <= n:
        if n % i == 0:
            s += i
            if i*i != n: s += n // i
        i += 1
    return s
for n in range(2, 10000):
    if ds(n) == n: out(n)
for a in range(2, 3000):
    bb = ds(a)
    if bb > a and ds(bb) == a: out(a); out(bb)
