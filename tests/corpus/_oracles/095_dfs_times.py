from _rt import *
sys.setrecursionlimit(10000)
t = tokens(); n, m = int(t[0]), int(t[1]); adj = [[0]*10 for _ in range(10)]
for i in range(m):
    u, v = int(t[2+2*i]), int(t[3+2*i]); adj[u][v] = adj[v][u] = 1
vis = [False]*10; disc = [0]*10; fin = [0]*10; clock = 0
def dfs(u):
    global clock
    vis[u] = True; clock += 1; disc[u] = clock; out(u)
    for v in range(n):
        if adj[u][v] == 1 and not vis[v]: dfs(v)
    clock += 1; fin[u] = clock
for r in range(n):
    if not vis[r]: dfs(r)
for i in range(n): out(disc[i]); out(fin[i])
