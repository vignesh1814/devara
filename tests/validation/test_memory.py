"""Memory-management attacks (heap/runtime-sized arrays freed at scope exit on every path; padham reference counting).

Contract under test: with env DEVARA_RT_STATS=1 the program prints `devara-rt: live=<n>` to stderr at normal exit and n
must be 0.  The "leak" programs allocate several GB in total, so they run under `bash -c 'ulimit -v 204800; exec prog'`
(200 MB address space): a leaking implementation dies of allocation failure long before the loop finishes.  Every program
also runs with MALLOC_PERTURB_ so that freed memory is overwritten (use-after-free shows up as wrong output) and glibc
aborts on a double free (exit status 134, "free(): ..." on stderr).

Each program has (a) a Python closed-form model of its stdout, (b) a small-N variant that is also checked against the
reference interpreter at -O0/-O1 (so the program text itself is validated independently of the memory features), and (c)
a big-N variant run with the cap.  Tests for the unmerged feature are the acceptance tests: they fail until it lands.
"""
import re

import pytest

from tests.validation.corpus_util import expected, pid, programs
from tests.validation.stress_util import build, check_against_reference, run, run_exe_limited
from tests.validation.stress_progs import prog

pytestmark = pytest.mark.slow

CAP_KB = 200 * 1024
ENV = {"DEVARA_RT_STATS": "1", "MALLOC_PERTURB_": "165"}
LIVE0 = "devara-rt: live=0"
BAD_STDERR = re.compile(r"double free|free\(\)|corrupt|munmap_chunk|invalid pointer|Segmentation|Aborted|malloc|realloc|memory|stack smashing", re.I)
OPTS = ["-O0", "-O1"]

BIG = ["padham big", "void mk charya () { big lo \"\" pettu\n prati i 0 nundi 50 varaku { big lo big + \"abcd\" pettu } }"]  # 200 bytes


def go(src, opt, stdin=b"", cap=CAP_KB, env=ENV):
    return run_exe_limited(build(src, opt), stdin, cap, env)


def assert_clean(p, out):
    assert p.rc == 0, f"rc={p.rc}\n{p.err[-500:]}"
    assert p.out == out, f"stdout {p.out[:200]!r} != {out[:200]!r}"
    assert p.err.strip() == LIVE0, f"stderr must be exactly {LIVE0!r}, got {p.err[-300:]!r}"


# =============================================================================================================
# program builders + closed-form models
# =============================================================================================================
def p_vla_loop(N):
    return prog("int n", "n ni chaduvu", "int total", "total lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{", "  int a[n]", "  a[0] lo i pettu", "  a[n - 1] lo 1 pettu", "  total lo total + a[0] + a[n - 1] + a[n / 2] pettu", "}",
                "total ni chupi"), b"512\n"


def m_vla_loop(N):
    return f"{sum(range(N)) + N}\n".encode()


def p_vla_func(N):
    return prog("int fill charya (int n, int k) {", "  int a[n]", "  a[k % n] lo k pettu", "  a[(k + 1) % n] lo a[k % n] + 1 pettu",
                "  a[n - 1] + a[k % n] + a[(k + 1) % n] ivvu", "}",
                "int n", "n ni chaduvu", "int total", "total lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{ total lo total + fill(n, i) pettu }}", "total ni chupi"), b"1000\n"


def m_vla_func(N, n=1000):
    total = 0
    for k in range(N):
        a = {}
        a[k % n] = k
        a[(k + 1) % n] = a[k % n] + 1
        total += a.get(n - 1, 0) + a[k % n] + a[(k + 1) % n]
    return f"{total}\n".encode()


def p_vla_2d(N):
    return prog("int n", "n ni chaduvu", "int total", "total lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{", "  int m[n][n]", "  m[i % n][(i * 7) % n] lo i pettu", "  total lo total + m[i % n][(i * 7) % n] + m[0][0] + m[n - 1][n - 1] pettu", "}",
                "total ni chupi"), b"16\n"


