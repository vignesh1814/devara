from _rt import *
s = sys.stdin.readline().rstrip("\n"); v = c = d = o = 0
for ch in s:
    ch = ch.lower()
    if ch in "aeiou": v += 1
    elif 'a' <= ch <= 'z': c += 1
    elif '0' <= ch <= '9': d += 1
    else: o += 1
out(v); out(c); out(d); out(o)
