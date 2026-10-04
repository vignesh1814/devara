from _rt import *
import bisect
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
ln = [1]*n; prev = [-1]*n; best = 0; bi = 0
for i in range(n):
    for j in range(i):
        if a[j] < a[i] and ln[j]+1 > ln[i]: ln[i] = ln[j]+1; prev[i] = j
    if ln[i] > best: best = ln[i]; bi = i
out(best); seq = []; cur = bi
while cur != -1: seq.append(a[cur]); cur = prev[cur]
for x in reversed(seq): out(x)
tails = []
for x in a:
    p = bisect.bisect_left(tails, x)
    if p == len(tails): tails.append(x)
    else: tails[p] = x
out(len(tails))
