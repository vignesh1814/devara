from _rt import *
t = tokens(); q = int(t[0])
for k in range(q):
    x = int(t[1+k]); s = str(x)
    out(sum(int(c) for c in s)); out(int(s[::-1])); out(b(s == s[::-1]))
for n in range(100, 1000):
    if sum(int(c)**3 for c in str(n)) == n: out(n)
