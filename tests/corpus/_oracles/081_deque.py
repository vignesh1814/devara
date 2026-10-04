from _rt import *
t = tokens(); q = int(t[0]); k = 1
buf = [0]*8; head = size = 0
for _ in range(q):
    cmd = int(t[k]); k += 1
    if cmd in (1, 2):
        v = int(t[k]); k += 1
        if size == 8: out(b(False))
        else:
            if cmd == 1:
                head = (head+7) % 8; buf[head] = v
            else:
                buf[(head+size) % 8] = v
            size += 1; out(b(True))
    elif cmd == 3:
        if size == 0: out(-1)
        else:
            out(buf[head]); head = (head+1) % 8; size -= 1
    else:
        if size == 0: out(-1)
        else:
            size -= 1; out(buf[(head+size) % 8])
