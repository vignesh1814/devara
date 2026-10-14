# Compiler Reconstruction & Implementation — Master Execution Prompt

> Governing instructions supplied by the project owner (2026-10-05). This
> supersedes `IMPLEMENTATION_MASTER_PROMPT.md` where they differ; that
> older file's implementation-agent ground rules (stop-and-report on
> contradictions, spec as test oracle, gated phases) remain compatible.

You are responsible for taking the existing **Devara compiler** from its current partially implemented / partially incorrect state to a **working, staged, end-to-end compiler**.

This is an academic compiler project and also a hobby project. The goal is **not perfection or industrial-scale compiler engineering**. The goal is:

> **A genuinely functional compiler, implemented quickly but with academically rigorous engineering, clear stage boundaries, strong tests, reproducible validation, and an auditable development history.**

The repository already contains substantial documentation. **The documentation/specification is the source of truth. Some existing implementation was written against an older or incorrect specification. Do not assume existing code is correct simply because it exists.**

---

# 0. NON-NEGOTIABLE OPERATING PRINCIPLES

## 0.1 Read before changing

Before modifying anything:

1. Inspect the entire repository structure.
2. Read all relevant documentation.
3. Read the authoritative language specification.
4. Read the existing compiler implementation.
5. Read the existing tests.
6. Identify the implemented compiler stages.
7. Identify where implementation and specification disagree.
8. Identify existing build/run/test infrastructure.
9. Identify available sample programs/corpus.
10. Identify the current execution environment.

**Do not start coding immediately.** You are expected to understand the existing system before proposing changes.

## 0.2 Specification is authoritative

The current language specification under `docs/` is authoritative unless the project documentation explicitly states otherwise. Existing implementation is **not evidence that a behavior is correct**. If implementation contradicts the current specification: specification wins. Do not silently modify the language to accommodate existing implementation.

## 0.3 Do not re-engineer unnecessarily

This is a hobby/academic compiler. Do not turn it into an LLVM project, a production compiler framework, an unnecessarily abstract compiler architecture, a research compiler, a distributed build system, a massive dependency graph, or an exercise in rewriting everything from scratch.

Prefer: **the simplest architecture that faithfully implements the frozen specification and can be thoroughly tested.** Use standard compiler-design approaches wherever appropriate. Do not invent novel solutions when a conventional compiler technique is sufficient.

---

# 1. FIRST DELIVERABLE: COMPLETE ENGINEERING PLAN

Before implementation begins, produce an **extremely detailed implementation plan**. The plan itself is a deliverable. It must be stored as a persistent Markdown artifact in the repository/project.

The plan must include:

### A. Repository assessment

repository structure; current compiler architecture; existing stages; current entry points; build system; test system; current dependencies; existing scripts; existing corpus; existing generated artifacts; existing CI/CD if any.

### B. Specification assessment

Read the complete language specification. Create a structured inventory of: lexical rules, tokens, literals, types, declarations, expressions, operators, precedence, statements, blocks, functions, arrays, loops, control flow, casts, input/output, standard library facilities, semantic rules, runtime behavior, error behavior, code-generation expectations.

For every potentially ambiguous or underspecified area, report:

| Area | Current specification | Ambiguity | Options | Recommended interpretation | Reason |
|---|---|---|---|---|---|

Do **not** silently resolve ambiguities. Where the specification already clearly decides something, do not reopen the decision unnecessarily. Where a decision is genuinely missing, recommend the simplest academically sensible option.

---

# 2. SPECIFICATION CONSISTENCY REVIEW

Before implementation, perform a dedicated specification review. Look specifically for: contradictions between sections; grammar/semantic mismatches; AST implications that aren't stated; type-system gaps; runtime behavior that isn't defined; code-generation assumptions; impossible grammar productions; unreachable language constructs; inconsistent terminology; missing error semantics; inconsistent array semantics; function-call semantics; conversion semantics; control-flow semantics; evaluation-order assumptions; integer/float behavior; I/O semantics; builtin/library behavior.

Do not manufacture problems simply to make the review longer. Classify findings:

- **BLOCKING** — implementation cannot proceed safely
- **IMPORTANT** — should be clarified before implementation
- **MINOR** — can reasonably use a documented convention
- **NON-ISSUE** — no action required

The goal is to remove genuine ambiguity, **not to over-specify the language**.

---

# 3. PRESERVE THE STAGED COMPILER ARCHITECTURE

The compiler must have explicit stages:

```text
Source → Lexer → Token Stream → Parser → AST → Semantic Analysis
→ Typed / Validated Representation → IR → Optimization / Lowering
→ x86-64 Assembly → Assembler / Linker → Executable
```

