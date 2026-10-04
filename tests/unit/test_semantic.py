"""Phase 4: semantic analysis — accept/reject tables per rule (P19–P40)."""

import pytest

from compiler.diagnostics import SemCategory as S
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import analyze, typed as T
from compiler.semantic.types import ArrayType, BOOL, CHAR, FLOAT, INT, PADHAM, VOID


def sema(src):
    lx = Lexer(src, "t.tel")
    toks = lx.tokenize()
    assert not lx.errors
    p = Parser(toks, "t.tel")
    prog = p.parse()
    assert not p.errors, [str(e) for e in p.errors]
    return analyze(prog, "t.tel")


def accept(src):
    t, d = sema(src)
    assert not d, [str(x) for x in d]
    assert t is not None
    return t


def reject(src, cat):
    t, d = sema(src)
    assert t is None and d, f"expected {cat} for: {src!r}"
    assert d[0].stage == "semantic"
    assert any(x.category == cat for x in d), ([str(x) for x in d], cat)
    return d


# ── declarations, scopes, globals (P19, P20, P33) ──

def test_globals_are_zero_initialized_globals_and_entry_is_top_level():
    t = accept("int x\nx lo 1 pettu\nx ni chupi")
    assert [t.symbols[i].name for i in t.globals] == ["x"]
    assert t.symbols[t.globals[0]].is_global
    assert len(t.entry.stmts) == 3 and isinstance(t.entry.stmts[0], T.TDecl)


def test_global_visible_in_function_only_if_declared_before():
    accept("int g\nint f charya() { g ivvu }")
    reject("int f charya() { g ivvu }\nint g", S.UNDECLARED)


def test_functions_visible_everywhere_forward_and_mutual_recursion():
    accept("int a charya(int n) { b(n) ivvu }\nint b charya(int n) { n > 0 ayite { a(n - 1) ivvu } 0 ivvu }")
    accept("f()\nvoid f charya() { }")


def test_redeclaration_same_scope_and_shadowing():
    reject("int x\nint x", S.REDECLARATION)
    reject("int f charya(int a) { int a\n0 ivvu }", S.REDECLARATION)   # params share outermost scope
    reject("int f charya(int a, int a) { 0 ivvu }", S.REDECLARATION)
    accept("int x\nx lo 1 pettu\nnijam ayite { int x\nx lo 2 pettu }")
    accept("int f charya(int a) { nijam ayite { int a\na lo 1 pettu } a ivvu }")


def test_function_and_variable_share_global_namespace():
    reject("int f charya() { 0 ivvu }\nint f", S.REDECLARATION)
    reject("int f charya() { 0 ivvu }\nint f charya() { 1 ivvu }", S.REDECLARATION)


def test_undeclared_and_use_before_declaration():
    reject("x lo 1 pettu", S.UNDECLARED)
    reject("x ni chupi\nint x", S.UNDECLARED)
    reject("foo(1)", S.UNDECLARED)
    reject("int a[a]", S.UNDECLARED)


def test_block_scope_ends_at_brace():
    reject("nijam ayite { int y }\ny ni chupi", S.UNDECLARED)


def test_range_and_for_variable_scopes():
    reject("prati i 0 nundi 3 varaku { }\ni ni chupi", S.UNDECLARED)
    reject("pratisari (int i lo 0 pettu; i < 3; i++) { }\ni ni chupi", S.UNDECLARED)
    accept("int s\ns lo 0 pettu\nprati i 0 nundi 3 varaku { s lo s + i pettu }")


def test_range_variable_is_int_and_shadows():
    t = accept("int i\ni lo 5 pettu\nprati i 0 nundi 3 varaku { i ni chupi }")
    loop = t.entry.stmts[2]
    assert isinstance(loop, T.TRange) and t.symbols[loop.variable].type == INT


# ── podavu (L48, P39) ──

def test_podavu_builtin_call_and_signature():
    t = accept('"abc" ni chupi\npodavu("abc") ni chupi')
    assert t.symbols[0].name == "podavu" and t.symbols[0].kind == "builtin"
    reject("podavu(1)", S.TYPE_MISMATCH)
    reject('podavu("a", "b")', S.ARGUMENT_COUNT)


