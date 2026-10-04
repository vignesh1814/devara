"""Stage observability / integration (master prompt §4, §11): every stage output can be fed to the next stage and
yields exactly the same result as running the whole pipeline from source."""
import json
import pytest
from tests.validation.helpers import run_cli, WORK, ROOT
from tests.validation.corpus_util import programs, pid, expected

PROGS = programs()
SUBSET = PROGS[::7]


def _data(out: bytes):
    d = json.loads(out)
    d.pop("file", None)
    return d


def tmp(name, data: bytes):
    p = WORK / name
    p.write_bytes(data)
    return str(p)


def stage_chain(tel, tag):
    t = str(tel)
    lex = run_cli(["lex", "--json", t])
    assert lex.rc == 0, lex.err
    tj = tmp(f"{tag}.tokens.json", lex.out)
    ast_src = run_cli(["parse", "--json", t])
    ast_tok = run_cli(["parse", "--json", tj])
    assert ast_src.rc == 0 and ast_tok.rc == 0, (ast_src.err, ast_tok.err)
    assert _data(ast_src.out) == _data(ast_tok.out), "parse(source) != parse(lex --json)"
    aj = tmp(f"{tag}.ast.json", ast_src.out)
    sema_src = run_cli(["sema", t])
    sema_ast = run_cli(["sema", aj])
    assert sema_src.rc == 0 and sema_ast.rc == 0, (sema_src.err, sema_ast.err)
    assert sema_src.out == sema_ast.out, "sema(source) != sema(parse --json)"
    ir_src = run_cli(["ir", "--json", t])
    assert ir_src.rc == 0, ir_src.err
    ij = tmp(f"{tag}.ir.json", ir_src.out)
    ir_txt_src = run_cli(["ir", t])
    assert ir_txt_src.rc == 0
    opt_src = run_cli(["opt", t])
    opt_ir = run_cli(["opt", ij])
    assert opt_src.rc == 0 and opt_ir.rc == 0, (opt_src.err, opt_ir.err)
    assert opt_src.out == opt_ir.out, "opt(source) != opt(ir --json)"
    for lvl in ("-O0", "-O1"):
        a_src = run_cli([lvl, "asm", t])
        a_ir = run_cli([lvl, "asm", ij])
        assert a_src.rc == 0 and a_ir.rc == 0, (a_src.err, a_ir.err)
        assert a_src.out == a_ir.out, f"asm {lvl}: source != ir --json"
    return ij


def check_end_to_end(tel, tag):
    inp, out, ex, _ = expected(tel)
    for lvl in ("-O0", "-O1"):
        asm = run_cli([lvl, "asm", str(tel)])
        s = tmp(f"{tag}{lvl}.s", asm.out)
        exe = str(WORK / f"{tag}{lvl}.exe")
        b = run_cli(["build", s, "-o", exe])
        assert b.rc == 0, b.err
        import subprocess
        r = subprocess.run([exe], input=inp, capture_output=True, timeout=30)
        assert r.stdout == out and r.returncode == ex, f"asm->build->run mismatch at {lvl}"


@pytest.mark.parametrize("tel", SUBSET, ids=pid)
def test_stage_round_trips_subset(tel):
    stage_chain(tel, "obs_" + tel.stem)


@pytest.mark.slow
@pytest.mark.parametrize("tel", PROGS, ids=pid)
def test_stage_round_trips_full_corpus(tel):
    stage_chain(tel, "obsf_" + tel.stem)
    check_end_to_end(tel, "obsf_" + tel.stem)


def test_stdin_dash_as_stage_input():
    src = b"int x\nx lo 3 pettu\nx ni chupi\n"
    for cmd in ("lex", "parse", "sema", "ir", "opt", "asm"):
        assert run_cli([cmd, "-"], src).rc == 0, cmd


def test_json_envelopes_declare_kind_and_version():
    t = str(ROOT / "tests/corpus/arrays/003_reverse.tel")
    for cmd, kind in (("lex", "tokens"), ("parse", "ast"), ("ir", "ir")):
        d = json.loads(run_cli([cmd, "--json", t]).out)
        assert d["devara"] == kind and isinstance(d["version"], int) and "data" in d


def test_earlier_stage_json_is_rejected_or_equivalent():
    # The plan's table says `asm` takes source or IR JSON; accepting AST JSON is a lenient extension, but if it is
    # accepted the result must equal the pipeline run from source.  Never an ICE.
    t = str(ROOT / "tests/corpus/arrays/003_reverse.tel")
    ast = tmp("wrong.ast.json", run_cli(["parse", "--json", t]).out)
    p = run_cli(["asm", ast])
    assert p.rc in (0, 1, 2), p.err
    if p.rc == 0:
        assert p.out == run_cli(["asm", t]).out


def test_token_json_to_asm_or_rejected():
    t = str(ROOT / "tests/corpus/arrays/003_reverse.tel")
    tok = tmp("wrong.tok.json", run_cli(["lex", "--json", t]).out)
    p = run_cli(["ir", tok])
    assert p.rc in (0, 1, 2), p.err


def test_corrupt_json_is_rejected_cleanly():
    bad = tmp("corrupt.json", b'{"devara": "ast", "version": 1, "data": {"_node": "Program"')
    for cmd in ("parse", "sema", "ir", "asm"):
        p = run_cli([cmd, bad])
        assert p.rc in (1, 2), (cmd, p.rc, p.err)


def test_json_with_missing_fields_is_rejected_cleanly():
    bad = tmp("missing.json", b'{"devara": "ast", "version": 1, "data": {"_node": "Program"}}')
    p = run_cli(["sema", bad])
    assert p.rc in (1, 2), (p.rc, p.err)
