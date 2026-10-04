from _rt import *
import math
t = tokens(); q = int(t[0])
for k in range(q):
    x = int(t[1+k])
    out(b(x >= 1 and (x & (x-1)) == 0)); pc = bin(x).count("1") if x > 0 else 0
    out(pc); out(b(pc % 2 == 1)); out(x.bit_length()-1 if x > 1 else 0)
    out(b(x >= 0 and math.isqrt(x)**2 == x))
