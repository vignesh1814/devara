from _rt import *
c = [[[i*100+j*10+k for k in range(5)] for j in range(4)] for i in range(3)]
out(sum(c[0][0])); out(sum(c[2][3])); out(sum(c[1][2][:3]))
for k in range(5): c[1][1][k] = 900+k
out(c[1][1][0]); out(c[1][1][4]); out(c[1][2][0]); out(c[1][0][4])
out(sum(sum(c[i][j]) for i in range(3) for j in range(4)))
n, m = (int(x) for x in tokens()[:2])
out(0)
g = [[i*m+j for j in range(m)] for i in range(n)]
for k in range(m): g[1][k] = 50+k
for i in range(n): out(sum(g[i]))
out(g[0][m-1] + g[1][0])
