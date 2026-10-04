from _rt import *
t = tokens(); n = int(t[0]); a = [int(x) for x in t[1:1+n]]
take = skip = 0
for x in a:
    ntake = skip + x; nskip = take
    if skip > nskip: nskip = skip
    take, skip = ntake, nskip
out(take if take > skip else skip)
mx = mn = ans = a[0]
for x in a[1:]:
    if x < 0: mx, mn = mn, mx
    mx = x if x > mx*x else mx*x
    mn = x if x < mn*x else mn*x
    if mx > ans: ans = mx
out(ans)
