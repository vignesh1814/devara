# Devara

> *You do not print a value. You **show** it: `x ni chupi`.*
> *You do not assign. You **put it in**: `x lo 5 pettu`.*
> *The verb comes last, because this is how Telugu sentences end.*

**Devara** is a programming language written in **Romanized Telugu**, with a real ahead-of-time compiler behind it:
`.tel` source goes in, a standalone native **x86-64 executable** (Linux ELF or Windows `.exe`) comes out.

```text
"Hello, Devara!" ni chupi
```

It is a joke that was taken seriously. The language is small and a little backwards, but the compiler is a complete,
hand-written pipeline (lexer, parser, semantic analysis, typed IR, optimizer, register-allocating x86-64 backend) in
plain Python 3.11 with **no dependencies**. `gcc` is used only to assemble and link at the very end.

- **Verb-last syntax.** `total lo total + 1 pettu` — "in total, put total plus one."
- **Conditions come first.** `n > 0 ayite { ... } lekunte { ... }` — "n greater than 0, if so ... if not ..."
- **Native code.** Two code generators (`-O0` and `-O1`) that must agree byte for byte.
- **Defined behaviour.** Division by zero, bad input, an out-of-range string index and running out of memory are
  reported errors with an exit status, never crashes. (Stack overflow is the one deliberate exception.)
- **Tested like it matters.** 6,900+ tests, a 128-program algorithm corpus, and a reference interpreter that every
  compiled program is cross-checked against.

---

## Contents

