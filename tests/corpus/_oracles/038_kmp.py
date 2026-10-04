from _rt import *
text = sys.stdin.readline().rstrip("\n"); pat = sys.stdin.readline().rstrip("\n")
n, m = len(text), len(pat); fail = [0]*m; k = 0
for i in range(1, m):
    while k > 0 and pat[i] != pat[k]: k = fail[k-1]
    if pat[i] == pat[k]: k += 1
    fail[i] = k
res = []; k = 0
for i in range(n):
    while k > 0 and text[i] != pat[k]: k = fail[k-1]
    if text[i] == pat[k]: k += 1
    if k == m:
        res.append(i-m+1); k = fail[k-1]
out(len(res))
for r in res: out(r)
for f in fail: out(f)
