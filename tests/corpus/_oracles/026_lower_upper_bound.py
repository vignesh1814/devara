from _rt import *
import bisect
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
for k in range(q):
    key = int(t[2+n+k]); lo = bisect.bisect_left(a, key); hi = bisect.bisect_right(a, key)
    out(lo); out(hi); out(hi-lo)
