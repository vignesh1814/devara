from _rt import *
t = tokens(); n = int(t[0]); k = int(t[1]); a = [int(x) for x in t[2:2+n]]
s = sum(a[:k]); best = s; where = 0; big = 1 if s >= 15 else 0
for st in range(1, n-k+1):
    s += a[st+k-1] - a[st-1]
    if s > best: best = s; where = st
    if s >= 15: big += 1
out(best); out(where); out(big)
