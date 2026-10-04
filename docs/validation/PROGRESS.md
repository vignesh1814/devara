# Validation progress log

| Milestone | Detail |
|---|---|
| Corpus batch 1 | 128 programs in tests/corpus (arrays 14, sorting 10, searching 8, strings 14, math 16, recursion 11, datastructures 10, dp 10, graphs 10, misc 25 incl. 10 runtime-error programs), each with .in/.out (+.exit/.err), outputs generated only from the independent Python oracles in tests/corpus/_oracles. Not yet run against a compiler (none exists on the developer branch). |
| Reference interpreter | tests/reference/interp.py (tree-walking, consumes `parse --json`). Differential vs oracle `.out`: 128/128 corpus programs agree (also validates the oracles, the parser and the interpreter against each other). |
| Lexer validation | tests/validation/test_lexer_validation.py + test_cli_contract.py: 323 passed against the merged developer branch (front end through sema; backend not yet present). |
| Parser/semantic validation | test_parser_productions.py (425 tests) and test_semantic_rules.py (489 tests) against the merged developer branch: all pass. Design-authority rulings Q-001..Q-009 (plan §L) are covered by tests in test_runtime_semantics.py. |
| Backend merge | Developer branch now has IR, optimizer, codegen, runtime. `scripts/run_corpus.py`: 128/128 correct at -O0 and at -O1 (compiled 128, executed 128, incorrect 0, timeouts 0). |
| Runtime / adversarial / fuzz | test_runtime_semantics.py (1045 tests), test_runtime_adversarial.py (356), test_stage_observability.py, test_cli_extra.py (35), tests/property (token-soup fuzz 8 properties, differential 27, I/O differential 47). One failure found: F-001 (see FAILURES.md). |
| Final run | Merged developer c3c2b2f: full pytest 5155 passed, 0 failed, 1 skipped; corpus 128/128 at -O0 and -O1; F-001..F-005 fixed. Verdict PASS (docs/validation/VALIDATION_REPORT.md). |
