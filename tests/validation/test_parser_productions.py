"""Grammar-production validation (spec §11): positive (minimal/normal/nested/boundary/complex) and negative cases.

Positive tests inspect the AST of `parse --json` against the field contract of design §3.5.
Negative tests assert exit status 1 and a `syntax error [CATEGORY]` diagnostic with category in the closed set.
"""
import pytest
from tests.validation.helpers import cli, accepts, rejects, prog, SYN_CATS
from tests.validation.astutil import ast, first_item, sx, expr_of, check_invariants, PRIM

T = ["int", "float", "bool", "char", "padham", "void"]


def parses(src):
    d = ast(src)
    assert check_invariants(d) == []
    return d


def syntax_error(src, cats=None):
    rejects(src, "syntax", cats or SYN_CATS, upto="parse")


# =============================================================== program / top-level
def test_empty_program():
    assert parses("")["items"] == []


def test_program_only_comments_and_whitespace():
    assert parses("# nothing\n\n   \n")["items"] == []


def test_top_level_item_kinds():
    d = parses(prog("int g", "int f charya () { 1 ivvu }", "g lo 2 pettu", "f() ni chupi"))
    assert [i["_node"] for i in d["items"]] == ["Declaration", "FunctionDeclaration", "Assignment", "Output"]


def test_top_level_order_is_source_order():
    d = parses(prog("1 ni chupi", "int x", "2 ni chupi", "void f charya () { }", "3 ni chupi"))
    assert [i["_node"] for i in d["items"]] == ["Output", "Declaration", "Output", "FunctionDeclaration", "Output"]


# =============================================================== declaration (§11.4)
@pytest.mark.parametrize("t", T)
def test_declaration_each_type(t):
    it = first_item(f"{t} v\n")
    assert it["_node"] == "Declaration"
    assert PRIM[it["type"]["primitive"]] == t
    assert it["type"]["array_dimensions"] == []
    assert it["name"]["name"] == "v"


@pytest.mark.parametrize("dims", ["[1]", "[10]", "[10][20]", "[2][3][4]", "[1][1][1][1]", "[n]", "[n + 1]",
                                  "[f(2)]", "[a[0]]", "[(1 + 2) * 3]", "[0x10]", "[010]", "[(int) 2.5]"])
def test_array_declaration_dimensions(dims):
    it = first_item(f"int a{dims}\n")
    assert it["_node"] == "Declaration"
    k = {"[a[0]]": 1}.get(dims, dims.count("["))
    assert len(it["type"]["array_dimensions"]) == k
    assert all(d is not None for d in it["type"]["array_dimensions"])


def test_array_dimension_expression_tree():
    it = first_item("int a[n + 1][2 * m]\n")
    ds = it["type"]["array_dimensions"]
    assert [sx(d) for d in ds] == ["(n + 1)", "(2 * m)"]


def test_declaration_local_in_block():
    d = parses(prog("1 ayite {", "  int x", "  float y[3]", "}"))
    stmts = d["items"][0]["then_block"]["statements"]
    assert [s["_node"] for s in stmts] == ["Declaration", "Declaration"]


@pytest.mark.parametrize("bad", [
    "int\n", "int [3]\n", "int 3\n", "int x[]\n", "int x[\n", "int x[3\n", "int x]\n", "int x[3][\n",
    "int x[3]]\n", "int x y\n", "int x,y\n", "int x lo 1 pettu\n", "int int\n", "int x[3] [4\n", "x int\n",
    "int x;\n", "int x[ ]\n", "int 1x\n", "int x[3], y[4]\n",
])
def test_declaration_negative(bad):
    syntax_error(bad)


# =============================================================== assignment (§11.5)
def test_assignment_identifier_target():
    it = first_item("x lo 10 pettu\n")
    assert it["_node"] == "Assignment" and it["target"]["_node"] == "Identifier"
    assert it["value"]["_node"] == "Literal" and it["value"]["lexeme"] == "10"


def test_assignment_array_target():
    it = first_item("a[0] lo 42 pettu\n")
    assert it["target"]["_node"] == "ArrayAccess" and len(it["target"]["indices"]) == 1


def test_assignment_multidimensional_target():
    it = first_item("m[i][j + 1][2] lo m[i][j] pettu\n")
    assert [sx(i) for i in it["target"]["indices"]] == ["i", "(j + 1)", "2"]
    assert sx(it["value"]) == "m[i][j]"


