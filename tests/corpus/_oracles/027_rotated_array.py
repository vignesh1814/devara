from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
def sr(a, n, key):
    l, r = 0, n-1
    while l <= r:
        mid = (l+r)//2
        if a[mid] == key: return mid
        if a[l] <= a[mid]:
            if a[l] <= key and key < a[mid]: r = mid-1
            else: l = mid+1
        else:
            if a[mid] < key and key <= a[r]: l = mid+1
            else: r = mid-1
    return -1
for k in range(q): out(sr(a, n, int(t[2+n+k])))
