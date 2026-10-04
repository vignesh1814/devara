from _rt import *
t = tokens(); n, target, limit = int(t[0]), int(t[1]), int(t[2]); a = [int(v) for v in t[3:3+n]]
total = hits = 0; best = 0
def go(i, s, p):
    global total, hits, best
    if i == n:
        total += 1
        if s == target: hits += 1
        if s <= limit and s > best: best = s
    else:
        go(i+1, s, p); go(i+1, s+a[i], p+1)
go(0, 0, 0)
out(total); out(hits); out(best)
for i in range(n):
    for j in range(i+1, n):
        if a[i]+a[j] == target: out(i); out(j)
