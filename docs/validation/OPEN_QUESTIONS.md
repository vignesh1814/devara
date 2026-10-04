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