def m_vla_2d(N, n=16):
    t = 0
    for i in range(N):
        m = {(i % n, (i * 7) % n): i}
        t += i + m.get((0, 0), 0) + m.get((n - 1, n - 1), 0)
    return f"{t}\n".encode()


EXITS = [
    "int g charya (int n, int mode) {", "  int a[n]", "  prati i 0 nundi 3 varaku {", "    int b[n + 1]", "    b[0] lo i pettu",
    "    prati j 0 nundi 3 varaku {", "      int c[n + 2]", "      padham s", "      s lo \"k\" + (padham) (char) (65 + j) pettu",
    "      mode == 0 && j == 1 ayite { aapu }", "      mode == 1 && j == 1 ayite { saagu }",
    "      mode == 2 && i == 1 && j == 2 ayite { c[0] + b[0] + podavu(s) ivvu }", "      mode == 3 ayite { b[0] + 100 ivvu }",
    "      c[0] lo j + b[0] pettu", "    }", "  }", "  a[0] + 7 ivvu", "}"]


def p_exits(N):
    return prog(*EXITS, "int total", "total lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{ total lo total + g(512, i % 4) pettu }}", "total ni chupi"), b""


def m_exits(N):
    vals = [7, 7, 3, 100]
    return f"{sum(vals[i % 4] for i in range(N))}\n".encode()


SKIP = ["int skip charya (int n, int k) {", "  int total", "  total lo 0 pettu", "  prati i 0 nundi 6 varaku {", "    i % 2 == 0 ayite { saagu }",
        "    int a[n]", "    padham s", "    a[0] lo i pettu", "    s lo \"x\" + (padham) (char) (48 + i) pettu", "    total lo total + a[0] + podavu(s) pettu", "  }",
        "  int w", "  w lo 0 pettu", "  w < 4 unnanta varaku {", "    w lo w + 1 pettu", "    w % 2 == 1 ayite { saagu }", "    int e[n]", "    padham f", "    f lo \"yy\" pettu",
        "    e[1] lo w pettu", "    total lo total + e[1] + podavu(f) pettu", "  }",
        "  k == 0 ayite { total ivvu }", "  int b[n]", "  padham t", "  t lo \"end\" pettu", "  b[1] lo 5 pettu", "  total + b[1] + podavu(t) ivvu", "}"]


def p_skipdecl(N):
    return prog(*SKIP, "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{ total lo total + skip(512, i % 2) pettu }}", "total ni chupi"), b""


def m_skipdecl(N):
    base = (1 + 3 + 5) + 6 + (2 + 2 + 4 + 2)   # i-loop: 1,3,5 (+len 2 each); while: w=2,4 -> e[1]=w, +len("yy")
    return f"{sum(base if i % 2 == 0 else base + 5 + 3 for i in range(N))}\n".encode()


def p_concat_grow(N1):
    return prog("padham s", "s lo \"\" pettu", f"prati i 0 nundi {N1} varaku {{ s lo s + \"ab\" pettu }}", "podavu(s) ni chupi",
                "padham u", "u lo \"\" pettu", f"prati i 0 nundi {N1} varaku {{ u lo (padham) (char) (97 + i % 26) + u pettu }}", "podavu(u) ni chupi", "u[0] ni chupi"), b""


def m_concat_grow(N1):
    return f"{2 * N1}\n{N1}\n".encode() + bytes([97 + (N1 - 1) % 26]) + b"\n"


def p_concat_temps(N):
    return prog("padham s", "padham t", "s lo \"\" pettu", "prati i 0 nundi 200 varaku { s lo s + \"ab\" pettu }",
                "int total", "int cnt", "total lo 0 pettu", "cnt lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{", "  t lo s + (padham) (char) (97 + i % 26) pettu", "  total lo total + podavu(t + t) pettu",
                "  t == s + (padham) (char) (97 + i % 26) ayite { cnt lo cnt + 1 pettu }",
                "  t != s ayite { cnt lo cnt + 0 pettu }", "}", "total ni chupi", "cnt ni chupi"), b""


def m_concat_temps(N):
    return f"{N * 802}\n{N}\n".encode()


