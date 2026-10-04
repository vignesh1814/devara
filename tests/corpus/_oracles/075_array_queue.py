from _rt import *
t = tokens(); q = int(t[0]); buf = [0]*5; head = size = 0
for k in range(q):
    cmd = int(t[1+k])
    if cmd > 0:
        if size == 5: out(b(False))
        else:
            buf[(head+size) % 5] = cmd; size += 1; out(b(True))
    else:
        if size == 0: out(-1)
        else:
            v = buf[head]; head = (head+1) % 5; size -= 1; out(v)
out(size); out(head)
