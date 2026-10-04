from _rt import *
def enc(s):
    r = ""; i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i] and j - i < 9: j += 1
        r += s[i] + chr(48 + (j-i)); i = j
    return r
def dec(s):
    r = ""
    for i in range(0, len(s), 2): r += s[i] * (ord(s[i+1]) - 48)
    return r
s = sys.stdin.readline().rstrip("\n"); e = enc(s)
out(e); out(dec(e)); out(b(dec(e) == s))
