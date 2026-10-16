# Devara Compiler — Final Validation Report

**Date:** 2026-10-04
**Branch:** `devara-compiler-cloud-migration-l3txzx`
**Validated tree:** developer HEAD `aabe4bc` merged with validation HEAD `be34ebd`. The final merge
`f5e3e01` adds only the validation report docs (`b1bea27`).
**Verdict:** **PASS.** All acceptance criteria hold. The exceptions are the documented limits in §8.

Every number below comes from commands that the design lead ran on that tree. The tester's
independent report is at `docs/validation/VALIDATION_REPORT.md`, with its own verdict: PASS.

---

## 1. Specification

| Item | Status |
|---|---|
| Specification version | `DEVARA_LANGUAGE_SPEC_v0.7.md` (unchanged) + Stage 2 design v1.1 + Stages 3–6 design v7 (L1–L49) |
| Ambiguities resolved | P1–P40 (plan §C), round-1 rulings OQ1–OQ11, Q-001–Q-009 (§L), round-2 rulings F-001, Q-010–Q-012, N-001, N-002 (§M) |
| Contradictions found | 1: the escape-sequence grammar text vs. "forms accepted by the lexer" (P13). Resolved in favour of the explicit lexer deferral |
| Remaining ambiguities | None blocking. The deliberately undefined behaviour is: NaN sign in output (Q-004), stack overflow (P38), out-of-bounds array access (L32) |
| Deviations from the spec | None. Implementation choices that differ from the design's suggested pipeline: no register allocation (a stack slot for every value, plan §D); runtime-sized arrays and padham values are never freed (P22) |

## 2. Architecture

```
source → Lexer → tokens → Parser → AST → Sema → typed tree → IRGen → IR+CFG (verified)
       → Optimizer → IR (re-verified) → x86-64 codegen → GNU asm → gcc (as+ld) + runtime/devara_rt.c → ELF
```

Every stage can be inspected and driven from the CLI (`./devara lex|parse|sema|ir|opt|asm|build|run`). The JSON
outputs feed the next stage: `lex --json → parse`, `parse --json → sema`, `ir --json → opt/asm`, `.s → build`.
Integration tests exercise each of these boundaries. Stage contracts are in plan §F; stage formats are in
`docs/STAGE_FORMATS.md`.

## 3. Implementation

| Component | Location | State |
|---|---|---|
| Diagnostics / serialization | `compiler/diagnostics.py`, `compiler/serialize.py` | new |
| Lexer | `compiler/lexer/` | kept; categories, CRLF, token ends, octal-run fix |
| AST + parser | `compiler/ast/`, `compiler/parser/` | AST rewritten to design §3.5; parser aligned with grammar, §3.6 categories, §3.7 recovery |
| Semantic analysis | `compiler/semantic/` | new: scopes, types, conversions, definite-init, return paths |
| IR / verifier / optimizer | `compiler/ir/`, `compiler/opt/` | new: typed 3-address IR, CFG, verifier, 8 passes (no float identities) |
| Code generation / runtime | `compiler/codegen/`, `runtime/devara_rt.c` | new: System V x86-64, stack-slot strategy |
| Driver / CLI | `compiler/driver.py`, `compiler/cli.py`, `./devara` | new |
| Infra | `.github/workflows/ci.yml`, `.devcontainer/`, `scripts/setup.sh`, `scripts/run_corpus.py` | new |

Size: about 6,400 lines of compiler and runtime source. The diff since baseline `5ef3931` touches 617 files
(+23,288 / −3,100), most of it tests and corpus.

Known technical debt (from `docs/DEVELOPER_STATUS.md`):
- No register allocation.
- Heap arrays and padham values are never freed.
- Global scalars are not constant-propagated.
- `scripts/run_corpus.py` spawns one process per program.
- `tests/audit_scripts/` holds legacy print scripts.

## 4. Testing (full run, `python3 -m pytest -q -rs`, 18 min 06 s)

```
5157 passed, 1 skipped in 1086.38s
SKIPPED [1] tests/regression/test_bug_cli_io_and_limits.py:44: root ignores directory permissions
```

| Layer | Owner | Tests (approx., from collection) |
|---|---|---|
| Unit (lexer, parser, sema, IR, opt, codegen, runtime) | developer | ~1,100 |
| Integration (stage round-trips, O0 vs O1) | developer | ~150 |
| Regression | developer + tester | ~60 + per-finding tests in `tests/validation` |
| Validation (spec-derived, black-box via CLI) | tester | 3,514 |
| Property / fuzz / differential | tester | 82 (+ two long campaigns: 1,500 random programs, 0 mismatches) |
| Reference interpreter self-tests | tester | 147 |
| **Total** | | **5,158 collected: 5,157 passed, 0 failed, 1 skipped, 0 xfail** |

Compiler crashes (exit 3) observed by any test: 0. Timeouts: 0.
The one skip needs a non-root user; the container runs as root, so it cannot run here.

## 5. Corpus (`python3 scripts/run_corpus.py`, 10 s timeout per program)

```
total 128 · compiled 128 · failed_compilation 0 · executed 128 · runtime_failed 0 · incorrect_output 0 · timeout 0 · correct 128
```

The corpus covers arrays 14, sorting 10, searching 8, strings 14, math 16, recursion 11, data structures 10, DP 10,
graphs 10, and misc 25. The misc programs include 10 runtime-error programs, which are checked for exit status
and stderr. Expected outputs were produced by independent Python oracles (`tests/corpus/_oracles/`), never by the
compiler. The tester verified all 128 at both `-O0` and `-O1`; this run used the default `-O1`.

