from _rt import *
m = [[i*5+j+1 for j in range(5)] for i in range(5)]
top, bottom, left, right = 0, 4, 0, 4
while top <= bottom and left <= right:
    for j in range(left, right+1): out(m[top][j])
    top += 1
    for i in range(top, bottom+1): out(m[i][right])
    right -= 1
    if top <= bottom:
        for j in range(right, left-1, -1): out(m[bottom][j])
        bottom -= 1
    if left <= right:
        for i in range(bottom, top-1, -1): out(m[i][left])
        left += 1
out(sum(m[i][i] for i in range(5))); out(sum(m[i][4-i] for i in range(5)))