def p_recstr(N):
    return prog("padham rs charya (int n) { n <= 0 ayite { \"\" ivvu }\n rs(n - 1) + (padham) (char) (97 + n % 26) ivvu }",
                "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{ total lo total + podavu(rs(400)) pettu }}", "rs(30) ni chupi", "total ni chupi"), b""


def m_recstr(N):
    return ("".join(chr(97 + k % 26) for k in range(1, 31)) + f"\n{400 * N}\n").encode()


def p_recstr_tree(N):
    return prog("padham tr charya (int n) { n <= 1 ayite { \"x\" ivvu }\n tr(n - 1) + tr(n - 2) ivvu }",
                "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{ total lo total + podavu(tr(20)) pettu }}", "tr(6) ni chupi", "total ni chupi"), b""


def m_recstr_tree(N):
    return f"{'x' * 13}\n{10946 * N}\n".encode()


def p_parr(N):
    return prog(*BIG, "int run charya (int n, int iters) {", "  int total", "  total lo 0 pettu", "  prati i 0 nundi iters varaku {", "    padham arr[n]",
                "    prati j 0 nundi 4 varaku {", "      arr[j * 7 % n] lo big + (padham) (char) (65 + j) + (padham) (char) (48 + i % 10) pettu", "    }",
                "    arr[0] lo arr[7] pettu", "    arr[7] lo arr[7] pettu", "    arr[14] lo arr[14] + \"!\" pettu",
                "    total lo total + podavu(arr[0]) + podavu(arr[7]) + podavu(arr[14]) + podavu(arr[21]) + podavu(arr[22]) pettu", "  }", "  total ivvu", "}",
                "mk()", "int n", "n ni chaduvu", f"run(n, {N}) ni chupi"), b"128\n"


def m_parr(N):
    return f"{N * 809}\n".encode()


def p_parr_const(N):
    return prog(*BIG, "int cs charya (int k) {", "  padham loc[6]", "  prati j 0 nundi 6 varaku { loc[j] lo big + (padham) (char) (48 + j) pettu }", "  loc[2] lo loc[3] pettu",
                "  podavu(loc[2]) + podavu(loc[5]) + k ivvu", "}", "mk()", "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{ total lo total + cs(i) pettu }}", "total ni chupi"), b""


def m_parr_const(N):
    return f"{sum(402 + i for i in range(N))}\n".encode()


def p_alias(N):
    return prog(*BIG, "int run charya (int iters) {", "  padham a", "  padham b", "  padham c", "  a lo \"\" pettu", "  b lo a pettu", "  c lo b pettu", "  int total", "  total lo 0 pettu", "  prati i 0 nundi iters varaku {",
                "    a lo big + (padham) (char) (48 + i % 10) pettu", "    b lo a pettu", "    c lo b pettu", "    a lo \"x\" pettu", "    b lo c pettu", "    c lo \"y\" pettu",
                "    b lo b pettu", "    total lo total + podavu(b) + podavu(a) + podavu(c) pettu", "  }", "  a ni chupi", "  b ni chupi", "  c ni chupi", "  total ivvu", "}",
                "mk()", f"run({N}) ni chupi"), b""


def m_alias(N):
    d = (N - 1) % 10
    return (b"x\n" + b"abcd" * 50 + str(d).encode() + b"\ny\n" + f"{N * 203}\n".encode())


