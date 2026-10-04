from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
for k in range(q):
    key = int(t[2+n+k]); idx = [i for i in range(n) if a[i] == key]
    out(idx[0] if idx else -1); out(idx[-1] if idx else -1)
