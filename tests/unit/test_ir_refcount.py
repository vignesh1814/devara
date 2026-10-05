"""IR-level contract of reference-counted padham (plan P22): ownership of temporaries, where
retain/release are emitted, the verifier's view of them and their treatment by the optimizer."""

import pytest

from compiler.diagnostics import InternalCompilerError
from compiler.ir import ir as I
from compiler.ir.runtime import MEMORY_EFFECTS, PURE, RUNTIME, has_side_effects
from compiler.ir.verify import check_module, verify_module
from tests.helpers.pipeline import to_ir

IT = I.IRType


def prog(*lines):
    return "\n".join(lines) + "\n"


def fn(m, name):
    return next(f for f in m.functions if f.name == name)


def calls(f):
    return [i for b in f.blocks for i in b.instrs if isinstance(i, I.RtCall)]


def names(f, only=None):
    return [c.name for c in calls(f) if only is None or c.name in only]


RC = {"dv_rt_retain", "dv_rt_release"}


# ── effect model / verifier ──

def test_refcount_and_allocation_calls_are_side_effecting_and_known_to_the_verifier():
    assert not (MEMORY_EFFECTS & PURE)
    assert MEMORY_EFFECTS <= set(RUNTIME)
    assert all(has_side_effects(n) for n in MEMORY_EFFECTS)
    assert RUNTIME["dv_rt_retain"] == ((IT.STR,), IT.VOID)
    assert RUNTIME["dv_rt_release"] == ((IT.STR,), IT.VOID)


def tiny(instrs, globals_=()):
    blk = I.BasicBlock("entry", instrs, I.Return(None))
    return I.IRModule(list(globals_), [I.IRFunction(I.ENTRY_FUNCTION, [], IT.VOID, [blk])])


def test_verifier_accepts_retain_and_release_of_str_registers():
    r = I.Reg("s", IT.STR)
    g = I.IRGlobal("null.str", IT.STR, "scalar", 1)
    m = tiny([I.Load(r, I.GlobalRef("null.str")), I.RtCall(None, "dv_rt_retain", [r]),
              I.RtCall(None, "dv_rt_release", [r]), I.RtCall(None, "dv_rt_release", [r])], [g])
    assert check_module(m) == []


def test_verifier_rejects_release_of_a_non_string_and_str_constants_outside_strlit():
    bad = tiny([I.RtCall(None, "dv_rt_release", [I.Const(IT.I64, 1)])])
    assert any("argument type" in e for e in check_module(bad))
    bad = tiny([I.RtCall(None, "dv_rt_output_str", [I.Const(IT.STR, b"x")])])
    assert any("str constant" in e for e in check_module(bad))
    r = I.Reg("t", IT.STR)
    ok = tiny([I.RtCall(r, "dv_rt_strlit", [I.Const(IT.STR, b"x")])])
    assert check_module(ok) == []
    with pytest.raises(InternalCompilerError):
        verify_module(bad)


# ── lowering ──

def test_string_literals_are_loaded_from_startup_initialized_globals():
    m = to_ir(prog('"hello" ni chupi', '"hello" ni chupi', '"" ni chupi'), 0)
    entry = fn(m, I.ENTRY_FUNCTION)
    assert names(entry)[:1] == ["dv_rt_strlit"] and names(entry).count("dv_rt_strlit") == 1
    assert {g.name for g in m.globals} == {"lit.0", "null.str"}
    assert not any(isinstance(o, I.Const) and o.type == IT.STR
                   for b in entry.blocks for i in b.instrs
                   if not (isinstance(i, I.RtCall) and i.name == "dv_rt_strlit")
                   for o in getattr(i, "args", []))


def test_concat_result_is_owned_and_released_after_its_single_use():
    m = to_ir(prog("padham a", "a lo \"x\" pettu", "a + a ni chupi"), 0)
    seq = names(fn(m, I.ENTRY_FUNCTION), RC | {"dv_rt_strcat", "dv_rt_output_str"})
    # a = "x": borrowed literal -> retain, old value released; output of an owned temp -> release
    assert seq == ["dv_rt_retain", "dv_rt_release", "dv_rt_strcat", "dv_rt_output_str",
                   "dv_rt_release", "dv_rt_release"]


def test_storing_an_owned_temporary_does_not_retain_and_releases_the_old_value():
    m = to_ir(prog("padham a", "a lo \"p\" + \"q\" pettu"), 0)
    seq = names(fn(m, I.ENTRY_FUNCTION), RC | {"dv_rt_strcat"})
    # the global's old value is released after the store; no retain of the owned concat result
    assert seq == ["dv_rt_strcat", "dv_rt_release", "dv_rt_release"]   # store-release, exit-release


