from _rt import *
t = tokens(); p = 0
for g_ in range(2):
    n, m = int(t[p]), int(t[p+1]); p += 2
    adj = [[0]*10 for _ in range(10)]; indeg = [0]*10
    for i in range(m):
        u, v = int(t[p]), int(t[p+1]); p += 2; adj[u][v] = 1; indeg[v] += 1
    q = [i for i in range(n) if indeg[i] == 0]; h = 0; order = []
    while h < len(q):
        u = q[h]; h += 1; order.append(u)
        for v in range(n):
            if adj[u][v] == 1:
                indeg[v] -= 1
                if indeg[v] == 0: q.append(v)
    if len(order) == n:
        for o in order: out(o)
    else: out(-1)
