# Developer progress log

One line per phase gate (phase, gate result, test counts).

- Phase 1 (infrastructure): PASS — `pytest -m "not slow"` 268 passed; `./devara lex examples/example.tel` works.
- Phase 2 (lexer): PASS — lexer unit + diagnostic tests green (19 new tests; 287 passed total).
- Phase 3 (AST + parser): PASS — parser unit/negative/recovery tests green; AST invariants pass on all 27 bundled `.tel` files; 431 passed.
- Phase 4 (semantic analysis): PASS — 89 semantic unit tests + 35 stage-boundary integration tests green; full suite: 555 passed in 5.70s.
- Phase 5 (IR + verifier + optimizer): PASS — lowering (33 IR-interpreter semantic tests at O0 and O1), verifier (negative cases), optimizer (35 tests incl. no-float-identity, trap/short-circuit/order preservation); verifier passes on all valid bundled programs at O0 and O1; full suite: 652 passed in 6.88s.
- Phase 6 (x86-64 codegen + C runtime): PASS — 15 codegen/runtime tests + 33 language-semantics tests run natively at O0 and O1 (slow marker) agree with the IR interpreter; every valid bundled program assembles and links at O0 and O1; full suite: 700 passed in 14.00s.
- Phase 7 (build/run end-to-end): PASS — CLI e2e + stage-chain tests, corpus e2e at O0 and O1 (128 programs × 2), mutation fuzz; full suite: 1683 passed in 76.97s (0:01:16); scripts/run_corpus.py: 128/128 correct at -O0 and -O1.
- Round 2 fixes (F-001, F-002, F-003, Q-012, N-001, N-002, plus quadratic merge_blocks): PASS — regression tests added in tests/regression/test_bug_cli_io_and_limits.py; tester suites (validation incl. test_round2_rulings, test_cli_extra) green; scripts/run_corpus.py 128/128 correct. Full pytest before the final nesting-limit change: 5076 passed, 1 failed (stale e2e expectation, since fixed).
