from _rt import *
counter = 0
def tick(v):
    global counter
    counter += 1; out(v); return v
out(tick(1) + tick(2) * tick(3))
out(tick(10) - tick(4) - tick(3))
out(b(bool(tick(0)) and bool(tick(5))))
out(b(bool(tick(1)) and bool(tick(2))))
out(b(bool(tick(1)) or bool(tick(9))))
out(b(bool(tick(0)) or bool(tick(7))))
x = tick(7); y = tick(8); z = tick(9); out(x*100+y*10+z)
out(tick(tick(2)+1))
p = tick(1); q = tick(2); r = tick(1); out(b((p < q) == r))
a = [0]*4
i = tick(1); a[i] = tick(5)
i = tick(0); a[i] = tick(2) + tick(1)
out(a[1]); out(a[0])
i = tick(2); a[i] = a[tick(1)] + a[tick(0)]
out(a[2])
out(b((not tick(0)) or (bool(tick(3)) and bool(tick(0)))))
out(counter)
