# Devara — Handoff for the local agent

Written 2026-10-08. All work is on `main` of **https://github.com/vigneshtheerdala-spec/devara**.

## Read this first

- **Correct remote:** `https://github.com/vigneshtheerdala-spec/devara.git`. An earlier local clone had `origin` pointing at `github.com/vignesh1814/devara`, which only holds an old `main`. Check with `git remote -v`; if it is wrong, clone the correct repo instead of fixing the old one.
- **History was rewritten on 2026-10-08** to remove the `Co-Authored-By` / `Claude-Session` trailers from 11 early commits. Every commit hash from the old history changed (the file contents did not). Any older clone must be thrown away or reset: `git fetch origin; git checkout main; git reset --hard origin/main`.
- **Work in a plain folder outside OneDrive**, for example `C:\dev\devara`: OneDrive can lock files while tests run.
- **Windows PowerShell 5.1 has no `&&`.** Put commands on separate lines or separate them with `;`.
- **The `devara` file is a bash script.** On Windows use `devara.cmd` or `python -m compiler.cli`.

## State

- Compiler complete: lexer → parser → semantic analysis → IR → optimizer → x86-64 (Linux System V and Windows x64 / MinGW) → gcc link. Pure Python 3.11+ up to the assembly text; gcc assembles, links and supplies the C runtime (`runtime/devara_rt.c`).
- `-O1`: linear-scan register allocation, peephole, shrink-wrapped callee-saved registers, frameless leaf functions, loop rotation. `-O0` is the reference stack-slot generator. Output must be identical at both levels.
- Memory: scope-exit freeing, reference-counted `padham`; `bool`/`char` array elements are one byte.
- **Last verified (Linux, with wine and MinGW installed): 6,988 tests passed, 1 skipped (root-only), 0 failed.** `scripts/check_machine.py` PASS: corpus 128/128 at `-O0` and `-O1`, leak check 236/236 `live=0`. About 700 fuzzed programs against the reference interpreter: 0 differences.
- **GitHub Actions is green on `ubuntu-latest` and `windows-latest`.** On Windows CI runs `pytest -m "not slow"`, `tests/integration/test_windows_target.py` and the corpus at `-O0` and `-O1`, all natively with MinGW-w64.
- The audit is done and every item was addressed: `docs/audit/AUDIT_REPORT.md` (findings plus a Resolution section) and `docs/audit/IMPROVEMENT_PLAN.md` (15 items with status and commits).

## First tasks on the Windows machine

Prerequisites: Python 3.11+, git, and a 64-bit MinGW-w64 gcc on PATH (`winget install BrechtSanders.WinLibs.POSIX.UCRT`, then open a **new** terminal).

```
cd C:\dev
git clone https://github.com/vigneshtheerdala-spec/devara.git
cd devara
python -m pip install -e . -r requirements-dev.txt pytest-xdist
python scripts/check_machine.py
python -m pytest -q -n 4 -m "not slow"
python -m pytest -q -n 4
```

1. `check_machine.py` writes `build\machine_report.txt` (toolchain, full corpus at both levels, leak check). Expect `RESULT: PASS`.
2. The `-m "not slow"` run is what CI does on Windows. The last command (everything, including the slow tests) has **never been run natively on Windows**: some tests need bash or wine and skip or fail there. Report anything that fails, with the first error line, before changing code.
3. The corpus files must be LF; `.gitattributes` handles that on a fresh clone. If the corpus runner reports wrong output, check `git config core.autocrlf` and re-clone.
4. Try it: `python -m compiler.cli run examples/example.tel`.

## Project map

- `compiler/` — `lexer/`, `parser/`, `ast/`, `semantic/` (checker, flow analysis), `ir/` (lowering, verifier, printer), `opt/` (passes), `codegen/` (`x86_64.py` = `-O0`; `prep.py`, `regalloc.py`, `x86_64_ra.py`, `peephole.py` = `-O1`; `target.py` = ABIs), `driver.py`, `cli.py`.
- `runtime/devara_rt.c` — I/O, padham (strings), reference counting, runtime errors.
- `tests/` — `unit/`, `integration/`, `regression/` (one test per fixed bug), `validation/` (black-box via the CLI), `property/` (fuzzing: `campaign.py START COUNT SIZE [JOBS]`), `reference/` (independent interpreter used as the oracle), `corpus/` (128 DSA programs with expected output).
- `scripts/` — `check_machine.py`, `run_corpus.py`, `bench.py`, `setup.sh`.
- `docs/` — `DEVARA_LANGUAGE_SPEC_v0.7.md` (authority for the language), `IMPLEMENTATION_PLAN.md` (all decisions P1–P43 and rulings §L–§O), `STAGE_FORMATS.md`, `PERFORMANCE.md`, `validation/`, `audit/`.

## Conventions

- The spec is the authority. A gap or contradiction goes to `docs/validation/OPEN_QUESTIONS.md`; rulings are recorded in `docs/IMPLEMENTATION_PLAN.md`. Do not invent language rules.
- Every bug gets a regression test in `tests/regression/` that fails without the fix.
- **No attribution trailers in commit messages** (`Co-Authored-By`, `Claude-Session`); do not add them.
- Never mark a failing test skipped or xfail to get green.
- Compare performance only on one machine, back to back: numbers from different hosts differ by more than the effects being measured.
- Language-visible changes need a ruling in the plan and tests; generated-code changes need `-O0`/`-O1` identical output and a differential fuzz run (`python tests/property/campaign.py 1000000 300 50 4`).

## Known caveats

- On Linux with wine, a full-suite run occasionally has a single failing Windows-target test because wine drops its server connection under load (3 of the first 4 runs, 0 of the last 3). The Windows tests now retry only on that error; anything else is real.
- `x86_64-w64-mingw32-gcc` and `wine` are needed for the Windows-target tests on Linux (`apt-get install mingw-w64 wine64`).

## Still open (not in the audit plan)

Inlining of small functions; division by constants without `idiv` (the matmul benchmark's `% 10`); making `rcx`/`rdx`/`r10` allocatable; coalescing call results into their consumers; general loop-invariant code motion; Python start-up cost per CLI call (about 0.1 s).

## Stale branches

`claude/devara-compiler-cloud-migration-l3txzx` and `claude/devara-validation-l3txzx` still hold the old history with the trailers; they are fully merged into `main` and can be deleted: `git push origin --delete <name>`.

## Prompt to start the local agent

> You are continuing work on the Devara compiler in this repository (read `HANDOFF.md` first). Confirm `git remote -v` points at `vigneshtheerdala-spec/devara`. Run the commands under "First tasks on the Windows machine" and report the results exactly, including the first error line of any failure, before changing anything. Follow the conventions in `HANDOFF.md`. Ask before pushing or rewriting history.