The exact architecture may differ if the repository/specification already establishes another valid design. But: **The output of every stage must be inspectable and usable as the input to the next stage.**

---

# 4. STAGE OBSERVABILITY IS MANDATORY

The compiler must not be a black box. Provide a CLI/debug mechanism allowing stages to be run individually, conceptually like:

```text
devara lex program.dv
devara parse program.dv
devara sema program.dv
devara ir program.dv
devara asm program.dv
devara build program.dv
```

At minimum, provide mechanisms to inspect: source → tokens; tokens → AST; AST → validated/annotated representation; validated AST → IR; IR → x86-64 assembly; source → executable. Each intermediate representation should have a stable, human-readable representation suitable for debugging and testing.

---

# 5. STAGE CONTRACTS

For every compiler stage, define a formal contract: **Input** (exact representation, invariants, ownership, assumptions); **Output** (exact representation, invariants, guarantees); **Errors** (error classes, diagnostics, failure behavior); **Tests** (unit, integration, negative, boundary).

Example:

```text
Lexer
Input:    source text
Output:   TokenStream
Guarantees:
    - every token has a source span
    - lexical errors are represented deterministically
    - parser never receives malformed token objects
Failure:  LexerDiagnostic
```

Do this for **every stage**.

---

# 6. EXISTING IMPLEMENTATION RECONSTRUCTION

Some stages already exist but were implemented against an incorrect specification. Do not blindly rewrite them. For every existing stage determine:

```text
Current implementation → Current tests → Current documented behavior
→ Current specification → Compatibility assessment → KEEP / MODIFY / REWRITE
```

For every major discrepancy record:

| Component | Existing behavior | Required behavior | Impact | Action |
|---|---|---|---|---|

Prioritize correctness over preservation of old implementation.

---

# 7. IMPLEMENTATION MUST BE PHASED

After the plan and specification review are approved, implementation must occur in clearly separated phases:

- **Phase 0 — Repository + specification baseline.** No compiler changes. Deliver: repository assessment, specification audit, architecture, implementation plan, test strategy, risk register.
- **Phase 1 — Infrastructure / stage interfaces.** Compiler CLI, stage interfaces, intermediate representations, serialization/debug output where useful, diagnostics infrastructure, test infrastructure, deterministic execution, build scripts.
- **Phase 2 — Lexer.** Implement/fix against current spec. Validate every token, literals, keywords, identifiers, whitespace, comments, malformed literals, source locations, invalid characters, boundaries.
- **Phase 3 — Parser / AST.** Validate every grammar production, precedence, associativity, statements, declarations, functions, arrays, loops, conditionals, expressions, error recovery, AST invariants, source spans.
- **Phase 4 — Semantic analysis.** Symbol tables, scopes, declaration/use checking, type checking, conversions, function checking, return checking, array semantics, control-flow constraints, definite initialization where required, builtin handling, semantic diagnostics.
- **Phase 5 — IR.** A clear intermediate representation. Every source construct has a defined lowering. No source construct silently disappears.
- **Phase 6 — x86-64 code generation.** Validate integer ops, floating-point ops, comparisons, branches, loops, calls, returns, arrays, memory, strings/text, I/O, runtime errors, stack discipline, calling conventions. Use the simplest correct ABI strategy appropriate for the project.
- **Phase 7 — End-to-end compiler.** source → lexer → parser → semantic analysis → IR → assembly → assembler/linker → executable.
- **Phase 8 — Corpus validation.** Run the entire corpus. No "representative sample" shortcut.

---

# 8. SONNET IMPLEMENTATION AGENT

After the plan is complete, implementation should be delegated to **Sonnet** in phases. Sonnet is the implementation agent. It must **not become the design authority**. Its job: implement the already-defined specification and engineering plan.

If Sonnet discovers a genuine contradiction or ambiguity: **STOP. REPORT. DO NOT INVENT A LANGUAGE RULE.** The design/validation layer resolves it.

---

# 9. STRICT DEV / TESTER SEPARATION

**Developer agent:** implementation, refactoring, fixing compiler bugs, writing production code, writing implementation-specific unit tests, commits.

**Tester / validation agent:** independently reading the specification, constructing tests, running tests, finding violations, adversarial testing, regression testing, corpus execution, differential testing where possible, reporting failures.

The tester should **not simply trust the developer's tests**:

```text
Developer implements → Independent Tester attacks → Developer fixes → Independent Tester re-validates
```

The tester must be able to say **PASS** or **FAIL** independently.

---

# 10. TESTING STANDARD

Testing is one of the highest priorities. Use multiple layers.

## 10.1 Unit tests

Every major compiler component must have unit tests. At minimum: lexer, tokenization, literal parsing, parser productions, AST construction, semantic rules, symbol table, type checker, conversions, IR construction, lowering, code generation utilities, diagnostics, runtime helpers.

