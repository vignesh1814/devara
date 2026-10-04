"""Independent Python model of Devara runtime values, used to compute expected results by hand-written lambdas."""
MASK = (1 << 64) - 1
INT_MIN = -(1 << 63)
INT_MAX = (1 << 63) - 1


def wrap(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def trem(a, b):
    return a - tdiv(a, b) * b


def g(x):
    return "%g" % x


def nb(x):
    return "nijam" if x else "abaddham"


def s8(x):
    x &= 255
    return x - 256 if x >= 128 else x
