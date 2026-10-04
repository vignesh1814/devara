from _rt import *
def is_even(n): return True if n == 0 else is_odd(n-1)
def is_odd(n): return False if n == 0 else is_even(n-1)
def F(n): return 1 if n == 0 else n - M(F(n-1))
def M(n): return 0 if n == 0 else n - F(M(n-1))
for v in (is_even(10), is_odd(10), is_even(7), is_odd(7), is_even(0)): out(b(v))
for i in range(15): out(F(i))
for i in range(15): out(M(i))