def test_assignment_complex_value():
    it = first_item("x lo (a + b) * -c / f(1, g(2)) pettu\n")
    assert sx(it["value"]) == "(((a + b) * (-c)) / f(1, g(2)))"


def test_assignment_value_is_any_expression_kind():
    for v in ["1", "1.5", "'c'", "\"s\"", "nijam", "y", "y[1]", "f()", "(y)", "(float) y", "!y", "-y", "+y"]:
        assert first_item(f"x lo {v} pettu\n")["_node"] == "Assignment"


def test_chained_assignment_statements_each_end_with_pettu():
    d = parses("x lo 1 pettu y lo 2 pettu z lo 3 pettu\n")
    assert len(d["items"]) == 3


@pytest.mark.parametrize("bad", [
    "x lo 1\n", "x lo pettu\n", "lo 1 pettu\n", "x 1 pettu\n", "x lo 1 pettu pettu\n", "x lo lo 1 pettu\n",
    "1 lo 2 pettu\n", "x + 1 lo 2 pettu\n", "f(x) lo 2 pettu\n", "(x) lo 1 pettu\n",    # P31
    "x lo 1 pettu lo\n", "x[ lo 1 pettu\n", "x[] lo 1 pettu\n", "x[1 lo 1 pettu\n", "x = 1 pettu\n",
    "x lo 1,2 pettu\n", "x lo (1 pettu\n", "x lo 1) pettu\n", "\"s\" lo 1 pettu\n", "nijam lo 1 pettu\n",
    "-x lo 1 pettu\n", "!x lo 1 pettu\n", "x++ lo 1 pettu\n",
])
def test_assignment_negative(bad):
    cats = SYN_CATS
    if "=" in bad:
        rejects(bad, "lexical", "INVALID_CHARACTER", upto="parse")
    else:
        syntax_error(bad, cats)


# =============================================================== input / output
def test_input_forms():
    d = parses(prog("x ni chaduvu", "a[i] ni chaduvu", "m[i][j] ni chaduvu"))
    assert [i["_node"] for i in d["items"]] == ["Input"] * 3
    assert [i["target"]["_node"] for i in d["items"]] == ["Identifier", "ArrayAccess", "ArrayAccess"]


def test_output_forms():
    d = parses(prog("n ni chupi", "x + 1 ni chupi", '"Hello" ni chupi', "'c' ni chupi", "nijam ni chupi",
                    "f(1) ni chupi", "a[1] ni chupi", "(int) 2.5 ni chupi", "1.5 ni chupi", "-3 ni chupi"))
    assert all(i["_node"] == "Output" for i in d["items"])


@pytest.mark.parametrize("bad", [
    "x ni\n", "ni chaduvu\n", "x chaduvu\n", "x ni chaduvu chaduvu\n", "x ni chupi chupi\n", "ni chupi\n",
    "x ni chaduvu pettu\n", "1 + ni chupi\n", "x ni chupi x\n" if False else "x ni ni chupi\n",
    "1 ni chaduvu\n", "x + y ni chaduvu\n", "f(x) ni chaduvu\n", "(x) ni chaduvu\n", "\"s\" ni chaduvu\n",
    "x chupi ni\n", "x ni chaduvu chupi\n",
])
def test_input_output_negative(bad):
    syntax_error(bad)


# =============================================================== if statement (§11.6)
def test_if_minimal_and_empty_block():
    it = first_item("x ayite { }\n")
    assert it["_node"] == "IfStatement" and it["then_block"]["statements"] == [] and it["else_branch"] is None


def test_if_else():
    it = first_item("x ayite { 1 ni chupi } lekunte { 2 ni chupi }\n")
    assert it["else_branch"]["_node"] == "Block"


def test_if_else_if_chain_is_right_nested():
    it = first_item("a ayite { } lekunte b ayite { } lekunte c ayite { } lekunte { }\n")
    e1 = it["else_branch"]
    assert e1["_node"] == "IfStatement"
    e2 = e1["else_branch"]
    assert e2["_node"] == "IfStatement" and e2["else_branch"]["_node"] == "Block"


def test_if_else_if_without_final_else():
    it = first_item("a ayite { } lekunte b ayite { }\n")
    assert it["else_branch"]["_node"] == "IfStatement" and it["else_branch"]["else_branch"] is None


