from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); E = [tuple(int(x) for x in t[2+3*i:5+3*i]) for i in range(m)]
src = int(t[2+3*m]); INF = 1000000000; dist = [INF]*n; dist[src] = 0
for _ in range(1, n):
    for u, v, w in E:
        if dist[u] < INF and dist[u]+w < dist[v]: dist[v] = dist[u]+w
neg = any(dist[u] < INF and dist[u]+w < dist[v] for u, v, w in E)
for d in dist: out(-1 if d == INF else d)
out(b(neg))
