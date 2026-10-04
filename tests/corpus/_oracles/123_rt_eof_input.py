from _rt import *
t = tokens(); s = 0
for i in range(5):
    if i >= len(t): rt_error("invalid input")
    s += int(t[i]); out(s)
