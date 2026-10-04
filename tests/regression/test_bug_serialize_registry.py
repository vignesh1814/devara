"""Regression: AST ``Block`` and IR ``Block`` shared a class name, so IR JSON decoded into the
wrong class and `parse --json` / `ir --json` round trips failed in one process."""

import pytest

from compiler import driver, serialize
from tests.helpers.pipeline import to_ir, to_typed


def test_bug_ir_and_ast_json_round_trip_in_the_same_process():
    driver._register_serializable()
    src = "int a[2]\nnijam ayite { a[1] lo 3 pettu }\n"
    typed = to_typed(src)
    ir = to_ir(src, 1)
    assert serialize.loads(serialize.dumps(typed)) == typed
    assert serialize.loads(serialize.dumps(ir)) == ir


def test_bug_duplicate_class_names_are_rejected_at_registration():
    import types
    from dataclasses import dataclass

    mod = types.ModuleType("fake_stage")

    @dataclass
    class Program:        # same name as compiler.ast.nodes.Program
        x: int

    Program.__module__ = "fake_stage"
    mod.Program = Program
    driver._register_serializable()
    with pytest.raises(RuntimeError, match="duplicate class name"):
        serialize.register(mod)