def test_podavu_redeclaration_and_inner_shadowing():
    reject("int podavu charya(padham s) { 0 ivvu }", S.REDECLARATION)
    reject("int podavu", S.REDECLARATION)
    accept("int f charya() { int podavu\npodavu lo 1 pettu\npodavu ivvu }")
    reject("int f charya() { int podavu\npodavu(\"a\") ivvu }", S.NOT_CALLABLE)


# ── types, conversions (P27, P28) ──

@pytest.mark.parametrize("dst,val", [
    ("int", "1.9"), ("int", "'a'"), ("int", "nijam"), ("float", "1"), ("char", "65"),
    ("bool", "5"), ("bool", "0.5"), ("char", "nijam"), ("float", "nijam"), ("padham", '"s"'),
])
def test_implicit_arithmetic_conversions_are_accepted(dst, val):
    t = accept(f"{dst} x\nx lo {val} pettu")
    assign = t.entry.stmts[1]
    assert assign.value.type.name == dst


@pytest.mark.parametrize("dst,val", [
    ("int", '"s"'), ("padham", "1"), ("padham", "'a'"), ("padham", "nijam"), ("float", '"s"'),
    ("char", '"s"'), ("bool", '"s"'),
])
def test_invalid_implicit_conversions_rejected(dst, val):
    reject(f"{dst} x\nx lo {val} pettu", S.TYPE_MISMATCH)


def test_conversion_nodes_are_explicit_in_the_tree():
    t = accept("float x\nx lo 1 pettu")
    v = t.entry.stmts[1].value
    assert isinstance(v, T.TConvert) and not v.explicit and v.type == FLOAT and v.operand.type == INT


def test_explicit_casts():
    accept("int x\nx lo (int) 3.7 pettu\nchar c\nc lo (char) 65 pettu")
    accept('padham s\ns lo (padham) \'a\' pettu\nchar c\nc lo (char) s pettu')
    accept("float f\nf lo (float) nijam pettu")
    reject('int x\nx lo (int) "s" pettu', S.INVALID_CONVERSION)
    reject("padham s\ns lo (padham) 1 pettu", S.INVALID_CONVERSION)
    reject("padham s\ns lo (padham) 1.5 pettu", S.INVALID_CONVERSION)
    reject("int x\nx lo (void) 1 pettu", S.VOID_MISUSE)


@pytest.mark.parametrize("expr,typ", [
    ("1 + 2", INT), ("1 + 2.0", FLOAT), ("'a' + 'b'", INT), ("nijam + nijam", INT),
    ("7 % 3", INT), ("'a' % 2", INT), ("nijam % 2", INT),
    ("1 < 2", BOOL), ("1.5 >= 2", BOOL), ("1 == 1.0", BOOL), ("nijam != 2", BOOL),
    ('"a" == "b"', BOOL), ('"a" + "b"', PADHAM), ("1 && 0.5", BOOL), ("1 || 0", BOOL),
    ("!5", BOOL), ("-1", INT), ("-'a'", INT), ("+nijam", INT), ("-1.5", FLOAT),
])
def test_operator_result_types(expr, typ):
    t = accept(f"{expr} ni chupi")
    assert t.entry.stmts[0].value.type == typ


@pytest.mark.parametrize("expr", [
    "1.5 % 2", "2 % 1.5", '"a" - "b"', '"a" * 2', '"a" + 1', "1 + \"a\"", '"a" < "b"',
    '"a" && nijam', '!"a"', '-"a"', '"a" == 1', "'a' == \"a\"",
])
def test_invalid_operands_rejected(expr):
    reject(f"{expr} ni chupi", S.INVALID_OPERAND)


def test_usual_arithmetic_conversions_insert_converts():
    t = accept("1 + 2.0 ni chupi")
    b = t.entry.stmts[0].value
    assert isinstance(b.left, T.TConvert) and b.left.type == FLOAT


def test_conditions_require_arithmetic():
    accept("5 ayite { }\n0.5 ayite { }\n'a' unnanta varaku { aapu }")
    reject('"s" ayite { }', S.INVALID_CONDITION)
    reject('"s" unnanta varaku { }', S.INVALID_CONDITION)
    reject('pratisari (int i lo 0 pettu; "s"; i++) { }', S.INVALID_CONDITION)
    t = accept("5 ayite { }")
    assert t.entry.stmts[0].condition.type == BOOL


