# Devara Compiler — Engineering Plan, Specification Review and Stage Contracts

**Status:** Phase 0 deliverable (design authority). Governs Phases 1–8.
**Authoritative sources (in order):**
1. `docs/DEVARA_LANGUAGE_SPEC_v0.7.md` (canonical language)
2. `docs/DEVARA_REMAINING_STAGES_THEORETICAL_DESIGN_v7.md` (Stages 3–6, frozen decisions L1–L49, AST contract §3.5, diagnostics §3.6, recovery §3.7)
3. `docs/DEVARA_STAGE_2_DESIGN_v1.1_FINAL (3).md` (parser design)
4. **This document** — resolves the remaining gaps (decisions `P1…`). Where this
   document and 1–3 disagree, 1–3 win, and the disagreement must be reported.

Process rules: `docs/process/MASTER_EXECUTION_PROMPT.md`.

---

## A. Repository assessment (baseline commit `5ef3931`)

| Item | Finding |
|---|---|
| Language | Python 3.11 (uses `enum.StrEnum`). No third-party runtime deps. |
| Layout | `compiler/{lexer,parser,ast,semantic,codegen}`; `semantic/` and `codegen/` are empty stubs. |
| Entry point | `main.py` with `lex` and `parse` commands only. |
| Tests | pytest, 255 tests, all passing: lexer (`test_lexer.py`, `test_exhaustive_lexer.py`), parser (`test_parser.py`, `test_parser_sieve.py`, `test_sieve.py`), `test_phase0.py`, and `test_programs_e2e.py` (lex+parse only). |
| Corpus | 25 `tests/programs/dsa/*.tel` + `sieve.tel` + `examples/example.tel`. Mostly function definitions with no top-level driver and no expected output. Parse-only. |
| Scripts | `tests/audit_scripts/*.py` (ad-hoc print scripts, not tests; since deleted). Root `multi.py`, `multi2.py`, `prompt.txt` are scratch files. |
| Build/CI | None. `requirements.txt` lists only pytest. `pyrightconfig.json` points to a Windows venv. |
| Toolchain in cloud container | x86-64 Linux, gcc/as/ld present, Python 3.11, 4 vCPU, 15 GB RAM. GPU: **not useful** (none needed). |

### Existing implementation vs. spec

| Component | Existing behavior | Required behavior | Impact | Action |
|---|---|---|---|---|
| Lexer tokens/regex | Matches spec lexical grammar (dec/oct/hex, floats, escapes, case-insensitive keywords) | Same | — | **KEEP** |
| Lexer diagnostics | `LexerError` without category | Structured diagnostic with category + span | Low | **MODIFY** |
| Lexer CR handling | `\r` is an "unexpected character" | Treat `\r\n` as a newline (P30) | Low | **MODIFY** |
| Token | `type, lexeme, line, column` | plus derivable half-open end (`column+len(lexeme)`) | Low | **KEEP** (add `end_column` property) |
| AST spans | `end_column` = *start* column of last token (closed, wrong) | Half-open `[start,end)` (design §3.5.1) | Medium | **REWRITE nodes** |
| AST names | `Declaration.name: str`, `Parameter.name: str`, `RangeLoop.target: str` | `Identifier` nodes (§3.5.5/10) | Medium | **MODIFY** |
| `ArrayAccess` | nested binary `array/index` | flat `base: Identifier, indices: list` (§3.5.11) | Medium | **MODIFY** |
| `FunctionCall.callee` | any expression | `Identifier` (§3.5.11) | Medium | **MODIFY** |
| `ForInit` | single class with optional `type` | tagged union of 3 variants (§3.5.7) | Medium | **MODIFY** |
| `ForLoop` fields | Optional `init/condition/update` | never `None` (§3.5.12 inv. 4) | Low | **MODIFY** |
| `IfStatement.else_block` | named `else_block` | `else_branch` (§3.5.6) | Low | **MODIFY** |
| `UnaryExpression.position` | carries PREFIX/POSTFIX | no position (unary ops are prefix only) | Low | **MODIFY** |
| Parser: bare `{...}` block statement | accepted | **not** in grammar (§11.3) — accidental extension | Medium | **REMOVE** |
| Parser: postfix chains `f(1)(2)`, `a[1](2)`, `f(x)[0]` | accepted | grammar: `identifier(...)`, `identifier[..]{[..]}` only | Medium | **REMOVE** |
| Parser: `(x) lo 1 pettu`, `++(x)`, `(x)++`, `(a) ni chaduvu` | accepted (parens stripped) | target must be bare `identifier | array-access` | Low | **REJECT** |
| Parser: function/declaration lookahead | ad-hoc multi-token scan | LL(3): `type IDENT CHARYA` | Low | **SIMPLIFY** |
| Parser diagnostics | message only | closed category set §3.6 + `expected` | Medium | **MODIFY** |
| Parser recovery | ad-hoc sync sets | §3.7 algorithm and sets | Medium | **MODIFY** |
| Semantic / IR / opt / codegen / runtime | absent | Stages 3–6 | High | **NEW** |
| CLI | `lex`, `parse` | all stages + build/run (§E) | High | **REWRITE** |

