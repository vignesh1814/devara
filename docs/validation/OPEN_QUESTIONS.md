# Open questions and conventions taken (developer agent)

Entries are **not** language changes. Where the plan was silent or ambiguous the developer took
the smallest conservative convention listed here; the design authority may override any of them.

| ID | Phase | Topic | Plan/spec text | Convention taken |
|---|---|---|---|---|
| OQ1 | 4 | Category for an *array used as a condition* | P28: conditions need an arithmetic type (`INVALID_CONDITION`); P29: arrays in conditions → `INVALID_OPERAND`/`TYPE_MISMATCH` | `INVALID_OPERAND` (same as every other array-as-scalar use). `padham` conditions stay `INVALID_CONDITION`. |
| OQ2 | 4 | Category for *implicit* conversion failures (assign, argument, return, index, range bound, dimension) | P27 only names `INVALID_CONVERSION` for explicit casts | `TYPE_MISMATCH` for implicit failures; `INVALID_CONVERSION` only for explicit casts. |
| OQ3 | 4 | Source byte model | L40 `char` is an 8-bit unit; spec §2 identifiers are ASCII | The CLI reads sources as bytes and decodes them as latin-1, so one byte = one character unit (non-ASCII bytes occur only in comments/strings/chars; a UTF-8 `é` in a char literal is two units → lexical error). Library callers passing a `str` with code points > 255 get UTF-8 bytes in string literals. |
| OQ4 | 4 | P21 with only *some* constant dimensions (e.g. `int a[0][n]`) | "If every dimension is constant it must be ≥ 1" | Only the all-constant case is a compile-time error; mixed cases are checked at runtime (`invalid array size`). |
| OQ5 | 4 | Function name used as a value / array or function as operand | not covered | `INVALID_OPERAND`. |
| OQ6 | 4 | Span of `MISSING_RETURN` | not covered | the function-name identifier. |
| OQ7 | 4 | Explicit cast to the same type (`(int) x` for an `int`) | not covered | kept as a `TConvert(explicit=true)` identity node; no diagnostic. |
| OQ8 | 4 | Float literal overflow (e.g. 400 digits) | not covered | evaluates to `inf` (no diagnostic). |
| OQ9 | 3 | Recovery inside delimited lists stops at an unmatched `}` as well | §3.7.3 lists COMMA/RPAREN/EOF (args) and RBRACKET/RPAREN/COMMA/RBRACE/EOF (indices) | `}` closing the enclosing block is never consumed by any recovery loop, so one error cannot swallow the following block terminator. |
| OQ10 | 3 | Statement recovery progress guard | §3.7.1 says leave a FIRST-set token unconsumed, but `IVVU` is in FIRST(statement) although no statement starts with it | If recovery makes no progress the loop force-consumes one token (termination invariant §3.7.4). |
| OQ11 | 3 | `int x lo 1 pettu` (initialised declaration) and nested `T f charya()` | not in grammar | rejected with `INVALID_DECLARATION` and a dedicated message. |

---

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

## Round 2 (tester)

| ID | Question | Where it matters | Sources consulted |
|---|---|---|---|
| Q-010 | P7 says numeric input follows "C++ `cin >>` semantics: skip whitespace, read one token", with `int` = "optional sign + decimal digits". For a token with trailing junk (`3.5`, `12abc`, `1x` read as `int`/`float`/`bool`) is the result (a) the leading prefix (C++ `cin`: reads `3`, leaves `.5`) or (b) `invalid input` for the whole token? The current compiler implements (b). Corpus and validation tests avoid this input; the reference interpreter implements both (`strict_tokens`) and the I/O fuzz test skips streams where they disagree. | P7, P10 | P7, P8, P10, L42 |
| Q-011 | `09`, `078`: the lexical grammar has no rule (an octal literal needs octal digits). The compiler reports lexical `INVALID_NUMBER` ("Invalid octal literal"); P15 suggests two tokens (`0`,`9`) for similar malformed numbers. Tests accept either. | lexer | P15, spec §3.1 |
| Q-012 | `devara build FILE.s` with a hand-written/invalid assembly file exits 3 (ICE: "assembler/linker rejected generated code"). Plan §E reserves exit 3 for failures on *generated* code; for user-supplied `.s` input the status is unspecified. Not tested. | CLI | §E |

## Round 3 (tester: register allocation / memory / Windows suites)

| ID | Question | Where it matters | Sources consulted |
|---|---|---|---|
| Q-013 | P7 says a float token is "`strtod`-acceptable", Q-010 says the whole token must match the type's form. `0x10` (hex float) and `infinity`/`nan(...)` are strtod-acceptable. The compiler reads `0x10` as `16.0`; the reference interpreter reports `invalid input`. Token tests avoid `0x..` float input. | P7, Q-010 | P7, Q-010 |
| Q-014 | `\r\n` on input. On Linux a `padham` line read from `a\r\n` is `a\r` (length 2: the compiler and the reference interpreter agree). For the Windows target the task statement says `\r\n` input "must behave like `\n`", so `padham` lines carry no `\r`. `test_windows_target.py` therefore compares the Windows run with the reference run on the CRLF-translated input (text-mode semantics: only `\r\n` pairs are translated; a lone `\r`, `0x1A` and every other byte are data). Linux behaviour for CRLF input is not changed by the tests. | P9, P30 (source files only), Windows task | P9, P30 |
