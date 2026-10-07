# Devara compiler audit (findings only, no fixes)

**Baseline:** branch `claude/devara-compiler-cloud-migration-l3txzx` at `ea2f0bf`.
**Environment:** Linux x86-64, Python 3.11.15, gcc 13.3. MinGW-w64 gcc and wine 9.0 were installed in the container part-way through the audit, for the Windows-target checks.
**Rule:** every finding below has a reproducer that was run. Anything that could not be confirmed is marked UNCONFIRMED. The ranked fix list is in [`IMPROVEMENT_PLAN.md`](IMPROVEMENT_PLAN.md).

## 0. Baseline

| Check | Result |
|---|---|
| `pytest -n 4` (no MinGW or wine) | 6,245 passed, 0 failed, 637 skipped. Every skip is a Windows-target test that needs MinGW and wine. 6,245 + 637 = 6,882 tests, which matches HANDOFF's 6,881 passed + 1 skipped. |
| `tests/validation/test_windows_target.py` (MinGW + wine) | 591/591 passed in 3 of 4 parallel runs. See F14 for the other run. |
| `scripts/check_machine.py` | PASS: corpus 128/128 at -O0 and 128/128 at -O1, and all 236 leak-check runs report `live=0`. |
| Differential fuzzing (`tests/property/campaign.py`, fresh seeds) | 400 programs of size 40 (seeds 900000–900399) and 200 of size 120 (seeds 950000–950199): **0 problems**. |

## Resolution (added after the fixes)

Every item of `IMPROVEMENT_PLAN.md` was addressed; see its status table for the commits. Final state: 6,988 tests passed (1 skipped, 0 failed), `scripts/check_machine.py` PASS (corpus 128/128 at -O0 and -O1, leak check 236/236), 700 further fuzzed programs with 0 problems, and `windows-latest` CI green.

Benchmarks on one machine, best of 5, seconds (`docs/audit/repro/bench_c`); "before" is the compiler at `375a7fd`:

| program | -O1 before | -O1 now | -O0 now | gcc -O0 | gcc -O2 |
|---|---:|---:|---:|---:|---:|
| fib(35) | 0.039 | 0.037 | 0.045 | 0.065 | 0.016 |
| sieve 3e7 | 0.848 | **0.206** | 0.475 | 0.336 | 0.183 |
| matmul 400 | 0.113 | 0.092 | 0.323 | 0.120 | 0.046 |
| float integrate 1e8 | 0.161 | 0.128 | 2.075 | 0.253 | 0.104 |

Two findings above were corrected: the "-O1 slower than -O0 on fib" reading in A.3 (F7) was noise from a different host, and F3 was only read from the code at the time; it is now reproduced (the old runtime segfaults on out-of-memory while reading input). The compile-time table in section C shows the numbers before F13; they are now 1.5 s (5,000 lines) and 6.6 s (20,000 lines).

## A. Stage-by-stage observation

### A.1 Valid programs: `A_programs/` (44 programs, 31 features and 13 runtime-error cases)

Each program was run through `devara -O0`, `devara -O1` and the reference interpreter (`tests/reference/interp.py`) using [`repro/diffrun.py`](repro/diffrun.py). Programs that read input get their stdin from `<name>.in`.

