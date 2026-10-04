from _rt import *
t = tokens(); n = int(t[0]); keys = [int(v) for v in t[1:1+n]]; ids = [i+1 for i in range(n)]
def is_sorted(k, n):
    for i in range(n-1):
        if k[i] > k[i+1]: return False
    return True
out(b(is_sorted(keys, n)))
for i in range(1, n):
    k, d = keys[i], ids[i]; j = i-1
    while j >= 0 and keys[j] > k:
        keys[j+1] = keys[j]; ids[j+1] = ids[j]; j -= 1
    keys[j+1] = k; ids[j+1] = d
for i in range(n):
    out(keys[i]); out(ids[i])
out(b(is_sorted(keys, n)))
