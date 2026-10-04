# Developer status — Phases 1–7

All numbers below come from commands run on the final tree of branch
`claude/devara-compiler-cloud-migration-l3txzx` (merged with the tester's branch
`claude/devara-validation-l3txzx` up to its commit `586571d`).

## Gate results

| Phase | Deliverable | Gate | Result |
|---|---|---|---|
| 1 | diagnostics, serialization, CLI, `./devara`, test layout, `slow` marker, CI, devcontainer, `scripts/setup.sh`, `scripts/run_corpus.py` | `pytest -m "not slow"` green; `./devara lex examples/example.tel` works | **PASS** |
| 2 | lexer categories, CRLF, token end column | lexer unit + validation tests green | **PASS** |
| 3 | AST rewrite (§3.5), parser fixes, §3.6 categories, §3.7 recovery, invariant checker | parser/negative tests green; AST invariants pass on every `.tel` in the repo | **PASS** |
| 4 | semantic analysis P19–P40, typed tree | semantic unit tests + stage-boundary tests green | **PASS** |
| 5 | IR + CFG, printer, JSON, verifier, optimizer | lowering tests green; verifier passes on all valid programs at O0 and O1 | **PASS** |
| 6 | x86-64 codegen + C runtime | codegen/runtime tests green; all programs assemble and link | **PASS** |
| 7 | `build` / `run`, stage-boundary integration tests, O0-vs-O1 | E2E tests green | **PASS** |

Per-phase lines are also in `docs/PROGRESS.md`.

## Test counts (real output)

```
$ pytest -q
1695 passed in 80.36s (0:01:20)

$ pytest -q -m "not slow"
1373 passed, 322 deselected in 55.61s
```

Collected per directory: unit 606, integration 751, regression 15, validation 323 (tester),
property 0 and reference 0 (tester helper package only, no tests collected yet).
No test is skipped or xfailed.

## Corpus (`scripts/run_corpus.py`, tester's 128-program corpus)

```
$ python3 scripts/run_corpus.py -O1        $ python3 scripts/run_corpus.py -O0
total                128                   total                128
compiled             128                   compiled             128
failed_compilation   0                     failed_compilation   0
executed             128                   executed             128
runtime_failed       0                     runtime_failed       0
incorrect_output     0                     incorrect_output     0
timeout              0                     timeout              0
correct              128                   correct              128
```

The same 128 programs also run as parametrized pytest cases at both levels
(`tests/integration/test_corpus_e2e.py`, slow).

## Performance (24 001-token generated program, one run)

lex 0.049 s · parse 0.082 s · sema 0.051 s · lower 0.043 s · optimize 0.509 s · codegen 0.010 s.
Corpus: ~0.17 s average compile (dominated by process start + `gcc` link), program run time ≤ 0.01 s.

## Verification beyond unit tests

* IR interpreter oracle (`tests/helpers/irinterp.py`) vs the native back end on the same programs.
* Deterministic mutation fuzzing of the whole pipeline (`tests/unit/test_pipeline_fuzz.py`) plus an ad-hoc
  4 500-mutation run (seeds 2–4): no compiler crash, no O0/O1 mismatch.
* Bugs fixed with regression tests in `tests/regression/`: parser accepted bare blocks / call-index
  chaining / parenthesized targets; AST end columns were not half-open; lexer treated `\r` as an invalid
  character and matched Unicode digits; AST and IR `Block` class-name collision broke JSON decoding.

## Known technical debt

* No register allocation (every value has a stack slot); generated code is correct but slow.
* Heap arrays (non-constant or > 64 KiB dimensions) and all padham values are never freed (P22).
* Global scalars live in memory, so constants are not propagated through them.
* Deep recursion beyond the 8 MiB stack segfaults and buffered stdout is lost (P38: undefined).
* Out-of-bounds array access is undefined (L32); the IR interpreter oracle raises instead.
* `scripts/run_corpus.py` spawns one `./devara build` process per program.
* `tests/audit_scripts/*` are legacy print scripts, not tests.

## Open questions / conventions

`docs/validation/OPEN_QUESTIONS.md` (OQ1–OQ11) — all accepted by the design authority
(`docs/IMPLEMENTATION_PLAN.md` §L, which also rules Q-001…Q-009; each is covered by a test).
`docs/validation/FAILURES.md` (tester) lists no open failure against the compiler at the time of writing.
