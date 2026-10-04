from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
scratch = [0]*200
def ms(a, l, r):
    if r - l < 1: return 0
    mid = l + (r-l)//2
    inv = ms(a, l, mid) + ms(a, mid+1, r)
    i, j, k = l, mid+1, l
    while i <= mid and j <= r:
        if a[i] <= a[j]:
            scratch[k] = a[i]; i += 1
        else:
            scratch[k] = a[j]; j += 1; inv += mid - i + 1
        k += 1
    while i <= mid: scratch[k] = a[i]; i += 1; k += 1
    while j <= r: scratch[k] = a[j]; j += 1; k += 1
    for x in range(l, r+1): a[x] = scratch[x]
    return inv
out(ms(a, 0, n-1))
for v in a: out(v)
