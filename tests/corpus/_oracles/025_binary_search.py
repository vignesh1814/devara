from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
def bs(a, n, key):
    l, r = 0, n-1
    while l <= r:
        mid = l + (r-l)//2
        if a[mid] == key: return mid
        elif a[mid] < key: l = mid+1
        else: r = mid-1
    return -1
for k in range(q): out(bs(a, n, int(t[2+n+k])))
