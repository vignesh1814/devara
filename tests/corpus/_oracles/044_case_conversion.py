from _rt import *
def up_(c): return chr(ord(c)-32) if 'a' <= c <= 'z' else c
def lo_(c): return chr(ord(c)+32) if 'A' <= c <= 'Z' else c
s = sys.stdin.readline().rstrip("\n")
up = low = tog = title = ""; start = True
for c in s:
    up += up_(c); low += lo_(c)
    tog += lo_(c) if up_(c) == c else up_(c)
    title += up_(c) if start else lo_(c)
    start = (c == ' ')
out(up); out(low); out(tog); out(title)