def test_integer_literal_range_p36():
    accept("9223372036854775807 ni chupi\n0xFF ni chupi\n0777 ni chupi")
    reject("9223372036854775808 ni chupi", S.LITERAL_OUT_OF_RANGE)
    reject("0xFFFFFFFFFFFFFFFF ni chupi", S.LITERAL_OUT_OF_RANGE)
    reject("-9223372036854775808 ni chupi", S.LITERAL_OUT_OF_RANGE)
    accept("-9223372036854775807 - 1 ni chupi")


def test_literal_values():
    t = accept("0x1F ni chupi\n017 ni chupi\n'\\xFF' ni chupi\n'\\n' ni chupi\n\"a\\tb\\x41\" ni chupi\nNIJAM ni chupi")
    vals = [s.value.value for s in t.entry.stmts]
    assert vals == [31, 15, -1, 10, b"a\tbA", True]


# ── assignment targets (P29, P35) ──

def test_assignment_target_rules():
    reject("int f charya() { 0 ivvu }\nf lo 1 pettu", S.NOT_ASSIGNABLE)
    reject("int a[3]\na lo 1 pettu", S.NOT_ASSIGNABLE)
    reject("int a[3][3]\na[1] lo 1 pettu", S.NOT_ASSIGNABLE)
    reject('padham s\ns lo "abc" pettu\ns[0] lo \'x\' pettu', S.NOT_ASSIGNABLE)
    reject("padham s\ns[0] ni chaduvu", S.NOT_ASSIGNABLE)
    reject("int a[3]\na ni chaduvu", S.NOT_ASSIGNABLE)
    accept("int a[3][3]\na[1][2] lo 5 pettu\na[1][2] ni chaduvu")


def test_arrays_not_valid_as_values():
    reject("int a[3]\na ni chupi", S.INVALID_OPERAND)
    reject("int a[3]\nint x\nx lo a pettu", S.INVALID_OPERAND)
    reject("int a[3]\na + 1 ni chupi", S.INVALID_OPERAND)
    reject("int a[3]\na ayite { }", S.INVALID_OPERAND)
    reject("int a[3][3]\nint x\nx lo a[1] pettu", S.INVALID_OPERAND)


def test_increment_decrement_operand_types_p35():
    accept("int i\ni lo 0 pettu\nfloat f\nf lo 0.0 pettu\nchar c\nc lo 'a' pettu\nint a[2]\n"
           "pratisari (int k lo 0 pettu; k < 1; k++) { }\n"
           "pratisari (i lo 0 pettu; i < 1; --i) { }\npratisari (f lo 0.0 pettu; f < 1; f++) { }\n"
           "pratisari (c lo 'a' pettu; c < 'z'; c++) { }\npratisari (int k lo 0 pettu; k < 1; a[0]++) { }")
    reject("bool b\nb lo nijam pettu\npratisari (b lo nijam pettu; b; b++) { }", S.INVALID_OPERAND)
    reject('padham s\ns lo "a" pettu\npratisari (s lo "a" pettu; nijam; s++) { }', S.INVALID_OPERAND)


def test_for_init_targets_p34():
    accept("int i\npratisari (i 0 tho modhalu; i < 3; i++) { }")
    reject("int a[3]\npratisari (a 0 tho modhalu; nijam; a[0]++) { }", S.NOT_ASSIGNABLE)
    reject("pratisari (zz 0 tho modhalu; nijam; zz++) { }", S.UNDECLARED)
    reject('int i\npratisari (i "s" tho modhalu; i < 3; i++) { }', S.TYPE_MISMATCH)
    reject("pratisari (void v; nijam; v++) { }", S.VOID_MISUSE)


# ── arrays (P21, P22, P29) ──

def test_array_dimension_constant_checks_p21():
    accept("int n\nn lo 5 pettu\nint a[n]\nint b[n + 1][2]\nint c[2 * 3]\nint d[(int) 2.9]")
    reject("int a[0]", S.INVALID_ARRAY_SIZE)
    reject("int a[-1]", S.INVALID_ARRAY_SIZE)
    reject("int a[2][0]", S.INVALID_ARRAY_SIZE)
    reject("int a[1 - 1]", S.INVALID_ARRAY_SIZE)
    reject("int a[0.5]", S.INVALID_ARRAY_SIZE)       # converts to constant 0
    reject('int a["x"]', S.TYPE_MISMATCH)
    accept("int n\nint a[n]\nint b[1 / 0 + 1]")      # non-constant (traps) -> runtime check