---

## B. Specification inventory (summary)

* **Lexical:** spaces/tabs/newlines skipped; `#` comments to EOL; identifiers `[A-Za-z_][A-Za-z0-9_]*`;
  26 keywords, case-insensitive (`AYITE` is a keyword).
* **Literals:** int (decimal `0|[1-9][0-9]*`, octal `0[0-7]+`, hex `0[xX][0-9a-fA-F]+`), float `d+.d+`,
  bool `nijam/abaddham`, char `'c'`/`'\e'`/`'\xHH'`, string `"..."` with the same escapes.
* **Operators:** `+ - * / %  < > <= >=  == !=  && || !  ++ --` (`++/--` only in `pratisari` update). No `=`.
* **Types:** `int float bool char padham void`; arrays of any non-void element type, any rank.
* **Statements:** declaration, assignment `t lo e pettu`, input `t ni chaduvu`, output `e ni chupi`,
  if `e ayite {} [lekunte ({}|if)]`, while `e unnanta varaku {}`, range `prati i a nundi b varaku {}`,
  three-part `pratisari (init; cond; update) {}`, `aapu`, `saagu`, `e ivvu`, call statement `f(...)`.
* **Functions:** `type name charya (params) {}`; params `type name` or `type name[]`; top level only.
* **Expressions:** precedence `|| < && < ==,!= < relational < +,- < *,/,% < unary(!,+,-,cast) < primary`;
  all binary operators left-associative; cast `(type) unary`.
* **Semantics (frozen):** L1–L49 in design §13.3 — C++ conversions, int=i64 wrapping, float=binary64,
  div/rem by zero and `INT64_MIN / -1` runtime errors, short-circuit, left-to-right evaluation,
  range loop `[start,end)` step +1, globals zero-initialized, definite initialization for locals,
  every path of non-void function returns, `podavu(padham)->int` predeclared builtin, padham immutable
  with `+ == != [] podavu`, `char↔padham` explicit only, no array bounds checks, row-major arrays.
* **Target:** x86-64 System V, GNU as `.intel_syntax noprefix`, ELF, linked with gcc.

---

## C. Specification consistency review and ambiguity resolutions

Classification: **B** = BLOCKING, **I** = IMPORTANT, **M** = MINOR, **N** = NON-ISSUE.
Each `P` decision is binding on the implementation agents. The project owner may override any of them;
an override is a spec change and must update this table and the affected tests.

### C.1 Output / input / runtime (needed for any golden test)

| ID | Cls | Area | Spec says | Ambiguity | Decision (recommended interpretation) | Reason |
|---|---|---|---|---|---|---|
| P1 | B | `chupi` line termination | "outputs value" | newline or not? | Every `chupi` writes the value followed by `\n`. | Statement-oriented language; no other way to separate numbers. |
| P2 | B | int output | — | format | Decimal, `-` sign for negatives (`printf("%lld")`). | C++ `cout`. |
| P3 | B | float output | — | format | C++ default `ostream` formatting = `printf("%g")` (6 significant digits): `3.14`, `10`, `1e+06`, `inf`, `-nan`. | Literal C++ model; enables differential tests vs g++. |
| P4 | B | bool output | — | `1/0`, `true/false`, or keywords | `nijam` / `abaddham`. | Language's own spelling; round-trips with input (P8). |
| P5 | B | char output | — | | The raw byte. | C++ `cout << char`. |
| P6 | B | padham output | "complete text value" | | All bytes of the text (embedded NUL included), then `\n`. | |
| P7 | B | int/float/char input | — | token vs line | C++ `cin >>` semantics: skip whitespace, read one token. `int`: optional sign + decimal digits, must fit i64; `float`: `strtod`-acceptable token; `char`: next non-whitespace byte. | C++ model. |
| P8 | B | bool input | — | | Token `nijam`/`abaddham` (case-insensitive) or `1`/`0`. | Symmetric with P4, accepts C++ form. |
| P9 | B | padham input | "one complete input line" (L10) | interaction with preceding token read | Reads bytes up to the next `\n` (consumed, not stored); a `\r` immediately before that `\n` is dropped (CRLF input reads like LF input, on every platform). If the previous input op was a token read and the rest of that line is only whitespace, that remainder is skipped first. | Avoids the classic `cin`/`getline` trap while staying line-based. |
| P10 | B | input failure (L42) | "defined runtime error" | | EOF or malformed token → runtime error. | |
| P11 | B | runtime error format (L43) | "diagnostic + non-zero" | | stderr: `devara: runtime error: <message>`; exit status **1**. Messages: `division by zero`, `remainder by zero`, `integer overflow in division`, `invalid input`, `string index out of range`, `invalid char conversion`, `invalid array size`. Stdout is flushed first. | |
| P12 | M | normal termination | — | | Exit status 0 after the last top-level statement. | |

