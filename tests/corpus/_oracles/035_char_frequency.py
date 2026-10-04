from _rt import *
s = sys.stdin.readline().rstrip("\n")
cnt = [0]*26
for ch in s:
    c = ch.lower()
    if 'a' <= c <= 'z': cnt[ord(c)-97] += 1
for k in range(26):
    if cnt[k] > 0:
        out(chr(97+k) + ":"); out(cnt[k])