* **43 of 44 agree byte for byte.** The exception is `p05_arith_float`, line 7 (`z / z` with `z = 0.0`): the compiled code prints `-nan` and the reference prints `nan`. x86 `divsd` produces the default NaN with the sign bit set, and ruling Q-004 explicitly leaves the NaN sign unspecified, so this is **not a bug**. The campaign harness already normalizes NaN signs.
* **Agreement alone doesn't prove correctness**, because both implementations come from the same project. So every output line of all 44 programs was **checked by hand** against C/C++ semantics, IEEE-754 and the P/L/Q rulings. **All are correct.** The hand-verified outputs are saved as `<name>.out`, and runtime-error cases also have `<name>.err` and `<name>.exit`. Highlights:
  * **int:** truncating `/`, `%` taking the dividend's sign, wraparound (`INT64_MAX + 1`, `21!` = −4249290049419214848), and `INT64_MIN % -1 = 0`. Q-001: `-INT64_MIN` wraps.
  * **float:** signed zeros are preserved through `x + 0.0` and `-1.0 * 0.0` (§12.4). `%g` formatting is used (`1.23457e+06`, `1e-05`), and an overflowing literal becomes `inf`.
  * **Conversions:** out-of-range and NaN float→int give `INT64_MIN` (`cvttsd2si`). Narrowing to `char` keeps the low 8 bits as a signed value. NaN→bool is `nijam` (Q-005).
  * **Loops:** range loops are half-open and the end is evaluated once. Modifying the loop variable in the body affects iteration (Q-007). Float and char bounds convert to `int` (P32). `INT64_MAX` as an end bound doesn't overflow.
  * **Scopes:** point-of-declaration (Q-002, `i lo i + 1 pettu int i`), P20 global visibility, and shadowing of the loop variable and of `podavu`.
  * **I/O:** P7–P10 and Q-010/013/014: the whitespace-only remainder of a line is skipped before a line read, empty lines work, and `1e3`, `-0.0`, `inf` and `ABADDHAM` are accepted.
  * **Runtime errors:** all 7 P11 messages, each with exit 1, and stdout is flushed first (`p3x_rt_divfunc` prints `before`).
* **ABI stress** (added during the audit, all correct):
  * 10 integer arguments, 10 float arguments, and 14 mixed arguments (int/float/char/bool/padham), which uses stack-passed arguments under System V.
  * Stack arguments carried through 1,000 levels of recursion.
  * Arrays of every element type passed together with scalars.

### A.2 Invalid programs: `A_invalid/` (20 programs and their diagnostics)

Every lexical, syntax and semantic category in plan §E was triggered at least once. The `.err` files record the exact diagnostics. Categories, spans and the Q-009 sort order are correct, and recovery after an unbalanced `(` and `{` produces no cascade (`n14`). Issues found:

* **F4: cascading error after `ni <identifier>`** (`n01_typo_chupi.tel`). `x ni chupi2` reports `3:6 MISSING_TOKEN` and then a spurious `4:1 INVALID_STATEMENT`. The cause is that recovery syncs to `FIRST_STATEMENT`, which includes `IDENTIFIER`, so `chupi2` starts a new "statement" (`compiler/parser/parser.py:432` with `_recoverable`).
* **F5: misplaced location for "Expected statement keyword after expression."** (`compiler/parser/parser.py:452`). The diagnostic is anchored at the *next* token, which is often on a later line, instead of at the expression or just after it. In `n19`, a stray `a + b` on line 5 is reported at `6:1`, and the missing `ivvu` in `n03` (line 2) is reported at `3:1` (the `}`). The message also doesn't suggest the likely fix (`ivvu`, `ni chupi`). By Clang/GCC convention, "expected X" is reported just after the previous token.
* **F6: internal enum names in messages** (`compiler/semantic/checker.py:669`): `operator SUB cannot be applied to padham and padham`, and likewise `MUL` and `LT`. The unary form omits the operator entirely: `operator cannot be applied to padham`. Other messages use the source spelling (`'%' requires integral operands`).

### A.3 Generated-code inspection (-O1)

Reproducers are in `repro/`, and all numbers below were measured.