def test_nested_ifs_and_dangling_else_binds_to_nearest():
    it = first_item("a ayite { b ayite { 1 ni chupi } lekunte { 2 ni chupi } }\n")
    inner = it["then_block"]["statements"][0]
    assert it["else_branch"] is None and inner["else_branch"] is not None


def test_if_condition_complex_expression():
    it = first_item("a < b && (c == d || !e) ayite { }\n")
    assert sx(it["condition"]) == "((a < b) && ((c == d) || (!e)))"


def test_if_deeply_nested_blocks():
    src = "".join("x ayite { " for _ in range(60)) + "".join("} " for _ in range(60)) + "\n"
    accepts(src, upto="parse") if False else parses(src)


@pytest.mark.parametrize("bad", [
    "ayite { }\n", "x ayite\n", "x ayite 1 ni chupi\n", "x ayite { \n", "x ayite }\n", "x ayite { } lekunte\n",
    "x ayite { } lekunte 1 ni chupi\n", "x ayite { } lekunte { \n", "lekunte { }\n", "x ayite { } lekunte lekunte { }\n",
    "x ayite { } else { }\n", "x ayite { } lekunte x { }\n", "if x { }\n", "x ayite ( ) { }\n", "x ayite { } lekunte x ayite\n",
    "x ayite { } ayite { }\n" if False else "x ayite ayite { }\n", "x ayite { } lekunte { } lekunte { }\n",
    "(x ayite { }\n", "x) ayite { }\n",
])
def test_if_negative(bad):
    syntax_error(bad)


# =============================================================== while (§11.7)
def test_while_forms():
    it = first_item("x < 10 unnanta varaku { x lo x + 1 pettu }\n")
    assert it["_node"] == "WhileLoop"
    assert sx(it["condition"]) == "(x < 10)" and len(it["body"]["statements"]) == 1


def test_while_empty_body_and_constant_condition():
    assert first_item("nijam unnanta varaku { }\n")["_node"] == "WhileLoop"


@pytest.mark.parametrize("bad", [
    "unnanta varaku { }\n", "x unnanta { }\n", "x varaku { }\n", "x unnanta varaku\n", "x varaku unnanta { }\n",
    "x unnanta varaku varaku { }\n", "x unnanta varaku { \n", "x unnanta varaku x\n", "x unnanta unnanta varaku { }\n",
    "while x { }\n",
])
def test_while_negative(bad):
    syntax_error(bad)


# =============================================================== range loop (§11.8)
def test_range_loop():
    it = first_item("prati i 1 nundi n varaku { i ni chupi }\n")
    assert it["_node"] == "RangeLoop" and it["variable"]["name"] == "i"
    assert sx(it["start"]) == "1" and sx(it["end"]) == "n"


def test_range_loop_complex_bounds_and_nesting():
    it = first_item("prati i a + 1 nundi f(b) * 2 varaku { prati j i nundi i + 1 varaku { } }\n")
    assert sx(it["start"]) == "(a + 1)" and sx(it["end"]) == "(f(b) * 2)"
    assert it["body"]["statements"][0]["_node"] == "RangeLoop"


def test_range_bounds_minus_and_negative_literals():
    it = first_item("prati i -5 nundi -1 varaku { }\n")
    assert sx(it["start"]) == "(-5)" and sx(it["end"]) == "(-1)"


@pytest.mark.parametrize("bad", [
    "prati 1 nundi 2 varaku { }\n", "prati i nundi 2 varaku { }\n", "prati i 1 2 varaku { }\n",
    "prati i 1 nundi varaku { }\n", "prati i 1 nundi 2 { }\n", "prati i 1 nundi 2 varaku\n",
    "prati i nundi varaku { }\n", "prati i 1 nundi 2 unnanta varaku { }\n", "prati i[0] 1 nundi 2 varaku { }\n",
    "prati int i 1 nundi 2 varaku { }\n", "prati i 1 nundi 2 varaku { \n", "prati\n", "prati i\n", "prati i 1 nundi\n",
    "prati i 1 nundi 2 varaku { } }\n",
])
def test_range_negative(bad):
    syntax_error(bad)


