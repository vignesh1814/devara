from _rt import *
moves = 0
def hanoi(n, s, d, t):
    global moves
    if n > 0:
        hanoi(n-1, s, t, d); out(s*10+d); moves += 1; hanoi(n-1, t, d, s)
def count(n): return 0 if n == 0 else 2*count(n-1)+1
hanoi(4, 1, 3, 2); out(moves)
for n in range(1, 13): out(count(n))
