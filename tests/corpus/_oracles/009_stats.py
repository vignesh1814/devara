from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
out(min(a)); out(max(a)); out(sum(a)); out(g(sum(a)/n))
mx = max(a); seen = False; second = 0
for x in a:
    if x != mx and (not seen or x > second):
        second = x; seen = True
out(b(seen)); out(second)
