# The Devara debugger

```text
devara debug prog.tel [--input FILE] [--commands FILE] [--max-steps N]
```

`devara debug` runs your program under a source-level debugger. It stops before the first statement and gives you a
`(devara-db)` prompt, where you set breakpoints and watchpoints, step through the program one statement at a time, look
at the call stack, and print any variable or expression.

It works in terms of your `.tel` file: lines, statements, variables, calls. Nothing is compiled; the program is run
by the reference interpreter (`compiler/interp.py`), the same engine that the test suite uses to check compiled programs.
`-O0` and `-O1` output are checked against it on thousands of programs, so what you see is what the executable does.
It cannot show you a bug that exists only in the generated machine code.

Compile errors are reported exactly as `devara run` reports them, and the debugger does not start.

## A session

```text
$ echo 4 > in.txt
$ devara debug examples/factorial.tel --input in.txt
Devara debugger: examples/factorial.tel  (type 'help'; the program is stopped before its first statement)
main() at examples/factorial.tel:8
=>    8 | n ni chaduvu
(devara-db) b 3 if n == 2
Breakpoint 1 at line 3 if n == 2
(devara-db) c
Breakpoint 1, line 3
fact(n=2) at examples/factorial.tel:3
=>    3 |   n <= 1 ayite { 1 ivvu }
(devara-db) bt
*#0  fact(n=2) at examples/factorial.tel:3   called from line 4
 #1  fact(n=3) at examples/factorial.tel:4   called from line 4
 #2  fact(n=4) at examples/factorial.tel:4   called from line 9
 #3  main() at examples/factorial.tel:9
(devara-db) fin
Run till exit: fact returned 2
fact(n=3) at examples/factorial.tel:4
=>    4 |   n * fact(n - 1) ivvu
(devara-db) p fact(5)
120
(devara-db) q
```

## Commands

An empty line repeats the previous command. Commands may be abbreviated as shown.

| Command | What it does |
|---|---|
| `step`, `s` | run the next statement; enter a function call if there is one |
| `next`, `n` | run the next statement; run a function call to completion |
| `finish`, `fin` | run until the current function returns and show the value it returned |
| `continue`, `c` (`run`, `r`) | run until a breakpoint, a watchpoint, an error or the end |
| `break N [if EXPR]`, `b` | stop before the statement on line N, only when EXPR is true if given. With no N: the current line. A line with no statement moves the breakpoint to the next line that has one |
| `watch EXPR` | stop whenever the value of EXPR changes, showing the old and new value |
| `delete [N]`, `d` | delete breakpoint or watchpoint N; with no number, delete all |
| `print EXPR`, `p` | evaluate any Devara expression in the selected frame: `p total + 1`, `p a[i]`, `p podavu(s)`, even `p fact(5)` |
| `backtrace`, `bt`, `where` | the call stack, innermost first, with the line each call was made from |
| `frame N`, `up`, `down` | select a frame; `print`, `info` and `list` then refer to it |
| `info locals` / `args` / `globals` / `break` / `frame` | variables of the selected frame, function arguments, global variables, breakpoints and watchpoints |
| `list [N]`, `list A,B`, `l` | show source lines around N, between A and B, or the next ten |
| `help`, `quit` (`q`) | |

Values print as the program would show them, with the type made visible where it helps: `nijam`/`abaddham` for booleans,
`120 'x'` for a `char`, `"text"` for a `padham`, `[1, 2, 3]` and `[[0, 0], [5, 0]]` for arrays.

## What a "step" is

Stepping is by **statement**. A loop header is one statement, and each statement in the loop body is one more, every
time round. A line with several statements (`prati i 1 nundi 4 varaku { i ni chupi }`) therefore stops more than once.
Top-level variable declarations (`int x`) are not statements that run, so they do not stop; function declarations do
not either.

## Errors and runaway programs

A run-time error does not end the session. The debugger reports it, stays on the line that failed, and lets you look
around (`print`, `info locals`, `bt`, `list`) before you quit; `step`/`next`/`continue` say the program is no longer
running. The exit status is then 1, like `devara run`.

A program that never stops is cut off after 50,000,000 evaluation steps (change it with `--max-steps`), reported as a
likely infinite loop, and can be inspected in the same way.

## Input and scripting

The terminal belongs to the debugger, so the program's own input (`x ni chaduvu`) comes from `--input FILE`. Without it
the program sees empty input, and a program that reads gets `invalid input`.

Commands normally come from the terminal. `--commands FILE`, or a pipe on standard input, run a scripted session; the
commands are echoed after the prompt so the output reads like a transcript. When the commands run out, the debugger
quits.

```text
$ printf 'b 11 if i == 3\nc\np i\np a\nq\n' | devara debug examples/fibonacci.tel --input six.txt
```

Programs that print output while running are shown as they print, between the prompts.
