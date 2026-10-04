from _rt import *
t = tokens(); nx = int(t[0]); ny = int(t[1])
x = [int(v) for v in t[2:2+nx]]; y = [int(v) for v in t[2+nx:2+nx+ny]]
m = []; i = j = 0
while i < nx and j < ny:
    if x[i] <= y[j]: m.append(x[i]); i += 1
    else: m.append(y[j]); j += 1
m += x[i:]; m += y[j:]
out(len(m))
for v in m: out(v)
