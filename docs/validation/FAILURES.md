# Failures found by the validation agent

Status legend: **OPEN** (reproduces on the latest merged developer branch), **FIXED** (regression test passes),
**NOTE** (observation: outside the contract or beyond "reasonable bounds"; no test asserts the opposite).
Regression tests live in `tests/validation/` and are never marked xfail.

## Summary

| ID | Severity | Area | Status | Regression test |
|---|---|---|---|---|
| F-001 | low | CLI / exit status | OPEN | `tests/validation/test_cli_extra.py::test_F001_build_to_unwritable_output_is_io_error_not_ice`, `::test_F001_build_output_is_a_directory_is_io_error` |
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

## N-001 Very deep nesting is reported as an internal compiler error

`"(" * 20000 + "1" + ")" * 20000 + " ni chupi"` exits 3 (`internal compiler error: recursion limit exceeded (program nests
too deeply)`). Nesting depths of 3000 (parentheses), 2000 (blocks, calls, casts, indices) are accepted. The plan (risk J)
documents the recursion bound, so this is recorded as an observation, not a failure; `tests/property/test_fuzz_frontend.py`
exercises depths up to 400 and requires exit 0/1.

## N-002 Parsing very long left-associative chains is super-linear

`1 + 1 + ... + 1` with 4000 / 8000 / 16000 terms parses in 0.8 s / 1.1 s / 23 s (`./devara parse`), and sema adds a similar
amount. Realistic programs (tens of terms) are unaffected; 20000 sequential statements compile in ~16 s. Observation only.
