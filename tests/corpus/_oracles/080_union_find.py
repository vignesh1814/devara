from _rt import *
t = tokens(); n, m = int(t[0]), int(t[1]); p = list(range(n)); sz = [1]*n
def find(x):
    while p[x] != x:
        p[x] = p[p[x]]; x = p[x]
    return x
def unite(a, b):
    a, b = find(a), find(b)
    if a != b:
        if sz[a] < sz[b]: a, b = b, a
        p[b] = a; sz[a] += sz[b]
k = 2
for _ in range(m):
    unite(int(t[k]), int(t[k+1])); k += 2
q = int(t[k]); k += 1
for _ in range(q):
    out(b(find(int(t[k])) == find(int(t[k+1])))); k += 2
roots = [i for i in range(n) if find(i) == i]
out(len(roots)); out(max(sz[i] for i in roots))
