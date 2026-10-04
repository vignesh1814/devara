from _rt import *
import heapq
t = tokens(); q = int(t[0]); h = []
for k in range(q):
    v = int(t[1+k])
    if v == -1: out(heapq.heappop(h) if h else -1)
    else: heapq.heappush(h, v)
out(len(h))