def test_indices_and_dimensions_count():
    reject("int a[3]\na[1][2] ni chupi", S.TOO_MANY_INDICES)
    reject("int x\nx[0] ni chupi", S.NOT_INDEXABLE)
    reject("int f charya() { 0 ivvu }\nf[0] ni chupi", S.NOT_INDEXABLE)
    reject('padham s\ns lo "ab" pettu\ns[0][1] ni chupi', S.TOO_MANY_INDICES)
    reject("int a[3]\na[\"x\"] ni chupi", S.TYPE_MISMATCH)
    accept("int a[3]\na[1.5] lo 1 pettu\na['a'] lo 2 pettu\na[nijam] lo 3 pettu")   # D9/§12.3: ordinary conversion model


def test_partial_indexing_types_and_string_index():
    t = accept('int a[2][3][4]\nint x\nx lo a[1][2][3] pettu\npadham s\ns lo "ab" pettu\nchar c\nc lo s[1] pettu')
    ty = t.entry.stmts[2].value
    assert ty.type == INT
    reject("int a[2][3]\nint x\nx lo a[1] pettu", S.INVALID_OPERAND)


def test_array_arguments_p29():
    accept("int sum charya(int a[], int n) { a[0] ivvu }\nint m[3]\nsum(m, 3) ni chupi")
    accept("int sum charya(int a[]) { a[0] ivvu }\nint m[3][4]\nsum(m[1]) ni chupi")
    reject("int sum charya(int a[]) { a[0] ivvu }\nint m[3][4]\nsum(m) ni chupi", S.TYPE_MISMATCH)
    reject("int sum charya(int a[]) { a[0] ivvu }\nfloat m[3]\nsum(m) ni chupi", S.TYPE_MISMATCH)
    reject("int sum charya(int a[]) { a[0] ivvu }\nsum(5) ni chupi", S.TYPE_MISMATCH)
    reject("int f charya(int a) { a ivvu }\nint m[3]\nf(m) ni chupi", S.INVALID_OPERAND)


def test_array_parameter_is_rank1_so_double_index_rejected():
    reject("int f charya(int a[]) { a[0][1] ivvu }", S.TOO_MANY_INDICES)


# ── calls / void (P26) ──

def test_call_checking():
    reject("int f charya(int a) { a ivvu }\nf(1, 2) ni chupi", S.ARGUMENT_COUNT)
    reject("int f charya(int a) { a ivvu }\nf() ni chupi", S.ARGUMENT_COUNT)
    reject("int x\nx(1)", S.NOT_CALLABLE)
    reject('int f charya(int a) { a ivvu }\nf("s") ni chupi', S.TYPE_MISMATCH)
    accept("float f charya(float a) { a ivvu }\nf(1) ni chupi")


def test_void_function_rules():
    accept("void p charya() { 1 ni chupi }\np()")
    reject("void p charya() { 1 ivvu }", S.INVALID_RETURN)
    reject("void p charya() { }\nint x\nx lo p() pettu", S.VOID_MISUSE)
    reject("void p charya() { }\np() ni chupi", S.VOID_MISUSE)
    reject("void p charya() { }\np() + 1 ni chupi", S.VOID_MISUSE)
    reject("void p charya() { }\np() ayite { }", S.VOID_MISUSE)
    reject("void p charya() { }\nint f charya() { p() ivvu }", S.VOID_MISUSE)
    reject("void v", S.VOID_MISUSE)
    reject("void p charya(void a) { }", S.VOID_MISUSE)
    reject("void a[3]", S.VOID_MISUSE)
    reject("int a[3]\na[(void) 1] ni chupi", S.VOID_MISUSE)


