from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
swaps = 0
for i in range(n-1):
    m = i
    for j in range(i+1, n):
        if a[j] < a[m]: m = j
    if m != i:
        a[i], a[m] = a[m], a[i]; swaps += 1
for k in range(n-1, -1, -1): out(a[k])
out(swaps)
