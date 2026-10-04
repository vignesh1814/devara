from _rt import *
def cmp(x, y):
    for i in range(min(len(x), len(y))):
        if x[i] < y[i]: return -1
        if x[i] > y[i]: return 1
    if len(x) < len(y): return -1
    if len(x) > len(y): return 1
    return 0
a = "apple"; w = a; w = w + "s"
out(a); out(w); out(b(a == w)); out(b(a != w)); out(b(a + "s" == w)); out(b("" + a == a))
out(cmp(a, w)); out(cmp(w, a)); out(cmp(a, "apple")); out(cmp("banana", "apple")); out(cmp("", "a"))
out(len(a + w)); out(len(""))
