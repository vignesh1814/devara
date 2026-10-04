from _rt import *
t = tokens(); v = [int(x) for x in t]
A = [v[0:3], v[3:6], v[6:9]]; B = [v[9:12], v[12:15], v[15:18]]
def mm(X, Y): return [[sum(X[i][k]*Y[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
C = mm(A, B)
for i in range(3):
    for j in range(3): out(C[i][j])
out(C[0][0]+C[1][1]+C[2][2])
for j in range(3):
    for i in range(3): out(C[i][j])  # t[i][j] = c[j][i]
P = [row[:] for row in A]
P = [row[:] for row in A]
for step in range(1, 5):
    Bm = [row[:] for row in P]
    # mul() computes c = a * b with the global a (original A) and b (copy of p)
    P = mm(A, Bm)
out(P[0][0]); out(P[2][1])
