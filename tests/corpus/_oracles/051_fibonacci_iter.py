from _rt import *
a, b_ = 0, 1
for i in range(101):
    if i <= 10 or i >= 88: out(a)
    a, b_ = b_, wrap(a + b_)