[Vocabulary](#vocabulary) · [Programs](#programs) · [The rest of the language](#the-rest-of-the-language) ·
[Quick start](#quick-start) · [Look inside the compiler](#look-inside-the-compiler) · [How it works](#how-it-works) ·
[FAQ](#faq) · [Tests](#tests) · [Windows notes](#windows-notes) · [Documentation](#documentation)

---

## Vocabulary

| Devara | Rough reading | Meaning |
|---|---|---|
| `x lo 5 pettu` | "in x, put 5" | assignment |
| `x ni chupi` | "show x" | print any expression: `x + 1 ni chupi` |
| `x ni chaduvu` | "read into x" | read a value from input |
| `cond ayite { } lekunte { }` | "if so ... if not ..." | if / else (the condition is written **first**) |
| `cond unnanta varaku { }` | "for as long as" | while |
| `prati i 1 nundi 10 varaku { }` | "for each i from 1 until 10" | range loop (the end is excluded) |
| `pratisari (i 0 tho modhalu; i < n; i lo i + 1 pettu) { }` | "every time (i beginning with 0 ...)" | three-part loop |
| `aapu` / `saagu` | "stop" / "go on" | break / continue |
| `int f charya (int a) { a * 2 ivvu }` | "action ... give" | function; the value is written **before** `ivvu` |
| `nijam` / `abaddham` | "truth" / "falsehood" | `true` / `false` |
| `padham` | "word" | the string type |
| `podavu(s)` | "length" | length of a `padham` |

Comments start with `#`. Keywords are case-insensitive (`Ayite`, `AYITE` and `ayite` are the same word). The Telugu
glosses are informal; corrections are welcome.

---

## Programs

Every program below is in [`examples/`](examples/), is run by the test suite, and produces exactly the output shown.

### Hello, World — [`hello.tel`](examples/hello.tel)

```text
"Hello, Devara!" ni chupi
```

### Truth machine — [`truth_machine.tel`](examples/truth_machine.tel)

Input `0`: print `0` and halt. Input `1`: print `1` forever. (The required esolang rite of passage.)

```text
int x
x ni chaduvu
x == 0 ayite {
  0 ni chupi
} lekunte {
  nijam unnanta varaku { 1 ni chupi }
}
```

### Factorial — [`factorial.tel`](examples/factorial.tel)

A recursive function. Notice that the result is written *before* `ivvu`.

```text
int fact charya (int n) {
  n <= 1 ayite { 1 ivvu }
  n * fact(n - 1) ivvu
}

int n
n ni chaduvu
fact(n) ni chupi
```

```text
$ echo 10 | devara run examples/factorial.tel
3628800
```

### FizzBuzz — [`fizzbuzz.tel`](examples/fizzbuzz.tel)

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

### Collatz — [`collatz.tel`](examples/collatz.tel)

```text
int n
n ni chaduvu

int steps
steps lo 0 pettu
n != 1 unnanta varaku {
  n % 2 == 0 ayite {
    n lo n / 2 pettu
  } lekunte {
    n lo 3 * n + 1 pettu
  }
  steps lo steps + 1 pettu
}
steps ni chupi
```

```text
$ echo 27 | devara run examples/collatz.tel
111
```

### Primes — [`primes.tel`](examples/primes.tel)

Functions, early return, and a loop whose condition is a call.

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

### More

| File | What it shows |
|---|---|
| [`fibonacci.tel`](examples/fibonacci.tel) | the first *n* Fibonacci numbers |
| [`sort.tel`](examples/sort.tel) | bubble sort over a run-time sized array, nested `pratisari` loops |
| [`reverse.tel`](examples/reverse.tel) | `padham` indexing and `podavu`: a string backwards, one character per line |
| [`squares.tel`](examples/squares.tel) | a function, input, and a range loop |
| [`example.tel`](examples/example.tel) | variables and arithmetic, the smallest useful program |

---

## The rest of the language

- **Types:** `int` (64-bit signed), `float` (IEEE-754 binary64), `bool`, `char`, `padham`, `void`.
- **Arrays:** `int a[10]`, `int m[3][4]`, and sized at run time: `int a[n]`. Arrays are freed when their scope exits,
  on every path out of it (including `ivvu`, `aapu` and `saagu`).
- **Casts:** C-style, `(int) x`, `(float) n`.
- **Declare before use:** every variable is declared with its type first (`int total`), then assigned with
  `total lo 0 pettu`. The `x 0 tho modhalu` in a `pratisari` loop assigns to a variable that already exists.
- **Operators:** `+ - * / %`, comparisons, `&& || !`, with the usual precedence.
- **Source encoding:** bytes, read as Latin-1, so `padham` literals are byte strings. A leading UTF-8 byte order mark is
  ignored (ruling A-006), which makes files saved by Windows Notepad work.

The complete language, with a formal grammar, is in [`docs/DEVARA_LANGUAGE_SPEC_v0.7.md`](docs/DEVARA_LANGUAGE_SPEC_v0.7.md).

**Computational class.** Unbounded loops, recursion and arrays sized at run time mean that anything a computer can
compute can be written in Devara, within the limits of 64-bit integers and the machine's memory.

---

## Quick start

You need **Python 3.11+** and a **`gcc`** on your `PATH` (the compiler writes assembly; `gcc` assembles and links it).

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

| Command | What it does |
|---|---|
| `devara run prog.tel` | compile and run; the program's exit status is yours |
| `devara build prog.tel -o prog` | write a standalone executable (`prog.exe` on Windows) |
| `devara lex\|parse\|sema\|ir\|opt\|asm prog.tel` | print what that compiler stage produced (add `--json` for machine-readable) |
| `-O0` / `-O1` | `-O1` (default) optimizes; `-O0` is the plain reference code generator. Output is identical at both levels |
| `--target linux\|windows` | cross-assemble for the other OS (default: this OS) |

Exit codes: `0` ok, `1` your program has a compile error or a run-time error, `2` bad command line, `3` the compiler
itself failed (a bug, or no `gcc`).

---

## Look inside the compiler

Every stage can be printed. Here is what happens to `x * x`:

```text
int square charya (int x) {
  x * x ivvu
}
```

```text
$ devara lex examples/squares.tel | head -3
2:1 INT 'int'
2:5 IDENTIFIER 'square'
2:12 CHARYA 'charya'

$ devara ir examples/squares.tel          # neutral IR
function square(x.2:i64) -> i64 {
  entry1:
    t1:i64 = mul x.2, x.2
    ret t1

$ devara asm examples/squares.tel         # x86-64, Windows ABI: the argument arrives in rcx
dv_f_square:
    mov r8, rcx
    imul r8, r8
    mov rax, r8
    ret

$ devara build examples/squares.tel -o squares
$ echo 7 | ./squares                      # a standalone ~340 KB executable; no Python needed
sum of squares:
140
```

Mistakes are caught before anything runs, with a position and a category:

```text
$ echo "total ni chupi" > bad.tel
$ devara run bad.tel
bad.tel:1:1: semantic error [UNDECLARED]: undeclared identifier 'total'
```

and run-time faults are defined, not crashes:

```text
$ devara run dz.tel          # a program that divides by a variable that is 0
devara: runtime error: division by zero
```

---

## How it works

```text
source ─▶ Lexer ─▶ Parser/AST ─▶ Semantic analysis ─▶ typed IR + CFG ─▶ optimizer ─▶ x86-64 asm ─▶ gcc ─▶ .exe / ELF
```

- **Two code generators.** `-O0` keeps everything in stack slots and is the reference. `-O1` adds a linear-scan
  register allocator, a peephole pass, shrink-wrapped callee-saved registers, frameless leaf functions and loop
  rotation. They must print identical output; a differential fuzzer checks that.
- **Two ABIs.** System V on Linux, Microsoft x64 on Windows (PE/COFF via MinGW-w64).
- **Memory.** Arrays are freed on every exit path; `padham` strings are reference counted.
  `DEVARA_RT_STATS=1 ./prog` prints `devara-rt: live=<n>` at exit, and the tests insist it is `0`.
- **A small C runtime** ([`runtime/devara_rt.c`](runtime/devara_rt.c)) does I/O, strings and run-time errors.
- **Identical bytes everywhere.** Output is the same on Linux and Windows (no CRLF translation); input treats `\r\n` as `\n`.

---

## FAQ

**Why Romanized Telugu?** Because Telugu is a verb-final language, and a language whose statements end in the verb
(`... ni chupi`, `... pettu`) reads very differently from the C family, while still compiling to the same machine code.

**Does it need the Telugu script?** No. Source files are plain ASCII/Latin-1 text.

**Is it a toy?** The language is small on purpose. The compiler is not: it targets two operating systems, has an
optimizer and a register allocator, and is checked against an independent interpreter on thousands of generated programs.

**Why did my program say `invalid input`?** `n ni chaduvu` reads one 64-bit integer. `1e9` is not an integer, and neither
is anything bigger than 9,223,372,036,854,775,807.

**`devara run prog.tel < input.txt` says `invalid input` on Windows?** That is a quirk of pyenv's `.bat` shims, not the
compiler. See [Windows notes](#windows-notes).

---

## Tests

```text
pip install -e . -r requirements-dev.txt pytest-xdist
python -m pytest -q -n 4 -m "not slow"                 # fast suite, a couple of minutes
python -m pytest -q -n 4                               # everything, about 30 minutes
python scripts/check_machine.py                        # corpus at -O0/-O1 plus a leak check
python tests/property/campaign.py 1000000 300 50 4     # differential fuzzing against the reference interpreter
```

Last full run on native Windows 11: **6,909 passed, 0 failed, 87 skipped** (86 need AddressSanitizer, 1 needs POSIX
permissions). The compiler package has 94% line-and-branch coverage, and 1,800 random programs compiled to `.exe` matched
the reference interpreter exactly. Linux and Windows both run in CI.

---

## Windows notes

- `devara.cmd` is a launcher that needs no install. Set `DEVARA_PYTHON=<path>\python.exe` to make it use a specific
  interpreter.
- **`devara run prog.tel < input.txt` says `invalid input`, or a failing run prints `The system cannot find the batch
  label specified`?** pyenv-win's `.bat` shims throw away a redirected stdin and mishandle a non-zero exit. Pipe the input
  (`type input.txt | devara run prog.tel`), use `<python dir>\Scripts\devara.exe`, or set `DEVARA_PYTHON`.
- A program that dies with exit code `-1073741571` (`0xC00000FD`) overflowed its 8 MiB stack, exactly as it would on
  Linux. Stack overflow is deliberately not a defined run-time error.
- `DEVARA_CC` picks the C compiler driver (default `gcc`); `DEVARA_RUNNER` prefixes the produced program, which lets you
  cross-check the Windows target on Linux:

```text
DEVARA_CC=x86_64-w64-mingw32-gcc DEVARA_RUNNER=wine WINEDEBUG=-all devara run --target windows prog.tel
```

---

## Documentation

See [`docs/README.md`](docs/README.md) for the index. The essentials:

| | |
|---|---|
| [`docs/DEVARA_LANGUAGE_SPEC_v0.7.md`](docs/DEVARA_LANGUAGE_SPEC_v0.7.md) | the language, with a formal grammar |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | every design decision and ruling (P1–P43, A-001…A-006) |
| [`docs/STAGE_FORMATS.md`](docs/STAGE_FORMATS.md) | what each `devara lex/parse/sema/ir/opt/asm --json` prints |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) | benchmarks |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | how to build, test and send a change |

*Devara is a hobby language. If a Telugu gloss above is wrong, or a keyword reads badly to a native speaker, please open an issue.*