* **F7: callee-saved registers are saved on every path (no shrink-wrapping).** `fib` saves and restores `rbx` and `r12` even on the `n < 2` path, which uses neither, and roughly half of all calls take that path. Result: **fib(35) runs in 0.073 s at -O1 against 0.064 s at -O0** (`repro/r04_fib35_O1_slower.tel`), so -O1 is slower than -O0.
* **F8: every array element takes 8 bytes,** including `bool` and `char` (a documented simplification, plan §D). The sieve of 3·10⁷ uses 240 MB, where C uses 30 MB. **-O1 takes 0.71 s, slower than gcc -O0 (0.40 s) and 5.3× slower than gcc -O2 (0.135 s)** (`repro/r05_sieve_8byte_bool.tel`).
* **F9: small allocatable caller-saved pool.** `rax rcx rdx r10 r11` are permanently reserved as scratch, which leaves only `rsi rdi r8 r9` (System V) or just `r8 r9` (Win64) to allocate. Even a 2-parameter leaf loop (`repro/r06_leaf_loop_uses_rbx.tel`) spills a temporary into callee-saved `rbx`, which costs a save, a restore and a stack frame. Win64 is affected more.
* **F10: no loop-invariant code motion.** `lea rax, [rip + dv_g_a]` is recomputed on every iteration of the `$entry` fill loop (same reproducer).
* **F11: redundant moves at call and return boundaries,** e.g. `mov rsi, rax; add r12, rsi; mov rax, r12` (fib) and `mov rbx, [..]; add r8, rbx` where a memory operand would do.
* **F12: leaf functions always set up `rbp` frames.**

Benchmarks, best of 3 runs in seconds, with identical outputs. The C equivalents are in `repro/bench_c/`.

| program | devara -O0 | devara -O1 | gcc -O0 | gcc -O2 |
|---|---:|---:|---:|---:|
| fib(35) | 0.064 | 0.073 | 0.080 | 0.020 |
| sieve 3e7 | 1.46 | 0.71 | 0.40 | 0.135 |
| matmul 400 | 0.338 | 0.119 | 0.148 | 0.047 |
| float integrate 1e8 | 2.28 | 0.165 | 0.265 | 0.129 |

## B. Code review (against the textbooks, both ABIs, IEEE-754 and C runtime safety)

### B.1 Correctness bugs (confirmed)

* **F1: the array-size product can overflow and silently corrupt the heap.** `compiler/ir/lower.py` (`s_TDecl`) multiplies the dimensions with a wrapping `MUL`, and only checks that each dimension is ≥ 1. `int a[n][4]` with `n = 2^62 + 1` wraps to 4 elements (32 bytes). Then `a[1][0] lo 7 pettu`, an access within the declared bounds, writes past the allocation and the program **exits 0**. Expected: runtime error `invalid array size` (P11, P21). Reproducer: `repro/r01_dim_product_overflow.tel`, same result at -O0 and -O1. A local `int a[3][2^62+1]` happens to be caught, because its wrapped product is negative.
* **F2: a huge constant-size *global* array causes an internal compiler error (exit 3).**
  * `int a[4611686018427387905][4]` and `int a[2000000000][2000000000]` fail with `Error: bignum invalid` from the assembler (`.zero` size ≥ 2^63).
  * `int a[100000000000]` fails with `relocation truncated to fit: R_X86_64_PC32` from the linker. **Any static array over 2 GiB** (e.g. `int a[300000000]`) hits this.
  * Exit 3 is reserved for compiler bugs (plan §E), but these are inputs the semantic checker accepts.

  Reproducers: `repro/r02_global_array_bignum_ice.tel` and `repro/r03_global_array_2gb_ice.tel`.
* **F3: unchecked allocation in the runtime.** In `runtime/devara_rt.c`, `read_token` (`malloc`/`realloc`), `in_unget` (`realloc`) and `dv_rt_input_str` (`malloc`/`realloc`) don't check for NULL, so out-of-memory during input would dereference NULL instead of reporting an error. `make_str`, `dv_rt_strcat` and `dv_rt_strlit` do check. This was found by reading the code and is not reproduced, because it needs an out-of-memory condition.

### B.2 Reviewed and found sound

* **Optimizer** (`compiler/opt/passes.py`):
  * Algebraic identities are restricted to `i64`, so §12.4 is respected.
  * Float folding refuses NaN results, which keeps the runtime NaN sign.
  * Integer folding and DCE never remove a division that could trap (divisor 0 or −1 with a non-constant divisor).
  * `convert_const` matches `cvttsd2si`, the low-8-bit `char` rule and NaN→true.
  * Constant propagation compares floats by bit pattern (F-006).
  * Negation always promotes `char`/`bool` to `int` first, so `fold_instr`'s fallback to float negation is never reached with those types.
