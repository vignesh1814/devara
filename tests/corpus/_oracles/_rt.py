"""Helpers shared by the corpus oracles (independent Python models of Devara semantics).

Only implements the documented semantics: i64 wraparound (L37), truncating
division (P28), %g float output (P3), bool output (P4), runtime-error exit (P11).
"""
import sys

MASK = (1 << 64) - 1
INT_MIN = -(1 << 63)
INT_MAX = (1 << 63) - 1


def wrap(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


def tdiv(a, b):
    if b == 0:
        rt_error("division by zero")
    if a == INT_MIN and b == -1:
        rt_error("integer overflow in division")
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def trem(a, b):
    if b == 0:
        rt_error("remainder by zero")
    if b == -1:
        return 0
    r = abs(a) % abs(b)
    return -r if a < 0 else r


def g(x):
    """printf("%g")"""
    return "%g" % x


def b(x):
    return "nijam" if x else "abaddham"


def rt_error(msg):
    sys.stdout.flush()
    sys.stderr.write("devara: runtime error: %s\n" % msg)
    sys.exit(1)


def out(*a):
    sys.stdout.write("".join(str(x) for x in a) + "\n")


def tokens():
    return sys.stdin.read().split()
