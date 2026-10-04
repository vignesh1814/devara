"""Surface-form robustness: whitespace variations, keyword case, token adjacency, unusual identifiers."""
import pytest
from tests.validation.helpers import cli, run, prog, OPTS

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("opt", OPTS)
def test_minimal_whitespace_program(opt):
    src = "int x\nx lo 1+2*3 pettu\nx ni chupi\nint a[3]\na[1]lo 4 pettu\na[1]ni chupi\nprati i 0 nundi 3 varaku{i ni chupi}\n(x)ni chupi\n"
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "7\n4\n0\n1\n2\n7\n"


@pytest.mark.parametrize("opt", OPTS)
def test_every_token_on_its_own_line_and_odd_spacing(opt):
    src = "int\nx\nx\nlo\n5\npettu\nx\nni\nchupi\n\n\n  \t  x\t\tlo\t x + 1 \n pettu \n x ni chupi # trailing\n"
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "5\n6\n"


@pytest.mark.parametrize("opt", OPTS)
def test_keywords_in_any_case(opt):
    src = ("INT x\nx LO 5 PETTU\nx Ni ChUpI\n"
           "x > 3 AYITE { \"big\" NI CHUPI } LEKUNTE { \"small\" NI CHUPI }\n"
           "PRATI i 0 NUNDI 2 VARAKU { i NI CHUPI }\n"
           "INT f CHARYA (INT a) { a IVVU }\nf(9) NI CHUPI\n"
           "PRATISARI (INT k LO 0 PETTU; k < 2; k++) { k NI CHUPI }\n"
           "BOOL b\nb LO NIJAM PETTU\nb NI CHUPI\nb LO ABADDHAM PETTU\nb NI CHUPI\n"
           "x < 9 UNNANTA VARAKU { AAPU }\n")
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "5\nbig\n0\n1\n9\n0\n1\nnijam\nabaddham\n"


def test_identifiers_differing_only_by_case_are_distinct():
    p = cli("run", prog("int x", "int X", "int Int_", "x lo 1 pettu", "X lo 2 pettu", "Int_ lo 3 pettu", "x ni chupi", "X ni chupi", "Int_ ni chupi"), ("-O1",))
    assert p.text == "1\n2\n3\n"


@pytest.mark.parametrize("ident", ["_", "__", "_1", "a1", "A_B_C", "x" * 255, "i", "I", "intx", "Integer", "pettu_", "_pettu", "lo1", "nijam2", "voidd"])
def test_unusual_identifiers_work_as_variables_and_functions(ident):
    src = prog(f"int {ident}", f"{ident} lo 41 pettu", f"int fn_{ident} charya (int p) {{ p + 1 ivvu }}", f"fn_{ident}({ident}) ni chupi")
    p = cli("run", src, ("-O1",))
    assert p.rc == 0, p.err
    assert p.text == "42\n"


@pytest.mark.parametrize("opt", OPTS)
def test_float_literal_digit_forms(opt):
    rows = [("0.30000000000000004", "0.3"), ("00012.50", "12.5"), ("123456789.123456789", "1.23457e+08"), ("0.000000000000000000000001", "1e-24"),
            ("99999999999999999999999999.0", "1e+26"), ("5.0", "5"), ("0.0", "0"), ("1.0000001", "1"), ("1.00001", "1.00001"), ("1000000.0", "1e+06"), ("999999.0", "999999")]
    p = run(prog(*[f"{e} ni chupi" for e, _ in rows]), b"", opt)
    assert p.text.split("\n")[:-1] == [x for _, x in rows]


@pytest.mark.parametrize("opt", OPTS)
def test_comments_everywhere(opt):
    src = "# top\nint x # decl\n# between\nx # target\nlo # op\n 5 # value\npettu # end\nx ni chupi# no space\n#\n# last line without newline"
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "5\n"


@pytest.mark.parametrize("opt", OPTS)
def test_hash_inside_literals_is_not_a_comment(opt):
    src = prog("\"a # b\" ni chupi", "'#' ni chupi", "podavu(\"###\") ni chupi")
    assert run(src, b"", opt).text == "a # b\n#\n3\n"


@pytest.mark.parametrize("opt", OPTS)
def test_empty_blocks_and_empty_bodies(opt):
    src = prog("void f charya () { }", "f()", "nijam ayite { }", "nijam ayite { } lekunte { }", "abaddham unnanta varaku { }", "prati i 0 nundi 3 varaku { }",
               "pratisari (int i lo 0 pettu; i < 3; i++) { }", "\"ok\" ni chupi")
    p = run(src, b"", opt)
    assert p.rc == 0 and p.text == "ok\n"


@pytest.mark.parametrize("opt", OPTS)
def test_statement_adjacency_without_separators(opt):
    src = "int a int b a lo 1 pettu b lo 2 pettu a ni chupi b ni chupi a + b ni chupi\n"
    p = run(src, b"", opt)
    assert p.rc == 0, p.err
    assert p.text == "1\n2\n3\n"
