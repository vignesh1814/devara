"""Windows (Win64 / MinGW-w64) target attacks.

`devara run|build|asm --target windows`, C compiler from env DEVARA_CC (x86_64-w64-mingw32-gcc), program launched through
the prefix in env DEVARA_RUNNER (wine, with WINEDEBUG=-all).  The contract: observable behaviour (stdout bytes, exit
status, runtime-error text) is byte-identical to the Linux target and to the reference interpreter; stdout is binary (no
CRLF translation); `\\r\\n` in the input behaves like `\\n`.

Skipped only when `x86_64-w64-mingw32-gcc` or `wine` is not installed (on a Windows host: when no MinGW-w64 gcc is on
PATH; the program then runs natively, without wine).  Until the Windows target is merged these tests fail
(unknown option); they are the acceptance tests for it.
"""
import pytest

from tests.validation import stress_progs as sp
from tests.validation.corpus_util import CORPUS, expected, pid, programs
from tests.validation.stress_util import (HAVE_WINDOWS_TOOLS, WIN_ENV, build, check_against_reference, devara, norm,
                                          reference, run, run_win, src_path)

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not HAVE_WINDOWS_TOOLS, reason="needs MinGW-w64 gcc and wine (or a Windows host)")]

OPTS = ["-O0", "-O1"]


def win(src, opt="-O1", stdin=b""):
    return run_win(src, opt, stdin)


def crlf_to_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def vs_reference(src, data=b"", opts=OPTS, expect_status=None):
    """Windows output == reference interpreter on the same bytes (both drop exactly one \\r before each \\n, Q-014)."""
    ref = reference(src, data)
    if expect_status is not None:
        assert ref.status == expect_status
    for opt in opts:
        p = win(src, opt, data)
        assert p.rc == ref.status, f"{opt}: rc={p.rc} ref={ref.status} ({ref.error})\n{p.err}\n{src}"
        assert norm(p.out) == norm(ref.stdout), f"{opt}: stdout differs\n got={p.out[:500]!r}\n ref={ref.stdout[:500]!r}\n{src}"
        if ref.status:
            assert p.err.strip() == f"devara: runtime error: {ref.error}", p.err
        else:
            assert p.err == "", f"unexpected stderr {p.err!r}"
    return ref


# =============================================================================================================
# 0. CLI surface
# =============================================================================================================
HELLO = 'int a\na lo 40 + 2 pettu\na ni chupi\n"hi" ni chupi\n'


def test_asm_for_windows_target_succeeds_and_differs_from_linux():
    f = src_path(HELLO)
    w = devara(["asm", "--target", "windows", "-O1", f], env=WIN_ENV)
    assert w.rc == 0, w.err
    linux = devara(["asm", "--target", "linux", "-O1", f])   # explicit: on a Windows host the default is windows
    assert linux.rc == 0
    assert w.out != linux.out and w.out.strip()
    assert b".intel_syntax" in w.out


@pytest.mark.parametrize("opt", OPTS)
def test_build_for_windows_writes_a_pe_executable(opt, tmp_path):
    out = tmp_path / "hello.exe"
    b = devara(["build", "--target", "windows", opt, src_path(HELLO), "-o", str(out)], env=WIN_ENV)
    assert b.rc == 0, b.err
    data = out.read_bytes()
    assert data[:2] == b"MZ", "not a PE image"
    assert b"PE\0\0" in data[:1024]


@pytest.mark.parametrize("opt", OPTS)
def test_run_for_windows_matches_linux_run(opt):
    w, l = win(HELLO, opt), run(HELLO, opt)
    assert (w.rc, w.out, w.err) == (l.rc, l.out, l.err) == (0, b"42\nhi\n", "")


def test_unknown_target_is_a_usage_error():
    p = devara(["run", "--target", "plan9", src_path(HELLO)], env=WIN_ENV)
    assert p.rc == 2 and "target" in p.err.lower()


