"""Phase 5: IR verifier accepts lowered programs and rejects each class of malformed IR."""

import copy
import glob
from pathlib import Path

import pytest

from compiler import serialize
from compiler.ir import ir as I
from compiler.ir.printer import format_module
from compiler.ir.verify import check_module, verify_module
from compiler.diagnostics import InternalCompilerError
from tests.helpers.pipeline import to_ir

IT = I.IRType
ROOT = Path(__file__).parent.parent.parent


def tiny(instrs, term=None, ret=IT.VOID, params=()):
    f = I.IRFunction("f", list(params), ret, [I.BasicBlock("b0", instrs, term or I.Return(None))])
    e = I.IRFunction(I.ENTRY_FUNCTION, [], IT.VOID, [I.BasicBlock("e0", [], I.Return(None))])
    return I.IRModule([], [f, e])


def r(n, t=IT.I64):
    return I.Reg(n, t)


def c(v, t=IT.I64):
    return I.Const(t, v)


def test_valid_tiny_module_passes():
    verify_module(tiny([I.Copy(r("a"), c(1))], I.Return(None)))


@pytest.mark.parametrize("name,mod,needle", [
    ("branch to unknown label", tiny([], I.Jump("nowhere")), "unknown label"),
    ("branch cond not bool", tiny([I.Copy(r("a"), c(1))], I.Branch(r("a"), "b0", "b0")), "bool"),
    ("return value in void fn", tiny([], I.Return(c(1))), "void function"),
    ("bare return in int fn", tiny([], I.Return(None), ret=IT.I64), "bare return"),
    ("return type mismatch", tiny([], I.Return(c(1.0, IT.F64)), ret=IT.I64), "return type"),
    ("copy type mismatch", tiny([I.Copy(r("a"), c(1.0, IT.F64))]), "copy type"),
    ("binop mixed types", tiny([I.BinOp("ADD", r("a"), c(1), c(1.0, IT.F64))]), "binop"),
    ("binop on bool", tiny([I.BinOp("ADD", r("a", IT.BOOL), c(True, IT.BOOL), c(True, IT.BOOL))]), "binop"),
    ("mod on float", tiny([I.BinOp("MOD", r("a", IT.F64), c(1.0, IT.F64), c(1.0, IT.F64))]), "mod"),
    ("cmp result not bool", tiny([I.Cmp("LT", r("a"), c(1), c(2))]), "cmp result"),
    ("cmp str ordering", tiny([I.Cmp("LT", r("a", IT.BOOL), c(b"a", IT.STR), c(b"b", IT.STR))]), "EQ/NE"),
    ("load from non-addr", tiny([I.Load(r("a"), c(1))]), "addr"),
    ("store to non-addr", tiny([I.Store(c(1), c(2))]), "addr"),
    ("ptradd float index", tiny([I.PtrAdd(r("a", IT.ADDR), r("b", IT.ADDR), c(1.0, IT.F64))]), "ptradd"),
    ("unknown callee", tiny([I.Call(None, "ghost", [])]), "unknown function"),
    ("call arity", tiny([I.Call(None, "f", [c(1)])]), "expected 0 args"),
    ("unknown runtime fn", tiny([I.RtCall(None, "dv_rt_nope", [])]), "unknown runtime"),
    ("rtcall arg type", tiny([I.RtCall(None, "dv_rt_output_i64", [c(1.5, IT.F64)])]), "argument type"),
    ("read of undefined register", tiny([I.Copy(r("a"), r("ghost"))]), "never defined"),
    ("register used with two types", tiny([I.Copy(r("a"), c(1)), I.Copy(r("a", IT.F64), c(1.0, IT.F64))]), "types"),
    ("unknown global", tiny([I.Load(r("a"), I.GlobalRef("nope"))]), "unknown global"),
    ("malformed constant", tiny([I.Copy(r("a"), I.Const(IT.I64, 1.5))]), "malformed constant"),
    ("i64 constant out of range", tiny([I.Copy(r("a"), I.Const(IT.I64, 1 << 63))]), "out of range"),
])
def test_verifier_rejects(name, mod, needle):
    errs = check_module(mod)
    assert errs, name
    assert any(needle in e for e in errs), (name, errs)
    with pytest.raises(InternalCompilerError):
        verify_module(mod)


def test_duplicate_labels_and_missing_entry_rejected():
    f = I.IRFunction("f", [], IT.VOID, [I.BasicBlock("x", [], I.Return(None)), I.BasicBlock("x", [], I.Return(None))])
    errs = check_module(I.IRModule([], [f]))
    assert any("duplicate block labels" in e for e in errs)
    assert any("missing entry" in e for e in errs)


def test_lowered_programs_have_single_terminator_per_block_and_verify():
    src = """
int f charya(int n) { n > 0 ayite { n ivvu } lekunte { aapu_never() ivvu } }
""".replace("aapu_never()", "0")
    m = to_ir(src, 0)
    verify_module(m)
    for fn in m.functions:
        for b in fn.blocks:
            assert isinstance(b.term, (I.Jump, I.Branch, I.Return))


def test_every_corpus_file_lowers_and_verifies_at_o0_and_o1():
    files = sorted(glob.glob(str(ROOT / "tests/programs/**/*.tel"), recursive=True)
                   + glob.glob(str(ROOT / "examples/*.tel")))
    assert files
    skipped = {"17_bfs_mock.tel", "18_n_queens.tel"}   # not valid Devara (see integration test)
    for f in files:
        if Path(f).name in skipped:
            continue
        src = Path(f).read_bytes().decode("latin-1")
        for level in (0, 1):
            verify_module(to_ir(src, level))


def test_ir_json_round_trip_and_printer_are_deterministic():
    src = "int a[3]\na[1] lo 2 pettu\n\"x\" ni chupi\n1.5 + 2 ni chupi\nnijam && abaddham ni chupi"
    m = to_ir(src, 0)
    back = serialize.loads(serialize.dumps(m))
    assert back == m
    assert format_module(back) == format_module(m)
    verify_module(back)
