from _rt import *
t = tokens(); out(int(t[0]))
try: int(t[1])
except ValueError: rt_error("invalid input")
