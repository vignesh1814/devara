# Improvement plan (ranked, nothing is fixed yet)

The findings and their reproducers are in [`AUDIT_REPORT.md`](AUDIT_REPORT.md). Items are ranked first by severity, then by value for the effort.
Effort: XS < 1 h · S ≈ half a day · M ≈ 1–2 days.
Every fix will come with a regression test in `tests/regression/`, and the full suite, the corpus at -O0 and -O1, the leak check and the Windows-target tests must stay green.

## Tier 1: correctness (do first)

| # | Finding | Severity | Effort | Proposed fix |
|---|---|---|---|---|
| 1 | **F1** The array-size product wraps, causing a silent heap overflow on in-bounds accesses. | High (memory corruption with exit 0) | S | Compute the element-count product with an overflow check, either a runtime helper (`dv_rt_dimmul`) or `imul` plus `jo`, and also check `total * 8`. On overflow, fail with `invalid array size`. Apply the same check to constant products in sema. |
| 2 | **F2** A constant-size global array over 2 GiB (or with a product ≥ 2^63) causes an internal compiler error. | Medium (exit 3 on accepted input) | S | Treat a constant total over `INT64_MAX/8` as semantic error `INVALID_ARRAY_SIZE`. Put global arrays above a threshold (e.g. 256 MiB) on the heap, using the existing runtime-sized global path, so they never reach `.bss` and relocation limits. |
| 3 | **F3** Unchecked `malloc`/`realloc` in the runtime's input helpers. | Low | XS | Add a `xmalloc`/`xrealloc` wrapper that calls `fail("out of memory")`, and add that message to P11's list. |

## Tier 2: generated-code performance (biggest measured gains)

| # | Finding | Measured effect | Effort | Proposed fix |
|---|---|---|---|---|
| 4 | **F8** 8-byte `bool`/`char` array elements. | Sieve: -O1 runs 0.71 s against gcc -O0 0.40 s and gcc -O2 0.135 s, using 8× the memory. | M | Use a per-element-type size (1 byte for `bool`/`char`, 8 for `int`, `float` and `padham`) in IR `ptradd`, in load/store widths (`movzx`/`movsx`, byte stores), in `dv_rt_newarray(n, elsize)`, and in frame and `.bss` sizing. Array parameters are already typed, so the ABI is unaffected. |
| 5 | **F7 + F12** No shrink-wrapping, and frames are always set up. | fib(35): -O1 0.073 s is slower than -O0 0.064 s. | M | Save callee-saved registers only in blocks that dominate their use, or at minimum skip the save and restore on early-return paths that don't use them. Omit the `rbp` frame in leaf functions with no spills and no stack arrays. |
| 6 | **F9** Only 4 (SysV) or 2 (Win64) caller-saved registers can be allocated. | Leaf loops spill into `rbx` and pay for a save, a restore and a frame. | M | Make `rcx`, `rdx`, `r10` and `r11` allocatable outside the instructions that need them (`idiv`, shifts, call setup), reserving them only at those points, or keep just one scratch register. Leaf functions benefit most, and so does Win64. |
| 7 | **F11** Redundant moves at call and return boundaries. | A few instructions per call. | S–M | Register hints: prefer the return register for a value that is returned and the argument register for a value that is passed. Coalesce copies whose live ranges don't interfere, and use memory operands for single-use loads. |
| 8 | **F10** No loop-invariant code motion. | Global array base recomputed each iteration. | M | A simple LICM pass for pure instructions (`ptradd` of a global, constant `cmp` operands) into a preheader. |

## Tier 3: diagnostics

| # | Finding | Effort | Proposed fix |
|---|---|---|---|
| 9 | **F4** Cascading error after `ni <identifier>`. | S | When the token after `ni` is an identifier on the same line, consume it as part of the bad statement before failing. Alternatively, suppress a second error that starts at the recovery point. |
| 10 | **F5** "Expected statement keyword" reported at the next token, often on a later line. | S | Anchor the diagnostic at the end of the expression (the previous token's end) and say "expected 'ivvu', 'ni chupi', 'lo … pettu', 'ayite' or 'unnanta varaku' after expression". |
| 11 | **F6** Enum names in messages (`SUB`, `MUL`, `LT`), and the unary message omits the operator. | XS | Map ops to their source spelling (`'-'`, `'*'`, `'<'`) in `checker.py`. |

## Tier 4: tooling and infrastructure

| # | Finding | Effort | Proposed fix |
|---|---|---|---|
| 12 | **F13** -O1 compiles about 10× slower than -O0 (52 s for 50,000 lines), with 45 verifications per function. | S | Iterate each function to its own fixed point and verify only the functions a pass changed, or verify once per round. Run the full verifier after every pass only under a debug flag. |
| 13 | **F16** CI never run, and native Windows never verified. | — | Pushing this audit triggers `.github/workflows/ci.yml`. Check the `windows-latest` job result, and run `python scripts/check_machine.py` on the owner's Windows machine. |
| 14 | **F14** Intermittent Windows-target test failure under parallel wine (UNCONFIRMED). | XS | Make the Windows test helper ignore known wine stderr noise (lines starting with `wine:` / `fixme:`), or set `WINEDEBUG=-all`, and capture the full failure if it recurs. |
| 15 | Repository leftovers: `main.py`, the duplicated `examples/`, and `docs/DEVARA_STAGE_2_DESIGN_v1.1_FINAL (3).md`. | XS | Remove or rename them, and update references. |

**Recommended order:** 1 → 2 → 3, then 11 (trivial), then 4 → 5 → 6, then 9 and 10, then 12. Items 7, 8 and 15 can be done whenever convenient.
