from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
def sift(a, start, end):
    root = start
    while root*2+1 <= end:
        child = root*2+1; swp = root
        if a[swp] < a[child]: swp = child
        if child+1 <= end and a[swp] < a[child+1]: swp = child+1
        if swp == root: break
        a[root], a[swp] = a[swp], a[root]; root = swp
s = (n-2)//2 if (n-2) >= 0 else -((-(n-2))//2)
while s >= 0:
    sift(a, s, n-1); s -= 1
e = n-1
while e > 0:
    a[0], a[e] = a[e], a[0]; sift(a, 0, e-1); e -= 1
for v in a: out(v)
