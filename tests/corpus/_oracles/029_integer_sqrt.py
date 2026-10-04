from _rt import *
import math
t = tokens(); q = int(t[0])
for k in range(q): out(math.isqrt(int(t[1+k])))
