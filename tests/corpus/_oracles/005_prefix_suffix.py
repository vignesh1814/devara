from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
pre = [0]*(n+1); suf = [0]*(n+1)
for i in range(n): pre[i+1] = pre[i] + a[i]
for j in range(n-1, -1, -1): suf[j] = suf[j+1] + a[j]
for x in pre: out(x)
for x in suf: out(x)
q = int(t[1+n]); p = 2+n
for _ in range(q):
    l, r = int(t[p]), int(t[p+1]); p += 2
    out(pre[r+1]-pre[l])
