from _rt import *
out(sum(range(10001))); out(1); out(1); out(2); out(19)
def pal(s, i, j):
    while i < j:
        if s[i] != s[j]: return False
        i += 1; j -= 1
    return True
out(b(pal("racecar", 0, 6))); out(b(pal("abca", 0, 3))); out(b(pal("x", 0, 0)))
import math
out(math.gcd(1071, 462)); out(math.gcd(17, 0))
