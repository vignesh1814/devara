from _rt import *
t = sys.stdin.read().split("\n"); q = int(t[0])
def bal(s):
    st = []
    for c in s:
        if c in "([{": st.append(c)
        elif c in ")]}":
            if not st: return False
            o = st.pop()
            if {")": "(", "]": "[", "}": "{"}[c] != o: return False
    return not st
for k in range(q): out(b(bal(t[1+k])))