def test_windows_build_without_wine_runner_still_builds(tmp_path):
    out = tmp_path / "x.exe"
    b = devara(["build", "--target", "windows", src_path(HELLO), "-o", str(out)], env={k: v for k, v in WIN_ENV.items() if k == "DEVARA_CC"})
    assert b.rc == 0, b.err
    assert out.read_bytes()[:2] == b"MZ"


# =============================================================================================================
# 1. representative corpus subset (~40 programs, every category) at -O0 and -O1
# =============================================================================================================
PICK = {
    "arrays": ["001", "004", "009", "013"], "datastructures": ["074", "077", "080"], "dp": ["084", "087", "089"], "graphs": ["094", "096", "099"],
    "math": ["047", "049", "052", "060"], "misc": ["104", "107", "108", "109", "110", "113", "116"], "recursion": ["065", "068", "070"],
    "searching": ["025", "028"], "sorting": ["015", "018", "020"], "strings": ["033", "034", "038", "046"],
}
SUBSET = [t for t in programs() if t.parent.name in PICK and t.stem.split("_")[0] in PICK[t.parent.name]]


def test_subset_covers_every_category_with_about_40_programs():
    assert {t.parent.name for t in SUBSET} == set(PICK)
    assert 36 <= len(SUBSET) <= 44, len(SUBSET)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("tel", SUBSET, ids=pid)
def test_corpus_subset_on_windows(tel, opt):
    inp, out, ex, err = expected(tel)
    p = win(tel.read_text(encoding="latin-1"), opt, inp)
    assert p.out == out, "stdout differs from the oracle"
    assert p.rc == ex
    if ex:
        assert p.err.strip() == err.strip()
    else:
        assert p.err == ""


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("tel", [t for t in programs() if "_rt_" in t.stem], ids=pid)
def test_runtime_error_corpus_exit_codes_on_windows(tel, opt):
    inp, out, ex, err = expected(tel)
    assert ex == 1
    p = win(tel.read_text(encoding="latin-1"), opt, inp)
    assert p.rc == 1, f"runtime error must exit with status 1 (got {p.rc})"
    assert p.out == out
    assert p.err.strip() == err.strip()


@pytest.mark.parametrize("tel", programs()[::7], ids=pid)
def test_windows_and_linux_outputs_identical(tel):
    inp, _, _, _ = expected(tel)
    src = tel.read_text(encoding="latin-1")
    w, l = win(src, "-O1", inp), run(src, "-O1", inp)
    assert (w.rc, w.out, w.err) == (l.rc, l.out, l.err)


# =============================================================================================================
# 2. runtime-error exit codes with pending output
# =============================================================================================================
RT = {
    "division by zero": "int z\nz ni chaduvu\n10 / z ni chupi\n",
    "remainder by zero": "int z\nz ni chaduvu\n10 % z ni chupi\n",
    "integer overflow in division": "int z\nz ni chaduvu\n(-9223372036854775807 - 1) / (z - 1) ni chupi\n",
    "invalid input": "int z\nz ni chaduvu\nz ni chupi\n",
    "string index out of range": "int z\nz ni chaduvu\npadham s\ns lo \"abc\" pettu\ns[z + 3] ni chupi\n",
    "invalid char conversion": "int z\nz ni chaduvu\npadham s\ns lo \"abc\" pettu\n(char) s ni chupi\n",
    "invalid array size": "int z\nz ni chaduvu\nint a[z - 1]\na[0] ni chupi\n",
}
RT_INPUT = {"invalid input": b"x\n"}


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("msg", list(RT))
def test_runtime_error_exit_status_message_and_flushed_stdout(msg, opt):
    pre = 'prati i 0 nundi 3 varaku { i ni chupi }\n"partial" ni chupi\n'
    src = pre + RT[msg]
    p = win(src, opt, RT_INPUT.get(msg, b"0\n"))
    assert p.rc == 1, f"exit status {p.rc}"
    assert p.out == b"0\n1\n2\npartial\n", "stdout must be flushed before the error exit"
    assert p.err.strip() == f"devara: runtime error: {msg}"