def test_return_rules():
    reject("1 ivvu", S.INVALID_RETURN)
    reject('int f charya() { "s" ivvu }', S.TYPE_MISMATCH)
    reject("int a[2]\nint f charya() { a ivvu }", S.INVALID_OPERAND)
    t = accept("float f charya() { 1 ivvu }")
    assert isinstance(t.functions[0].body.stmts[0].value, T.TConvert)


def test_break_continue_context():
    reject("aapu", S.BREAK_OUTSIDE_LOOP)
    reject("saagu", S.CONTINUE_OUTSIDE_LOOP)
    reject("nijam ayite { aapu }", S.BREAK_OUTSIDE_LOOP)
    reject("int f charya() { aapu\n0 ivvu }", S.BREAK_OUTSIDE_LOOP)
    t = accept("nijam unnanta varaku { prati i 0 nundi 2 varaku { saagu } aapu }")
    w = t.entry.stmts[0]
    inner = w.body.stmts[0]
    assert w.body.stmts[1].loop_id == w.loop_id
    assert inner.body.stmts[0].loop_id == inner.loop_id != w.loop_id


# ── definite initialization (P23, P24) ──

def test_definite_initialization():
    reject("int f charya() { int x\nx ivvu }", S.UNINITIALIZED)
    reject("int f charya(int c) { int x\nc ayite { x lo 1 pettu } x ivvu }", S.UNINITIALIZED)
    accept("int f charya(int c) { int x\nc ayite { x lo 1 pettu } lekunte { x lo 2 pettu } x ivvu }")
    accept("int f charya() { int x\nx ni chaduvu\nx ivvu }")
    reject("int f charya(int n) { int x\nn > 0 unnanta varaku { x lo 1 pettu\naapu } x ivvu }", S.UNINITIALIZED)
    reject("int f charya(int n) { int x\nprati i 0 nundi n varaku { x lo 1 pettu } x ivvu }", S.UNINITIALIZED)
    accept("int f charya(int n) { int x\nnijam unnanta varaku { x lo 1 pettu\naapu } x ivvu }")
    accept("int f charya(int n) { int x\n1 unnanta varaku { x lo 1 pettu\naapu } x ivvu }")
    reject("int f charya(int n) { int x\n0 unnanta varaku { x lo 1 pettu } x ivvu }", S.UNINITIALIZED)
    accept("int f charya() { int x\npratisari (int i lo 0 pettu; i < 1; i++) { }\n0 ivvu }")
    reject("int f charya() { int x\npratisari (int i; i < 1; i++) { }\n0 ivvu }", S.UNINITIALIZED)
    accept("int f charya() { int x\npratisari (x lo 0 pettu; x < 1; x++) { }\n0 ivvu }")
    accept("int f charya() { int x\npratisari (x 0 tho modhalu; x < 1; x++) { }\nx ivvu }")
    accept("int f charya(int a) { a ivvu }")                         # parameters are initialized


def test_uninitialized_in_expression_and_conditions():
    reject("int f charya() { int x\nint y\ny lo x + 1 pettu\ny ivvu }", S.UNINITIALIZED)
    reject("int f charya() { int x\nx ayite { }\n0 ivvu }", S.UNINITIALIZED)
    reject("int f charya() { int x\nint a[2]\na[x] lo 1 pettu\n0 ivvu }", S.UNINITIALIZED)
    reject("int f charya() { int x\nx++ ni chupi\n0 ivvu }".replace("x++ ni chupi", "pratisari (int i lo 0 pettu; i < 1; x++) { }"), S.UNINITIALIZED)


def test_arrays_are_exempt_and_globals_always_initialized_p23():
    accept("int f charya() { int a[3]\na[0] ni chupi\n0 ivvu }")
    accept("int g\nint f charya() { g ivvu }\ng ni chupi")


def test_unreachable_reads_not_reported_and_declaration_resets():
    accept("int f charya() { int x\n1 ivvu\nx ni chupi }".replace("x ni chupi }", "x ni chupi\n}"))
    reject("int f charya() { 1 unnanta varaku { int x\nx ni chupi\naapu } 0 ivvu }", S.UNINITIALIZED)
    # a declaration inside a loop body makes the variable uninitialized again each iteration
    reject("int f charya() { int s\ns lo 0 pettu\nprati i 0 nundi 3 varaku { int x\ns lo s + x\n"
           "x lo 1 pettu } s ivvu }".replace("s lo s + x\n", "s lo s + x pettu\n"), S.UNINITIALIZED)


