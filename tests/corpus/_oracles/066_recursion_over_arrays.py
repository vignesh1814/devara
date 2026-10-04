from _rt import *
t = tokens(); n = int(t[0]); a = [int(v) for v in t[1:1+n]]
def power(bs, e):
    if e == 0: return 1
    h = power(bs, e//2)
    if e % 2 == 0: return wrap(h*h)
    return wrap(wrap(h*h)*bs)
out(sum(a)); out(max(a)); out(sum(1 for x in a if x % 2 == 0))
for x in reversed(a): out(x)
for bs, e in ((2,10),(3,39),(3,40),(7,30),(-2,63),(5,0)): out(power(bs, e))
