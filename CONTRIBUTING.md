# Contributing to Devara

Bug reports, test programs and fixes to the Telugu glosses are all welcome.

## Set up

You need Python 3.11+ and a `gcc` on `PATH` (MinGW-w64 on Windows).

```text
git clone https://github.com/vignesh1814/devara.git
cd devara
pip install -e . -r requirements-dev.txt pytest-xdist
devara run examples/hello.tel
```

## Run the tests

```text
python -m pytest -q -n 4 -m "not slow"     # fast suite
python -m pytest -q -n 4                   # everything (about 30 minutes)
python scripts/check_machine.py            # 128-program corpus at -O0 and -O1, plus a leak check
```

## Ground rules

- **The compiler has no dependencies** beyond the Python standard library. Keep it that way.
- **`-O0` and `-O1` must print identical output** for every program. A change to the optimizer or backend needs a test
  that runs the same source at both levels (see `check_against_reference` in `tests/validation/stress_util.py`).
- **A bug fix needs a regression test** that fails without the fix (`tests/regression/`).
- **Language changes** (new syntax, changed behaviour) need a ruling recorded in
  [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md), and an update to the
  [language spec](docs/DEVARA_LANGUAGE_SPEC_v0.7.md).
- **Both targets matter.** The Linux (System V) and Windows (x64) code generators share everything above the ABI; if you
  can only test one, say so in the pull request.
- New example programs go in `examples/` and get a case in `tests/validation/test_readme_examples.py`.

## Reporting a bug

Include the `.tel` source, the command you ran, what you expected and what happened (the full message and exit code).
`devara asm`/`devara ir` output is welcome for code-generation problems.
