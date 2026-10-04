from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
l, r = 0, n-1
while l < r:
    mid = (l+r)//2
    if a[mid] < a[mid+1]: l = mid+1
    else: r = mid
out(l); out(a[l])
