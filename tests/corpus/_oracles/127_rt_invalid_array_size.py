from _rt import *
t = tokens(); sizes = [int(t[0]), int(t[1])]
for k in range(2):
    if sizes[k] < 1:
        rt_error("invalid array size")
    out("ok")
out("end")
