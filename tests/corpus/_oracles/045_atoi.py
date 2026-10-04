from _rt import *
def atoi(s):
    i = 0; sign = 1; v = 0
    while i < len(s) and s[i] == ' ': i += 1
    if i < len(s) and s[i] in "-+":
        if s[i] == '-': sign = -1
        i += 1
    while i < len(s) and '0' <= s[i] <= '9':
        v = v*10 + ord(s[i]) - 48; i += 1
    return sign*v
t = sys.stdin.read().split("\n"); q = int(t[0])
for k in range(q): out(atoi(t[1+k]))
