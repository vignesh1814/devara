from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
low = mid = 0; high = n-1
while mid <= high:
    if a[mid] == 0:
        a[low], a[mid] = a[mid], a[low]; low += 1; mid += 1
    elif a[mid] == 1: mid += 1
    else:
        a[mid], a[high] = a[high], a[mid]; high -= 1
for v in a: out(v)
