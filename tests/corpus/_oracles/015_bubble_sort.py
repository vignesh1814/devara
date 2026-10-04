from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
passes = 0; end = n-1
while True:
    swapped = False; passes += 1
    for j in range(end):
        if a[j] > a[j+1]:
            a[j], a[j+1] = a[j+1], a[j]; swapped = True
    if not swapped: break
    end -= 1
out(passes)
for v in a: out(v)
