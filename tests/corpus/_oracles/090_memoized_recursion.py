from _rt import *
memo = {}
def ways(n):
    if n < 0: return 0
    if n == 0: return 1
    if n not in memo: memo[n] = ways(n-1)+ways(n-2)+ways(n-3)
    return memo[n]
for n in range(1, 41, 3): out(ways(n))
cat = [0]*26; cat[0] = 1
for n in range(1, 26):
    for i in range(n): cat[n] += cat[i]*cat[n-1-i]
for n in range(26): out(cat[n])
