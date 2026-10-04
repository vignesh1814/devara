from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
a.reverse()
for x in a: out(x)
