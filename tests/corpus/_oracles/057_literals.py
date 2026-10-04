from _rt import *
for v in (0x1F, 0xFF, 0o17, 0o777, 0, 0, 0xdeadBEEF, 0x7FFFFFFFFFFFFFFF, 9223372036854775807, 0x10+0o10+10, 0xA*0o12): out(v)
out("A"); out("z"); out("Hi!"); out(3); out(ord("A")+1); out("B")
