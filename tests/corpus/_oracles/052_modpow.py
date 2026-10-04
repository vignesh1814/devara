from _rt import *
t = tokens(); q = int(t[0])
for k in range(q):
    b0, e0, m0 = (int(x) for x in t[1+3*k:4+3*k])
    out(pow(b0, e0, m0)); inv = pow(b0, m0-2, m0); out(inv); out(inv*b0 % m0)
