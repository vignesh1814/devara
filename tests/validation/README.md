# Independent validation suite (tester agent)

Everything here is derived from `docs/DEVARA_LANGUAGE_SPEC_v0.7.md`, the frozen design (L1-L49, AST contract §3.5) and
`docs/IMPLEMENTATION_PLAN.md` (P1-P40, CLI contract §E, rulings §L). No test was derived from the compiler's code or tests;
the compiler is exercised only through the `./devara` CLI (the reference interpreter additionally consumes the *parser's* AST JSON).

| Path | What |
|---|---|
| `tests/corpus/<category>/NNN_name.{tel,in,out,exit,err}` | 128 DSA programs; expected output generated **only** by the Python oracles in `tests/corpus/_oracles/NNN_name.py` (`build_expected.py` regenerates `.out/.exit/.err`) |
| `tests/validation/test_lexer_validation.py` | lexical structure (§2-§5, P13-P15, P30) |
| `tests/validation/test_parser_productions.py` | every grammar production: positive (minimal/normal/nested/boundary/complex) + negative; AST shape (§3.5), precedence/associativity, spans |
| `tests/validation/test_semantic_rules.py` | every semantic decision P19-P40 / L-decisions: accept + reject with exact category |
| `tests/validation/test_runtime_semantics.py` | expression tables, I/O formats P1-P10, runtime errors P11, loop and evaluation-order semantics, rulings Q-001..Q-009 (slow) |
| `tests/validation/test_runtime_adversarial.py` | optimizer / codegen probes: evaluation order with side effects, aliasing, NaN, signed zero, trap preservation, calling convention (slow) |
| `tests/validation/test_stage_observability.py` | `lex --json`→`parse`, `parse --json`→`sema`, `ir --json`→`asm`/`opt`, `asm`→`build` |
| `tests/validation/test_cli_contract.py`, `test_cli_extra.py` | exit statuses, diagnostics format/positions, build/run behaviour |
| `tests/validation/test_corpus_e2e.py` | the 128 corpus programs at -O0 and -O1 (slow) |
| `tests/validation/test_forms_and_whitespace.py` | whitespace / keyword case / identifier forms |
| `tests/reference/interp.py` | independent tree-walking reference interpreter (differential oracle) |
| `tests/property/` | hypothesis fuzzing (token soup, mutated corpus, deep nesting), well-typed random-program generator (`proggen.py`) + differential tests vs the interpreter, I/O stream differential fuzz, long `campaign.py` |

Fast suite: `pytest -m "not slow"`. Full suite: `pytest` (use `-n 4` with pytest-xdist). Long campaign:
`python3 tests/property/campaign.py START COUNT SIZE [JOBS]`.
