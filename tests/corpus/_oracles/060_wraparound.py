from _rt import *
mx = INT_MAX; mn = INT_MIN
for v in (mx, mn, wrap(mx+1), wrap(mx+mx), wrap(mx*2), wrap(mx*mx), wrap(mn-1), wrap(mn*-1), wrap(mn*mn), trem(mn, -1), mn, tdiv(mn, 2), wrap(mn+mn), wrap(3037000500*3037000500), wrap(mx-mn), wrap(mn-mx)): out(v)
h = 7
for i in range(1, 60): h = wrap(h*31 + i)
out(h)
s = 1
for i in range(70): s = wrap(s*3)
out(s)