# 11. INTEGRATION TESTING

Test actual stage boundaries: source → lexer → parser; … → semantic analysis; … → IR; … → assembly; … → executable. The suite must catch errors where individual stages pass but their contracts disagree.

# 12. VALIDATION TESTING

Build an independent specification-derived test suite. For every grammar production:

- **Positive:** minimal valid form, normal form, nested form, boundary form, complex form.
- **Negative:** missing tokens, invalid tokens, wrong ordering, malformed expressions, invalid types, invalid declarations, invalid control flow, invalid function usage.
- **Boundary:** empty structures, nesting, large expressions, deep recursion, large arrays, minimum/maximum numeric values, unusual identifiers, whitespace variations.

# 13. PROPERTY / GENERATIVE TESTING

Where practical: generate valid/invalid token sequences (lexer); generate grammar-valid programs and verify `parse(program)` does not crash (parser); verify AST invariants; for generated valid programs `compile(program) → executable` must either produce the expected result or fail with a documented runtime condition. The compiler must never crash unexpectedly.

# 14. FUZZ TESTING

At minimum fuzz: lexer, parser, malformed syntax, nested expressions, delimiters, function calls, arrays, loops. Primary invariant: malformed input may produce a diagnostic, but must not cause uncontrolled compiler crashes, hangs, infinite loops, or memory disasters under reasonable bounds.

# 15. END-TO-END TEST CORPUS

Mandatory. A **minimum corpus of 100 complete Devara programs**; target **100–150 high-quality programs** with substantial technical variety; do not pad with trivial variations. Preferably **DSA-oriented**:

- **Arrays:** linear search, binary search, insertion, deletion, reversal, rotation, prefix sums, suffix sums, Kadane's algorithm, two pointers, sliding window.
- **Sorting:** bubble, insertion, selection, merge, quick, heap.
- **Searching:** binary search variants, lower/upper-bound style problems, search in rotated array.
- **Strings / `padham`:** reversal, palindrome, frequency counting, substring search, anagram detection, pattern matching.
- **Mathematics:** GCD, LCM, prime checking, sieve, factorial, Fibonacci, modular arithmetic, exponentiation.
- **Recursion:** factorial, Fibonacci, binary search, tree-style recursion where language facilities permit.
- **Data structures (where expressible):** stacks, queues, linked-list-like structures, matrices, graph representations.
- **Dynamic programming (where expressible):** coin change, knapsack, LIS, LCS, grid paths.
- **Graph algorithms (where expressible):** BFS, DFS, shortest path, connected components.
- **Miscellaneous:** nested loops, functions, arrays, multidimensional arrays where supported, casts, conditionals, all loop forms, I/O, control flow.

The corpus must exercise the language rather than merely demonstrate algorithms.

# 16. CORPUS REQUIREMENTS

Every corpus program should have metadata: program ID, category, features exercised, expected behavior, expected output, difficulty, semantic features. Example:

```text
DSA-037
Category: Sorting
Algorithm: Merge Sort
Exercises: functions, arrays, recursion, loops, conditionals, integer arithmetic, input/output
Expected: ...
```

# 17. RUN EVERY TEST

At the end: **Run every test against the entire corpus.** Not "most tests", "representative tests" or "the important tests". Record: total tests, passed, failed, skipped, xfail, compiler crashes, runtime failures, timeouts. For corpus: total programs, compiled, failed compilation, executed, runtime failed, incorrect output, timeout.

# 18. GOLDEN / EXPECTED OUTPUT TESTING

Where practical, every executable corpus program should have an expected result: compile + execute + compare output. "The compiler generated assembly" is not sufficient. The ultimate validation is: **Does the generated executable behave correctly?**

# 19. REGRESSION TESTING

Every discovered bug becomes a regression test: bug found → minimal reproducer → test added → fix → full regression suite. Never fix a compiler bug without preserving a regression test unless there is a documented reason.

# 20. COMPILER SELF-CONSISTENCY

Test stage output independently: `lex program` must produce a token stream that can actually be fed to the parser; `parse program` must produce an AST accepted by semantic analysis. The architecture must not merely *pretend* to be staged.

# 21. COMMITS ARE PART OF THE ENGINEERING DELIVERABLE

Use disciplined commits; no single gigantic commit at the end. Examples:

```text
docs: finalize compiler implementation plan
test: establish lexer regression baseline
fix: align lexer with language specification
test: add parser grammar coverage
feat: implement semantic analysis
test: add semantic negative cases
feat: lower expressions to IR
feat: implement x86-64 code generation
test: add end-to-end DSA corpus
fix: correct array lowering
test: add regression for array lowering
```

