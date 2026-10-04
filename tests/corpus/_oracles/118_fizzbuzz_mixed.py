from _rt import *
for i in range(1, 31):
    out("FizzBuzz" if i % 15 == 0 else "Buzz" if i % 5 == 0 else "Fizz" if i % 3 == 0 else i)
for r in range(1, 5):
    for c in range(1, 5):
        if r == c: continue
        out(r*c)
