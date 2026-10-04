from _rt import *
t = tokens(); n = int(t[0]); tr = [int(v) for v in t[1:1+n]]
def pre(i):
    if i < n: out(tr[i]); pre(2*i+1); pre(2*i+2)
def ino(i):
    if i < n: ino(2*i+1); out(tr[i]); ino(2*i+2)
def post(i):
    if i < n: post(2*i+1); post(2*i+2); out(tr[i])
def height(i):
    if i >= n: return 0
    return max(height(2*i+1), height(2*i+2)) + 1
def leaf_sum(i):
    if i >= n: return 0
    if 2*i+1 >= n: return tr[i]
    return leaf_sum(2*i+1) + leaf_sum(2*i+2)
pre(0); ino(0); post(0); out(height(0)); out(leaf_sum(0))