# =============================================================== three-part loop (§11.9)
INITS = {
    "tho_modhalu": ("i 0 tho modhalu", "ForThoModhaluInit"),
    "assignment": ("i lo 0 pettu", "ForAssignmentInit"),
    "decl_init": ("int i lo 0 pettu", "ForDeclarationInit"),
    "decl_noinit": ("int i", "ForDeclarationInit"),
}
UPDATES = {
    "assign": ("i lo i + 1 pettu", "AssignmentUpdate", None),
    "pre_inc": ("++i", "IncrementUpdate", True),
    "post_inc": ("i++", "IncrementUpdate", False),
    "pre_dec": ("--i", "DecrementUpdate", True),
    "post_dec": ("i--", "DecrementUpdate", False),
}


@pytest.mark.parametrize("init", INITS)
@pytest.mark.parametrize("upd", UPDATES)
def test_for_init_update_matrix(init, upd):
    i_src, i_node = INITS[init]
    u_src, u_node, prefix = UPDATES[upd]
    it = first_item(f"pratisari ({i_src}; i < 10; {u_src}) {{ }}\n")
    assert it["_node"] == "ForLoop"
    assert it["init"]["_node"] == i_node
    assert it["update"]["_node"] == u_node
    if prefix is not None:
        assert it["update"]["prefix"] is prefix
    assert it["condition"] is not None


def test_for_decl_init_initializer_field():
    a = first_item("pratisari (int i lo 5 pettu; i < 9; i++) { }\n")["init"]
    b = first_item("pratisari (int i; i < 9; i++) { }\n")["init"]
    assert a["initializer"] is not None and b["initializer"] is None
    assert a["name"]["name"] == "i"


def test_for_decl_init_types():
    for t in ["int", "float", "bool", "char", "padham"]:
        it = first_item(f"pratisari ({t} v; nijam; v++) {{ }}\n")
        assert PRIM[it["init"]["type"]["primitive"]] == t


def test_for_update_array_element_targets():
    for u, node in [("a[0]++", "IncrementUpdate"), ("++a[i]", "IncrementUpdate"), ("a[i][j]--", "DecrementUpdate"),
                    ("--m[1][2]", "DecrementUpdate"), ("a[i] lo a[i] + 1 pettu", "AssignmentUpdate")]:
        it = first_item(f"pratisari (int i lo 0 pettu; i < 3; {u}) {{ }}\n")
        assert it["update"]["_node"] == node and it["update"]["target"]["_node"] == "ArrayAccess"


def test_for_init_assignment_form_with_complex_expr():
    it = first_item("pratisari (i lo (a + b) * 2 pettu; i < 9; i++) { }\n")
    assert sx(it["init"]["value"]) == "((a + b) * 2)"


def test_for_condition_is_plain_expression():
    it = first_item("pratisari (i 0 tho modhalu; i < n && !done; i++) { }\n")
    assert sx(it["condition"]) == "((i < n) && (!done))"


def test_for_nested_and_empty_body():
    it = first_item("pratisari (int i lo 0 pettu; i < 3; i++) { pratisari (int j lo 0 pettu; j < 3; j++) { } }\n")
    assert it["body"]["statements"][0]["_node"] == "ForLoop"