Requirements: focused commits; no unrelated changes; no generated junk; meaningful messages; tests associated with changes; build remains understandable throughout.

# 22. CLOUD DEVELOPMENT

Cloud credits are available; the implementation should be designed to run in a cloud development environment. Before selecting infrastructure: inspect the repository; identify required resources; determine whether GPU is actually useful; avoid paying for unnecessary infrastructure; prefer reproducible environments; use containers/devcontainers if appropriate; document setup. The cloud environment should make it easy to: clone → install → test → build → run corpus. Do not use expensive resources unless there is a demonstrated benefit.

# 23. CI

- **Fast suite (every commit):** unit tests, parser tests, semantic tests, IR tests, basic compiler tests.
- **Full suite (merge/release):** complete unit tests, integration tests, validation suite, complete corpus, end-to-end execution, regression tests.

If the full corpus is too slow for every commit, document the split rather than silently omitting it.

# 24. PERFORMANCE

Correctness comes first. Measure: compile time, lexer throughput, parser throughput, semantic-analysis time, code-generation time, corpus execution time. Do not prematurely optimize: a correct compiler that takes a reasonable amount of time is better than a sophisticated fast compiler that is difficult to trust.

# 25. FAILURE HANDLING

Distinguish: **compiler bug** (internal exception, malformed AST, impossible IR, code-generation crash); **user program error** (syntax error, type error, invalid declaration, invalid control flow); **runtime error** (divide by zero, invalid runtime operation, input failure). Do not collapse all three into "Compilation failed."

# 26. QUALITY GATES

Do not proceed automatically if a phase fails its gate.

- **Lexer gate:** all lexer unit tests pass; all lexer validation tests pass; no known specification mismatch.
- **Parser gate:** lexer tests pass; parser tests pass; AST invariants pass; negative tests pass.
- **Semantic gate:** all semantic tests pass; negative semantic corpus passes.
- **IR gate:** all lowering tests pass; IR invariants pass.
- **Codegen gate:** assembly tests pass; runtime tests pass.
- **Final gate:** all tests pass + all corpus programs compile + all expected-output tests pass + no unexplained failures.

# 27. NO FAKE SUCCESS

Never report "Done" because the compiler builds. Never report "All tests pass" unless the tests were actually run. Never report "Corpus validated" unless the complete corpus was actually executed. Never mark tests as passing based on inspection. Never skip a failing test merely to obtain a green result. If something cannot be tested, explicitly report **NOT VERIFIED** and explain why.

# 28. FINAL VALIDATION REPORT

At the end produce a permanent report containing:

- **Specification:** version; ambiguities resolved; remaining ambiguities; deviations.
- **Architecture:** compiler stages; stage contracts; representations.
- **Implementation:** files changed; components implemented; known technical debt.
- **Testing:** Unit / Integration / Validation / Regression / Fuzz / E2E / Corpus.
- **Corpus:** Programs / Compiled / Executed / Correct / Failed / Timeouts.
- **Bugs:** discovered; fixed; unresolved.
- **Git:** commit count; major commits; final commit; dirty/clean working tree.
- **Reproducibility:** exact commands to install, test, compile, run corpus, build executable.

# 29. FINAL ACCEPTANCE CRITERIA

**Specification:** current specification fully read; genuine ambiguities identified; decisions documented; no unexplained implementation/spec conflicts remain.

**Architecture:** stages explicit; stage boundaries real; stage outputs inspectable; stage outputs feed subsequent stages.

**Implementation:** lexer, parser, semantic analysis, IR, x86-64 generation, assembler/linker integration, executable generation all work.

**Testing:** unit; integration; specification validation; negative; regression; end-to-end; fuzz/property where appropriate; minimum 100-program corpus; complete corpus executed; expected outputs verified.

**Engineering:** developer/tester separation maintained; meaningful commits; reproducible cloud environment; no unexplained skipped tests; no false PASS claims; final validation report produced.

# 30. MOST IMPORTANT INSTRUCTION

**Do not rush into implementation merely because implementation is possible.** First establish:

```text
SPECIFICATION → CLARIFICATION → ARCHITECTURE → STAGE CONTRACTS → TEST STRATEGY
→ IMPLEMENTATION PLAN → PHASED IMPLEMENTATION → INDEPENDENT VALIDATION
→ FULL CORPUS → END-TO-END EXECUTION → FINAL COMPILER
```

However, do **not** turn planning into endless analysis. The project is optimized for: **working compiler quickly + academically defensible engineering + strong validation.** Once the specification is sufficiently clear and the implementation plan is complete, **start building.**

The end state is: **a working Devara compiler that can take real programs, compile them through every stage, produce x86-64 executables, and demonstrate correctness through an independently validated test suite and a substantial DSA corpus.**
