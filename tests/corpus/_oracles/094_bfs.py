from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); adj = [[0]*10 for _ in range(10)]
for i in range(m):
    u, v = int(t[2+2*i]), int(t[3+2*i]); adj[u][v] = adj[v][u] = 1
src = int(t[2+2*m]); dist = [-1]*n; dist[src] = 0; q = [src]; h = 0
while h < len(q):
    u = q[h]; h += 1; out(u)
    for v in range(n):
        if adj[u][v] == 1 and dist[v] == -1:
            dist[v] = dist[u]+1; q.append(v)
for d in dist: out(d)