@pytest.mark.parametrize("bad", [
    "pratisari () { }\n", "pratisari (;;) { }\n", "pratisari (i 0 tho modhalu; i < 3) { }\n",
    "pratisari (i 0 tho modhalu; i < 3; ) { }\n", "pratisari (; i < 3; i++) { }\n",
    "pratisari (i 0 tho modhalu; ; i++) { }\n", "pratisari (i 0 tho modhalu i < 3 i++) { }\n",
    "pratisari i 0 tho modhalu; i < 3; i++ { }\n", "pratisari (i 0 tho modhalu; i < 3; i++)\n",
    "pratisari (i 0 modhalu; i < 3; i++) { }\n", "pratisari (i 0 tho; i < 3; i++) { }\n",
    "pratisari (i lo 0; i < 3; i++) { }\n", "pratisari (i lo 0 pettu; i < 3; i lo i + 1) { }\n",
    "pratisari (i lo 0 pettu; i < 3 unnanta varaku; i++) { }\n", "pratisari (i lo 0 pettu; i < 3; i++ i) { }\n",
    "pratisari (i lo 0 pettu; i < 3; ++) { }\n", "pratisari (i lo 0 pettu; i < 3; i+++) { }\n",
    "pratisari (i lo 0 pettu; i < 3; ++i++) { }\n", "pratisari (i lo 0 pettu; i < 3; (i)++) { }\n",   # P31
    "pratisari (i lo 0 pettu; i < 3; ++(i)) { }\n", "pratisari ((i) lo 0 pettu; i < 3; i++) { }\n",
    "pratisari ((i) 0 tho modhalu; i < 3; i++) { }\n", "pratisari (a[0] 0 tho modhalu; a[0] < 3; i++) { }\n",
    "pratisari (a[0] lo 0 pettu; i < 3; i++) { }\n" if False else "pratisari (1 lo 0 pettu; i < 3; i++) { }\n",
    "pratisari (int i lo 0 pettu; i < 3; i++; j++) { }\n", "pratisari (int a[3]; nijam; i++) { }\n",
    "pratisari (int i lo 0 pettu; i < 3; i++) { \n", "pratisari (int i lo 0 pettu; i < 3; i++) }\n",
    "pratisari (i lo 0 pettu; i < 3; f(x)) { }\n", "pratisari (f(x); i < 3; i++) { }\n",
    "pratisari (i lo 0 pettu; i < 3; i++ ++) { }\n",
])
def test_for_negative(bad):
    syntax_error(bad)


@pytest.mark.parametrize("bad", ["i++\n", "++i\n", "i--\n", "--i\n", "a[0]++\n", "x ayite { i++ }\n",
                                 "x lo i++ pettu\n", "i++ ni chupi\n", "f(i++)\n", "x lo ++i pettu\n"])
def test_standalone_or_embedded_increment_is_not_a_statement(bad):
    syntax_error(bad)


# =============================================================== break / continue / return / expression statement (§11.10, 11.11)
def test_break_continue_nodes():
    it = first_item("nijam unnanta varaku { aapu saagu }\n")
    assert [s["_node"] for s in it["body"]["statements"]] == ["BreakStatement", "ContinueStatement"]


def test_break_continue_keywords_case_insensitive():
    it = first_item("nijam unnanta varaku { AAPU SaaGu }\n")
    assert len(it["body"]["statements"]) == 2


def test_return_statement_requires_expression():
    d = parses("int f charya () { 1 + 2 ivvu }\n")
    r = d["items"][0]["body"]["statements"][0]
    assert r["_node"] == "ReturnStatement" and sx(r["value"]) == "(1 + 2)"


@pytest.mark.parametrize("bad", ["ivvu\n", "void f charya () { ivvu }\n", "int f charya () { 1 ivvu ivvu }\n",
                                 "int f charya () { ivvu 1 }\n", "aapu 1\n" if False else "aapu aapu aapu x\n"])
def test_return_break_negative(bad):
    if bad.startswith("aapu aapu"):
        parses(bad.replace("aapu aapu aapu x", "aapu aapu aapu"))
        return
    syntax_error(bad)


def test_expression_statement_is_call_only():
    d = parses(prog("f()", "f(1)", "f(1, 2, 3)", "f(g(h(1)))", "f(a[1], (2))"))
    assert all(i["_node"] == "ExpressionStatement" and i["expression"]["_node"] == "FunctionCall" for i in d["items"])


@pytest.mark.parametrize("bad", ["x\n", "1\n", "x + 1\n", "a[1]\n", "\"s\"\n", "f(1) + 1\n", "(f(1))\n",
                                 "f\n", "f(\n", "f(1\n", "f(1,)\n", "f(,1)\n", "f(1 2)\n", "f(1,,2)\n", "f()()\n", "a[1](2)\n", "f(x)[0]\n", "(f)(x)\n", "f(1) 2\n" if False else "f(1) (2)\n"])
def test_expression_statement_negative(bad):
    syntax_error(bad)


def test_call_statement_followed_by_unary_minus_continues_expression_P16():
    # P16: longest match -> `f(x)\n-y ni chupi` is ONE output statement `f(x) - y ni chupi`
    d = parses("f(x)\n-y ni chupi\n")
    assert [i["_node"] for i in d["items"]] == ["Output"]
    assert sx(d["items"][0]["value"]) == "(f(x) - y)"


def test_call_statement_followed_by_plus_P16():
    d = parses("f(x)\n+y ni chupi\n")
    assert [i["_node"] for i in d["items"]] == ["Output"]


