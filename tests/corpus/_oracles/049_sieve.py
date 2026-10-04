from _rt import *
n = int(tokens()[0]); comp = [False]*(n+1); count = 0; last = 0
for i in range(2, n+1):
    if not comp[i]:
        count += 1; last = i
        for j in range(i*i, n+1, i): comp[j] = True
out(count)
for i in range(2, 50):
    if i <= n and not comp[i]: out(i)
out(last)
