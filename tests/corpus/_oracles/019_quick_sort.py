from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
def partition(a, l, r):
    p = a[r]; s = l
    for j in range(l, r):
        if a[j] < p:
            a[s], a[j] = a[j], a[s]; s += 1
    a[s], a[r] = a[r], a[s]
    return s
def qs(a, l, r):
    if l < r:
        p = partition(a, l, r); qs(a, l, p-1); qs(a, p+1, r)
qs(a, 0, n-1)
for v in a: out(v)
