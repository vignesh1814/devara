from _rt import *
A = [7, -7, 7, -7, 0, -1, 6, -9]; B = [2, 2, -2, -2, 5, 3, -3, 9]
for x, y in zip(A, B):
    out(tdiv(x, y)); out(trem(x, y)); out(b(x == tdiv(x, y)*y + trem(x, y)))
out(tdiv(-7, 2)); out(trem(-7, 2)); out(tdiv(7, -2) * -2)
