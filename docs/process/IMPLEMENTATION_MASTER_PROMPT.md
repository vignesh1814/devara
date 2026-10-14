# Devara Compiler — Alignment & Full Implementation (Phased, Gated)

## Source-of-truth documents (pin exact versions before starting)

- `DEVARA_LANGUAGE_SPEC.md` — canonical language spec (confirm the version header; if it still reads an older number than the filename/other documents claim, fix the header first and record the correction — do not proceed on an ambiguous version)
- `DEVARA_STAGE_2_DESIGN_v1_0_FINAL.md` — Stage 2 parser/AST design
- `DEVARA_REMAINING_STAGES_THEORETICAL_DESIGN_v7.md` — Stages 3–6 design
- Existing Stage 1 (lexer) and Stage 2 (parser) implementation and test suites

If any of these disagree with each other on a point that affects what you are about to implement, **stop and report the contradiction** rather than picking a side. Use exactly this phrasing pattern, per the design doc's own Implementation Boundary section:

> "The design specifies X, but [the other document / the current implementation] requires Y."

---

## Ground rules — apply in every phase below

1. **You are an implementation agent, not a design agent.** Every decision needed to write code must already exist in the source-of-truth documents. If you reach a point where you would have to invent, guess, or pick between equally-plausible interpretations to proceed, stop and report it as an open question — do not resolve it yourself, and do not proceed past it by choosing the "obviously correct" answer.
2. **Spec/design is the oracle for expected test results.** Derive every expected output independently from the documents before running any code. Never generate an "expected" value by running your own implementation and recording what it produced.
3. **No phase begins until the previous phase's verification gate has explicitly passed.** Do not begin Phase N+1 work — not even reading ahead to plan it — until Phase N's report has been produced and reviewed.
4. **Every verification report must be evidence-based**: quoted code (file:line), pasted command output, pasted test results — never a summary or a bare "PASS"/"looks correct" with nothing backing it. A finding without evidence attached doesn't count.
5. **Preserve all existing tests.** Integrate new tests alongside them; do not delete or silently rewrite an existing test to make it pass — if an existing test conflicts with the current spec, flag it explicitly and only change it if the spec is clearly authoritative.
6. **Classify every test failure before touching code**: (A) implementation defect — fix it; (B) incorrect expected value in the test — fix the test; (C) spec/design ambiguity — stop, report, do not resolve unilaterally; (D) existing test conflicts with current spec — flag, fix only if spec is clearly authoritative.
7. **Exhaustive test corpus discipline, every phase**: "exhaustive" means full coverage of the finite rule space defined by the spec/design for that phase, plus its meaningful boundary conditions — not infinite-input enumeration. Wherever you use bounded generation (e.g., all short programs over some construct), state the exact bound and alphabet used. Never claim a bounded sweep proves arbitrary-input correctness.
8. **Never silently expand or narrow the language.** If a construct's behavior isn't nailed down by the documents, that's a Ground Rule 1 stop, not an invitation to pick the conventional-language behavior (e.g., don't assume C-style semantics anywhere the Devara documents are silent).

---

## Phase-gate report format (produce this at the end of every phase, no exceptions)

```
### Phase N — [name] — Verification Report

## Scope covered
[what was implemented, referencing exact design-doc section numbers]

## Test corpus
| Category | Cases | Boundary cases | Invalid/error cases | Status |
[one row per category from that phase's corpus list below]

## Bounded exhaustive domains
[each domain used, with its explicit bound/alphabet stated]

## Test results
[exact totals: run / passed / failed / errored / skipped — pasted, not summarized]

## Failures
[each one, classified A/B/C/D, with evidence]

## Open questions raised to the design owner
[anything where Ground Rule 1 triggered — or "None"]

## Verdict
PASS — Phase N complete, ready to proceed to Phase N+1
FIX — Phase N has unresolved issues, do not proceed
BLOCKED — an open design question must be answered before Phase N can complete
```

Do not issue `PASS` while any `BLOCKED` or unresolved `C`/`D` classification remains outstanding.

---

## Phase 0 — Align Stage 1 & Stage 2 with the current spec/design

### What actually needs to change here

Cross-checking the current spec/design against the existing Stage 1/2 implementation, only one syntactic change is in scope for this phase: the C-style explicit cast `(type) expression`, added to the grammar as:

```
unary-expression =
    cast-expression
  | unary-operator, unary-expression
  | primary-expression ;

cast-expression =
    "(", type, ")", unary-expression ;
```

and the corresponding AST node from the Stage 3–6 design doc §3.5.11:

```
CastExpression
 ├── target_type: TypeSyntax
 └── expression: Expression
```

