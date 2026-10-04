from _rt import *
for x in (0, 1):
    for y in (0, 1):
        p, q = bool(x), bool(y)
        out(b(p and q)); out(b(p or q)); out(b(p == q)); out(b(p != q)); out(b((not p) or q))
out(b(True or (False and False))); out(b((True or False) and False)); out(b((not False) == True))
out(b(not (False == True))); out(b((1 < 2) == (2 > 1))); out(b(int(3 > 2) > 1))
out(b(not 5)); out(b(not 0.0)); out(b(not 0)); out(-1); out(3); out(b(True == 1)); out(b(False == 0))
out(b(bool(2) and bool(3))); out(b(bool(0) or bool(0.5))); out(b(bool(97) and bool(0)))