def p_strfn(N):
    return prog("padham big", "padham gs", "void mk charya () { big lo \"\" pettu\n prati i 0 nundi 100 varaku { big lo big + \"abcd\" pettu }\n gs lo \"global!\" pettu }",
                "padham idf charya (padham s) { s ivvu }", "padham dup charya (padham s) { s + s ivvu }",
                "padham pick charya (padham a, padham b, int k) { k > 0 ayite { a ivvu }\n b ivvu }", "padham rep charya (padham s) { s lo s + \"!\" pettu\n s ivvu }",
                "padham lit charya () { \"literal\" ivvu }", "padham gl charya () { gs ivvu }", "void sink charya (padham s) { padham t\n t lo s pettu\n t lo \"q\" pettu }",
                "int run charya (int iters) {", "  padham r", "  padham q", "  int total", "  total lo 0 pettu", "  r lo \"seed\" pettu", "  prati i 0 nundi iters varaku {",
                "    q lo dup(big) pettu", "    r lo pick(idf(q), rep(big), i % 2) pettu", "    sink(r)", "    dup(r)", "    idf(lit())",
                "    total lo total + podavu(r) + podavu(idf(idf(r))) + podavu(lit()) + podavu(gl()) + podavu(rep(r)) pettu", "  }", "  podavu(r) ni chupi", "  total ivvu", "}",
                "mk()", f"run({N}) ni chupi", "gs ni chupi", "lit() ni chupi"), b""


def m_strfn(N):
    total = 0
    last = None
    for i in range(N):
        r = 800 if i % 2 else 401
        total += 3 * r + 15
        last = r
    # big has 400 bytes; dup(big)=800 (odd i) ; rep(big)=401 (even i)
    return f"{last}\n{total}\nglobal!\nliteral\n".encode()


GS = ["padham gs", "padham gsa[4]",
      "void upd charya (int i) { gs lo gs + \"a\" pettu\n i % 400 == 0 ayite { gs lo \"\" pettu }\n gsa[i % 4] lo gs + gs pettu\n gsa[(i + 1) % 4] lo gsa[i % 4] pettu }"]


def p_globals(N):
    return prog(*GS, f"prati i 0 nundi {N} varaku {{ upd(i) }}", "podavu(gs) ni chupi", "prati i 0 nundi 4 varaku { podavu(gsa[i]) ni chupi }", "gsa[0] + gs ni chupi"), b""


