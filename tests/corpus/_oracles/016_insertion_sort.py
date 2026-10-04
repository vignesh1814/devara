from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
shifts = 0
for i in range(1, n):
    key = a[i]; j = i-1
    while j >= 0 and a[j] > key:
        a[j+1] = a[j]; j -= 1; shifts += 1
    a[j+1] = key
out(shifts)
for v in a: out(v)
