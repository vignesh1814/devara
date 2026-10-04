from _rt import *
for v in (15, 15, 15, 54321, 54321, 18): out(v)
for _ in range(5): out(0)          # a[0]++ : 0..4, prints c==0
for _ in range(3): out(0)          # ++a[1]
for v in (3, 2, 1): out(v)         # a[2]-- loop prints before decrement
for v in (3, 2): out(v)            # --a[3] loop
for v in (5, 3, 0, 1): out(v)      # final a[0..3]
for f in (0.5, 1.5, 2.5): out(g(f))
for ch in "abcde": out(ch)
for v in (3, 2, 1): out(v)
for r in range(-2, 2): out(r)
