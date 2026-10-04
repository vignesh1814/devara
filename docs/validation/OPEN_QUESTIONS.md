# Open questions (tester agent)

Items where the spec / plan is silent or ambiguous. The tester did **not** invent a rule: corpus programs avoid
these cases, and validation tests for them are omitted or marked as "undefined behaviour" probes that only
assert "no crash (exit 0/1, never 3)".

| ID | Question | Where it matters | Sources consulted |
|---|---|---|---|
| Q-001 | Unary minus applied to `INT64_MIN`: L37 lists only binary `+ - *` as wrapping. Is `-x` for `x == INT64_MIN` wrapped (→ `INT64_MIN`) or an error? | runtime semantics | L37, P28 |
| Q-002 | Inside a block, a name used *before* a later same-scope declaration of the same name (`x ni chupi` then `int x`) — does the first use resolve to the outer/global `x`, or is it `UNDECLARED`/error? | scoping | §4.4, L18, P20, P33 |
| Q-003 | Constant-expression array dimension that traps when folded (`int a[1/0]`): semantic error (`INVALID_ARRAY_SIZE`?) or runtime `division by zero`? | P21 | P21, L38 |
| Q-004 | NaN output spelling: P3 says `-nan`; glibc prints `nan` or `-nan` depending on the sign bit. Tests avoid NaN-producing programs. | float output | P3 |
| Q-005 | Float-to-char / float-to-bool through assignment of out-of-range values (e.g. `char c lo 1.0e30`) — P27 only specifies NaN/out-of-range → `INT64_MIN` for float→int. Is float→char = (char)(int)f? Corpus uses only in-range values. | conversions | P27 |
| Q-006 | `pratisari (int i; cond; update)` with no initializer: if `cond` reads `i` the program is always `UNINITIALIZED`; if the condition does not read it (e.g. `nijam`) and the update assigns it, is it accepted? | L46, P24 | L46, §4.19 |
| Q-007 | Range loop modifying its own loop variable in the body (L47: "mutable, increment occurs after each body execution"). Taken literally the next value is `i_modified + 1`; the tester assumes this reading in validation tests only (not in the corpus). | loops | L47, §4.18 |
| Q-008 | Is a `padham` element-type array parameter (`padham a[]`) accepted? Plan P29 says element type may be any non-void type; corpus uses it (DSA-115) on that basis. | arrays | P29, §3.5.2 |
| Q-009 | Order of diagnostics when a source has both semantic errors in multiple functions: sorted by position (plan F) — tests only check the *set* of categories. | diagnostics | §F |
