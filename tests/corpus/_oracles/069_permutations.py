from _rt import *
import itertools
c = 0
for p in itertools.permutations(range(1, 5)):
    out(int("".join(map(str, p)))); c += 1
out(c)
c = 0
for p in itertools.permutations(range(1, 4)):
    out(int("".join(map(str, p)))); c += 1
out(c)
