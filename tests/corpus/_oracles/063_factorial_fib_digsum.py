from _rt import *
sys.setrecursionlimit(100000)
def fact(n): return 1 if n <= 1 else wrap(n*fact(n-1))
def fib(n): return n if n < 2 else fib(n-1)+fib(n-2)
def digsum(n): return n if n < 10 else n % 10 + digsum(n//10)
t = tokens(); q = int(t[0])
for k in range(q):
    n = int(t[1+k]); out(fact(n)); out(fib(n)); out(digsum(fact(n)))
