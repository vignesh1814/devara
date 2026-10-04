from _rt import *
t = tokens(); rows, cols = int(t[0]), int(t[1]); v = [int(x) for x in t[2:]]
wall = [v[i*cols:(i+1)*cols] for i in range(rows)]; dist = [[-1]*cols for _ in range(rows)]
q = []
if wall[0][0] == 0: q.append(0); dist[0][0] = 0
h = 0; dr = [-1, 1, 0, 0]; dc = [0, 0, -1, 1]
while h < len(q):
    cur = q[h]; h += 1; r, c = cur // cols, cur % cols
    for k in range(4):
        nr, nc = r+dr[k], c+dc[k]
        if 0 <= nr < rows and 0 <= nc < cols and wall[nr][nc] == 0 and dist[nr][nc] == -1:
            dist[nr][nc] = dist[r][c]+1; q.append(nr*cols+nc)
out(dist[rows-1][cols-1]); out(len(q))
