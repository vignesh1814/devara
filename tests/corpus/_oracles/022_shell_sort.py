from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
gap = n // 2
while gap > 0:
    for i in range(gap, n):
        tmp = a[i]; j = i
        while j >= gap and a[j-gap] > tmp:
            a[j] = a[j-gap]; j -= gap
        a[j] = tmp
    gap //= 2
for v in a: out(v)