@pytest.mark.parametrize("opt", OPTS)
def test_large_buffered_output_is_flushed_before_runtime_error(opt):
    src = ('int z\nz ni chaduvu\nprati i 0 nundi 30000 varaku { i ni chupi }\n1 / z ni chupi\n')
    p = win(src, opt, b"0\n")
    assert p.rc == 1 and p.out == b"".join(b"%d\n" % i for i in range(30000))
    assert "division by zero" in p.err


@pytest.mark.parametrize("opt", OPTS)
def test_eof_on_input_is_a_runtime_error_with_status_1(opt):
    p = win("int a\na ni chaduvu\nint b\nb ni chaduvu\na + b ni chupi\n", opt, b"5\n")
    assert p.rc == 1 and p.err.strip() == "devara: runtime error: invalid input" and p.out == b""


# =============================================================================================================
# 3. CRLF input must behave like LF
# =============================================================================================================
TYPES = ["int", "float", "char", "bool", "padham"]


def reader(types):
    lines = []
    for i, t in enumerate(types):
        lines += [f"{t} v{i}", f"v{i} ni chaduvu", f"v{i} ni chupi"]
    return "\n".join(lines) + "\n\"end\" ni chupi\n"


CRLF_CASES = [
    (["int", "padham"], b"5\r\nhello\r\n"), (["padham", "padham"], b"a\r\nb\r\n"), (["int", "int", "padham"], b"1\r\n2\r\nline\r\n"),
    (["char", "padham"], b"x\r\nrest\r\n"), (["padham"], b"abc\r\n"), (["bool", "bool"], b"nijam\r\nabaddham\r\n"),
    (["int", "padham", "padham"], b"5  \r\n\r\nx\r\n"), (["padham", "int"], b"\r\n7\r\n"), (["float", "padham"], b"1.5\r\nz y\r\n"),
    (["padham", "padham", "padham"], b"\r\n\r\n\r\n"), (["int", "float", "char", "bool", "padham"], b"-4 2.5 q 1\r\ntail text  \r\n"),
    (["int", "padham"], b"5\r\n"), (["padham"], b"no newline at all"), (["padham", "padham"], b"a\r\r\nb\r\n"),
    (["padham"], b"a\rb\r\n"), (["int", "int"], b"1\r\n\r\n\r\n2\r\n"), (["char", "char", "char"], b"a\r\nb\r\n c\r\n"),
]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("types,data", CRLF_CASES)
def test_crlf_input_behaves_like_lf(types, data, opt):
    src = reader(types)
    vs_reference(src, data, opts=(opt,))
    # and literally equal to the LF run on the same target
    if b"\r\r\n" not in data:      # (the translated text would itself still contain CRLF)
        a, b = win(src, opt, data), win(src, opt, crlf_to_lf(data))
        assert (a.rc, a.out, a.err) == (b.rc, b.out, b.err)


@pytest.mark.parametrize("opt", OPTS)
def test_many_crlf_lines_of_every_type(opt):
    n = 3000
    data = f"{n}\r\n".encode() + b"".join(b"%d %.3f\r\nline %d\r\n" % (i - 1500, i / 7.0, i) for i in range(n))
    src = sp.prog("int n", "n ni chaduvu", "int w", "float x", "padham s", "int total", "float ft", "total lo 0 pettu", "ft lo 0.0 pettu",
                  "prati i 0 nundi n varaku { w ni chaduvu\n x ni chaduvu\n s ni chaduvu\n total lo total + w + podavu(s) pettu\n ft lo ft + x pettu }",
                  "total ni chupi", "ft ni chupi", "s ni chupi", "podavu(s) ni chupi")
    ref = vs_reference(src, data, opts=(opt,), expect_status=0)
    assert ref.stdout.endswith(b"line 2999\n9\n")


