# Devara — Handoff (resume locally)

## State (all on branch `claude/devara-compiler-cloud-migration-l3txzx`)
- Compiler complete: lexer → parser → sema → IR → optimizer → x86-64 (Linux SysV + Windows x64/MinGW) → gcc link.
- -O1: linear-scan register allocation + peephole. Memory: scope-exit freeing, refcounted `padham`.
- Last verified: 6,881 tests pass (1 root-only skip); corpus 128/128 on linux/windows × -O0/-O1; leak check 236/236 live=0.
- Docs: `docs/IMPLEMENTATION_PLAN.md` (all language decisions P1–P43, rulings §L–§N),
  `docs/FINAL_VALIDATION_REPORT.md`, `docs/validation/`, `docs/PERFORMANCE.md`, `docs/STAGE_FORMATS.md`.

## Get it locally (Windows)
```
git fetch origin
git checkout claude/devara-compiler-cloud-migration-l3txzx
pip install -e .            # needs Python >= 3.11
pip install -r requirements-dev.txt pytest-xdist
```
Needs a 64-bit MinGW-w64 gcc on PATH: `winget install BrechtSanders.WinLibs.POSIX.UCRT` (new terminal after).
To merge into main locally: `git checkout main && git merge claude/devara-compiler-cloud-migration-l3txzx`.

## Verify
```
python scripts/check_machine.py          # toolchain + full corpus -O0/-O1 + leak check -> build/machine_report.txt
python -m pytest -q -n 4 -m "not slow"   # fast suite
python -m pytest -q -n 4                 # full suite (some tests need bash/wine and skip or fail on native Windows — not yet verified there)
python scripts/bench.py                  # performance
devara run examples/example.tel
```

## Open items (not started)
1. **History cleanup**: 11 early commits (3 on `main`) contain `Co-Authored-By`/`Claude-Session` trailers. Force-push was blocked in the cloud. Locally:
   ```
   git checkout claude/devara-compiler-cloud-migration-l3txzx
   git filter-branch -f --msg-filter 'grep -viE "^(co-authored-by:|claude-session:)"' -- main claude/devara-compiler-cloud-migration-l3txzx
   git push --force-with-lease origin main claude/devara-compiler-cloud-migration-l3txzx
   git push origin --delete claude/devara-validation-l3txzx   # fully merged, optional
   ```
2. **Audit: done (findings only, nothing fixed).** See `docs/audit/AUDIT_REPORT.md` and the ranked `docs/audit/IMPROVEMENT_PLAN.md`. 44 programs were checked by hand (`docs/audit/A_programs/`, with `.in`/`.out`), 20 diagnostics cases (`docs/audit/A_invalid/`), plus a code review, benchmarks against gcc, compile-time scaling and 600 fuzzed programs. Top issues: an overflow in the array-size product (silent heap corruption) and an ICE on global arrays over 2 GiB. Next step: fix the issues in the plan's order, once the owner approves.
3. **Improvement candidates**: superseded by `docs/audit/IMPROVEMENT_PLAN.md` (not yet ranked there: inlining small functions, and Python start-up cost per CLI call).
4. **Windows CI**: the `windows` job in `.github/workflows/ci.yml` had been failing during test collection (`os.geteuid` at import), so native Windows was never actually tested. The collection error is fixed on `claude/sharp-faraday-yb2rr7`; see `docs/audit/AUDIT_REPORT.md` F16 for the first real run's result.

## Conventions
- Spec is authority; implementation gaps → `docs/validation/OPEN_QUESTIONS.md`, rulings recorded in plan.
- Every bug gets a regression test in `tests/regression/`. No attribution trailers in commits.