# ── return paths (P25) ──

def test_missing_return_rules():
    reject("int f charya() { }", S.MISSING_RETURN)
    reject("int f charya(int c) { c ayite { 1 ivvu } }", S.MISSING_RETURN)
    accept("int f charya(int c) { c ayite { 1 ivvu } lekunte { 2 ivvu } }")
    accept("int f charya(int c) { c ayite { 1 ivvu } lekunte c ayite { 2 ivvu } lekunte { 3 ivvu } }")
    reject("int f charya(int c) { c ayite { 1 ivvu } lekunte c ayite { 2 ivvu } }", S.MISSING_RETURN)
    accept("int f charya() { nijam unnanta varaku { } }")                     # constant-true, no aapu
    reject("int f charya() { nijam unnanta varaku { aapu } }", S.MISSING_RETURN)
    reject("int f charya(int n) { n > 0 unnanta varaku { 1 ivvu } }", S.MISSING_RETURN)
    reject("int f charya(int n) { prati i 0 nundi n varaku { 1 ivvu } }", S.MISSING_RETURN)
    accept("int f charya() { 1 ivvu\n2 ni chupi }")                           # code after return allowed
    accept("void f charya() { }\nvoid g charya() { 1 ni chupi }")


def test_if_condition_is_not_folded_for_return_analysis():
    reject("int f charya() { nijam ayite { 1 ivvu } }", S.MISSING_RETURN)


# ── diagnostics order and multiple errors ──

def test_all_errors_collected_and_sorted():
    _, d = sema("x lo 1 pettu\nint y\ny lo \"s\" pettu\nz ni chupi")
    assert [x.category for x in d] == [S.UNDECLARED, S.TYPE_MISMATCH, S.UNDECLARED]
    assert [x.line for x in d] == sorted(x.line for x in d)


def test_error_spans_point_at_offending_construct():
    _, d = sema("int x\nx lo \"s\" pettu")
    assert (d[0].line, d[0].column) == (2, 6)


# ── typed tree shape ──

def test_typed_tree_symbol_resolution_and_scope_depth():
    t = accept("int g\nint f charya(int p) { int l\nl lo p + g pettu\nl ivvu }")
    f = t.functions[0]
    names = {s.name: s for s in t.symbols}
    assert names["p"].scope_depth == names["l"].scope_depth == 1
    assert names["g"].is_global and not names["l"].is_global
    assert names["l"].owner == "f" and f.params == [names["p"].id]


def test_evaluation_order_and_loop_lowering_inputs_present():
    t = accept("pratisari (int i lo 0 pettu; i < 3; i++) { }")
    loop = t.entry.stmts[0]
    assert isinstance(loop, T.TFor) and len(loop.init) == 2 and isinstance(loop.update, T.TIncDec)


# ── design-authority rulings (plan §L) ──

def test_q002_point_of_declaration_rule():
    # a use before a later same-scope declaration sees the enclosing declaration
    accept("int x\nx lo 1 pettu\nnijam ayite { x ni chupi\nint x\nx lo 2 pettu }")
    reject("nijam ayite { x ni chupi\nint x }", S.UNDECLARED)
    accept("int f charya() { int a\na lo 1 pettu\nnijam ayite { a ni chupi\nint a\na lo 2 pettu }\n0 ivvu }")


def test_q003_trapping_dimension_is_not_a_constant():
    accept("int a[1 / 0]")                       # evaluated (and trapping) at run time
    accept("int a[(-9223372036854775807 - 1) / -1]")
    accept("int a[5 % 0]")
    reject("int a[10 - 10]", S.INVALID_ARRAY_SIZE)


def test_q006_for_declaration_without_initializer():
    accept("pratisari (int i; nijam; i lo 0 pettu) { aapu }")
    reject("pratisari (int i; i < 3; i lo i + 1 pettu) { }", S.UNINITIALIZED)


def test_q008_padham_arrays_and_parameters():
    accept('padham a[3]\na[0] lo "x" pettu\na[1] lo a[0] + "y" pettu\na[1] ni chupi\n'
           'int f charya(padham p[]) { podavu(p[0]) ivvu }\nf(a) ni chupi')
