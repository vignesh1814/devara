from _rt import *
D = "0123456789abcdef"
def to_base(n, base):
    if n == 0: return "0"
    s = ""
    while n > 0:
        s = D[n % base] + s; n //= base
    return s
def from_base(s, base):
    v = 0
    for c in s: v = wrap(v*base + D.index(c))
    return v
t = tokens(); q = int(t[0])
for k in range(q):
    x = int(t[1+k])
    out(to_base(x, 2)); out(to_base(x, 8)); out(to_base(x, 16))
    out(from_base(to_base(x, 16), 16)); out(b(from_base(to_base(x, 2), 2) == x))