Everything else that changed recently in the design documents (`podavu` symbol resolution, array-index conversion rules, the float algebraic-optimization baseline) is **Stage 3/Stage 5 semantic territory with no Stage 1 or Stage 2 impact** — `podavu` is an ordinary identifier + call, already representable by the existing `FunctionCall` grammar/AST with no new syntax; array-index and float-optimization rules don't touch lexing or parsing at all. Do not modify the lexer or parser for these — confirm and record that no change is needed, rather than silently skipping the check.

### Tasks

1. **Lexer (Stage 1):** confirm no new tokens are required for the cast production (it reuses existing `(`, `)`, and the existing `type` keyword set). Run the full existing lexical test suite unchanged. Record confirmation that Stage 1 requires zero code changes for this revision.
2. **Parser (Stage 2):**
   - Add the `cast-expression` production to the recursive-descent parser at the `unary-expression` level, exactly as specified — this must be tried before falling through to unary-operator/primary-expression, per the grammar's alternation order and standard longest-match resolution for a leading `(` that could start either a cast or a parenthesized grouped expression. If your parsing strategy needs a disambiguation rule (e.g., lookahead to check whether `(` is followed by a `type` keyword then `)`), that rule must follow directly from the grammar as written — if it doesn't, stop and report rather than inventing a disambiguation heuristic.
   - Add the `CastExpression` AST node with exactly the two fields specified (`target_type: TypeSyntax`, `expression: Expression`), with the same half-open `Span` metadata every other node carries (§3.5.1).
   - Update the diagnostic/recovery paths only if the new production changes any `FIRST` set used in panic-mode recovery (§3.7 of the Stage 3–6 design doc defines the frozen `FIRST(statement)`/`FIRST(declaration)` sets used by Stage-2-adjacent recovery — check whether `LPAREN`-initiated cast expressions change any recovery boundary; if the existing `FIRST` sets already include `LPAREN`, no change should be needed, but verify rather than assume).