## 6. Bugs

| ID | Found by | Summary | Status |
|---|---|---|---|
| F-001 | tester | `build -o` to an unwritable path → ICE exit 3 (should be 2) | fixed `70fed32`, regression tests pass |
| F-002 | tester | char literal or cast treated as a constant-true `while` (P24/P25) | fixed `70fed32` |
| F-003 | tester | `078` lexed as `07` `8` instead of INVALID_NUMBER | fixed `70fed32` |
| F-004 | tester | an invalid user `.s` file → ICE instead of exit 1 | fixed `70fed32`/`c26971d` |
| F-005 | tester | too-deep nesting → ICE or killed process | fixed `70fed32`/`aabe4bc` |
| N-002 | tester | super-linear parse of long chains | fixed: a 64,000-term chain parses in 1.8 s |
| Unresolved | | none | |

The developer also fixed bugs it found itself during Phases 1–7. Each of those has a test in `tests/regression/`.

## 7. Performance (largest corpus program, 100 lines; wall time including ~0.1 s Python start-up)

| Stage | Time |
|---|---|
| lex / parse / sema / ir / opt / asm | 0.13 / 0.18 / 0.12 / 0.12 / 0.16 / 0.14 s |
| build (to executable) | 0.18 s |
| Whole corpus, 128 programs, build + run + compare | 6.8 s |

## 8. Limits (NOT VERIFIED / out of contract)

- Only one platform was tested: x86-64 Linux, gcc 13.3, Python 3.11.
- The NaN sign in `%g` output is not tested (Q-004).
- Recursion deeper than the 8 MiB stack is undefined (P38). Only 20,000-frame recursion is tested.
- GitHub Actions CI (`.github/workflows/ci.yml`) exists, but this report does not verify that it runs on GitHub.
- The skipped permission test requires a non-root environment.

## 9. Git

- 45 commits since baseline `5ef3931` (35 non-merge: 15 test, 8 docs, 7 feat, 2 fix, 2 chore, plus this report), on two branches merged at `f5e3e01`.
- Major commits:
  - `6043ad6` plan
  - `eb2b8ae` AST/parser
  - `16e6bd3` semantic analysis
  - `66e5ba5` IR/opt
  - `4cc0df9` codegen/runtime
  - `e46c2c0` corpus
  - `f92c16e` validation suites
  - `70fed32` round-2 fixes
- Attribution trailers: commits from 19:58 UTC onward carry none. Eight earlier commits still do (`6043ad6 d551ee3 b6e6e5b 74ec5a1 eb2b8ae b432f73 c5470ee 51009ee`). Removing them requires a history rewrite and force-push, which the owner has to approve.
- The working tree is clean after the final commit.

## 10. Reproducibility

```sh
git clone https://github.com/vignesh1814/devara && cd devara
git checkout devara-compiler-cloud-migration-l3txzx
./scripts/setup.sh                      # pip install -r requirements-dev.txt (pytest, hypothesis)
python3 -m pytest -m "not slow" -q      # fast suite (~10 s)
python3 -m pytest -q                    # full suite (~18 min serial; the tester used -n 4 with pytest-xdist: ~4 min)
python3 scripts/run_corpus.py           # corpus statistics
./devara build tests/corpus/sorting/<file>.tel -o prog && ./prog < input.txt
./devara run examples/example.tel
```

Requirements: x86-64 Linux, Python ≥ 3.11 and gcc. No GPU is needed; a standard cloud container is enough.

---

## 11. Round 2 (2026-10-05): register allocation, memory management, Windows

Verified by the design lead on HEAD after merging the three agents' work.

| Check | Result |
|---|---|
| Full `pytest -n 4` (incl. slow, property, Windows-under-Wine) | 6,881 passed, 0 failed, 1 skipped (root-permission test) |
| Corpus linux -O0 / -O1 | 128/128 / 128/128 |
| Corpus windows -O0 / -O1 (MinGW-w64 + Wine) | 128/128 / 128/128 |
| Leak check (`DEVARA_RT_STATS=1`, all normally-exiting programs × 2 levels) | 236/236 live=0 |
| ASan/UBSan runtime build on memory-heavy programs | clean (85 cases) |
| `scripts/check_machine.py` on Linux | PASS |

Benchmarks (`scripts/bench.py`, wall time):

| program | -O0 | -O1 | speedup |
|---|---:|---:|---:|
| sieve 1e7 | 0.482 s | 0.200 s | 2.4× |
| matmul 200 | 0.037 s | 0.010 s | 3.7× |
| fib(32) | 0.011 s | 0.011 s | 1.0× |
| sort 1e6 | 0.212 s | 0.108 s | 2.0× |
| float loop 2e7 | 0.354 s | 0.030 s | 11.6× |

Bugs found this round, all fixed with regression tests:
- an ICE on statements after `ivvu`/`aapu`/`saagu`;
- F-006 (`-0.0` merged with `0.0` by constant propagation);
- dead-code elimination dropping the "invalid array size" error at -O1;
- a racy temp-dir test.

Not verified:
- the `windows-latest` CI job;
- running the compiler itself on a native Windows host (only cross-compiled and run under Wine). `scripts/check_machine.py` is the one-command check for that.

Remaining debt:
- interned string literals and `padham` globals stay alive until exit, by design;
- call-heavy code gains little from -O1 (no inlining).
