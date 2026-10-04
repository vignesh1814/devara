from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
best = cur = a[0]; bs = be = cs = 0
for i in range(1, n):
    if cur + a[i] < a[i]:
        cur = a[i]; cs = i
    else:
        cur = cur + a[i]
    if cur > best:
        best = cur; bs = cs; be = i
out(best); out(bs); out(be)
