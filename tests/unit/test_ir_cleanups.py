"""IR lowering of scope-exit cleanups (plan P22): which instructions are emitted, in what order."""

from compiler.ir import ir as I
from tests.helpers.pipeline import to_ir


def prog(*lines):
    return "\n".join(lines) + "\n"


def fn(m, name):
    return next(f for f in m.functions if f.name == name)


def instrs(f):
    return [i for b in f.blocks for i in b.instrs]


def rtnames(f):
    return [i.name for i in instrs(f) if isinstance(i, I.RtCall)]


def test_ivvu_evaluates_value_then_frees_innermost_first():
    src = prog(
        "int f charya (int n) {",
        "  int a[n]",
        "  n > 0 ayite {",
        "    int b[n]",
        "    b[0] lo 4 pettu",
        "    b[0] ivvu",
        "  }",
        "  0 ivvu",
        "}",
        "f(1) ni chupi",
    )
    f = fn(to_ir(src, 0), "f")
    then = next(b for b in f.blocks if b.label.startswith("then"))
    names = [(type(i).__name__, getattr(i, "name", None)) for i in then.instrs]
    # the returned element is loaded before any array is freed; b (inner) before a (outer)
    load_pos = max(k for k, i in enumerate(then.instrs) if isinstance(i, I.Load))
    frees = [k for k, i in enumerate(then.instrs)
             if isinstance(i, I.RtCall) and i.name == "dv_rt_freearray"]
    assert len(frees) == 2 and load_pos < frees[0], names
    inner, outer = (then.instrs[k].args[0].name for k in frees)
    assert inner.startswith("b.") and outer.startswith("a.")
    assert isinstance(then.term, I.Return)


def test_normal_fallthrough_frees_at_scope_end_and_params_are_never_freed():
    src = prog(
        "void g charya (int a[], int n) { a[0] lo n pettu }",
        "void f charya (int n) {",
        "  int x[n]",
        "  g(x, n)",
        "}",
        "f(2)",
    )
    m = to_ir(src, 0)
    assert rtnames(fn(m, "g")) == []
    assert rtnames(fn(m, "f")).count("dv_rt_freearray") == 1


def test_break_and_continue_free_only_scopes_inside_the_loop():
    src = prog(
        "void f charya (int n) {",
        "  int outer[n]",
        "  int i",
        "  i lo 0 pettu",
        "  i < 3 unnanta varaku {",
        "    int a[n]",
        "    i lo i + 1 pettu",
        "    i == 1 ayite { saagu }",
        "    i == 2 ayite { aapu }",
        "  }",
        "}",
        "f(2)",
    )
    f = fn(to_ir(src, 0), "f")
    freed = [i.args[0].name.split(".")[0] for i in instrs(f)
             if isinstance(i, I.RtCall) and i.name == "dv_rt_freearray"]
    # saagu, aapu and the body's fallthrough each free 'a'; 'outer' only once, at the function end
    assert freed.count("a") == 3 and freed.count("outer") == 1


def test_small_constant_arrays_stay_in_the_frame_and_are_not_freed():
    src = prog("void f charya () { int a[3][3]\n a[1][1] lo 2 pettu }", "f()")
    f = fn(to_ir(src, 0), "f")
    assert any(isinstance(i, I.NewArray) and isinstance(i.count, I.Const) and i.count.value == 9
               for i in instrs(f))
    assert "dv_rt_freearray" not in rtnames(f) and "dv_rt_newarray" not in rtnames(f)


def test_entry_frees_global_runtime_sized_arrays_and_calls_shutdown_last():
    src = prog("int n", "n lo 3 pettu", "int g[n]", "g[0] lo 1 pettu")
    entry = fn(to_ir(src, 0), I.ENTRY_FUNCTION)
    names = rtnames(entry)
    assert names[-2:] == ["dv_rt_freearray", "dv_rt_shutdown"]
