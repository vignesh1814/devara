# Devara

A compiler for **Devara**, a Romanized-Telugu, statement-oriented language
(`x lo 10 pettu`, `n ni chupi`, `cond ayite { ... }`), targeting x86-64 Linux and Windows.

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

## Windows

Devara builds native Windows x64 executables (Microsoft x64 ABI, PE/COFF) with a MinGW-w64 `gcc`
as assembler/linker.

1. Install Python 3.11 or newer.
2. Install a MinGW-w64 `gcc` and put it on `PATH`, for example WinLibs or MSYS2 UCRT64:
   `winget install BrechtSanders.WinLibs.POSIX.UCRT`.
3. From the repository root:

```
pip install -e .
devara run file.tel
```

`devara.cmd` in the repository root is an equivalent launcher that needs no installation
(`devara.cmd run file.tel`). `--target linux|windows` (default: the host OS) selects the output
format for `asm`, `build` and `run`; `build` appends `.exe` for the Windows target.

Environment variables: `DEVARA_CC` selects the C compiler driver (default `gcc`), and `DEVARA_RUNNER`
is a prefix for running produced programs, which allows cross-checking on Linux:

```
DEVARA_CC=x86_64-w64-mingw32-gcc DEVARA_RUNNER=wine WINEDEBUG=-all \
    devara run --target windows file.tel
DEVARA_CC=x86_64-w64-mingw32-gcc DEVARA_RUNNER=wine WINEDEBUG=-all \
    python3 scripts/run_corpus.py --target windows
```

Program output is byte-identical on both platforms (standard streams are binary on Windows), and input
treats `\r\n` like `\n`.
