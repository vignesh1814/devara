# Devara

**A programming language where you don't *print* a value, you *show it* — `x ni chupi` — and you don't assign, you *put it in*: `x lo 5 pettu`.**

Devara is an esoteric-flavoured, statement-oriented language written in **Romanized Telugu**, with a real
ahead-of-time compiler behind it: source goes in, a native x86-64 executable (Linux **or Windows**) comes out.

```text
"Hello, Devara!" ni chupi
```

```text
> devara run examples/hello.tel
Hello, Devara!
```

No interpreter shortcuts: the compiler is a hand-written pipeline (lexer, parser, semantic analysis, typed IR,
optimizer, register-allocating x86-64 backend) in plain Python 3.11 with no dependencies. `gcc` only assembles and
links the result. It has **6,900+ tests**, a 128-program algorithm corpus, and an independent reference interpreter
that every compiled program is cross-checked against.

---

## The vocabulary (a rough gloss)

| Devara | Rough reading | What it does |
|---|---|---|
| `x lo 5 pettu` | "in x, put 5" | assignment |
| `x ni chupi` | "show x" | print (any expression: `x + 1 ni chupi`) |
| `x ni chaduvu` | "read into x" | read input |
| `cond ayite { } lekunte { }` | "if so ... if not ..." | if / else (the condition comes **first**) |
| `cond unnanta varaku { }` | "for as long as" | while |
| `prati i 1 nundi 10 varaku { }` | "for each i from 1 until 10" | range loop (end excluded) |
| `pratisari (i 0 tho modhalu; i < n; i lo i + 1 pettu) { }` | "each time (i starting with 0 ...)" | three-part loop |
| `aapu` / `saagu` | "stop" / "go on" | break / continue |
| `int f charya (int a) { a * 2 ivvu }` | "action ... give" | function; the value comes **before** `ivvu` |
| `nijam` / `abaddham` | "truth" / "falsehood" | `true` / `false` |
| `padham` | "word" | the string type |

Types: `int` (64-bit), `float`, `bool`, `char`, `padham`, `void`, plus arrays (`int a[10]`, `int m[3][4]`, even
sized at run time: `int a[n]`). Comments start with `#`. Keywords are case-insensitive, so `Ayite` and `AYITE`
are reserved too. Casts look like C: `(int) x`.

The word order is the point: statements are written *verb last*, the way Telugu sentences are. The full
language, with a formal grammar, is in [`docs/DEVARA_LANGUAGE_SPEC_v0.7.md`](docs/DEVARA_LANGUAGE_SPEC_v0.7.md).

---

## Gallery

**FizzBuzz** — [`examples/fizzbuzz.tel`](examples/fizzbuzz.tel). Note that the condition is written before `ayite`:

```text
prati i 1 nundi 16 varaku {
  i % 15 == 0 ayite {
    "FizzBuzz" ni chupi
  } lekunte {
    i % 3 == 0 ayite {
      "Fizz" ni chupi
    } lekunte {
      i % 5 == 0 ayite {
        "Buzz" ni chupi
      } lekunte {
        i ni chupi
      }
    }
  }
}
```

**Primes** — [`examples/primes.tel`](examples/primes.tel). Functions, early return, input:

```text
bool isprime charya (int k) {
  k < 2 ayite { abaddham ivvu }
  int d
  d lo 2 pettu
  d * d <= k unnanta varaku {
    k % d == 0 ayite { abaddham ivvu }
    d lo d + 1 pettu
  }
  nijam ivvu
}

int n
n ni chaduvu
prati i 2 nundi n + 1 varaku {
  isprime(i) ayite { i ni chupi }
}
```

**Bubble sort** — [`examples/sort.tel`](examples/sort.tel). Run-time sized arrays and nested `pratisari` loops.

---

## Try it

You need **Python 3.11+** and a **`gcc`** on `PATH` (the compiler writes assembly; `gcc` assembles and links it).

**Windows** — install a MinGW-w64 `gcc` (for example `winget install BrechtSanders.WinLibs.POSIX.UCRT`), open a *new*
terminal, then:

```text
git clone https://github.com/vignesh1814/devara.git
cd devara
pip install -e .
devara run examples/hello.tel
```

**Linux** — `sudo apt install gcc`, then the same four commands. (`./devara` also works without installing.)

If you'd rather not install anything, `devara.cmd run examples/hello.tel` (Windows) or `./devara run ...` (Linux) works
straight from the checkout.

### Commands

| Command | What it does |
|---|---|
| `devara run prog.tel` | compile and run; the program's exit status is yours |
| `devara build prog.tel -o prog` | write an executable (`prog.exe` on Windows) |
| `devara lex\|parse\|sema\|ir\|opt\|asm prog.tel` | print the output of that compiler stage (add `--json` for machine-readable) |
| `-O0` / `-O1` | `-O1` (default) optimizes; `-O0` is the plain reference code generator. Output is identical at both levels |
| `--target linux\|windows` | cross-assemble for the other OS (default: this OS) |

