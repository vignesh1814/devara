from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); INF = 1000000000
d = [[0 if i == j else INF for j in range(n)] for i in range(n)]
for i in range(m):
    u, v, c = (int(x) for x in t[2+3*i:5+3*i])
    if c < d[u][v]: d[u][v] = c
for k in range(n):
    for i in range(n):
        for j in range(n):
            if d[i][k] < INF and d[k][j] < INF and d[i][k]+d[k][j] < d[i][j]: d[i][j] = d[i][k]+d[k][j]
for i in range(n):
    for j in range(n): out(-1 if d[i][j] >= INF else d[i][j])
