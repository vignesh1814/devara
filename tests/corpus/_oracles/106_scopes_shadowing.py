from _rt import *
x = 100; y = 200
def show(px):
    out(px); px += 1; out(y); return px
def blocks():
    out(x); out(7); out(8); out(7); out(x); out(0); out(1); out(x); out(1); out(2)
def depth(n):
    local = n*10
    if n > 0: depth(n-1)
    out(local); return local
out(show(5)); out(x); blocks(); out(depth(2))
out(0); out(1); out(y)
