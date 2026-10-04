from _rt import *
i = 0
while i < 10:
    i += 1
    if i % 2 == 0: continue
    if i > 7: break
    out(i)
for a in range(6):
    if a == 2: continue
    if a == 5: break
    out(a)
k = 0
while k < 8:
    if k == 3: k += 1; continue
    if k == 6: break
    out(k); k += 1
found = 0
for r in range(1, 10):
    if found == 0:
        for c in range(1, 10):
            if r*c == 42:
                out(r); out(c); found = 1; break
oc = ic = 0
for x in range(4):
    for y in range(4):
        if y > x: break
        ic += 1
    oc += 1
out(oc); out(ic)
