# Failures found by the validation agent

Status legend: **OPEN** (reproduces on the latest merged developer branch), **FIXED** (regression test passes),
**NOTE** (observation: outside the contract or beyond "reasonable bounds"; no test asserts the opposite).
Regression tests live in `tests/validation/` and are never marked xfail.

## Summary

| ID | Severity | Area | Status | Regression test |
|---|---|---|---|---|
| F-001 | low | CLI / exit status | FIXED (developer c3c2b2f; regression tests pass) | `tests/validation/test_cli_extra.py::test_F001_build_to_unwritable_output_is_io_error_not_ice`, `::test_F001_build_output_is_a_directory_is_io_error` |
| F-002 | low | semantic (P24/P25) | FIXED (developer c3c2b2f; regression tests pass) | `tests/validation/test_semantic_rules.py::test_F002_*` |
| F-003 | low | lexer (Q-011) | FIXED (developer c3c2b2f; regression tests pass) | `test_round2_rulings.py::test_Q011_leading_zero_with_8_or_9_is_invalid_number` |
| F-004 | low | CLI (Q-012, F-001 wording) | FIXED (developer c3c2b2f; regression tests pass) | `test_round2_rulings.py::test_Q012_*`, `::test_F001_message_format` |
| F-005 | low | parser (N-001, ruled a bug) | FIXED (developer c3c2b2f; regression tests pass) | `test_round2_rulings.py::test_N001_too_deep_*` |
| N-001 | note | robustness | NOTE | `tests/validation/test_cli_extra.py` (nesting up to 3000 passes) |
| N-002 | note | performance | FIXED (linear: 64000-term chain parses in 1.8 s) | - |

---

## F-001 `build -o <unwritable path>` exits 3 (internal compiler error) instead of 2 (I/O error)

* **Reproducer**

  ```sh
  echo '1 ni chupi' > a.tel
  ./devara build a.tel -o /nonexistent/dir/out ; echo $?     # -> 3
  mkdir d && ./devara build a.tel -o d           ; echo $?     # -> 3
  ```
* **Expected** (plan §E): "`2` usage / I/O error; `3` internal compiler error (uncaught exception, IR verifier failure,
  assembler/linker failure of *generated code*)". Failing to write the requested output file is an I/O error, not a
  compiler bug, so the status must be `2` and the message must not say "internal compiler error".
* **Actual**: exit `3`, stderr `a.tel: internal compiler error: assembler/linker rejected generated code:
  /usr/bin/ld: cannot open output file /nonexistent/dir/out: No such file or directory`.
* **Status**: FIXED in developer c3c2b2f (regression tests pass).

## F-002 Any literal behind a conversion counts as a "constant-true" `while` condition

* **Reproducer**

  ```sh
  printf "int f charya () { 'a' unnanta varaku { 1 ivvu } }\n" > c.tel && ./devara sema c.tel ; echo $?    # -> 0
  printf "int f charya () { (int) 1 unnanta varaku { 1 ivvu } }\n" > c.tel && ./devara sema c.tel ; echo $? # -> 0
  ```
* **Expected** (plan P24, restated by P25): a `while` is treated as "constant true" only when its condition "is the literal
  `nijam` or a non-zero int literal". `'a'` is a char literal and `(int) 1`, `(char) 1`, `(bool) 1`, `(float) 1` are cast
  expressions, so these functions *can* complete normally -> `MISSING_RETURN`; and in the definite-initialisation analysis the
  after-loop state is the state after the condition, not the intersection over `aapu`s (`UNINITIALIZED` on a later read).
  (`1 + 1`, `-1`, `!abaddham`, `nijam && nijam` are already treated correctly as non-literals.)
* **Actual**: accepted (exit 0): the analysis sees through implicit/explicit conversions of a literal.
* **Impact**: accepts programs the plan says must be rejected (conservative direction is the opposite); no wrong code
  is generated for accepted programs.
* **Status**: FIXED in developer c3c2b2f (regression tests pass).

## N-001 Very deep nesting is reported as an internal compiler error

`"(" * 20000 + "1" + ")" * 20000 + " ni chupi"` exits 3 (`internal compiler error: recursion limit exceeded (program nests
too deeply)`). Nesting depths of 3000 (parentheses), 2000 (blocks, calls, casts, indices) are accepted. The plan (risk J)
documents the recursion bound, so this is recorded as an observation, not a failure; `tests/property/test_fuzz_frontend.py`
exercises depths up to 400 and requires exit 0/1.

## N-002 Parsing very long left-associative chains is super-linear

`1 + 1 + ... + 1` with 4000 / 8000 / 16000 terms parses in 0.8 s / 1.1 s / 23 s (`./devara parse`), and sema adds a similar
amount. Realistic programs (tens of terms) are unaffected; 20000 sequential statements compile in ~16 s. Observation only.

## F-003 `0` followed by digits containing 8/9 is only rejected for two-digit forms (plan §M, Q-011)

* Reproducer: `echo 078 > n.tel; ./devara lex n.tel` -> tokens `07` `8` (also `0189` -> `01`,`89`; `00009` -> `0000`,`9`).
* Expected: lexical `INVALID_NUMBER` for any `0` + decimal digits that include `8` or `9` (only a digit run followed by a letter/underscore splits per P15). `08`/`09` already behave correctly.
* Status: FIXED in developer c3c2b2f (regression tests pass).

## F-004 Round-2 CLI rulings not yet implemented (Q-012, F-001 message)

* `./devara build bad.s -o out` (invalid assembly) must exit 1 with `FILE: assembler error: ...`; currently exit 3 ICE.
* `build -o /nonexistent/dir/out` must exit 2 with `cannot write output '<path>'`; currently exit 3 (see F-001).
* Status: FIXED in developer c3c2b2f (regression tests pass).

## F-005 Nesting limit (plan §M, N-001 now ruled a bug)

* `"(" * 30000 + "1" + ")" * 30000 + " ni chupi"` must exit 1 with `syntax error [INVALID_EXPRESSION]` (implementation limit; supported depth >= 1000), not exit 3 / process kill. Observed: ICE exit 3 at 20000 and the process was killed (rc -9, likely memory) at larger depths in the test harness.
* Status: FIXED in developer c3c2b2f (regression tests pass).

## Status after merge of developer c3c2b2f

All of F-001..F-005 are fixed and their regression tests pass in the final full run (5155 passed, 1 skipped). N-001/N-002 were ruled bugs/perf items by the design authority and are fixed (N-001 is covered by `test_round2_rulings.py::test_N001_*`). No open findings remain.
