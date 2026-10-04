from _rt import *
s = sys.stdin.readline().rstrip("\n"); n = len(s)
def expand(l, r):
    while l >= 0 and r < n and s[l] == s[r]: l -= 1; r += 1
    return r - l - 1
bs = bl = 0
for i in range(n):
    l1, l2 = expand(i, i), expand(i, i+1); l = max(l1, l2)
    if l > bl: bl = l; bs = i - (l-1)//2
out(s[bs:bs+bl]); out(bl)
dp = [[0]*n for _ in range(n)]
for i in range(n): dp[i][i] = 1
for ln in range(2, n+1):
    for i in range(n-ln+1):
        j = i+ln-1
        if s[i] == s[j]: dp[i][j] = (dp[i+1][j-1] if i+1 <= j-1 else 0) + 2
        elif dp[i+1][j] > dp[i][j-1]: dp[i][j] = dp[i+1][j]
        else: dp[i][j] = dp[i][j-1]
out(dp[0][n-1])
