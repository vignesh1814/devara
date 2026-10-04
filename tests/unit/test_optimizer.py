"""Phase 5: optimizer passes preserve behavior; float identities are never applied (L49)."""

import pytest

from compiler.ir import ir as I
from compiler.ir.printer import format_module
from compiler.ir.verify import verify_module
from compiler.opt import optimize
from compiler.opt import passes
from tests.helpers.pipeline import to_ir, run_ir

IT = I.IRType


def text(src, level=1):
    return format_module(to_ir(src, level))


def entry_instrs(src, level=1):
    m = to_ir(src, level)
    fn = [f for f in m.functions if f.name == I.ENTRY_FUNCTION][0]
    return [i for b in fn.blocks for i in b.instrs]


def main_instrs(body, level=1):
    """Instructions of a function whose body is ``body`` (locals are registers, so they optimize)."""
    m = to_ir("void m charya() {\n" + body + "\n}\nm()", level)
    fn = [f for f in m.functions if f.name == "m"][0]
    return [i for b in fn.blocks for i in b.instrs]


def count(instrs, cls):
    return sum(isinstance(i, cls) for i in instrs)


def test_constant_folding_and_propagation():
    t = text("2 * 3 + 4 ni chupi\n2 + 3 ni chupi")
    assert "rtcall dv_rt_output_i64(10)" in t and "rtcall dv_rt_output_i64(5)" in t
    ins = main_instrs("int x\nx lo 2 pettu\nint y\ny lo x * 3 pettu\ny ni chupi")
    assert count(ins, I.BinOp) == 0
    assert ins[0].args == [I.Const(IT.I64, 6)]


def test_local_constant_propagates_through_straight_line_code():
    ins = entry_instrs("""
int f charya() { int a\na lo 4 pettu\nint b\nb lo a + 1 pettu\nb * 2 ivvu }
f() ni chupi
""")
    m = to_ir("int f charya() { int a\na lo 4 pettu\nint b\nb lo a + 1 pettu\nb * 2 ivvu }\nf() ni chupi", 1)
    f = [x for x in m.functions if x.name == "f"][0]
    assert len(f.blocks) == 1 and f.blocks[0].instrs == []
    assert f.blocks[0].term == I.Return(I.Const(IT.I64, 10))


def test_branch_simplification_and_unreachable_block_elimination():
    t = text('nijam ayite { "yes" ni chupi } lekunte { "no" ni chupi }')
    assert "yes" in t and "no" not in t and "branch" not in t
    t = text('5 > 3 ayite { "yes" ni chupi } lekunte { "no" ni chupi }')
    assert "branch" not in t and "'no'" not in t
    t = text('0 unnanta varaku { "never" ni chupi }')
    assert "never" not in t


def test_copy_propagation_removes_copies():
    ins = entry_instrs("int a\na ni chaduvu\nint b\nb lo a pettu\nint c\nc lo b pettu\nc ni chupi")
    assert count(ins, I.Copy) == 0


def test_dead_code_elimination_keeps_effects():
    ins = main_instrs("int u\nu lo 1 + 2 pettu\nint v\nv lo u * 7 pettu\n\"x\" ni chupi", 1)
    assert all(not isinstance(i, I.BinOp) for i in ins)
    assert count(ins, I.RtCall) == 1


def test_calls_and_io_are_never_removed():
    src = "int f charya() { \"side\" ni chupi\n1 ivvu }\nint u\nu lo f() pettu\nint z\nz ni chaduvu"
    ins = entry_instrs(src)
    assert count(ins, I.Call) == 1
    assert any(isinstance(i, I.RtCall) and i.name == "dv_rt_input_i64" for i in ins)


def test_stores_are_never_removed():
    ins = entry_instrs("int g\ng lo 5 pettu")
    assert count(ins, I.Store) == 1


@pytest.mark.parametrize("expr", [
    "x + 0.0", "0.0 + x", "x - 0.0", "x * 1.0", "1.0 * x", "x / 1.0", "x * 0.0", "0.0 * x",
])
def test_no_float_algebraic_identities_l49(expr):
    src = f"float x\nx ni chaduvu\n{expr} ni chupi"
    m = to_ir(src, 1)
    fn = [f for f in m.functions if f.name == I.ENTRY_FUNCTION][0]
    binops = [i for b in fn.blocks for i in b.instrs if isinstance(i, I.BinOp)]
    assert len(binops) == 1 and binops[0].dst.type == IT.F64


def test_float_signed_zero_semantics_preserved():
    # -0.0 + 0.0 = +0.0 (so `x + 0.0 -> x` is invalid); both opt levels must agree.
    src = "float z\nz ni chaduvu\nz + 0.0 ni chupi\n-z ni chupi"
    a = run_ir(src, b"-0.0", 0)
    b = run_ir(src, b"-0.0", 1)
    assert a == b and a[0] == b"0\n0\n"


def test_integer_algebraic_identities_apply():
    ins = entry_instrs("int x\nx ni chaduvu\nx + 0 ni chupi\nx * 1 ni chupi\nx - 0 ni chupi\nx / 1 ni chupi\nx * 0 ni chupi")
    assert count(ins, I.BinOp) == 0


