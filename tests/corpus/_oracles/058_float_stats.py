from _rt import *
t = tokens(); n = int(t[0]); x = [float(v) for v in t[1:1+n]]
sm = 0.0
for v in x: sm = sm + v
mean = sm / n; var = 0.0
for v in x: var = var + (v-mean)*(v-mean)
var = var / n; s = var/2 + 1
for k in range(40): s = (s + var/s)/2
out(g(mean)); out(g(var)); out(g(s)); out(g(min(x))); out(g(max(x)))
for v in (1234567.0, 123456.0, 1.234/100000, 100.0, 3.0, -2.25, 1000000.0*1000000000, 2.0/3, 0.0001, 0.00001): out(g(v))