* **Win64 ABI** (`compiler/codegen/target.py`, `x86_64_ra.py`):
  * Positional register slots are shared between int and float arguments (`positional=True`).
  * The 32-byte shadow space and `___chkstk_ms` probing for frames over 4 KiB are present.
  * `xmm6`–`xmm15` are saved in full 128 bits (`movups`), and `rdi`/`rsi` are treated as callee-saved.
* **System V:** 6 integer and 8 float argument registers, stack arguments, 16-byte alignment and the red zone are not violated. This is confirmed by the ABI stress program and 600 fuzzed programs.
* **Runtime** (`runtime/devara_rt.c`):
  * The refcount discipline is consistent: literals are immortal, `strcat` returns an owned reference even when it shares an argument, and `release_elems` resets elements to NULL.
  * Strict token parsing matches Q-010, CRLF handling matches Q-014, the P9 whitespace-only remainder is skipped, and `fail()` flushes stdout before reporting.
* **Semantic edge cases** (spot-checked, all correct):
  * P20: a function using a global declared after it gets `UNDECLARED`.
  * P24: a `while nijam` loop with `aapu` initializes, while an ordinary `while` loop does not.
  * P25: returns inside a `while nijam` loop are accepted, and one with `aapu` gives `MISSING_RETURN`.
  * Redeclaring `podavu` is `REDECLARATION`.
  * A `void` function containing `e ivvu` gets `INVALID_RETURN`.
* **Implementation limits** (N-001):
  * Nesting depth ≥ 5,000 works for parentheses, unary operators and `if`.
  * Beyond the limit (parentheses ~10,000, unary 20,000), the compiler gives the clean diagnostic `nesting too deep (implementation limit)` with exit 1 and no internal compiler error.
* **CI workflow** (`.github/workflows/ci.yml`): every path and flag it references exists (`tests/integration/test_windows_target.py`, `scripts/setup.sh`, `run_corpus.py -O0`). The Windows job has been failing during test collection (F16).

## C. Stress and metrics

* **F13: -O1 compile time.** The generated programs (`repro/compile_scaling.py`) are many small functions plus a top-level driver:

  | lines | -O0 | -O1 | -O1 peak RSS |
  |---:|---:|---:|---:|
  | 1,000 | 0.16 s | 0.75 s | 26 MB |
  | 5,000 | 0.44 s | 3.64 s | 56 MB |
  | 20,000 | 1.70 s | 17.6 s | 164 MB |
  | 50,000 | 4.79 s | 52.9 s | 371 MB |

  -O0 is linear at about 0.09 ms/line. -O1 is about 10× slower and grows slightly faster than linear (0.73 → 1.06 ms/line). Splitting the time for 20,000 lines: the front end takes 1.6 s, the optimizer about 7 s and the register-allocating backend about 10 s. Profiling shows `ir/verify.py:_check_function` is called **90,045 times for about 2,000 functions**. That's because `opt/__init__.py` iterates *all* functions to a module-wide fixed point (up to 12 rounds) and re-verifies the *whole module* after every pass. Low priority per ruling N-002.
* **Long expressions:** a 20,000-term `x + x + …` compiles in 7.0 s, and 5,000 terms in 1.5 s, which is roughly linear.
* **Runtime against gcc:** see the table in A.3. -O1 is 1.3× (float) to 5.3× (sieve) slower than gcc -O2, and it is slower than gcc -O0 only on the sieve (F8).

## D. Test infrastructure