def test_float_division_by_zero_and_nan_are_not_folded():
    ins = entry_instrs("1.0 / 0.0 ni chupi\n0.0 / 0.0 ni chupi")
    assert count(ins, I.BinOp) == 2


def test_division_by_constant_zero_is_kept():
    ins = entry_instrs("int z\nz lo 5 / 0 pettu")
    assert count(ins, I.BinOp) == 1
    o, st, err = run_ir("int z\nz lo 5 / 0 pettu", b"", 1)
    assert st == 1 and "division by zero" in err


def test_safe_integer_division_folds():
    ins = entry_instrs("7 / 2 ni chupi\n7 % 4 ni chupi")
    assert count(ins, I.BinOp) == 0


def test_redundant_conversion_roundtrip_removed():
    body = "bool b\nb ni chaduvu\nint i\ni lo b pettu\nbool c\nc lo i pettu\nc ni chupi"
    ins = main_instrs(body)
    assert count(ins, I.Convert) == 0
    src = "void m charya() {\n" + body + "\n}\nm()"
    assert run_ir(src, b"1", 0) == run_ir(src, b"1", 1)


def test_constant_conditions_through_variables():
    t = text('void m charya() { int n\nn lo 3 pettu\nn > 5 ayite { "big" ni chupi } lekunte { "small" ni chupi } }\nm()')
    assert "big" not in t and "small" in t


def test_short_circuit_preserved_by_optimizer():
    src = 'int f charya() { "called" ni chupi\n1 ivvu }\n0 && f() ni chupi\n1 || f() ni chupi\nnijam && f() ni chupi'
    o, _, _ = run_ir(src, b"", 1)
    assert o.decode().split() == ["abaddham", "nijam", "called", "nijam"]
    assert run_ir(src, b"", 0) == run_ir(src, b"", 1)


def test_evaluation_order_preserved_by_optimizer():
    src = 'int f charya(int x) { x ni chupi\nx ivvu }\nf(1) + f(2) ni chupi'
    assert run_ir(src, b"", 1)[0].decode().split() == ["1", "2", "3"]


def test_optimizer_does_not_mutate_its_input_and_is_idempotent():
    m = to_ir("int a\na lo 2 * 3 pettu\na ni chupi", 0)
    before = format_module(m)
    once = optimize(m, 1)
    assert format_module(m) == before
    twice = optimize(once, 1)
    assert format_module(twice) == format_module(once)
    verify_module(once)


def test_o0_does_not_change_the_ir():
    m = to_ir("int a\na lo 2 * 3 pettu\na ni chupi", 0)
    assert format_module(optimize(m, 0)) == format_module(m)


PROGRAMS = [
    # (source, stdin)
    ("int n\nn ni chaduvu\nint s\ns lo 0 pettu\nprati i 1 nundi n + 1 varaku { s lo s + i * i pettu }\ns ni chupi", b"10"),
    ("int a[10]\nprati i 0 nundi 10 varaku { a[i] lo (i * 7) % 10 pettu }\n"
     "pratisari (int i lo 0 pettu; i < 10; i++) { pratisari (int j lo 0 pettu; j < 9 - i; j++) {"
     " a[j] > a[j + 1] ayite { int t\nt lo a[j] pettu\na[j] lo a[j + 1] pettu\na[j + 1] lo t pettu } } }\n"
     "prati k 0 nundi 10 varaku { a[k] ni chupi }", b""),
    ("int gcd charya(int a, int b) { b == 0 ayite { a ivvu } gcd(b, a % b) ivvu }\ngcd(48, 18) ni chupi\ngcd(17, 5) ni chupi", b""),
    ("float x\nx lo 1.0 pettu\nint i\ni lo 0 pettu\ni < 5 unnanta varaku { x lo x * 1.5 + 0.25 pettu\ni lo i + 1 pettu }\nx ni chupi", b""),
    ('padham s\ns lo "abc" pettu\nint i\ni lo podavu(s) - 1 pettu\ni >= 0 unnanta varaku { s[i] ni chupi\ni lo i - 1 pettu }', b""),
    ("bool p[30]\nprati i 2 nundi 30 varaku { p[i] lo nijam pettu }\n"
     "prati i 2 nundi 30 varaku { p[i] ayite { prati j i * i nundi 30 varaku { j % i == 0 ayite { p[j] lo abaddham pettu } } } }\n"
     "prati i 2 nundi 30 varaku { p[i] ayite { i ni chupi } }", b""),
    ("int x\nx ni chaduvu\nx > 3 && x < 10 || x == 100 ayite { \"in\" ni chupi } lekunte { \"out\" ni chupi }", b"100"),
    ("char c\nc lo 'a' pettu\nprati i 0 nundi 5 varaku { c ni chupi\nc lo c + 1 pettu }", b""),
]


@pytest.mark.parametrize("src,stdin", PROGRAMS)
def test_o0_and_o1_agree_on_programs(src, stdin):
    a = run_ir(src, stdin, 0)
    b = run_ir(src, stdin, 1)
    assert a == b
    assert a[1] == 0


def test_o1_reduces_instruction_count():
    src = PROGRAMS[0][0]
    n0 = sum(len(b.instrs) for f in to_ir(src, 0).functions for b in f.blocks)
    n1 = sum(len(b.instrs) for f in to_ir(src, 1).functions for b in f.blocks)
    assert n1 < n0
