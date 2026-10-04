# Validation progress log

| Milestone | Detail |
|---|---|
| Corpus batch 1 | 128 programs in tests/corpus (arrays 14, sorting 10, searching 8, strings 14, math 16, recursion 11, datastructures 10, dp 10, graphs 10, misc 25 incl. 10 runtime-error programs), each with .in/.out (+.exit/.err), outputs generated only from the independent Python oracles in tests/corpus/_oracles. Not yet run against a compiler (none exists on the developer branch). |
| Reference interpreter | tests/reference/interp.py (tree-walking, consumes `parse --json`). Differential vs oracle `.out`: 128/128 corpus programs agree (also validates the oracles, the parser and the interpreter against each other). |
| Lexer validation | tests/validation/test_lexer_validation.py + test_cli_contract.py: 323 passed against the merged developer branch (front end through sema; backend not yet present). |
