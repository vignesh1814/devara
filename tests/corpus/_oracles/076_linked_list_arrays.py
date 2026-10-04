from _rt import *
L = []
def show(): out(len(L)); [out(v) for v in L]
L.append(1); L.append(2); L.insert(0, 0); L.append(3); L.append(4); show()
for v in (2, 0, 99):
    if v in L: L.remove(v)
show(); L.reverse(); show(); L.insert(0, 7); L.remove(4); show()
