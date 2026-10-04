from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
start, stop = 0, n-1; swapped = True
while swapped:
    swapped = False
    i = start
    while i < stop:
        if a[i] > a[i+1]:
            a[i], a[i+1] = a[i+1], a[i]; swapped = True
        i += 1
    if not swapped: break
    stop -= 1
    i = stop - 1
    while i >= start:
        if a[i] > a[i+1]:
            a[i], a[i+1] = a[i+1], a[i]; swapped = True
        i -= 1
    start += 1
for v in a: out(v)
