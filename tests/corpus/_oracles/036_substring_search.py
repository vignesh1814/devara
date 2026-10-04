from _rt import *
text = sys.stdin.readline().rstrip("\n"); pat = sys.stdin.readline().rstrip("\n")
n, m = len(text), len(pat)
idx = [i for i in range(n-m+1) if text[i:i+m] == pat]
out(len(idx))
for i in idx: out(i)