Exit codes: `0` ok, `1` your program had a compile error or a run-time error, `2` bad command line, `3` the compiler
itself failed (a bug, or no `gcc`).

---

## Walkthrough: what happens to `x * x`

```text
int square charya (int x) {
  x * x ivvu
}
```

```text
> devara lex examples/squares.tel          # words:      INT  IDENTIFIER(square)  CHARYA  LPAREN ...
> devara ir examples/squares.tel           # neutral IR: t1:i64 = mul x.2, x.2   /   ret t1
> devara asm examples/squares.tel          # machine code (Windows x64 ABI, argument arrives in rcx):
dv_f_square:
    mov r8, rcx
    imul r8, r8
    mov rax, r8
    ret
> devara build examples/squares.tel -o squares
> squares.exe                  # a standalone ~340 KB executable, no Python needed (type a number, e.g. 4)
```

Mistakes are caught before anything runs, with a position and a category:

A file containing just `total ni chupi`:

```text
> devara run bad.tel
bad.tel:1:1: semantic error [UNDECLARED]: undeclared identifier 'total'
```

and run-time faults are defined, never crashes (division by zero, out-of-range string index, bad input, out of memory):

A file that does `10 / z` with `z` equal to 0:

```text
> devara run dz.tel
devara: runtime error: division by zero
```

---

## How it works

```text
source ─▶ Lexer ─▶ Parser/AST ─▶ Semantic analysis ─▶ typed IR + CFG ─▶ optimizer ─▶ x86-64 asm ─▶ gcc ─▶ .exe / ELF
```

- **Two code generators.** `-O0` keeps everything in stack slots and is the reference. `-O1` adds a linear-scan
  register allocator, a peephole pass, shrink-wrapped callee-saved registers, frameless leaf functions and loop
  rotation. They must produce byte-identical program output; a fuzzer checks that.
- **Two ABIs.** System V on Linux, Microsoft x64 on Windows (PE/COFF via MinGW-w64).
- **Memory.** Arrays are freed when their scope exits on every path (including `ivvu`, `aapu`, `saagu`); `padham`
  strings are reference counted. `DEVARA_RT_STATS=1 ./prog` prints `devara-rt: live=<n>` at exit, and the tests
  insist it is `0`.
- **A C runtime** ([`runtime/devara_rt.c`](runtime/devara_rt.c)) handles I/O, strings and run-time errors.
- **Binary I/O.** Output bytes are identical on Linux and Windows (no CRLF translation); input treats `\r\n` as `\n`.
  A leading UTF-8 byte order mark in a source file is ignored.

---

## Tests

```text
pip install -e . -r requirements-dev.txt pytest-xdist
python -m pytest -q -n 4 -m "not slow"        # fast suite, a couple of minutes
python -m pytest -q -n 4                      # everything, about 30 minutes
python scripts/check_machine.py              # corpus at -O0/-O1 + leak check; writes build/machine_report.txt
python tests/property/campaign.py 1000000 300 50 4   # differential fuzzing against the reference interpreter
```

Last full run on native Windows 11: **6,909 passed, 0 failed, 87 skipped** (86 need AddressSanitizer, 1 needs POSIX
permissions); the compiler package has 94% line-and-branch coverage; 1,800 random programs compiled to `.exe` and
matched the reference interpreter exactly. Linux and Windows both run in CI.

---

## Windows notes

- `devara.cmd` is a launcher that needs no install. Set `DEVARA_PYTHON=<path>\python.exe` to make it use a specific
  interpreter.
- **`devara run prog.tel < input.txt` says `invalid input` but `type input.txt | devara run prog.tel` works?**
  pyenv-win's `.bat` shims throw away a redirected stdin. Use `<python dir>\Scripts\devara.exe` or set
  `DEVARA_PYTHON`.
- A program that dies with exit code `-1073741571` (`0xC00000FD`) overflowed its 8 MiB stack, exactly as it would on
  Linux; stack overflow is deliberately not a defined run-time error.
- `DEVARA_CC` picks the C compiler driver (default `gcc`); `DEVARA_RUNNER` prefixes the produced program, which lets
  you cross-check the Windows target on Linux:

```text
DEVARA_CC=x86_64-w64-mingw32-gcc DEVARA_RUNNER=wine WINEDEBUG=-all devara run --target windows prog.tel
```

---

## Where to look

| | |
|---|---|
| [`docs/DEVARA_LANGUAGE_SPEC_v0.7.md`](docs/DEVARA_LANGUAGE_SPEC_v0.7.md) | the language, with a formal grammar |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | every design decision and ruling (P1–P43, A-001…A-006) |
| [`docs/STAGE_FORMATS.md`](docs/STAGE_FORMATS.md) | what each `devara lex/parse/sema/ir/opt/asm --json` prints |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) | benchmarks |
| [`docs/audit/`](docs/audit/) | the audit and how each finding was resolved |
| `compiler/` · `runtime/` · `tests/` · `examples/` | the code, the C runtime, the tests (`corpus/` holds 128 DSA programs), runnable samples |

*Devara is a hobby language: the Telugu glosses above are informal, and contributions that fix them are welcome.*
