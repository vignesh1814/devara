from _rt import *
import math
for i in range(15):
    out(math.comb(i, i//2)); out(2**i)
t = tokens(); q = int(t[0])
for k in range(q): out(math.comb(int(t[1+2*k]), int(t[2+2*k])))
