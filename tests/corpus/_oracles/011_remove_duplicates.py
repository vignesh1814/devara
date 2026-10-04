from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
w = 1
for r in range(1, n):
    if a[r] != a[w-1]:
        a[w] = a[r]; w += 1
out(w)
for i in range(w): out(a[i])
