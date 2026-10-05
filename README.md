# Devara

A compiler for **Devara**, a Romanized-Telugu, statement-oriented language
(`x lo 10 pettu`, `n ni chupi`, `cond ayite { ... }`), targeting x86-64 Linux.

```
source -> Lexer -> Parser/AST -> Semantic analysis -> typed IR + CFG -> optimizer -> x86-64 asm -> gcc -> executable
```

Python 3.11 standard library only (plus `gcc` to assemble/link and a small C runtime).

## Use

```
./scripts/setup.sh                        # dev dependencies (pytest, hypothesis)
./devara run examples/example.tel         # compile and run
./devara build prog.tel -o prog           # executable
./devara lex|parse|sema|ir|opt|asm prog.tel [--json] [-O0|-O1]
pytest -m "not slow"                      # fast suite      |  pytest   # everything
python3 scripts/run_corpus.py [-j N]      # end-to-end corpus statistics (parallel, default: CPU count)
DEVARA_RT_STATS=1 ./prog                  # print live heap arrays + strings at exit: devara-rt: live=<n>
```

Docs: `docs/DEVARA_LANGUAGE_SPEC_v0.7.md` (language), `docs/IMPLEMENTATION_PLAN.md` (decisions and
stage contracts), `docs/STAGE_FORMATS.md` (CLI artifacts), `docs/PROGRESS.md`,
`docs/validation/` (open questions and failures).
