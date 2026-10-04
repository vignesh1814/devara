from _rt import *
def f(x): return (x-37)*(x-37)+5
lo_b, hi_b = -1000, 1000
while hi_b - lo_b > 2:
    m1 = lo_b + tdiv(hi_b-lo_b, 3); m2 = hi_b - tdiv(hi_b-lo_b, 3)
    if f(m1) < f(m2): hi_b = m2 - 1
    else: lo_b = m1 + 1
best = lo_b
for x in range(lo_b, hi_b+1):
    if f(x) < f(best): best = x
out(best); out(f(best))
thr = int(tokens()[0]); p = 1
while p <= thr: p *= 2
out(p)
