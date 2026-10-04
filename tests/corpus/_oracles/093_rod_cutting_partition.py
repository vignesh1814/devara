from _rt import *
price = [0,1,5,8,9,10,17,17,20]; best = [0]*9
for ln in range(1, 9):
    for cut in range(1, ln+1):
        if price[cut]+best[ln-cut] > best[ln]: best[ln] = price[cut]+best[ln-cut]
    out(best[ln])
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]; total = sum(a)
can = [False]*201; can[0] = True
for x in a:
    for s in range(200, x-1, -1):
        if can[s-x]: can[s] = True
out(b(total % 2 == 0 and can[total//2]))
