# Independent Validation Report (tester agent)

Branch `devara-validation-l3txzx`, merged with developer branch HEAD `c3c2b2f`. All numbers below are from the
commands run on that merged tree.

## 1. Full test run

`python3 -m pytest -n 4 -q -p no:cacheprovider -rs` (everything, including slow, property and fuzz tests; run on an otherwise idle machine):

```
5155 passed, 1 skipped in 233.06s
SKIPPED [1] tests/regression/test_bug_cli_io_and_limits.py:44: root ignores directory permissions
```

| Metric | Count |
|---|---|
| Total tests | 5156 |
| Passed | 5155 |
| Failed | 0 |
| Skipped | 1 (developer's directory-permission test; cannot fail meaningfully as root; documented reason) |
| xfail | 0 (no test is marked xfail by the tester) |
| Compiler crashes (exit 3) observed by any test | 0 |
| Timeouts | 0 |

An earlier run of the same tree reported 1 failure (`test_cli_extra.py::test_run_does_not_leave_temp_files_behind`) while a
separate corpus job was running concurrently and creating its own `devara_*` temp directories; it passes in isolation and in the clean run above. The temp-dir
leftovers that exist in /tmp were created by processes the tester killed on purpose (infinite-loop probes), not by normal runs.

Tests by suite (from `pytest --collect-only`): tester suites `tests/validation` 3,514 (runtime 1,045; adversarial 532; semantic rules 525;
parser productions 425; corpus e2e 412; lexer 306; stage observability 153; round-2 rulings 46; CLI 52; forms 32), `tests/property` 82, `tests/reference` 147; the rest (about 1,400) are the developer's unit/integration/regression tests.

## 2. Corpus statistics (`python3 scripts/run_corpus.py`, 10 s timeout per program)

| | -O0 | -O1 |
|---|---|---|
| total programs | 128 | 128 |
| compiled | 128 | 128 |
| failed compilation | 0 | 0 |
| executed | 128 | 128 |
| runtime-failed (unexpected) | 0 | 0 |
| incorrect output | 0 | 0 |
| timeout | 0 | 0 |
| **correct** | **128** | **128** |

Corpus: arrays 14, sorting 10, searching 8, strings 14, math 16, recursion 11, data structures 10, DP 10, graphs 10, misc 25 (including 10
runtime-error programs with `.exit`/`.err`). Every expected `.out` was produced by the independent Python oracle in `tests/corpus/_oracles/`, never by compiler output.
The tester's own pytest corpus check (`test_corpus_e2e.py`) additionally verifies the stderr diagnostic of the 10 runtime-error programs,
and that -O0 and -O1 agree.

## 3. Independent evidence beyond the corpus

* **Reference interpreter** (`tests/reference/interp.py`, written from the spec, consuming the parser AST): reproduces all 128 oracle outputs.
* **Differential fuzzing** (random well-typed, trap-free programs with side-effecting calls, array-parameter aliasing, 2-D rows, floats,
  chars, padham): 27 hypothesis/fixed-seed tests plus two long campaigns (300 programs size 30; 1,200 programs size 45): 0 compiler
  mismatches at -O0/-O1 (2 campaign "problems" were a generator bug, an explicit `/ -1` on INT64_MIN, fixed).
* **I/O differential fuzz** (random read sequences over random byte streams incl. CRLF, NUL, high bytes): 47 tests, 0 mismatches.
* **Front-end fuzz**: token soup, bad fragments, Latin-1 text, mutated and truncated corpus programs, deep nesting: 0 crashes/hangs, only exit 0/1 with well-formed diagnostics.
* **Adversarial probes**: evaluation order with side effects, aliasing, NaN/signed zero, float-algebra prohibition (L49), trap preservation under
  algebraic rewrites, calling-convention stress (up to 40 parameters, every stack parity), signed char/bool storage, embedded NULs, 1 MB input lines, 10^6 output lines, 20,000-deep recursion.

## 4. Findings

Five conformance findings were reported and all are fixed and verified by regression tests that pass:

| ID | Summary | Status |
|---|---|---|
| F-001 | `build -o` to an unwritable path exited 3 instead of 2 | FIXED |
| F-002 | char/cast literal treated as constant-true `while` (P24/P25) | FIXED |
| F-003 | `078`, `0189`, `00009` lexed as two tokens instead of INVALID_NUMBER (Q-011) | FIXED |
| F-004 | bad user `.s` file -> ICE exit 3 instead of exit 1 assembler error (Q-012) | FIXED |
| F-005 | nesting limit gave ICE / killed process instead of exit 1 INVALID_EXPRESSION (N-001) | FIXED |

Performance note N-002 (super-linear parse of long chains) is fixed: 4,000 / 16,000 / 64,000-term chains parse in 0.21 s / 0.55 s / 1.83 s.
Details and reproducers: `docs/validation/FAILURES.md`. Specification gaps and the design authority's rulings: `docs/validation/OPEN_QUESTIONS.md`.

## 5. Limits of this validation (what was not shown)

* One platform: x86-64 Linux, gcc 13, Python 3.11. Behaviour of NaN sign in `%g` output (Q-004) is intentionally untested.
* Stack overflow for very deep recursion is undefined by the plan (P38); only 20,000-frame recursion is tested.
* The 1 skipped test needs a non-root user.
* Randomized tests sample the space; they do not prove absence of bugs.

## 6. Verdict

**PASS.** On the merged tree the complete test suite is green (5155 passed, 0 failed, 1 documented skip), all 128 independent corpus programs compile and
produce the oracle-expected stdout and exit status at both -O0 and -O1 (128/128), the differential fuzzers found no disagreement between the compiler and the
independent reference interpreter, and every defect the tester found has been fixed and is covered by a passing regression test. No open findings remain.
