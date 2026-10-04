from _rt import *
def f(x): return x*x - 2
l, r = 1.0, 2.0
for i in range(40):
    m = (l+r)/2
    if f(m) > 0: r = m
    else: l = m
out(g(l)); out(g((l+r)/2)); out(g(f(1.5))); out(g(0.1+0.2)); out(g(1.0/3)); out(g(100000.0*10))
