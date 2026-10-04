from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); w = [[0]*10 for _ in range(10)]; INF = 1000000000
for i in range(m):
    u, v, c = (int(x) for x in t[2+3*i:5+3*i]); w[u][v] = c; w[v][u] = c
src, dst = int(t[2+3*m]), int(t[3+3*m])
dist = [INF]*n; pred = [-1]*n; done = [False]*n; dist[src] = 0
for _ in range(n):
    u = -1
    for i in range(n):
        if not done[i] and dist[i] < INF and (u == -1 or dist[i] < dist[u]): u = i
    if u == -1: break
    done[u] = True
    for v in range(n):
        if w[u][v] > 0 and dist[u]+w[u][v] < dist[v]: dist[v] = dist[u]+w[u][v]; pred[v] = u
for d in dist: out(-1 if d == INF else d)
path = []; cur = dst
if dist[dst] < INF:
    while cur != -1: path.append(cur); cur = pred[cur]
out(len(path))
for p in reversed(path): out(p)
