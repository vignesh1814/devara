# Failures found by the validation agent

Status legend: **OPEN** (reproduces on the latest merged developer branch), **FIXED** (regression test passes),
**NOTE** (observation: outside the contract or beyond "reasonable bounds"; no test asserts the opposite).
Regression tests live in `tests/validation/` and are never marked xfail.

## Summary

| ID | Severity | Area | Status | Regression test |
|---|---|---|---|---|
| F-001 | low | CLI / exit status | OPEN | `tests/validation/test_cli_extra.py::test_F001_build_to_unwritable_output_is_io_error_not_ice`, `::test_F001_build_output_is_a_directory_is_io_error` |
| F-002 | low | semantic (P24/P25) | OPEN | `tests/validation/test_semantic_rules.py::test_F002_*` |
| N-001 | note | robustness | NOTE | `tests/validation/test_cli_extra.py` (nesting up to 3000 passes) |
| N-002 | note | performance | NOTE | - |

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
* **Status**: OPEN.

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
* **Status**: OPEN.

## N-001 Very deep nesting is reported as an internal compiler error

`"(" * 20000 + "1" + ")" * 20000 + " ni chupi"` exits 3 (`internal compiler error: recursion limit exceeded (program nests
too deeply)`). Nesting depths of 3000 (parentheses), 2000 (blocks, calls, casts, indices) are accepted. The plan (risk J)
documents the recursion bound, so this is recorded as an observation, not a failure; `tests/property/test_fuzz_frontend.py`
exercises depths up to 400 and requires exit 0/1.

## N-002 Parsing very long left-associative chains is super-linear

`1 + 1 + ... + 1` with 4000 / 8000 / 16000 terms parses in 0.8 s / 1.1 s / 23 s (`./devara parse`), and sema adds a similar
amount. Realistic programs (tens of terms) are unaffected; 20000 sequential statements compile in ~16 s. Observation only.
