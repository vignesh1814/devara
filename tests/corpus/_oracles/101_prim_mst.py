from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); w = [[0]*10 for _ in range(10)]
for i in range(m):
    u, v, c = (int(x) for x in t[2+3*i:5+3*i]); w[u][v] = c; w[v][u] = c
INF = 1000000000; key = [INF]*n; par = [-1]*n; ins = [False]*n; key[0] = 0; total = 0; added = []
for _ in range(n):
    u = -1
    for i in range(n):
        if not ins[i] and (u == -1 or key[i] < key[u]): u = i
    ins[u] = True; total += key[u]
    if par[u] != -1: added.append(u)
    for v in range(n):
        if w[u][v] > 0 and not ins[v] and w[u][v] < key[v]: key[v] = w[u][v]; par[v] = u
out(total)
for a in added: out(par[a]); out(a)
