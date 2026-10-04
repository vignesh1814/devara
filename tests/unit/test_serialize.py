import json
from dataclasses import dataclass
from enum import StrEnum

from compiler import serialize
from compiler.lexer import Lexer
from compiler.lexer import tokens as tokens_mod


def test_token_list_round_trips():
    serialize.register(tokens_mod)
    toks = Lexer("int x\nx lo 1 pettu").tokenize()
    text = serialize.dumps(toks)
    assert serialize.loads(text) == toks


def test_enum_optional_and_nonfinite_float_round_trip():
    class Color(StrEnum):
        RED = "RED"

    @dataclass
    class Box:
        color: Color
        items: list[int]
        maybe: "Box | None"
        value: float

    import sys
    mod = sys.modules[__name__]
    Box.__module__ = mod.__name__
    globals()["Box"] = Box
    globals()["Color"] = Color
    serialize.register(mod)
    b = Box(Color.RED, [1, 2], Box(Color.RED, [], None, float("inf")), 1.5)
    out = serialize.loads(serialize.dumps(b))
    assert out == b
    json.loads(serialize.dumps(b))  # valid JSON even with inf


def test_format_tree_is_stable_and_indented():
    @dataclass
    class N:
        name: str
        kids: list

    out = serialize.format_tree(N("a", [N("b", [])]))
    assert out.splitlines()[0] == "N"
    assert "  name: 'a'" in out
