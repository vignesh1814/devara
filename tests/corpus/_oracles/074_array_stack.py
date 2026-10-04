from _rt import *
t = tokens(); p = 0
def nxt():
    global p
    v = int(t[p]); p += 1; return v
stack = []
q = nxt()
for _ in range(q):
    cmd = nxt()
    if cmd == 1: stack.append(nxt())
    elif cmd == 2: out(stack.pop())
    elif cmd == 3: out(b(len(stack) == 0))
    else: out(stack[-1])
out(len(stack))
stack = []
m = nxt()
for _ in range(m):
    tok = nxt()
    if tok >= 0: stack.append(tok)
    else:
        y = stack.pop(); x = stack.pop()
        stack.append(x+y if tok == -1 else x-y if tok == -2 else x*y if tok == -3 else tdiv(x, y))
out(stack.pop())