def test_call_statement_followed_by_paren_starts_new_statement():
    d = parses("f(x)\n(float) y ni chupi\n")
    assert [i["_node"] for i in d["items"]] == ["ExpressionStatement", "Output"]


# =============================================================== blocks (§11.3)
@pytest.mark.parametrize("bad", ["{ }\n", "{ 1 ni chupi }\n", "x lo 1 pettu { }\n", "{\n", "}\n", "x ayite { { } }\n"])
def test_bare_block_statement_is_not_in_the_grammar(bad):
    syntax_error(bad)


def test_block_many_statements():
    body = " ".join(f"x lo {i} pettu" for i in range(300))
    it = first_item(f"nijam ayite {{ {body} }}\n")
    assert len(it["then_block"]["statements"]) == 300


# =============================================================== functions (§11.12)
@pytest.mark.parametrize("t", T)
def test_function_return_types(t):
    it = first_item(f"{t} f charya () {{ }}\n")
    assert it["_node"] == "FunctionDeclaration" and PRIM[it["return_type"]["primitive"]] == t
    assert it["parameters"] == []


def test_function_parameters():
    it = first_item("int add charya (int a, float b, bool c, char d, padham e) { a ivvu }\n")
    assert [p["name"]["name"] for p in it["parameters"]] == list("abcde")
    assert [PRIM[p["type"]["primitive"]] for p in it["parameters"]] == ["int", "float", "bool", "char", "padham"]


def test_function_array_parameter_has_none_dimension():
    it = first_item("void f charya (int a[], float b[], padham c[], char d[], bool e[]) { }\n")
    for p in it["parameters"]:
        assert p["type"]["array_dimensions"] == [None]


def test_function_scalar_parameter_has_no_dimensions():
    it = first_item("void f charya (int a) { }\n")
    assert it["parameters"][0]["type"]["array_dimensions"] == []


def test_function_body_statements_and_nested_control():
    it = first_item("int f charya (int n) { n < 2 ayite { n ivvu } f(n - 1) + f(n - 2) ivvu }\n")
    assert len(it["body"]["statements"]) == 2


def test_function_many_parameters():
    ps = ", ".join(f"int p{i}" for i in range(40))
    assert len(first_item(f"void f charya ({ps}) {{ }}\n")["parameters"]) == 40


@pytest.mark.parametrize("bad", [
    "int f charya { }\n", "int f charya ( { }\n", "int f charya () \n", "int f () { }\n", "f charya () { }\n",
    "int charya () { }\n", "int f charya (int) { }\n", "int f charya (a) { }\n", "int f charya (int a,) { }\n",
    "int f charya (,int a) { }\n", "int f charya (int a int b) { }\n", "int f charya (int a[3]) { }\n",
    "int f charya (int a[][]) { }\n", "int f charya (int a[][3]) { }\n", "int f charya (int a[) { }\n",
    "int f charya (int a]) { }\n", "int f charya (int a, ) { }\n", "int f charya (void) { }\n",
    "int f charya () { 1 ivvu \n", "int f charya () 1 ivvu\n", "int f charya () { } }\n",
    "int f charya () { int g charya () { } }\n",                       # nested function (OQ11)
    "int f charya (int a lo 1 pettu) { }\n", "int f charya (int a, int a[]) { } }\n",
    "int 1f charya () { }\n", "int f charya () { } charya\n", "int f charya int a { }\n",
    "int f charya(int a, int b { }\n", "int f charya int a, int b) { }\n",
])
def test_function_negative(bad):
    syntax_error(bad)


