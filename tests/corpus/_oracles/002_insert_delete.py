from _rt import *
data = [0]*20; size = 0
def show(a, n):
    out(n)
    for i in range(n): out(a[i])
def insert_at(a, pos, v):
    global size
    k = size
    while k > pos:
        a[k] = a[k-1]; k -= 1
    a[pos] = v; size += 1
def delete_at(a, pos):
    global size
    for k in range(pos, size-1): a[k] = a[k+1]
    size -= 1
for i in range(6): insert_at(data, i, (i+1)*10)
show(data, size)
insert_at(data, 0, 5); insert_at(data, 3, 25); insert_at(data, size, 99)
show(data, size)
delete_at(data, 0); delete_at(data, 2); delete_at(data, size-1)
show(data, size)
