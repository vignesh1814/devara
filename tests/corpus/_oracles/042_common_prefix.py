from _rt import *
import os
t = sys.stdin.read().split("\n"); n = int(t[0]); words = t[1:1+n]
p = os.path.commonprefix(words)
out(p); out(len(p))
