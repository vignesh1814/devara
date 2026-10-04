from _rt import *
t = tokens(); n, cap = int(t[0]), int(t[1]); w = [int(x) for x in t[2:2+n]]; v = [int(x) for x in t[2+n:2+2*n]]
dp = [[0]*(cap+1) for _ in range(n+1)]
for i in range(1, n+1):
    for c in range(cap+1):
        dp[i][c] = dp[i-1][c]
        if w[i-1] <= c and dp[i-1][c-w[i-1]] + v[i-1] > dp[i][c]: dp[i][c] = dp[i-1][c-w[i-1]] + v[i-1]
out(dp[n][cap]); c = cap
for i in range(n, 0, -1):
    if dp[i][c] != dp[i-1][c]:
        out(i-1); c -= w[i-1]