@pytest.mark.parametrize("opt", OPTS)
def test_padham_lines_do_not_carry_a_trailing_carriage_return(opt):
    p = win("padham s\ns ni chaduvu\npodavu(s) ni chupi\ns[podavu(s) - 1] ni chupi\n", opt, b"abc\r\n")
    assert (p.rc, p.out) == (0, b"3\nc\n")


@pytest.mark.parametrize("opt", OPTS)
def test_eof_without_trailing_newline_after_crlf_lines(opt):
    vs_reference(reader(["padham", "padham"]), b"first\r\nsecond", opts=(opt,))


# =============================================================================================================
# 4. binary output / input
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
def test_every_byte_value_is_written_unchanged(opt):
    src = "prati i 0 nundi 256 varaku { (char) i ni chupi }\n"
    p = win(src, opt)
    assert p.rc == 0
    assert p.out == b"".join(bytes([i]) + b"\n" for i in range(256))


@pytest.mark.parametrize("opt", OPTS)
def test_carriage_return_and_newline_in_strings_and_chars(opt):
    src = ('"a\\r\\nb\\0c\\xff" ni chupi\n\'\\r\' ni chupi\n\'\\n\' ni chupi\n"\\r" + "\\n" ni chupi\n(padham) \'\\n\' ni chupi\n'
           'padham s\ns lo "x\\r\\ry\\n\\nz" pettu\ns ni chupi\npodavu(s) ni chupi\n')
    p = win(src, opt)
    assert p.rc == 0
    assert p.out == b"a\r\nb\x00c\xff\n" + b"\r\n" + b"\n\n" + b"\r\n\n" + b"\n\n" + b"x\r\ry\n\nz\n" + b"7\n"


@pytest.mark.parametrize("opt", OPTS)
def test_large_binary_output_has_no_crlf_translation(opt):
    src = "prati i 0 nundi 100000 varaku { '\\n' ni chupi\n '\\r' ni chupi }\n"
    p = win(src, opt)
    assert p.rc == 0 and p.out == b"\n\n\r\n" * 100000