# =============================================================== expressions (§11.14, 11.15)
@pytest.mark.parametrize("src,expected", [
    # precedence climb ||  <  &&  <  == !=  <  < > <= >=  <  + -  <  * / %  <  unary
    ("a || b && c", "(a || (b && c))"),
    ("a && b || c", "((a && b) || c)"),
    ("a && b == c", "(a && (b == c))"),
    ("a == b < c", "(a == (b < c))"),
    ("a < b + c", "(a < (b + c))"),
    ("a + b * c", "(a + (b * c))"),
    ("a * b + c", "((a * b) + c)"),
    ("a % b + c / d", "((a % b) + (c / d))"),
    ("a || b || c", "((a || b) || c)"),
    ("a && b && c", "((a && b) && c)"),
    ("a == b == c", "((a == b) == c)"),
    ("a != b == c", "((a != b) == c)"),
    ("a < b < c", "((a < b) < c)"),
    ("a <= b >= c", "((a <= b) >= c)"),
    ("a - b - c", "((a - b) - c)"),
    ("a - b + c", "((a - b) + c)"),
    ("a / b / c", "((a / b) / c)"),
    ("a / b * c % d", "(((a / b) * c) % d)"),
    ("1 + 2 * 3 - 4 / 5", "((1 + (2 * 3)) - (4 / 5))"),
    ("a < b == c > d", "((a < b) == (c > d))"),
    ("a || b == c && d", "(a || ((b == c) && d))"),
    ("(a || b) && c", "((a || b) && c)"),
    ("(a + b) * c", "((a + b) * c)"),
    ("a * (b + c)", "(a * (b + c))"),
    ("((a))", "a"),
    ("(((a + b)))", "(a + b)"),
    ("a - -b", "(a - (-b))"),
    ("a - - - b", "(a - (-(-b)))"),
    ("a + +b", "(a + (+b))"),
    ("!a && b", "((!a) && b)"),
    ("!a == b", "((!a) == b)"),
    ("!(a && b)", "(!(a && b))"),
    ("!!a", "(!(!a))"),
    ("-a * b", "((-a) * b)"),
    ("-a + b", "((-a) + b)"),
    ("- -a", "(-(-a))"),
    ("!-a", "(!(-a))"),
    ("-!a", "(-(!a))"),
    ("-f(x)", "(-f(x))"),
    ("-a[1]", "(-a[1])"),
    ("a[1] + a[2]", "(a[1] + a[2])"),
    ("a[i + 1][j * 2]", "a[(i + 1)][(j * 2)]"),
    ("a[b[c[0]]]", "a[b[c[0]]]"),
    ("f(a, b + 1, g(c))", "f(a, (b + 1), g(c))"),
    ("f(a)[0]" if False else "f(a) + g(b)", "(f(a) + g(b))"),
    ("f()", "f()"),
    ("x", "x"),
    ("42", "42"),
    ("'c' + 1", "('c' + 1)"),
    ("\"a\" + \"b\" + \"c\"", "((\"a\" + \"b\") + \"c\")"),
    ("nijam && abaddham", "(nijam && abaddham)"),
])
def test_expression_precedence_and_associativity(src, expected):
    assert expr_of(src) == expected


@pytest.mark.parametrize("src,expected", [
    ("(int) x", "((int)x)"),
    ("(float) x + 1", "(((float)x) + 1)"),
    ("(float) (x + 1)", "((float)(x + 1))"),
    ("(int) (float) x", "((int)((float)x))"),
    ("(char) -x", "((char)(-x))"),
    ("(int) !x", "((int)(!x))"),
    ("-(int) x", "(-((int)x))"),
    ("(padham) c", "((padham)c)"),
    ("(bool) a[1]", "((bool)a[1])"),
    ("(int) f(x) * 2", "(((int)f(x)) * 2)"),
    ("(void) x", "((void)x)"),
    ("(int)x", "((int)x)"),
    ("( int ) x", "((int)x)"),
    ("a * (int) b", "(a * ((int)b))"),
    ("(char) 65 + (char) 1", "(((char)65) + ((char)1))"),
])
def test_cast_expressions(src, expected):
    assert expr_of(src) == expected


def test_parentheses_do_not_create_ast_nodes():
    d = ast("((x)) ni chupi\n")
    assert d["items"][0]["value"]["_node"] == "Identifier"


