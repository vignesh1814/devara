from _rt import *
sys.setrecursionlimit(10000)
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]; q = int(t[1+n])
def bs(l, r, key):
    if l > r: return -1
    mid = (l+r)//2
    if a[mid] == key: return mid
    if a[mid] < key: return bs(mid+1, r, key)
    return bs(l, mid-1, key)
for k in range(q): out(bs(0, n-1, int(t[2+n+k])))