@pytest.mark.parametrize("opt", OPTS)
def test_high_and_nul_bytes_on_input_pass_through(opt):
    src = "char c\nint i\nprati i 0 nundi 4 varaku { c ni chaduvu\n (int) c ni chupi\n c ni chupi }\n"
    vs_reference(src, b"\xff\x80\xe9\x7f", opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
def test_ctrl_z_byte_on_input_is_data_not_end_of_file(opt):
    # Only CRLF is translated on input; every other byte (including 0x1A, EOF in Windows text mode) is data, as on Linux.
    src = "char c\nint i\nprati i 0 nundi 3 varaku { c ni chaduvu\n (int) c ni chupi }\npadham s\ns ni chaduvu\npodavu(s) ni chupi\ns ni chupi\n"
    vs_reference(src, b"\x1aA\x1a\nab\x1acd\r\n", opts=(opt,), expect_status=0)


# =============================================================================================================
# 5. output formats of the C runtime on Windows (msvcrt-style %g, %lld, strtod ...) equal Linux
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
def test_float_formats_exponents_inf_nan(opt):
    vals = ["1.0", "10.0", "100000.0", "1000000.0", "10000000.0", "0.0001", "0.00001", "0.000001", "123456789.0", "3.14159265358979", "0.1", "100.5",
            "123456.0", "1234567.0", "0.5", "999999.5", "99999.95", "0.00012345678"]
    L = ["float z", "z ni chaduvu", "float x", "float y"]
    for v in vals:
        L += [f"x lo {v} pettu", "x ni chupi", "(0.0 - x) ni chupi"]
    L += ["x lo 1.0 pettu", "prati i 0 nundi 40 varaku { x lo x * 7.5 pettu\n x ni chupi }",       # 1e+xx exponents up to 1e+35
          "prati i 0 nundi 6 varaku { x lo x * x pettu\n x ni chupi\n (0.0 - x) ni chupi }",       # 3-digit exponents, then inf
          "x lo 1.0 pettu", "prati i 0 nundi 50 varaku { x lo x / 7.5 pettu\n x ni chupi }",
          "prati i 0 nundi 6 varaku { x lo x * x pettu\n x ni chupi }",                              # 1e-xxx, denormals, 0
          "y lo 1.0 / z pettu", "y ni chupi", "(0.0 - y) ni chupi", "y lo z / z pettu", "y ni chupi", "z ni chupi", "(0.0 - z) ni chupi",
          "y lo (0.0 - 1.0) / z pettu", "y ni chupi", "(y * 0.0) ni chupi"]
    src = "\n".join(L) + "\n"
    ref = vs_reference(src, b"0.0\n", opts=(opt,), expect_status=0)
    assert b"e+" in ref.stdout and b"e-" in ref.stdout and b"inf" in ref.stdout


@pytest.mark.parametrize("opt", OPTS)
def test_int_extremes_output_and_input(opt):
    src = ("int a\nint b\na ni chaduvu\nb ni chaduvu\na ni chupi\nb ni chupi\n(a + 1) ni chupi\n(b - 1) ni chupi\n"
           "a * 3 ni chupi\nb / 2 ni chupi\n(float) a ni chupi\n(float) b ni chupi\n(char) a ni chupi\n(bool) b ni chupi\n"
           "(int) (float) a ni chupi\n(int) (1000000000.0 * 1000000000.0 * 1000000000.0) ni chupi\n(int) (0.0 - 1000000000.0 * 1000000000.0 * 1000000000.0) ni chupi\n")
    vs_reference(src, b"9223372036854775807\r\n-9223372036854775808\r\n", opts=(opt,), expect_status=0)


PIECES = [b"0", b"-3", b"+12", b"007", b"9223372036854775807", b"-9223372036854775808", b"9223372036854775808", b"3.5", b"-0.25", b"1e3", b".5", b"nijam",
          b"abaddham", b"NIJAM", b"1", b"x", b"hello", b"12abc", b"inf", b"nan", b"1e400", b"1e-400", b"1,5", b"1e", b"-", b"+"]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("t", ["int", "float", "bool", "char"])
@pytest.mark.parametrize("piece", PIECES)
def test_token_parsing_matches_reference(piece, t, opt):
    vs_reference(reader([t, "padham"]), piece + b"\r\nrest\r\n", opts=(opt,))


# =============================================================================================================
# 6. calling convention: >4 arguments (shadow space + stack args), float arguments in positions 1-8
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 17, 24])
def test_int_argument_counts_around_the_four_register_limit(n, opt):
    vs_reference(*sp.int_args(n), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("n", [5, 8, 10, 13, 17, 24, 33, 40])
@pytest.mark.parametrize("seed", [1, 2])
def test_many_mixed_arguments(n, seed, opt):
    vs_reference(*sp.many_params(seed * 1000 + n, n), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("t,n", [("float", 12), ("float", 40), ("char", 20), ("bool", 20), ("padham", 12), ("int", 40)])
def test_homogeneous_many_arguments(t, n, opt):
    vs_reference(*sp.many_params(n, n, [t] * n), opts=(opt,), expect_status=0)


FLOAT_POS = [{i} for i in range(8)] + [{0, 1, 2, 3}, {4, 5, 6, 7}, {0, 2, 4, 6}, {1, 3, 5, 7}, {0, 1, 2, 3, 4, 5, 6, 7}, {3, 4}, {0, 7}, {2, 5, 8, 9}]


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("floats", FLOAT_POS, ids=lambda s: "f" + "".join(map(str, sorted(s))))
def test_float_arguments_in_positions_1_to_8(floats, opt):
    npar = max(max(floats) + 1, 8)
    vs_reference(*sp.float_positions(npar, floats, seed=len(floats)), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("pattern", ["if", "fi", "iffi", "ififif", "ffffiiii", "iiiiffff", "cbpcbpf"])
def test_alternating_argument_kinds(pattern, opt):
    m = {"i": "int", "f": "float", "c": "char", "b": "bool", "p": "padham"}
    ts = [m[c] for c in pattern * 3]
    vs_reference(*sp.many_params(len(pattern), len(ts), ts), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("depth", [1, 3, 6])
def test_nested_calls_in_arguments_with_stack_args(depth, opt):
    vs_reference(*sp.nested_call_args(depth), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("n", [3, 8])
def test_recursion_passing_stack_arguments(n, opt):
    vs_reference(*sp.recursion_live(n), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
def test_array_arguments_beyond_the_register_slots(opt):
    vs_reference(*sp.array_aliasing(), opts=(opt,), expect_status=0)


# =============================================================================================================
# 7. callee-saved registers (rbx, rsi, rdi, r12-r15, xmm6-xmm15) across runtime and user calls
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(6))
def test_values_live_across_runtime_calls(seed, opt):
    vs_reference(*sp.rt_calls_live(seed), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("ni,nf,seed", [(20, 1, 1), (1, 24, 2), (30, 20, 3), (14, 14, 4), (60, 30, 5)])
def test_many_live_values_across_user_calls(ni, nf, seed, opt):
    vs_reference(*sp.many_live(seed, ni, nf, 80), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(4))
def test_many_live_values_with_strings_chars_bools(seed, opt):
    vs_reference(*sp.many_live(seed + 40, 22, 12, 60, extra_types=True), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
def test_heavy_register_use_then_normal_exit_flushes_everything(opt):
    # the C runtime's exit path (stdio flush) must find rbx/rsi/rdi/r12-r15/xmm6-15 as the entry point received them
    src, stdin = sp.many_live(77, 40, 24, 120, extra_types=True)
    src += "prati i 0 nundi 5000 varaku { i * 3 ni chupi }\n"
    ref = vs_reference(src, stdin, opts=(opt,), expect_status=0)
    assert ref.stdout.endswith(b"14997\n")


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(4))
def test_deep_expression_trees(seed, opt):
    kind = ["int", "float", "mixed", "bool"][seed]
    vs_reference(*sp.deep_expr(seed, 40 if seed < 2 else 7, "right" if seed < 2 else "bal", kind, calls=seed % 2 == 0), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
def test_float_specials_and_int_edges_in_registers(opt):
    vs_reference(*sp.float_specials(), opts=(opt,), expect_status=0)
    vs_reference(*sp.int_edges(), opts=(opt,), expect_status=0)
    vs_reference(*sp.char_signext(), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(4))
def test_short_circuit_side_effects(seed, opt):
    vs_reference(*sp.short_circuit(seed + 50, nterms=8, depth=4), opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(6))
def test_generated_programs(seed, opt):
    from tests.property.proggen import generate
    src, stdin = generate(31000 + seed, 14, pressure=bool(seed % 2))
    vs_reference(src, stdin, opts=(opt,), expect_status=0)


# =============================================================================================================
# 8. heap objects on the Windows target
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
def test_vla_and_strings_in_loops(opt):
    src = sp.prog("int n", "n ni chaduvu", "int total", "total lo 0 pettu", "padham s", "s lo \"\" pettu",
                  "prati i 0 nundi 20000 varaku { int a[n]\n a[n - 1] lo i pettu\n padham t\n t lo \"v\" + (padham) (char) (65 + i % 26) pettu\n total lo total + a[n - 1] + a[0] + podavu(t) pettu\n s lo t + s pettu\n s lo (padham) (char) (97 + i % 26) pettu }",
                  "total ni chupi", "s ni chupi")
    vs_reference(src, b"64\r\n", opts=(opt,), expect_status=0)


@pytest.mark.parametrize("opt", OPTS)
def test_stats_line_on_windows_when_requested(opt):
    p = run(HELLO, opt, b"", "windows", {**WIN_ENV, "DEVARA_RT_STATS": "1"})
    assert p.rc == 0 and p.out == b"42\nhi\n"
    assert p.err.strip() == "devara-rt: live=0"