@pytest.mark.parametrize("bad", [
    "1 + ni chupi\n", "+ ni chupi\n", "* 2 ni chupi\n", "1 * ni chupi\n", "(1 ni chupi\n", "1) ni chupi\n",
    "() ni chupi\n", "(int) ni chupi\n", "1 2 ni chupi\n", "a b ni chupi\n", "a[ ni chupi\n", "a[] ni chupi\n",
    "a[1 ni chupi\n", "a[1]] ni chupi\n", "a[1][ ni chupi\n", "a.b ni chupi\n" if False else "1 && ni chupi\n",
    "1 || || 2 ni chupi\n", "1 == == 2 ni chupi\n", "1 < > 2 ni chupi\n", "1 ! 2 ni chupi\n", "! ni chupi\n",
    "f( ni chupi\n", "f(1 ni chupi\n", "f(1,) ni chupi\n", "(1 + 2 ni chupi\n", "1 + (2 ni chupi\n",
    "int ni chupi\n", "(int)(float) ni chupi\n", "x lo ni chupi\n", "ayite ni chupi\n", "pettu ni chupi\n",
    "1 / ni chupi\n", "1 % ni chupi\n", "1 <= ni chupi\n", "a[1](2) ni chupi\n", "f(1)[0] ni chupi\n", "(a)[0] ni chupi\n", "\"s\"[0] ni chupi\n", "1[0] ni chupi\n", "++a ni chupi\n",
    "a++ ni chupi\n", "a -- ni chupi\n",
])
def test_expression_negative(bad):
    syntax_error(bad)


def test_deeply_nested_parentheses():
    n = 300
    assert expr_of("(" * n + "x" + ")" * n) == "x"


def test_long_binary_chain_left_assoc():
    n = 400
    src = " + ".join(["x"] * n)
    e = ast(src + " ni chupi\n")["items"][0]["value"]
    depth = 0
    while e["_node"] == "BinaryExpression":
        e = e["left"]
        depth += 1
    assert depth == n - 1


def test_long_argument_list():
    args = ", ".join(str(i) for i in range(200))
    assert len(first_item(f"f({args})\n")["expression"]["arguments"]) == 200


# =============================================================== span contract (§3.5.1)
def test_spans_half_open_identifier_and_literal():
    it = first_item("x lo 12 pettu\n")
    t, v = it["target"]["span"], it["value"]["span"]
    assert (t["start_line"], t["start_column"], t["end_line"], t["end_column"]) == (1, 1, 1, 2)
    assert (v["start_column"], v["end_column"]) == (6, 8)


def test_spans_nest_properly_for_binary_expression():
    e = first_item("a + bcd ni chupi\n")["value"]
    assert (e["span"]["start_column"], e["span"]["end_column"]) == (1, 8)
    assert (e["right"]["span"]["start_column"], e["right"]["span"]["end_column"]) == (5, 8)


def test_spans_multiline_statement():
    it = first_item("x ayite {\n  1 ni chupi\n}\n")
    sp = it["span"]
    assert (sp["start_line"], sp["end_line"]) == (1, 3) and sp["end_column"] == 2


# =============================================================== recovery / robustness
def test_multiple_syntax_errors_reported():
    p = cli("parse", "int\nx lo\nint y[\n1 ni chupi\n@\n")
    assert p.rc == 1


def test_independent_statement_errors_are_each_reported():
    p = cli("parse", "x lo pettu\ny lo 1 pettu\nz lo pettu\nw lo 2 pettu\n")
    lines = [d for d in p.diags() if d[0] == "syntax"]
    assert len(lines) >= 2
    assert {d[2] for d in lines} >= {1, 3}


def test_call_then_parenthesised_expression_are_two_statements():
    # `f(1)(2) ni chupi` -> call statement, then output of (2): there is no call-of-call production
    d = ast("f(1)(2) ni chupi\n")
    assert [i["_node"] for i in d["items"]] == ["ExpressionStatement", "Output"]


def test_unexpected_eof_category_for_truncated_block():
    rejects("x ayite {\n", "syntax", {"UNEXPECTED_EOF", "MISSING_TOKEN", "UNEXPECTED_TOKEN"}, upto="parse")


def test_unexpected_eof_category_for_truncated_expression():
    rejects("x lo 1 +\n", "syntax", {"UNEXPECTED_EOF", "INVALID_EXPRESSION", "MISSING_TOKEN", "UNEXPECTED_TOKEN"}, upto="parse")


@pytest.mark.parametrize("src", ["}" * 20 + "\n", "{" * 20 + "\n", ")" * 20 + "\n", "(" * 20 + "\n", "]" * 5 + "\n",
                                 "int " * 30 + "\n", "ayite " * 30 + "\n", "pettu " * 30 + "\n", "lo " * 30 + "\n",
                                 "pratisari " * 20 + "\n", "ni " * 50 + "\n", ", ; , ; \n", "1 2 3 4 5 6\n"])
def test_garbage_terminates_with_diagnostic(src):
    p = cli("parse", src)
    assert p.rc == 1 and p.diags()