### C.2 Lexical / syntactic

| ID | Cls | Area | Spec says | Ambiguity | Decision | Reason |
|---|---|---|---|---|---|---|
| P13 | I | escape set | §11.16 `escape-character` = any char except `' " \`, but §3.4/§11.17 defer to "forms accepted by the lexer" | grammar text would forbid `\\ \' \"` and allow `\q` | Use the lexer's set: `\n \t \r \b \f \0 \\ \' \"` and `\xHH`. Anything else is a lexical error. | Spec explicitly defers to the lexer; the grammar placeholder is acknowledged as provisional. |
| P14 | M | identifier case | silent | | Identifiers are case-sensitive (`x` ≠ `X`); keywords case-insensitive (spec). | C convention. |
| P15 | M | `123abc`, `0x` | grammar has no rule | | Lexed as two tokens (`123`,`abc`), parser then reports the error. No change. | Conforms to lexical grammar. |
| P16 | M | call-statement followed by statement starting with `+`/`-` | grammar is ambiguous for `f(x)⏎-y ni chupi` | | Longest-match: the parser continues the expression (`f(x) - y ni chupi`). Documented; tests pin it. | Standard greedy rule; no terminators exist. |
| P17 | N | top-level `declaration` vs `declaration-statement` | both productions | | Same `Declaration` node. | |
| P18 | N | bool literal token kind | design FIRST set says `BOOL_LITERAL`, lexer emits `NIJAM`/`ABADDHAM` | | Equivalent; keep lexer kinds. | |
| P30 | M | CRLF | "newlines" | `\r` | `\r\n` is a newline; a lone `\r` is an invalid character. | Windows-authored sources. |
| P31 | I | parenthesized targets | grammar: target = identifier \| array-access | parser strips parens | `(x) lo 1 pettu`, `(x) ni chaduvu`, `++(x)`, `(x)++` are **syntax errors** (`INVALID_STATEMENT`). | Grammar conformance (design §3.5.12 inv. 8). |

### C.3 Semantics

