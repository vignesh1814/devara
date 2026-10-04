"""Exact Devara arithmetic helpers shared by semantic analysis and the optimizer.

``int`` is signed 64-bit two's complement (wrapping), ``float`` is IEEE-754
binary64, ``char`` is a signed 8-bit unit (L35–L40, P27, P28).
"""

from __future__ import annotations

import math
import struct

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


def wrap64(x: int) -> int:
    x &= (1 << 64) - 1
    return x - (1 << 64) if x >= (1 << 63) else x


def wrap8(x: int) -> int:
    x &= 0xFF
    return x - 256 if x >= 128 else x


def idiv(a: int, b: int) -> int:
    """C-style truncating division; caller must exclude b == 0 and the overflow case."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def irem(a: int, b: int) -> int:
    """C-style remainder (sign of dividend); caller must exclude b == 0."""
    if b == -1:
        return 0
    return a - idiv(a, b) * b


def float_to_int(x: float) -> int:
    """cvttsd2si semantics: truncate toward zero; NaN / out of range -> INT64_MIN."""
    if math.isnan(x) or math.isinf(x):
        return INT64_MIN
    t = math.trunc(x)
    if t < INT64_MIN or t > INT64_MAX:
        return INT64_MIN
    return t


def int_to_float(x: int) -> float:
    return float(x)


def f64(x: float) -> float:
    """Round a Python float to binary64 (identity; documents intent)."""
    return struct.unpack("<d", struct.pack("<d", x))[0]


def fdiv(a: float, b: float) -> float:
    """IEEE-754 division (no exception on zero divisor)."""
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return math.nan
        neg = (math.copysign(1.0, a) < 0) != (math.copysign(1.0, b) < 0)
        return -math.inf if neg else math.inf
    return a / b
