from _rt import *
def shift(s, k):
    r = ""
    for ch in s:
        c = ord(ch)
        if 97 <= c <= 122: c = (c-97+k) % 26 + 97
        elif 65 <= c <= 90: c = (c-65+k) % 26 + 65
        r += chr(c)
    return r
t = sys.stdin.read().split("\n"); k = int(t[0]); s = t[1]
e = shift(s, k)
out(e); out(shift(e, 26-k)); out(b(shift(e, 26-k) == s))
