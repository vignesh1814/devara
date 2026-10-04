from _rt import *
def factor(n):
    phi = n; p = 2
    while p*p <= n:
        if n % p == 0:
            e = 0
            while n % p == 0: n //= p; e += 1
            out(p); out(e); phi = phi // p * (p-1)
        p += 1
    if n > 1:
        out(n); out(1); phi = phi // n * (n-1)
    out(phi)
t = tokens(); q = int(t[0])
for k in range(q): factor(int(t[1+k]))
