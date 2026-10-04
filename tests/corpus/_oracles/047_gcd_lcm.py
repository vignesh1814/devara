from _rt import *
import math
t = tokens(); q = int(t[0])
for k in range(q):
    x, y = int(t[1+2*k]), int(t[2+2*k])
    g_ = math.gcd(x, y)
    out(g_); out(x // g_ * y); out(x)
