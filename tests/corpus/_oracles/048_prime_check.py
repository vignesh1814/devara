from _rt import *
def ip(n):
    if n < 2: return False
    i = 2
    while i*i <= n:
        if n % i == 0: return False
        i += 1
    return True
t = tokens(); q = int(t[0])
for k in range(q): out(b(ip(int(t[1+k]))))
out(sum(1 for i in range(2000) if ip(i)))
