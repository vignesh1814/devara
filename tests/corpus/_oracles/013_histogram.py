from _rt import *
t = tokens(); n = int(t[0]); cnt = [0]*10
for v in t[1:1+n]: cnt[int(v)] += 1
for d in range(10):
    out(cnt[d]); out("*"*cnt[d])
