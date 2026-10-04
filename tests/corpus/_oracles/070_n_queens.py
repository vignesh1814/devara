from _rt import *
n = int(tokens()[0]); col = [0]*16; first = [0]*16; sols = 0
def safe(row, c):
    for r in range(row):
        if col[r] == c: return False
        d = abs(col[r]-c)
        if d == row - r: return False
    return True
def solve(row):
    global sols
    if row == n:
        sols += 1
        if sols == 1:
            for i in range(n): first[i] = col[i]
    else:
        for c in range(n):
            if safe(row, c):
                col[row] = c; solve(row+1)
solve(0); out(sols)
for i in range(n): out(first[i])