def m_globals(N):
    gs = 0
    gsa = [0, 0, 0, 0]
    for i in range(N):
        gs += 1
        if i % 400 == 0:
            gs = 0
        gsa[i % 4] = 2 * gs
        gsa[(i + 1) % 4] = gsa[i % 4]
    return ("%d\n" % gs + "".join("%d\n" % x for x in gsa) + "a" * (gsa[0] // 2 * 0) + "").encode() + (b"a" * gsa[0]) + (b"a" * gs) + b"\n"


RETS = [*BIG,
        "padham f1 charya (int n) { padham arr[n]\n arr[1] lo \"zz\" + (padham) (char) (48 + n % 10) pettu\n arr[2] lo big pettu\n arr[1] ivvu }",
        "padham f2 charya (int n) { padham s\n padham t\n s lo big + \"L\" pettu\n t lo \"R\" pettu\n s + t ivvu }",
        "padham f3 charya (int n) { padham s\n s lo big + \"S\" pettu\n prati i 0 nundi 3 varaku { int tmp[n]\n tmp[0] lo i pettu\n padham u\n u lo s + (padham) (char) (48 + i) pettu\n i == 1 ayite { u ivvu } }\n s ivvu }",
        "int f4 charya (int n) { int a[n]\n int b[n]\n a[0] lo 7 pettu\n b[n - 1] lo 8 pettu\n a[0] + b[n - 1] + a[n - 1] ivvu }"]


def p_returns(N):
    return prog(*RETS, "mk()", "int n", "n ni chaduvu", "int total", "total lo 0 pettu",
                f"prati i 0 nundi {N} varaku {{ total lo total + podavu(f1(n + i % 3)) + podavu(f2(n)) + podavu(f3(n)) + f4(n) pettu }}",
                "total ni chupi", "f1(7) ni chupi", "f2(3) ni chupi", "f3(3) ni chupi", "f4(3) ni chupi"), b"300\n"


def m_returns(N):
    return (f"{N * (3 + 202 + 202 + 15)}\n").encode() + b"zz7\n" + b"abcd" * 50 + b"LR\n" + b"abcd" * 50 + b"S1\n15\n"


def p_deep_vla(N):
    return prog("int deep charya (int d, int n) {", "  int a[n]", "  a[0] lo d pettu", "  d <= 0 ayite { a[0] ivvu }", "  deep(d - 1, n) + a[0] ivvu }",
                "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{ total lo total + deep(2000, 100) pettu }}", "total ni chupi"), b""


def m_deep_vla(N):
    return f"{N * (2000 * 2001 // 2)}\n".encode()


def p_big_vla(N):
    return prog("int n", "n ni chaduvu", "int total", "total lo 0 pettu", f"prati i 0 nundi {N} varaku {{", "  int a[n]", "  a[n - 1] lo i pettu", "  a[0] lo 1 pettu",
                "  total lo total + a[n - 1] + a[0] + a[n / 2] pettu", "}", "total ni chupi"), b"2000000\n"


def m_big_vla(N):
    return f"{sum(range(N)) + N}\n".encode()


# name -> (builder, model, small N, big N)
LEAKY = {
    "vla_loop": (p_vla_loop, m_vla_loop, 40, 1_000_000),
    "vla_in_function": (p_vla_func, m_vla_func, 40, 1_000_000),
    "vla_2d": (p_vla_2d, m_vla_2d, 40, 1_000_000),
    "vla_early_exits_aapu_saagu_ivvu": (p_exits, m_exits, 24, 60_000),
    "vla_decl_skipped_by_saagu_or_ivvu": (p_skipdecl, m_skipdecl, 10, 120_000),
    "concat_grow": (p_concat_grow, m_concat_grow, 60, 25_000),
    "concat_temporaries": (p_concat_temps, m_concat_temps, 20, 1_000_000),
    "recursion_returning_strings": (p_recstr, m_recstr, 3, 6_000),
    "recursion_tree_strings": (p_recstr_tree, m_recstr_tree, 2, 1000),
    "padham_vla_arrays": (p_parr, m_parr, 5, 200_000),
    "padham_const_arrays": (p_parr_const, m_parr_const, 5, 200_000),
    "string_aliasing_reassign": (p_alias, m_alias, 12, 1_000_000),
    "strings_through_functions": (p_strfn, m_strfn, 12, 200_000),
    "global_strings": (p_globals, m_globals, 450, 1_000_000),
    "returning_locals_and_elements": (p_returns, m_returns, 7, 100_000),
    "recursion_with_vla_per_level": (p_deep_vla, m_deep_vla, 2, 3_000),
    "huge_vla_repeated": (p_big_vla, m_big_vla, 5, 120),
}
NAMES = list(LEAKY)


# =============================================================================================================
# 0. the programs themselves are valid: small-N runs match the model and the reference interpreter (no new feature needed)
# =============================================================================================================
@pytest.mark.parametrize("name", NAMES)
def test_program_model_matches_reference_small(name):
    build_, model, small, _ = LEAKY[name]
    src, stdin = build_(small)
    ref = check_against_reference(src, stdin, expect_status=0)
    assert ref.stdout == model(small), "closed-form model disagrees with the reference interpreter"


# =============================================================================================================
# 1. leak attacks: live=0 + bounded address space
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("name", NAMES)
def test_no_leak_under_address_space_cap(name, opt):
    build_, model, _, big = LEAKY[name]
    src, stdin = build_(big)
    assert_clean(go(src, opt, stdin), model(big))


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("name", ["vla_loop", "padham_vla_arrays", "string_aliasing_reassign", "global_strings"])
def test_stats_line_absent_without_env_and_stderr_empty(name, opt):
    build_, model, small, _ = LEAKY[name]
    src, stdin = build_(small)
    p = go(src, opt, stdin, cap=None, env={"MALLOC_PERTURB_": "165"})
    assert p.rc == 0 and p.out == model(small) and p.err == ""


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("name", NAMES)
def test_live_is_zero_for_small_runs_too(name, opt):
    build_, model, small, _ = LEAKY[name]
    src, stdin = build_(small)
    assert_clean(go(src, opt, stdin, cap=None), model(small))


# =============================================================================================================
# 2. many lines of input into one padham variable, strings from input freed
# =============================================================================================================
@pytest.mark.parametrize("opt", OPTS)
def test_padham_input_lines_released(opt):
    lines = 20000
    body = b"".join((b"line%06d " % i) + b"z" * (i % 1500) + b"\n" for i in range(lines))
    stdin = f"{lines}\n".encode() + body
    src = prog("int n", "n ni chaduvu", "padham s", "int total", "total lo 0 pettu",
               "prati i 0 nundi n varaku { s ni chaduvu\n total lo total + podavu(s) pettu }", "total ni chupi", "s ni chupi")
    exp = f"{sum(11 + i % 1500 for i in range(lines))}\n".encode() + b"line%06d " % (lines - 1) + b"z" * ((lines - 1) % 1500) + b"\n"
    assert_clean(go(src, opt, stdin, cap=None), exp)


# =============================================================================================================
# 3. targeted semantic probes of the refcount / scope-exit protocol (small, exact output + live=0)
# =============================================================================================================
def probe(opt, src, out, stdin=b""):
    assert_clean(go(src, opt, stdin, cap=None), out)


@pytest.mark.parametrize("opt", OPTS)
def test_self_assignment_forms(opt):
    src = prog("int f charya (int n) {", "  padham a", "  padham arr[n]", "  a lo \"hello\" + (padham) (char) 33 pettu", "  a lo a pettu", "  a lo a + \"\" pettu",
               "  arr[1] lo a pettu", "  arr[1] lo arr[1] pettu", "  arr[2] lo arr[1] pettu", "  arr[1] lo \"\" pettu", "  a lo arr[2] pettu", "  arr[2] lo a pettu",
               "  a ni chupi", "  arr[1] ni chupi", "  arr[2] ni chupi", "  podavu(arr[2]) ivvu", "}", "f(4) ni chupi")
    probe(opt, src, b"hello!\n\nhello!\n6\n")


@pytest.mark.parametrize("opt", OPTS)
def test_literal_strings_are_never_freed(opt):
    src = prog("padham lit charya () { \"lit\" ivvu }", "padham pass charya (padham s) { s ivvu }", "int f charya (int n) {", "  padham a", "  padham b", "  padham arr[n]", "  a lo \"\" pettu", "  b lo \"\" pettu",
               "  prati i 0 nundi 3 varaku { a lo \"lit\" pettu\n b lo a pettu\n arr[i] lo pass(lit()) pettu\n b lo pass(b) pettu\n a lo \"\" pettu }",
               "  arr[0] + arr[1] + arr[2] + b ni chupi", "  podavu(arr[0]) ivvu", "}", "padham g", "g lo \"glob\" pettu", "g lo g pettu", "g lo pass(g) pettu",
               "f(3) ni chupi", "g ni chupi")
    probe(opt, src, b"litlitlitlit\n3\nglob\n")


@pytest.mark.parametrize("opt", OPTS)
def test_empty_strings_and_zero_filled_string_arrays(opt):
    src = prog("padham em charya (int k) { padham s\n s lo \"\" pettu\n k > 0 ayite { s ivvu }\n padham t\n t lo s + \"\" pettu\n t ivvu }",
               "padham mid charya (int k) { padham u\n u lo \"\" pettu\n k == 1 ayite { u lo \"set\" pettu }\n u ivvu }",
               "int f charya (int k) {", "  padham a", "  a lo \"\" pettu", "  padham arr[k]", "  podavu(a) + podavu(arr[0]) + podavu(em(1)) + podavu(em(0)) + podavu(mid(0)) + podavu(mid(1)) ivvu", "}",
               "f(2) ni chupi", "podavu(em(1) + em(0)) ni chupi")
    probe(opt, src, b"3\n0\n")


@pytest.mark.parametrize("opt", OPTS)
def test_string_stored_in_array_and_variable_then_array_dies_first(opt):
    src = prog("padham keep charya (int n) {", "  padham s", "  s lo \"abc\" + (padham) (char) (48 + n) pettu", "  padham arr[n + 1]", "  arr[0] lo s pettu", "  arr[n] lo arr[0] + arr[0] pettu",
               "  n > 2 ayite { arr[n] ivvu }", "  s ivvu", "}", "padham x", "x lo keep(1) pettu", "x ni chupi", "x lo keep(3) + x pettu", "x ni chupi", "podavu(x) ni chupi")
    probe(opt, src, b"abc1\nabc3abc3abc1\n12\n")


@pytest.mark.parametrize("opt", OPTS)
def test_nested_scopes_with_arrays_and_strings_every_exit_path(opt):
    L = ["int walk charya (int n, int mode) {", "  int a[n]", "  padham s", "  s lo \"S\" + (padham) (char) (48 + mode) pettu", "  int total", "  total lo 0 pettu",
         "  int i", "  i lo 0 pettu", "  i < 5 unnanta varaku {", "    i lo i + 1 pettu", "    int b[n + i]", "    padham t", "    t lo s + s pettu",
         "    b[i] lo i pettu", "    mode == 0 && i == 2 ayite { saagu }", "    mode == 1 && i == 3 ayite { aapu }", "    mode == 2 && i == 4 ayite { total + podavu(t) + b[i] ivvu }",
         "    pratisari (int j lo 0 pettu; j < 3; j++) {", "      int c[j + n]", "      padham u", "      u lo t + (padham) (char) (48 + j) pettu",
         "      mode == 3 && j == 1 ayite { saagu }", "      mode == 4 && j == 2 ayite { aapu }", "      mode == 5 && j == 1 && i == 2 ayite { podavu(u) + total ivvu }",
         "      total lo total + c[j] + podavu(u) pettu", "    }", "    total lo total + b[i] + podavu(t) pettu", "  }", "  total + a[0] + podavu(s) ivvu", "}",
         "prati m 0 nundi 6 varaku { walk(40, m) ni chupi }"]

    def model(mode):
        total = 0
        for i in range(1, 6):
            t = 4
            if mode == 0 and i == 2:
                continue
            if mode == 1 and i == 3:
                break
            if mode == 2 and i == 4:
                return total + t + i
            for j in range(3):
                u = t + 1
                if mode == 3 and j == 1:
                    continue
                if mode == 4 and j == 2:
                    break
                if mode == 5 and j == 1 and i == 2:
                    return u + total
                total += 0 + u
            total += i + t
        return total + 0 + 2
    exp = "".join(f"{model(m)}\n" for m in range(6)).encode()
    src = prog(*L)
    check_against_reference(src, b"", expect_status=0)
    probe(opt, src, exp)


# =============================================================================================================
# 4. runtime errors in the middle of scopes holding heap objects: exit 1, message, no crash / double free
# =============================================================================================================
def errprog(body):
    return prog("int gz", "int gm", "gz ni chaduvu", "gm ni chaduvu", *body)


ERRS = {
    "div_by_zero_with_live_heap": (["int f charya (int n, int z) {", "  int a[n]", "  padham s", "  s lo \"x\" + \"y\" pettu", "  prati i 0 nundi 3 varaku {", "    int b[n]",
                                    "    padham t", "    t lo s + s pettu", "    b[0] lo 10 / (z - i) pettu", "  }", "  podavu(s) ivvu", "}", "\"before\" ni chupi", "f(64, gz + 2) ni chupi", "\"after\" ni chupi"],
                                   b"0 0\n", "division by zero", b"before\n"),
    "invalid_array_size_second_array": (["int f charya (int n, int m) {", "  int a[n]", "  padham s", "  s lo \"keep\" + \"me\" pettu", "  int b[m]", "  a[0] + b[0] ivvu", "}",
                                        "f(8, 4) ni chupi", "f(8, gz) ni chupi", "\"after\" ni chupi"], b"0 0\n", "invalid array size", b"0\n"),
    "negative_array_size_in_loop_after_good_iterations": (["int f charya (int n) {", "  int t", "  t lo 0 pettu", "  prati i 0 nundi 5 varaku {", "    int a[n - i * 2]", "    padham s",
                                                         "    s lo \"v\" + (padham) (char) (48 + i) pettu", "    a[0] lo i pettu", "    t lo t + a[0] + podavu(s) pettu", "  }", "  t ivvu", "}",
                                                         "f(9) ni chupi", "f(5) ni chupi"], b"0 0\n", "invalid array size", b"20\n"),
    "string_index_out_of_range": (["int f charya (int n) {", "  padham arr[n]", "  arr[0] lo \"abc\" + \"d\" pettu", "  padham s", "  s lo arr[0] + arr[0] pettu",
                                   "  int a[n]", "  (int) s[n + 40] ivvu", "}", "f(2) ni chupi", "\"after\" ni chupi"], b"0 0\n", "string index out of range", b""),
    "invalid_input_with_live_strings": (["int f charya (int n) {", "  padham s", "  s lo \"k\" + \"k\" pettu", "  int a[n]", "  int x", "  x ni chaduvu", "  x + a[0] + podavu(s) ivvu", "}",
                                         "f(4) ni chupi", "f(4) ni chupi"], b"0 0 12 notanumber\n", "invalid input", b"14\n"),
    "eof_input_inside_loop_with_arrays": (["int f charya (int n) {", "  int t", "  t lo 0 pettu", "  prati i 0 nundi 9 varaku {", "    int a[n]", "    padham s", "    s ni chaduvu",
                                           "    t lo t + podavu(s) + a[0] pettu", "  }", "  t ivvu", "}", "f(4) ni chupi"], b"0 0\nab\ncde\n", "invalid input", b""),
    "int_min_division_with_live_heap": (["int f charya (int n, int d) {", "  int a[n]", "  padham s", "  s lo \"q\" + \"q\" pettu", "  (-9223372036854775807 - 1) / d ivvu", "}",
                                         "f(3, 1) ni chupi", "f(3, -1) ni chupi"], b"0 0\n", "integer overflow in division", b"-9223372036854775808\n"),
    "char_conversion_error_with_live_heap": (["int f charya (int n) {", "  int a[n]", "  padham s", "  s lo \"ab\" + \"c\" pettu", "  (int) (char) s ivvu", "}", "f(3) ni chupi"],
                                             b"0 0\n", "invalid char conversion", b""),
}


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("name", list(ERRS))
def test_runtime_error_with_live_heap_objects_is_clean(name, opt):
    body, stdin, msg, out_before = ERRS[name]
    p = go(errprog(body), opt, stdin, cap=None)
    assert p.rc == 1, f"rc={p.rc} (134=abort/double free, 139=segfault)\n{p.err[-400:]}"
    assert f"devara: runtime error: {msg}" in p.err
    assert not BAD_STDERR.search(p.err.replace("devara: runtime error: invalid array size", "")), p.err
    assert p.out == out_before, (p.out, out_before)
    assert b"after" not in p.out


# =============================================================================================================
# 5. whole existing corpus and random programs: live=0 at normal exit
# =============================================================================================================
CORPUS = programs()


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("tel", CORPUS, ids=pid)
def test_corpus_program_live_is_zero(tel, opt):
    src = tel.read_text(encoding="latin-1")
    inp, out, ex, _ = expected(tel)
    p = go(src, opt, inp, cap=1 << 20, env={"DEVARA_RT_STATS": "1", "MALLOC_PERTURB_": "85"})
    assert p.out == out and p.rc == ex
    if ex == 0:
        assert p.err.strip() == LIVE0, p.err[-300:]
    else:
        assert not BAD_STDERR.search(p.err.replace("invalid array size", ""))


@pytest.mark.parametrize("opt", OPTS)
@pytest.mark.parametrize("seed", range(30))
def test_generated_programs_live_is_zero_and_match_reference(seed, opt):
    from tests.property.proggen import generate
    src, stdin = generate(9000 + seed, 14, pressure=bool(seed % 2))
    ref = check_against_reference(src, stdin, opts=(opt,), expect_status=0)
    p = go(src, opt, stdin, cap=None)
    assert p.rc == 0 and p.err.strip() == LIVE0, p.err[-300:]
    assert p.out.replace(b"-nan", b"nan") == ref.stdout.replace(b"-nan", b"nan")