| ID | Cls | Area | Decision | Reason |
|---|---|---|---|---|
| P19 | B | Top-level declarations | Are **global** variables (global scope, static storage, zero-initialized per L21). Top-level statements are the entry region (L41). Range/`pratisari` variables at top level are loop-local. `ivvu` at top level → semantic error `INVALID_RETURN`. | Design §4.15 mentions globals; top level is the only place they can exist. |
| P20 | B | Global visibility in functions | A function body sees a global only if the global's declaration appears **textually before** the function declaration. Functions themselves are visible everywhere (L22). | C rule; avoids using storage before its declaration executes. |
| P21 | B | Array dimension expressions | Must have a type convertible to `int`. If every dimension is an integer constant expression (literals, unary/binary arithmetic on them, casts of them) it must be ≥ 1, else semantic error `INVALID_ARRAY_SIZE`. Non-constant dimensions (e.g. `bool prime[n + 1]`) are allowed; they are evaluated once, left-to-right, when the declaration executes, and a value < 1 is runtime error `invalid array size`. | Spec: "dimension is an expression"; existing sieve corpus depends on it. |
| P22 | B | Array storage | Every array (local or global, constant or not) is **zero-filled** when its declaration executes (globals: at program start for constant dims, at declaration execution for non-constant). Small constant-size local arrays (≤ `FRAME_ARRAY_LIMIT`) live in the stack frame; every other local array is heap-allocated by the runtime (`dv_rt_newarray`, `calloc`) and **freed (`dv_rt_freearray`) on every exit path of its scope** (fallthrough; `aapu`/`saagu` for scopes inside the target loop; `ivvu` for all function scopes, after the return value is evaluated), innermost scope first. Array parameters are views and are never freed by the callee. Global runtime-sized arrays are freed at the end of `$entry`, which then calls `dv_rt_shutdown` (prints `devara-rt: live=<n>` to stderr when `DEVARA_RT_STATS=1`). Zero padham = empty string. **Padham ownership (reference counting):** every runtime operation that produces a padham (concat, `char→padham`, line input) and every call returns an *owned* (+1) reference; variables, parameters and array elements are *borrowed* when read (a load from global/array memory in a statement that can run a user call is retained into an owned temporary so a callee cannot free it underneath). Storing into a variable, element or global takes ownership (retain if borrowed, as is if an owned temporary) and releases the old value; an owned temporary is released right after its last consuming use (output, compare, `podavu`, index, call argument, discarded call result, concat operand). Call arguments are borrowed by the callee, except that a padham parameter the body assigns to is retained on entry and released on exit. `ivvu` evaluates the value, retains it if borrowed, then runs the cleanups. At scope exit padham locals are released and every element of a padham array declared in the scope is released (`dv_rt_release_elems` / `dv_rt_freearray_str`); globals are released at the end of `$entry`. `dv_rt_retain/release/newarray/freearray*` are side-effecting in the IR effect model (`compiler/ir/runtime.py: MEMORY_EFFECTS`, never `PURE`), so the optimizer neither removes nor moves them. The runtime counts live arrays + strings (`DEVARA_RT_STATS=1` → `devara-rt: live=<n>` at normal exit; `tests/integration/test_leaks.py`, `test_corpus_leaks.py`, `test_sanitizers.py`). | Deterministic, simple; no cycles are possible, so reference counting is complete. |
| P23 | I | Definite initialization for arrays | Arrays are exempt from definite-initialization checking (elements are zero-filled by P22). Scalar locals (incl. `padham`) are checked path-sensitively. | Element-wise static tracking (§4.15 "where necessary") is undecidable in general; zero-fill makes reads defined. |
| P24 | B | Definite-init algorithm | Javac-style forward "definitely assigned" analysis over the typed tree: `if` = intersection of branches (missing else = state after condition); loops: state after loop = state after condition (body may run 0 times), except a `while` whose condition is the literal `nijam` or a non-zero int literal: after-state = intersection over its `aapu`s (⊤ if none = unreachable). `aapu/saagu/ivvu` make the remainder unreachable (⊤). Reads in unreachable code are not reported. Assignment, input, `tho modhalu`, for-declaration initializer, range variable, and parameters initialize. Globals are always initialized. | Standard technique. |
| P25 | B | Return-path analysis (L26) | A statement list *completes normally* unless some statement cannot complete: `ivvu`; `if` with else where both branches cannot complete; `while` with constant-true condition (as in P24) and no `aapu` targeting it. Non-void function whose body can complete normally → `MISSING_RETURN`. Code after a non-completing statement is allowed (no diagnostic). | javac reachability rules; simple and conservative. |
| P26 | B | `void` functions | `e ivvu` inside a void function → `INVALID_RETURN`. A call to a void function is only valid as an expression statement; in any value context → `VOID_MISUSE`. `void` as variable/parameter/element/cast type → `VOID_MISUSE`. | L28; bare `ivvu` does not exist. |
| P27 | B | Conversions (D1–D9 concretized) | Arithmetic types: `bool`, `char`, `int`, `float`. **Implicit** conversion between any two arithmetic types (C++ standard conversions incl. narrowing): float→int truncates toward zero (NaN/out-of-range → `INT64_MIN`, the `cvttsd2si` result, documented); int→char keeps low 8 bits; anything→bool is `!= 0`; bool→int 0/1; char is **signed** (x86-64 SysV). `padham` converts implicitly only to `padham`. Arrays never convert except array→same-element-type array parameter (P29). **Explicit cast** `(T)e` allows everything implicit plus `char→padham` and `padham→char` (runtime error unless length is 1). All other casts → `INVALID_CONVERSION`. | L1, L11, D1–D10. |
| P28 | B | Operator typing | Usual arithmetic conversions: `bool/char` promote to `int`; if either operand is `float` → `float`, else `int`. `+ - * /`: arithmetic → promoted type; `padham + padham` → `padham` (only string `+`). `%`: both operands integral (bool/char/int) → `int`; float → `INVALID_OPERAND`. `< > <= >=`: arithmetic only → `bool`. `== !=`: arithmetic pair (promoted) or `padham` pair → `bool`. `&& \|\| !`: operands contextually converted to bool (arithmetic only) → `bool`. Unary `+ -`: arithmetic → promoted type. `padham` with any non-`+ == !=` operator, or mixed with a non-padham → `INVALID_OPERAND`. Conditions (if/while/pratisari): arithmetic type required. Integer `/` truncates toward zero; `%` takes the sign of the dividend; `INT64_MIN % -1` = 0 (not an error — L38 lists only the quotient). Float `/` by zero follows IEEE. | C++ semantics + frozen padham operation set L4. |
| P29 | B | Arrays in expressions | Arrays (full or partial) are valid only (a) as the base of further indexing, (b) as a call argument to an array parameter. Argument rule: the argument must be an array of rank 1 (after partial indexing) whose element type equals the parameter element type exactly. Using an array as an assignment target/source, in output/input, arithmetic, conditions, or return → `INVALID_OPERAND`/`TYPE_MISMATCH`. An array parameter `T a[]` has type "rank-1 array of T, unknown size". Indexing a padham yields an rvalue `char` (bounds-checked at runtime, P11); padham elements are not assignable/inputtable (`NOT_ASSIGNABLE`). | L25, L34, L7, L8. |
| P32 | I | Range-loop variable type | `int`. Start/end are converted to `int` by assignment conversion (non-arithmetic → error). | Only sensible C-like choice; step is integer `+1`. |
| P33 | I | Scopes | Global → function (parameters and the function's outermost block share **one** scope, C++ rule) → nested blocks. Range loop: a loop scope holding the variable; the body block is a nested scope. `pratisari`: loop scope holds a for-declaration-init variable; body nested. Shadowing allowed across scopes; same-scope redeclaration → `REDECLARATION`. | C++; L18, L19. |
| P34 | I | `for-tho-modhalu-init` / `for-assignment-init` target | Must resolve to an existing scalar (non-array) variable or parameter (L44/L45). | |
| P35 | M | `++`/`--` operand | `int`, `char`, `float` scalars or array elements of those types. `bool` → `INVALID_OPERAND` (C++17). | |
| P36 | I | Integer literals | Value must be ≤ `INT64_MAX` (all bases) else `LITERAL_OUT_OF_RANGE`. (`INT64_MIN` is written `-9223372036854775807 - 1`.) Char literal value = byte of the escape (signed char). | i64 type. |
| P37 | M | Symbol mangling | User functions → `dv_f_<name>`, globals → `dv_g_<name>`; runtime helpers `dv_rt_*`; generated entry `main`. | Avoids clashes with libc (`main`, `printf`...). |
| P38 | M | Deep recursion | Stack overflow is not a defined runtime error (OS terminates). Documented. | |
| P39 | M | `podavu` | Builtin `padham -> int`; argument converted by assignment rules (so only `padham` accepted). | §12.2. |
| P40 | M | Evaluation order details | Assignment: target address (indices) evaluated **before** the value; call arguments left-to-right; array declaration dims left-to-right; binary operands left then right. | L30/L31 + C++17 for `lo` is irrelevant; pick one and freeze it. |

Contradictions found: only **P13** (escape grammar text vs lexer deferral) — resolved in favour of the
explicit deferral. No BLOCKING contradiction remains; all BLOCKING gaps above are now decided.

---

## D. Architecture

```
source ──Lexer──▶ list[Token] ──Parser──▶ AST (syntax only)
      ──Sema──▶ TypedProgram (typed tree, explicit Convert nodes, resolved Symbols)
      ──IRGen──▶ IRModule (typed 3-address, non-SSA, CFG of basic blocks) ──Verifier
      ──Opt──▶ IRModule (verified)  ──Codegen──▶ x86-64 GNU asm (.intel_syntax noprefix)
      ──gcc (as+ld) + runtime/devara_rt.c──▶ ELF executable
```

Package layout (Python, no new runtime deps; `hypothesis` for tests only):

```
compiler/
  diagnostics.py     Span, Diagnostic(stage, category, message, span), DiagnosticError, ICE
  serialize.py       generic dataclass <-> JSON (tokens, AST, IR)
  lexer/             (kept) + categories
  ast/nodes.py       rewritten to design §3.5
  parser/parser.py   rewritten/modified recursive descent
  semantic/          types.py, symbols.py, typed.py (typed tree), checker.py, flow.py (init/return)
  ir/                ir.py (instructions, blocks), lower.py, verify.py, printer.py
  opt/               passes.py (const fold/prop, copy prop, int-only algebraic, branch simplify,
                     unreachable-block elim, DCE, redundant-convert elim)
  codegen/x86_64.py  IR -> asm (every virtual register gets a stack slot; rax/rcx/rdx/xmm0/xmm1 scratch)
  driver.py          stage orchestration, toolchain invocation
  cli.py             argument parsing
runtime/devara_rt.c  I/O, padham helpers, runtime errors, allocation
devara               executable wrapper: `python3 -m compiler.cli "$@"`
```

Code generation strategy (simplest correct ABI): every IR temporary/local/parameter has a fixed
`rbp`-relative stack slot; each instruction loads operands into scratch registers, computes, stores.
No register allocation (design §7.6 "linear scan is sufficient" — a stack-slot allocator is the
degenerate correct case; documented deviation). Calls: System V — first 6 integer-class args in
`rdi,rsi,rdx,rcx,r8,r9`, first 8 float args in `xmm0–7`, rest on stack right-to-left, `rsp` 16-byte
aligned at `call`, `al` = number of vector args for varargs runtime calls. Returns in `rax` / `xmm0`.
padham values are pointers to an immutable, reference-counted runtime object
`{int64 refcnt; int64 len; char bytes[len+1]}`; `NULL` means empty string. Literals are immortal
(`refcnt = -1`): the back end's `.rodata` constants have no header, so lowering turns each literal into
a global initialised once at the start of `$entry` by `dv_rt_strlit` and every use is a load of that
global (the empty string is a load of the never-written global `null.str`). Bools are bytes 0/1 widened to 64-bit slots; chars are signed
8-bit stored sign-extended in 64-bit slots. Arrays: element size 8 bytes for all element types
(simplicity; documented), row-major; array parameters pass the base address; partial indexing yields
an address.

## E. CLI contract (black-box interface used by the tester)

`./devara <command> [options] <file>` (equivalently `python3 -m compiler.cli ...`).

| Command | Input | Output (stdout) |
|---|---|---|
| `lex FILE` | source, or nothing else | one token per line: `LINE:COL TYPE 'lexeme'`; `--json` → JSON token list |
| `parse FILE` | source, or token JSON (`*.json` from `lex --json`) | indented AST tree; `--json` → AST JSON |
| `sema FILE` | source, or AST JSON | typed tree with types, conversions, symbol table |
| `ir FILE` | source | textual IR (unoptimized); `--json` → IR JSON |
| `opt FILE` | source, or IR JSON | optimized textual IR; `--json` |
| `asm FILE` | source, or IR JSON | x86-64 assembly (`-O0` disables optimization) |
| `build FILE -o OUT` | source, or `.s` file | executable `OUT` (default: file stem) |
| `run FILE` | source | builds into a temp dir and executes; stdin/stdout/exit status pass through |

Global options: `-O0` / `-O1` (default `-O1`) for `asm|build|run`.

**Exit status of the compiler:** `0` success; `1` user-program error (lexical/syntax/semantic);
`2` usage / I/O error; `3` internal compiler error (uncaught exception, IR verifier failure,
assembler/linker failure of generated code). On `run`, the program's own exit status is returned
(runtime error = 1, P11).

**Diagnostic format (stderr, one per line):**
`FILE:LINE:COL: <stage> error [<CATEGORY>]: <message>` with `<stage>` ∈ `lexical|syntax|semantic`.
ICE: `FILE: internal compiler error: <message>` (exit 3).

Categories:
* lexical: `INVALID_CHARACTER, UNTERMINATED_STRING, UNTERMINATED_CHAR, INVALID_ESCAPE, INVALID_CHAR_LITERAL, INVALID_NUMBER`
* syntax (design §3.6, closed): `UNEXPECTED_TOKEN, UNEXPECTED_EOF, MISSING_TOKEN, INVALID_EXPRESSION, INVALID_STATEMENT, INVALID_DECLARATION`
* semantic: `UNDECLARED, REDECLARATION, TYPE_MISMATCH, INVALID_CONVERSION, INVALID_OPERAND, NOT_ASSIGNABLE, NOT_CALLABLE, NOT_INDEXABLE, TOO_MANY_INDICES, ARGUMENT_COUNT, INVALID_RETURN, MISSING_RETURN, BREAK_OUTSIDE_LOOP, CONTINUE_OUTSIDE_LOOP, UNINITIALIZED, VOID_MISUSE, INVALID_ARRAY_SIZE, LITERAL_OUT_OF_RANGE, INVALID_CONDITION`

Stage failure stops the pipeline: lexical errors → no parse; syntax errors → no sema; etc.

## F. Stage contracts

**Lexer.** In: `str` source. Out: `list[Token]` ending with exactly one `EOF`; every token has
`line ≥ 1, column ≥ 1`, lexeme equal to the source slice, half-open end = `column + len(lexeme)`
(tokens never span lines). Errors: list of lexical `Diagnostic`s; tokenization continues after an
error; deterministic. If any error exists the token list must not be passed on.

**Parser.** In: error-free token list. Out: `Program` satisfying design §3.5.12 invariants 1–8 with
half-open spans, or ≥ 1 syntax diagnostic (then no AST is returned to later stages). Recovery per §3.7;
every recovery loop consumes a token or stops at a sync token (termination guaranteed). Never throws
on any token list (any exception = ICE).

**Semantic analysis.** In: `Program`. Out: `TypedProgram`: every expression node has a semantic type;
every implicit conversion is an explicit `Convert` node; every identifier refers to a `Symbol`
(kind, type, scope depth, unique id); every function has a signature; globals list; entry statements
list; loop statements know their `aapu/saagu` targets. Guarantees design §3.2 + P19–P40. Errors:
semantic diagnostics (collect all, sorted by position). Does not modify the AST.

**IR generation.** In: `TypedProgram`. Out: `IRModule` {globals, string constants, functions incl.
synthetic `__entry`}; each function = params, locals (with types/sizes), ordered basic blocks each
ending in exactly one terminator (`jump`, `branch`, `ret`). Instructions per design §5.7 plus
runtime-call instructions; all operands typed (`i64, f64, bool, char, str, addr, void`). Every source
construct has a lowering (table in tests). Verifier (§5.26) must pass; failure = ICE.

**Optimizer.** In/Out: verified `IRModule`. Must preserve observable behavior (output, input
consumption, exit status, runtime errors). Float algebraic simplifications are forbidden (L49). Never
removes calls, I/O, stores, or potentially-trapping division. Verifier re-run after every pass.

**Code generator.** In: verified `IRModule`. Out: assembly text that `gcc -c` accepts; System V ABI;
16-byte stack alignment at every call. Output assembly must assemble and link (§7.22).

**Driver/linker.** `gcc -no-pie prog.s runtime/devara_rt.c -o prog -lm` (or a cached prebuilt
runtime object). Toolchain failure on generated code = ICE.

## G. Test strategy

| Layer | Location | Owner | Content |
|---|---|---|---|
| Unit | `tests/unit/` | Developer | lexer, parser productions, AST invariants, types/conversions table, symbol table, flow analysis, IR lowering per construct, verifier, each opt pass, codegen helpers, runtime helpers (via tiny programs) |
| Integration | `tests/integration/` | Developer | stage boundary round-trips: `lex --json` → `parse`; `parse --json` → `sema`; `ir --json` → `asm`; `asm` → `build`; O0 vs O1 output equality |
| Validation (spec-derived, black-box via CLI) | `tests/validation/` | **Tester** | per grammar production positive/negative/boundary; per semantic rule accept/reject with category; runtime semantics (wrap, division, conversions, I/O formats P1–P11) |
| Property / fuzz | `tests/property/` | **Tester** | hypothesis: random token soup → lexer/parser never crash/hang; generated well-typed programs → compiled output == reference interpreter output |
| Reference interpreter | `tests/reference/` | **Tester** | independent tree-walking interpreter over the typed tree, written from the spec (differential oracle for IR/opt/codegen/runtime) |
| Corpus (E2E) | `tests/corpus/<category>/NNN_name.tel` + `.in` + `.out` (+ `.exit` if non-zero) | **Tester** | ≥ 100 DSA programs; expected output computed independently (hand/Python), **never** copied from compiler output |
| Regression | `tests/regression/` | Both | one test per fixed bug (`test_bug_<id>_<slug>`) |

Corpus metadata header (first lines of each program):
```
# ID: DSA-037
# Category: sorting
# Algorithm: merge sort
# Exercises: functions, arrays, recursion, while, if/else, integer arithmetic, output
# Difficulty: medium
# Expected: sorted array printed one element per line
```

Markers: `@pytest.mark.slow` for corpus/property/E2E. Fast suite: `pytest -m "not slow"`; full: `pytest`.
`scripts/run_corpus.py` prints the §17 statistics table (total/compiled/failed/executed/runtime-failed/
incorrect/timeout) and writes `build/corpus_report.json`. Timeout per program: 10 s.

## H. Phases and gates

| Phase | Owner | Deliverable | Gate (all must hold, verified by running the commands) |
|---|---|---|---|
| 0 | Design | this document | committed |
| 1 | Dev | `diagnostics.py`, `serialize.py`, CLI skeleton, `devara` wrapper, test layout, markers, `scripts/run_corpus.py`, CI workflow, devcontainer | `pytest -m "not slow"` green; `./devara lex examples/example.tel` works |
| 2 | Dev | lexer categories, CRLF, token end | lexer unit + validation tests green |
| 3 | Dev | AST rewrite, parser fixes, recovery, diagnostics; old parser tests migrated | parser unit tests green; AST invariant checker passes on all corpus files; negative tests green |
| 4 | Dev | semantic analysis | semantic unit + tester's semantic validation green |
| 5 | Dev | IR + verifier + optimizer | lowering tests green; verifier passes on all corpus programs at O0 and O1 |
| 6 | Dev | codegen + runtime | runtime/codegen tests green; all programs assemble+link |
| 7 | Dev | `build`/`run` end-to-end | E2E tests green |
| 8 | Tester | full validation run, report | 100% corpus correct, all tests pass, no unexplained skips |

Final gate: `pytest` (everything, incl. slow) green + `scripts/run_corpus.py` reports all programs
correct + `docs/FINAL_VALIDATION_REPORT.md` written from actual command output.

## I. Agent protocol

* **Developer agent** (Sonnet, cloud session) owns `compiler/`, `runtime/`, `devara`, `scripts/`,
  `tests/unit`, `tests/integration`, `tests/regression`, CI/devcontainer. Commits per phase on the
  development branch with conventional messages; pushes after each green gate.
* **Tester agent** (Sonnet, separate cloud session, separate branch) owns `tests/validation`,
  `tests/property`, `tests/reference`, `tests/corpus`. Never edits `compiler/`. Tests the compiler
  only through the CLI (§E) and the typed-tree API for the reference interpreter. Reports failures as
  `docs/validation/FAILURES.md` entries (minimal reproducer, expected per spec section/P-id, actual).
* Both: if the spec/this plan is contradictory or silent, **stop and report** under
  `docs/validation/OPEN_QUESTIONS.md`; do not invent language rules. Never mark a failing test
  skip/xfail to get green unless it is listed with a reason in the final report.
* No claim of PASS without the command output that shows it.

## J. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Stack-slot codegen slow for heavy corpus programs | Low | 10 s timeout ample; optimize only if measured |
| Python recursion limit on deep expressions | Medium | `sys.setrecursionlimit` raised in CLI; fuzz bound documented |
| Definite-init false positives in corpus | Medium | P24 precisely specified; tester covers both directions |
| Golden outputs wrong (oracle error) | Medium | expected outputs from independent Python + reference interpreter differential |
| Leaked VLA heap memory (P22) | Low | freed at scope exit; `tests/integration/test_leaks.py` asserts `live=0` |
| Two agents on one branch conflict | Medium | separate branches; tester touches disjoint paths; design layer merges |

## K. Cloud environment

No GPU needed; a standard Claude Code cloud container (or any x86-64 Linux with Python ≥ 3.11 and
gcc) suffices. Reproducible setup: `.devcontainer/devcontainer.json` (Python 3.11 image + gcc) and
`scripts/setup.sh` (`pip install -r requirements-dev.txt`). Commands:

```
git clone … && cd devara
./scripts/setup.sh
pytest -m "not slow"          # fast suite
pytest                        # full suite
python3 scripts/run_corpus.py # corpus statistics
./devara run tests/corpus/sorting/001_bubble_sort.tel < input.txt
```

---

## L. Design-authority rulings on open questions (round 1)

Binding from now on. These rulings refine §C; they do not change any frozen L-decision.

| Ref | Ruling |
|---|---|
| OQ1–OQ11 (developer) | **Accepted as written** and promoted to rules: array used as a condition → `INVALID_OPERAND`; implicit conversion failure → `TYPE_MISMATCH` and explicit-cast failure → `INVALID_CONVERSION`; sources are read as bytes decoded as latin-1; mixed constant/non-constant dimensions are checked at runtime; a function name used as a value → `INVALID_OPERAND`; the `MISSING_RETURN` span is the function name; an identity cast is legal; a float literal that overflows becomes `inf`; recovery never consumes a block-closing `}`; a recovery loop that makes no progress force-consumes one token; an initialised declaration or a nested function → `INVALID_DECLARATION`. |
| Q-001 | Unary `-` on `INT64_MIN` **wraps** to `INT64_MIN` (two's-complement `0 - x`, consistent with L37). Not an error. |
| Q-002 | **Point-of-declaration rule (C++).** A name is visible from its declaration to the end of its scope. A use before a later same-scope declaration resolves to the nearest enclosing declaration visible at that point, otherwise `UNDECLARED`. The later declaration is legal if it does not redeclare a name already declared in the same scope. |
| Q-003 | A dimension whose folding would trap (`1/0`, `INT64_MIN / -1`, `x % 0`) is **not a constant expression** (C++ rule). It is evaluated at runtime and raises the runtime error (`division by zero`, etc.). |
| Q-004 | NaN output is exactly what glibc `printf("%g")` prints (`nan` or `-nan` depending on the sign bit). P3's `-nan` was only an example. Tests should avoid depending on the NaN sign. |
| Q-005 | float→bool = `f != 0.0` (NaN → `nijam`). float→char = float→int (P27, `cvttsd2si`) followed by int→char (low 8 bits, signed). The same composition applies to explicit casts. |
| Q-006 | No special rule: the ordinary P24 analysis applies. `pratisari (int i; nijam; i lo 0 pettu) { aapu }` is accepted. Any read of `i` that is not definitely preceded by an assignment is `UNINITIALIZED` (the body runs before the first update). |
| Q-007 | **Confirmed:** after each body execution the loop variable becomes (its current value) + 1. Modifications made in the body therefore affect the iteration. The end bound is still evaluated only once (L17). |
| Q-008 | **Confirmed:** `padham a[]` parameters and `padham` arrays are legal. |
| Q-009 | Diagnostics are sorted by (line, column, category). Tests may compare either the set of categories or the ordered list. |

## M. Design-authority rulings (round 2)

| Ref | Ruling |
|---|---|
| F-001 | Confirmed bug. Failing to write the requested output path (missing directory, path is a directory, no permission) is an I/O error: exit **2** with `FILE: error: cannot write output '<path>': <reason>`. It is not an ICE. Check this before invoking the toolchain. |
| Q-010 | **Strict tokens** (the current behaviour): the whole whitespace-delimited token must match the type's form (P7/P8). `3.5` or `12abc` read as `int`, or `1x` read as `float`/`bool`, is runtime error `invalid input`. There is no C++-style prefix parsing. |
| Q-011 | `0` followed by decimal digits that include `8` or `9` (`09`, `078`) is lexical error **`INVALID_NUMBER`** (the current behaviour). P15 (two tokens) applies only to a digit sequence followed by a letter or underscore. |
| Q-012 | A user-supplied `.s` file that the assembler/linker rejects is a user-input error: exit **1** with `FILE: assembler error: <tool output>`. Exit 3 stays reserved for generated code. |
| N-001 | Exceeding the nesting depth is an implementation limit, not a compiler bug: exit **1** with `FILE:LINE:COL: syntax error [INVALID_EXPRESSION]: nesting too deep (implementation limit)` (or the position of the last token reached), and no ICE. The supported depth must stay ≥ 1000. |
| N-002 | Performance: compile time for long left-associative chains should be roughly linear. Profile it, and fix it if the cause is cheap to remove (e.g. repeated list copies or recursion-limit resets). Low priority; correctness first. |
