from _rt import *
t = tokens(); n = int(t[0]); cnt = [0]*100
for v in t[1:1+n]: cnt[int(v)] += 1
for v in range(100):
    for _ in range(cnt[v]): out(v)
