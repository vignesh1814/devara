from _rt import *
t = tokens(); n = int(t[0]); target = int(t[1]); a = [int(x) for x in t[2:2+n]]
def has_pair(a, n, target):
    i, j = 0, n-1
    while i < j:
        if a[i]+a[j] == target: return True
        elif a[i]+a[j] < target: i += 1
        else: j -= 1
    return False
c = sum(1 for i in range(n) for j in range(i+1, n) if a[i]+a[j] == target)
out(b(has_pair(a, n, target))); out(b(has_pair(a, n, target+1000))); out(c)
