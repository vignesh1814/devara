from _rt import *
m = [[i*5 + j*j - 3 for j in range(5)] for i in range(4)]
for i in range(4): out(sum(m[i]))
for j in range(5): out(sum(m[i][j] for i in range(4)))
out(sum(m[i][i] for i in range(4)))
out(sum(map(sum, m)))
