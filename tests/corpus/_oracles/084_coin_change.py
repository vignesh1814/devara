from _rt import *
t = tokens(); n = int(t[0]); coin = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
INF = 1000000000; minc = [INF]*101; ways = [0]*101; minc[0] = 0; ways[0] = 1
for a in range(1, 101):
    for c in coin:
        if c <= a and minc[a-c]+1 < minc[a]: minc[a] = minc[a-c]+1
for c in coin:
    for a in range(c, 101): ways[a] += ways[a-c]
for k in range(q):
    amt = int(t[2+n+k])
    out(-1 if minc[amt] >= INF else minc[amt]); out(ways[amt])