* **F14: intermittent failures of the Windows-target tests under parallel wine (cause identified for one of them, environment only).**
  * `pytest -n 4 tests/validation/test_windows_target.py` was run 7 times on its own. 5 runs passed 591/591. Run 1 failed because wine printed its first-run configuration message on stderr (the tests require empty stderr). Run 2 had one failing test, `test_token_parsing_matches_reference[1e3-float--O0]`, whose message was not captured.
  * Of the 4 full-suite runs with the Windows toolchain installed, 3 had exactly one failing Windows-target test, a different one each time: one not identified, `test_deep_expression_trees[1--O1]` (message not captured), and `test_crlf_input_behaves_like_lf[types10-…--O0]`. The last one was captured: the failing run returned exit code 1 with empty stdout and a stderr that pytest truncates to `win…et by peer`, while the reference run of the same program printed the correct output. That is wine's connection to its server being reset under CPU load, not a Devara result. Every one of these tests passes when run alone.
  * The other failures were not captured, so they are *consistent with* the same cause but not proven to be it.
  * Not changed. A retry on that specific wine error signature in `tests/validation/stress_util.py` would remove the noise without hiding compiler failures (IMPROVEMENT_PLAN item 14).
* **F15: informational, not a defect.** The reference interpreter prints `nan` where x86 hardware gives `-nan`. Q-004 permits either.
* **F16: the Windows CI job never tested anything until this audit. Fixed in this branch, three layers deep.**
  * GitHub Actions has run `.github/workflows/ci.yml` 34 times before this branch, with the `windows` job red every time. This corrects HANDOFF's "CI never run".
  * **Layer 1, collection** (run on `ea2f0bf`): `tests/regression/test_bug_cli_io_and_limits.py` calls `os.geteuid()` at import, which doesn't exist on Windows, so pytest aborted after 7 seconds. Also `tests/helpers/native.py` used the POSIX-only `preexec_fn`. Fixed in `3c4cdff`.
  * **Layer 2, launching the compiler** (run on `3c4cdff`): 10 places in the tests executed the extensionless bash wrapper `devara` as a subprocess, which Windows can't do (`WinError 193`). 1,403 tests failed. `tests/helpers/cli.py` now provides `DEVARA_CMD` (`python -m compiler.cli` off POSIX), and all call sites use it. Fixed in `8c1a9ff`.
  * **Layer 3, 29 remaining failures** (run 37525595755 on `8c1a9ff`: 2,468 passed natively, 29 failed). All were test or repo-configuration problems, with no compiler defect found:
    * 20 tests: `threading.stack_size(1 << 29)` in `tests/reference/interp.py` is rejected by Windows. `compiler/cli.py` already has a fallback loop; the interpreter now uses the same one.
    * 5 tests (3 corpus-runner, 1 CRLF-input, and the fixtures behind them): `Path.write_text` turns `\n` into `\r\n` on Windows, and a GitHub Windows checkout converts the repo's text files to CRLF. The corpus `.in`/`.out` files had no line-ending rule, so **any Windows clone with git's default `autocrlf=true` gets CRLF corpus files and wrong results from the corpus runner and `scripts/check_machine.py`**. `.gitattributes` now has `* text=auto eol=lf` (with `*.cmd` kept CRLF and the deliberate CRLF fixture `p03_crlf_ws_comments` excluded).
    * 3 tests: the Windows target appends `.exe` to a suffix-less `-o` or default output name (`compiler/driver.py:189`), and the tests expected the bare name. They now use `driver.executable_path`.
  * **Result on `65106ad` (run 37526893287): green.** The `fast` (Linux) and `windows` jobs both pass. On native `windows-latest`, every step succeeded: `pytest -m "not slow"` (about 2.9 minutes), `tests/integration/test_windows_target.py`, and `scripts/run_corpus.py` at **-O0 and -O1** (the 128-program corpus; the compiler, assembler and linker ran natively with MinGW-w64 gcc).
  * **Still not covered on Windows:** the `slow`-marked tests (the corpus end-to-end suite, property tests, leak tests), which CI runs only on Linux pull requests, and the `scripts/check_machine.py` leak check. Both are for the owner's Windows machine.
