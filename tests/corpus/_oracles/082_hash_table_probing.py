from _rt import *
t = tokens(); q = int(t[0]); table = [-1]*17; count = 0
def slot(key):
    i = key % 17
    while table[i] != -1 and table[i] != key: i = (i+1) % 17
    return i
for k in range(q):
    op, key = int(t[1+2*k]), int(t[2+2*k])
    if op == 1:
        if count == 17: out(-2); continue
        s = slot(key)
        if table[s] == key: out(0); continue
        table[s] = key; count += 1; out(1)
    else:
        s = slot(key); out(s if table[s] == key else -1)
out(count)
