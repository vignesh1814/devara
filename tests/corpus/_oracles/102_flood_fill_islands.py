from _rt import *
sys.setrecursionlimit(10000)
t = tokens(); rows, cols = int(t[0]), int(t[1]); v = [int(x) for x in t[2:]]
g = [v[i*cols:(i+1)*cols] for i in range(rows)]
def fill(r, c):
    if r < 0 or c < 0 or r >= rows or c >= cols: return 0
    if g[r][c] != 1: return 0
    g[r][c] = 2
    return 1 + fill(r+1, c) + fill(r-1, c) + fill(r, c+1) + fill(r, c-1)
isl = lg = 0
for i in range(rows):
    for j in range(cols):
        if g[i][j] == 1:
            s = fill(i, j); isl += 1; lg = max(lg, s)
out(isl); out(lg)
