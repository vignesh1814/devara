# Performance

`-O0` keeps the reference stack-slot code generator (every virtual register lives in an 8-byte frame
slot). `-O1` runs the IR optimizer and then the register-allocating back end.

## The -O1 back end

* **Allocation** (`compiler/codegen/regalloc.py`): CFG liveness over the linear block order, one
  conservative interval per virtual register (extended across loop back edges), linear scan. Intervals
  live across a call may only use callee-saved registers (`rbx r12-r15`, plus `rdi rsi` on Windows);
  others may also use the caller-saved registers outside the scratch set. SysV has no callee-saved xmm
  register, so call-crossing floats spill there; on Windows they use `xmm6-xmm15`. When registers run
  out, the interval with the lowest loop-depth weighted access count per unit of length is spilled to a
  stack slot (slots are reused after an interval ends). Only the callee-saved registers actually used
  are saved and restored; frames stay 16-byte aligned.
* **Scratch registers** (never allocated): `rax rcx rdx r10 xmm0 xmm1`; `r11` is allocatable (audit F9). Call
  arguments and incoming parameters are moved with a parallel-move resolver (cycles broken through `rax`).
* **Shrink-wrapped callee-saved registers** (audit F7, `prep._wrap_calls` + `x86_64_ra`): when every call lies in a
  single-entry region (rooted at the deepest block dominating all calls), parameters used after a call there are
  copied into fresh registers at its entry, and callee-saved registers used only inside the region are saved on
  entry to it and restored by the returns inside it, so a recursive function's base case touches none of them.
* **Frameless leaves** (audit F12): a function with no calls, no integer division, no stack parameters and an
  empty frame (nothing spilled, saved or in a frame array) is emitted without `push rbp` / `leave`.
* **Pre-allocation rewrites** (`compiler/codegen/prep.py`): scalar globals and array base pointers that
  only `$entry` touches become registers of `$entry` (top-level programs keep all their variables in
  globals; `str` globals stay in memory so interned literals remain reachable); `t = op; x = copy t`
  becomes `x = op`; a single-use `ptradd` folds into the `[base + index*8]` addressing mode of its
  load/store; a trailing `cmp` fuses into its `branch`.
* **Instruction selection**: `lea` for three-address adds, signed division/remainder by powers of two
  without `idiv`, immediates and memory operands used directly, loop rotation (a back edge to a tiny
  condition block duplicates the test instead of jumping).
* **Peephole** (`compiler/codegen/peephole.py`): drops `mov r,r`, folds store/reload pairs, removes a
  jump to the next label and dead code after unconditional transfers, inverts `jcc A; jmp B; A:`, and
  turns `cmp r,0` into `test r,r`.

Runtime calls (including retain/release) are never reordered or removed by these steps.

## Benchmarks

`python3 scripts/bench.py [--runs N] [--markdown]` compiles each program at both levels and reports the
minimum wall time over N runs (compile time excluded). Linux x86-64, gcc runtime at `-O2`, N = 7:

| program | what it stresses | -O0 (s) | -O1 (s) | speedup |
|---|---|---:|---:|---:|
| sieve 1e7 | loop + array | 0.441 | 0.165 | 2.7x |
| matmul 200 | 2-D arrays, triple loop | 0.027 | 0.008 | 3.3x |
| fib(32) | recursion, calls | 0.011 | 0.009 | 1.2x |
| sort 1e6 | merge sort, array params | 0.212 | 0.134 | 1.6x |
| float loop 2e7 | float arithmetic | 0.348 | 0.027 | 13.1x |

Notes: the compute-bound loops (matmul, float loop) exceed 3x. The sieve and the merge sort are bound by
memory (an 8 MB array of 8-byte cells, page faults, cache misses and unpredictable branches; bool and char
arrays use one byte per element since audit F8, which made the sieve 3.7x faster), and
fib(32) by call/return overhead, where the stack-slot code already benefits from store forwarding, so
they gain less than 3x. Absolute times are for the sizes fixed by the task and are short, so expect
noise of a few milliseconds. Timings under wine are dominated by wine's ~2.4 s process start-up and are
not meaningful.

## Compile time

`devara -O1 asm` on generated programs made of many small functions (`docs/audit/repro/compile_scaling.py`);
`-O0` is about 0.09 ms per line throughout. Times in seconds on one machine, before and after audit item F13
(each function now runs to its own fixed point and is verified only after a pass that changed it; the IR is
cloned instead of deep-copied; passes detect changes with structural keys instead of `repr`):

| lines | before | after |
|---:|---:|---:|
| 5,000 | 3.8 | 1.5 |
| 20,000 | 17.6 | 6.6 |

The generated assembly is byte-identical before and after.