3. **Documentation sync:** update `DEVARA_STAGE_2_DESIGN_v1_0_FINAL.md` itself to include the `cast-expression`/`CastExpression` production (it currently only exists in the Stage 3–6 document's §3.5, which stands in for the Stage 2 contract but should be reflected in the Stage 2 document proper). Do not use this as an opportunity to change anything else in that document.

### Phase 0 test corpus

| Category | What to cover |
|---|---|
| Cast parses as expression, not statement | `(int) x`, `(float) x`, `(char) x`, `(bool) x`, `(padham) x`, cast used as a sub-expression (`(int) x + 1`), cast as a function argument, cast as an array index, cast as an assignment's right-hand side |
| Cast vs. grouped-expression disambiguation | `(x)` (plain grouping, not a cast — `x` is not a type keyword), `(int)(x)` (cast of a grouped expression), nested casts `(int)(float) x` |
| Cast precedence | Confirm cast binds at the unary level: `(int) x + 1` parses as `((int) x) + 1`, not `(int) (x + 1)` |
| Cast AST shape | For each cast, assert the resulting node has exactly `target_type` and `expression`, with correct span covering from `(` through the end of the cast's operand |
| Every primitive type as cast target | `int`, `float`, `bool`, `char`, `padham`, and confirm `void` as a cast target either parses (deferred to Stage 3 semantic rejection) or is handled exactly as the grammar dictates — do not have the parser itself reject `(void) x` unless the grammar says casts are restricted to non-void types |
| Malformed casts | `(int` (unterminated), `(nonexistenttype) x` (not a `type` keyword — must not be misparsed as a cast), `() x` (empty parens) |
| Regression | Full existing Stage 1 + Stage 2 test suites, unchanged, all still passing |

### Phase 0 gate

Produce the Phase-gate report. Do not proceed to Phase 1 until it's `PASS`.

---

## Phase 1 — Stage 3: Semantic Analysis

Implement per Stages 3–6 design doc §4 in full: symbol tables (§4.3), scope management (§4.4), function collection (§4.5), the type system (§4.6–4.7), type checking (§4.8), the conversion model (§4.9, "literal C++ conversion system" for D1–D9, plus the D10 cast semantics), condition semantics (§4.10), assignment analysis (§4.11), expression analysis (§4.12), array semantic analysis including the index-conversion rule with **no hard-coded type whitelist** (§4.13), `padham` semantics including the `podavu` predeclared-symbol resolution rule exactly as specified (§4.14), initialization analysis (§4.15), function analysis and return-path checking (§4.16), loop context for `aapu`/`saagu` (§4.17), range-loop semantics (§4.18), three-part-loop initializer semantics for all three `for-init` variants (§4.19), and structured semantic diagnostics (§4.20).

### Phase 1 test corpus

| Category | Cases |
|---|---|
| Symbol resolution | resolved identifiers, undeclared-identifier errors, forward function references, mutual recursion |
| Scope | shadowing at each nesting level, same-scope redeclaration errors, range-loop variable scope boundaries, `for-declaration-init` loop-local scope |
| Type checking | every arithmetic/relational/equality/logical operator across every valid type-pair combination the conversion model permits, and rejections for combinations it doesn't |
| Conversions | every D1–D9 conversion category exercised in both a succeeding and a failing direction; explicit cast (D10) for every primitive-to-primitive pair the C++ model permits, and rejection where it doesn't |
| Assignment | valid target/value pairs, invalid target (non-assignable expression), conversion failures |
| Function calls | correct arity/types, wrong arity, wrong argument types, return-type checking, void-function-call-as-expression rejection |
| Array semantics | partial indexing at every dimension depth, index-type acceptance/rejection driven purely by the conversion model (int/char/bool accepted via conversion, `float`/`padham`/`void` rejected — verify this falls out of the general model, don't hard-code the expected accept/reject list from anywhere except re-deriving it from the conversion rules), dimension-count-exceeded errors |
| `padham`/`podavu` | concatenation, equality, indexing-returns-char, `podavu` builtin call and its signature check, user redeclaration of `podavu` at global scope (must error), user shadowing of `podavu` in an inner scope (must succeed and resolve to the shadow), `char↔padham` explicit conversion both directions including the "exactly one character" runtime-failure case, rejection of implicit numeric↔padham |
| Initialization | read-before-init errors on every reachable-path shape (straight-line, if/else where only one branch initializes, loop bodies), global zero-initialization for every primitive type |
| Functions | non-void missing-return-on-some-path errors, void completing without return, recursion, mutual recursion |
| Loop context | `aapu`/`saagu` inside each loop kind, `aapu`/`saagu` outside any loop (error), nested loops targeting the correct nearest enclosing loop |
| Range/for-loop semantics | inclusive-start/exclusive-end boundary cases (start==end, start>end → zero iterations), all three `for-init` variants' declare-vs-assign distinction |
| Diagnostics | one example of every listed semantic diagnostic category, each with correct source span |

### Phase 1 gate

Same report format. `PASS` required before Phase 2.

---

## Phase 2 — Stage 4: Intermediate Representation

Implement per design doc §5: three-address IR (§5.4), the frozen IR type set and operand kinds (§5.5–5.6), the core instruction set (§5.7), basic blocks and CFG construction (§5.8–5.9), expression/evaluation-order translation (§5.10–5.11), conversion translation (§5.12), assignment and array-address translation (§5.13–5.15), conditional/short-circuit translation (§5.16–5.17), each control construct's lowering (`if` §5.18, `while` §5.19, range-loop §5.20, three-part-loop §5.21), function translation and calls (§5.22), return translation respecting the "no bare `ivvu`" source rule while permitting an internal parameterless terminator for void completion (§5.23), the top-level executable entry region (§5.24), I/O translation with side-effect preservation (§5.25), and the IR verifier (§5.26).

### Phase 2 test corpus

| Category | Cases |
|---|---|
| Expression lowering | precedence-correct three-address decomposition for each operator, nested expressions, mixed-type expressions with explicit conversion IR ops |
| Evaluation order | `f() + g()` and every binary op with both operands as calls — assert generated IR calls left operand's call before right operand's |
| Short-circuit | `&&`/`||` branch structure — assert right operand's block is unreachable when left is statically false/true respectively (structurally, not by constant-folding — that's Stage 5) |
| Array addressing | 1D/2D/3D address calculation against the row-major formula, partial-indexing reference (no-copy) cases |
| Control flow | CFG shape for every construct in §5.18–5.21 — block count, edge count, terminator kind, verify `aapu`/`saagu` target the documented blocks exactly |
| Function calls | argument IR ordering, return-value capture, void call as a statement |
| Top-level region | interleaved top-level declarations and statements lowered into the generated entry region in source order |
| I/O | input/output IR ops present and never eliminated even when their result is unused |
| IR verification | a deliberately malformed IR fragment for each verifier check in §5.26 (bad operand, type mismatch, invalid branch target, bad terminator, wrong call arity, bad return type, invalid memory operand) — confirm the verifier actually rejects each one |

### Phase 2 gate

Same format. `PASS` required before Phase 3.

---

## Phase 3 — Stage 5: Optimization

Implement per design doc §6, exactly the pipeline in §6.2: constant folding, constant propagation, copy propagation, algebraic simplification, branch simplification, unreachable-block elimination, dead-code elimination, redundant-conversion elimination — each with its stated safety constraints (§6.3–6.10), evaluation-order preservation (§6.11), short-circuit preservation (§6.12), runtime-error preservation (§6.13), and — critically — the **empty** floating-point algebraic-simplification baseline from §6.14: implement zero float-involving algebraic identities; do not add any of `x+0.0→x`, `x-0.0→x`, `x*1.0→x`, `x/1.0→x`, `x*0.0→0.0` even though they're valid for integers, and do not generalize the integer versions of these rules to float operands anywhere in the pass.

### Phase 3 test corpus

| Category | Cases |
|---|---|
| Constant folding | every foldable operator with constant operands, non-foldable cases left alone |
| Constant/copy propagation | straightforward chains, propagation blocked by an intervening redefinition |
| Algebraic simplification — integer only | `x+0`, `x*1` and similar, confirmed applied only when operand types are statically non-float |
| Algebraic simplification — float exclusion | for every identity listed in §6.14, construct a float-typed IR fragment and assert the optimizer leaves it untouched; include the `-0.0 + 0.0` case specifically, comparing optimized vs. unoptimized execution to confirm the sign bit is preserved unsimplified |
| Branch/unreachable/dead-code elimination | each with a case that's eligible and a near-miss case that must NOT be eliminated (has a side effect, is a required runtime error, is reachable) |
| Evaluation-order preservation | `f() + g()`-shaped IR before/after optimization — confirm call order is byte-identical |
| Short-circuit preservation | confirm optimization never introduces evaluation of the right operand when the left statically determines the result via a non-constant-fold path |
| Runtime-error preservation | a division-by-zero (or other required-error) computation with unused result — confirm it survives dead-code elimination |
| End-to-end equivalence | for a representative program set, compare observable behavior (output, exit status) of the unoptimized vs. optimized IR when both are executed — must be identical |

### Phase 3 gate

Same format. `PASS` required before Phase 4.

---

## Phase 4 — Stage 6: x86-64 Code Generation

Implement per design doc §7: machine-level lowering and instruction selection (§7.3–7.4), register classes (§7.5), register allocation with spilling (§7.6–7.7), stack frame layout and function entry/exit (§7.8–7.9), System V AMD64 ABI conformance (§7.10), integer operations including the required divide-by-zero/remainder/overflow behavior (§7.11), floating-point via SSE (§7.12), boolean/comparison lowering (§7.13–7.14), array addressing without bounds checks (§7.15), the `padham` runtime contract (§7.16), function calls and return-value ABI placement (§7.17–7.18), runtime support (§7.19), program entry (§7.20), and assembly emission/verification (§7.21–7.22) — **assembly must actually assemble, link, and run**, not merely be emitted as text.

### Phase 4 test corpus

| Category | Cases |
|---|---|
| Per-instruction correctness | every arithmetic/relational/equality/logical operator, each primitive type, checked by actually executing the compiled binary and checking output/exit code — not by inspecting emitted assembly text |
| ABI conformance | integer args in the correct registers, float args in SSE registers, mixed argument lists, argument-count exceeding register capacity (stack-passed args), return value placement for each type including `void` |
| Register allocation/spilling | a program with more simultaneously-live values than available registers — confirm correct behavior under forced spilling |
| Runtime errors | divide-by-zero, remainder-by-zero, `INT64_MIN / -1`, confirmed to produce the documented runtime diagnostic and non-zero exit status, not a silent wrong answer or a crash with no diagnostic |
| Overflow | `+`/`-`/`*` wraparound at the signed-64-bit boundary, confirmed against the exact two's-complement wrap value |
| Arrays | multi-dimensional address calculation executed and checked against expected element values; partial-indexing reference passed into further indexing |
| `padham` runtime | concatenation, equality, indexing, `podavu`, line input, output — each executed end-to-end |
| Control flow | every loop/conditional construct executed with inputs driving every branch |
| Program entry | interleaved top-level declarations/statements executed in source order; confirm user functions are not auto-invoked |
| Full assemble/link/run | every test in this corpus goes through the complete `assembler → object file → linker → executable → run` path — a test that only checks emitted assembly text does not count as covering this category |

### Phase 4 gate

Same format. `PASS` required before Phase 5.

---

## Phase 5 — End-to-End Integration & Full Regression

1. Run the complete pipeline (source → tokens → AST → semantic representation → IR → optimized IR → assembly → executable) on every existing example/DSA program in the repository, plus a representative program exercising every language construct in combination (not just in isolation, as the per-phase corpora did).
2. Run the full existing test suite across all stages together — confirm nothing from an earlier phase regressed.
3. Confirm every §9 cross-stage invariant from the design doc holds in the integrated pipeline (name resolution complete by Stage 4, types/conversions known by Stage 4, evaluation order survives to codegen, control flow is explicit CFG before optimization, memory operations are explicit, optimization changes nothing observable, the backend never reinterprets source semantics).
4. Confirm §10 error propagation: a lexical error never gets reported as a parser error, a parser error never gets reported as semantic, and so on — each stage's diagnostics stay in that stage's category.

### Phase 5 gate

Same report format, plus a final line:

```
### Devara Compiler — Overall Status
READY — full pipeline implemented, verified end-to-end, matches frozen design in every phase
NOT READY — [list exactly which phase(s) and which specific issues]
```