def test_returning_a_borrowed_value_retains_it_before_the_scope_cleanups():
    src = prog("padham f charya (padham p) {", "  padham l", "  l lo p pettu", "  l ivvu", "}",
               "padham g charya (padham p) { p ivvu }", "f(\"a\") ni chupi")
    f = fn(to_ir(src, 0), "f")
    seq = names(f, RC)
    # l = p -> retain(p), release(old l); return l -> retain(l) THEN release(l) at scope exit
    assert seq == ["dv_rt_retain", "dv_rt_release", "dv_rt_retain", "dv_rt_release"]
    g = fn(to_ir(src, 0), "g")
    assert names(g, RC) == ["dv_rt_retain"]            # parameters are never released by the callee


def test_assigned_parameter_is_owned_by_the_callee():
    src = prog("padham f charya (padham p) { p lo p + p pettu  p ivvu }", "f(\"a\") ni chupi")
    f = fn(to_ir(src, 0), "f")
    seq = names(f, RC | {"dv_rt_strcat"})
    assert seq[0] == "dv_rt_retain" and seq[-1] == "dv_rt_release"


def test_memory_loads_are_borrowed_unless_a_call_can_intervene():
    pure = prog("padham a[2]", "padham x", "x lo a[0] pettu")
    with_call = prog("padham a[2]", "padham x", "padham id charya (padham p) { p ivvu }",
                     "x lo id(a[0]) pettu")
    n_pure = names(fn(to_ir(pure, 0), I.ENTRY_FUNCTION), RC).count("dv_rt_retain")
    n_call = names(fn(to_ir(with_call, 0), I.ENTRY_FUNCTION), RC).count("dv_rt_retain")
    assert n_pure == 1          # only the store's retain of the borrowed value
    assert n_call == 1          # arg retained (owned), call result owned: store takes it
    seq = names(fn(to_ir(with_call, 0), I.ENTRY_FUNCTION), RC | {"dv_rt_strcat"})
    assert seq.index("dv_rt_retain") < seq.index("dv_rt_release")


def test_padham_array_elements_are_released_at_scope_exit():
    src = prog("void f charya (int n) {", "  padham fr[3]", "  padham h[n]", "  fr[0] lo \"x\" pettu",
               "}", "f(2)")
    f = fn(to_ir(src, 0), "f")
    assert "dv_rt_release_elems" in names(f)       # frame array
    assert "dv_rt_freearray_str" in names(f)       # heap array: elements first, then the block


# ── optimizer ──

PROGRAMS = [
    prog("padham a", "padham b", "a lo \"x\" + \"y\" pettu", "b lo a pettu", "b + a ni chupi",
         "a lo \"\" pettu", "b ni chupi"),
    prog("padham f charya (padham p, int n) {", "  n == 0 ayite { p ivvu }",
         "  f(p + \"z\", n - 1) ivvu", "}", "f(\"a\", 4) ni chupi"),
    prog("padham arr[3]", "prati i 0 nundi 3 varaku { arr[i] lo arr[(i + 1) % 3] + \"k\" pettu }",
         "arr[2] ni chupi"),
]


@pytest.mark.parametrize("src", PROGRAMS)
def test_optimizer_keeps_every_retain_release_in_order_relative_to_other_runtime_calls(src):
    keep = RC | {"dv_rt_output_str", "dv_rt_strcat", "dv_rt_char2str", "dv_rt_input_str",
                 "dv_rt_freearray_str", "dv_rt_release_elems"}
    for f0 in to_ir(src, 0).functions:
        f1 = fn(to_ir(src, 1), f0.name)
        assert names(f0, keep) == names(f1, keep), f0.name


def test_optimizer_prunes_literals_of_dead_branches_but_keeps_used_ones():
    m = to_ir(prog("void m charya () {", "  int n", "  n lo 3 pettu",
                   "  n > 5 ayite { \"big\" ni chupi } lekunte { \"small\" ni chupi }", "}", "m()"), 1)
    lits = [c.args[0].value for c in calls(fn(m, I.ENTRY_FUNCTION)) if c.name == "dv_rt_strlit"]
    assert lits == [b"small"]
    assert [g.name for g in m.globals if g.name.startswith("lit.")] == ["lit.1"]
