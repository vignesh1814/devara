from _rt import *
t = tokens(); r, c = int(t[0]), int(t[1]); v = [int(x) for x in t[2:]]
obs = [v[i*c:(i+1)*c] for i in range(r)]; cost = [v[r*c+i*c:r*c+(i+1)*c] for i in range(r)]
ways = [[0]*c for _ in range(r)]
for i in range(r):
    for j in range(c):
        if obs[i][j] == 1: continue
        if i == 0 and j == 0: ways[i][j] = 1
        else:
            if i > 0: ways[i][j] += ways[i-1][j]
            if j > 0: ways[i][j] += ways[i][j-1]
out(ways[r-1][c-1])
best = [[0]*c for _ in range(r)]
for i in range(r):
    for j in range(c):
        if i == 0 and j == 0: best[i][j] = cost[i][j]
        elif i == 0: best[i][j] = best[i][j-1] + cost[i][j]
        elif j == 0: best[i][j] = best[i-1][j] + cost[i][j]
        elif best[i-1][j] < best[i][j-1]: best[i][j] = best[i-1][j] + cost[i][j]
        else: best[i][j] = best[i][j-1] + cost[i][j]
out(best[r-1][c-1])
