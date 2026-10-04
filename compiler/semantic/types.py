"""Semantic types of Devara (design §4.6).

``PrimType`` covers the six primitives (``void`` only as a function result) and
the internal ``error`` type used to suppress cascading diagnostics. ``ArrayType``
is a rank-n array (or a partial-index view); ``FuncType`` is a function
signature.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrimType:
    name: str  # int | float | bool | char | padham | void | error

    def compact(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class ArrayType:
    element: PrimType
    rank: int

    def compact(self) -> str:
        return f"{self.element.name}{'[]' * self.rank}"

    def __str__(self) -> str:
        return self.compact()


@dataclass(frozen=True)
class FuncType:
    params: tuple[ArrayType | PrimType, ...]
    ret: PrimType

    def compact(self) -> str:
        return f"({', '.join(str(p) for p in self.params)}) -> {self.ret}"

    def __str__(self) -> str:
        return self.compact()


Type = PrimType | ArrayType | FuncType

INT = PrimType("int")
FLOAT = PrimType("float")
BOOL = PrimType("bool")
CHAR = PrimType("char")
PADHAM = PrimType("padham")
VOID = PrimType("void")
ERROR = PrimType("error")

_BY_NAME = {t.name: t for t in (INT, FLOAT, BOOL, CHAR, PADHAM, VOID)}

ARITHMETIC = (BOOL, CHAR, INT, FLOAT)
INTEGRAL = (BOOL, CHAR, INT)


def prim(name: str) -> PrimType:
    return _BY_NAME[name]


def is_arithmetic(t: Type) -> bool:
    return t in ARITHMETIC


def is_integral(t: Type) -> bool:
    return t in INTEGRAL


def is_scalar(t: Type) -> bool:
    return isinstance(t, PrimType) and t not in (VOID, ERROR)


def promote(a: PrimType, b: PrimType) -> PrimType:
    """Usual arithmetic conversions (P28): float if either is float, else int."""
    return FLOAT if FLOAT in (a, b) else INT
