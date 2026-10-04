from _rt import *
s = "abc"; i = int(tokens()[0])
for k in range(i):
    if k >= len(s): rt_error("string index out of range")
    out(s[k])
