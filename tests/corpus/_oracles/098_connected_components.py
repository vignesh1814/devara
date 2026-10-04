from _rt import *
sys.setrecursionlimit(10000)
t = tokens(); n, m = int(t[0]), int(t[1]); adj = [[0]*12 for _ in range(12)]
for i in range(m):
    u, v = int(t[2+2*i]), int(t[3+2*i]); adj[u][v] = 1; adj[v][u] = 1
label = [0]*12
def dfs(u, ident):
    label[u] = ident; size = 1
    for v in range(n):
        if adj[u][v] == 1 and label[v] == 0: size += dfs(v, ident)
    return size
comps = 0; sizes = []
for r in range(n):
    if label[r] == 0:
        comps += 1; sizes.append(dfs(r, comps))
for i in range(n): out(label[i])
out(comps)
for s in sizes: out(s)
out(max(sizes))
