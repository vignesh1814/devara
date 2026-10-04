from _rt import *
def edit(s, t):
    n, m = len(s), len(t); dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1] + (0 if s[i-1] == t[j-1] else 1))
    return dp[n][m]
L = sys.stdin.read().split("\n"); q = int(L[0])
for k in range(q): out(edit(L[1+2*k], L[2+2*k]))
