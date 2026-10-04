from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]; q = int(t[1+n])
for k in range(q):
    key = int(t[2+n+k])
    out(a.index(key) if key in a else -1)
