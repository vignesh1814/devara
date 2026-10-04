from _rt import *
t = tokens(); n = int(t[0]); k = int(t[1]); a = [int(x) for x in t[2:2+n]]
k %= n
a = a[k:] + a[:k]
for x in a: out(x)
