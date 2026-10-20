"""Source-level debugger for Devara (``devara debug prog.tel``).

It runs the program on the reference interpreter (``compiler/interp.py``) and stops it through the interpreter's
``hook``: before every statement, and around every user function call. Everything is therefore expressed in terms of
the ``.tel`` source: lines, statements, variables and calls. The compiled program is not involved.

Stepping is per *statement*: ``step`` stops before the next statement that runs (entering calls), ``next`` stops at the
next statement of the same or an outer call, ``finish`` runs until the current function returns.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from compiler import driver, serialize
from compiler.interp import Arr, Interp, RuntimeErr, StepLimit, fmt_g

PROMPT = "(devara-db) "
DEFAULT_MAX_STEPS = 50_000_000
_STMT_NODES = {n[2:] for n in dir(Interp) if n.startswith("s_")} - {"Block"}


class _Quit(Exception):
    """Raised inside the interpreter to abandon the program when the user quits."""


@dataclass(eq=False)
class Frame:
    name: str
    call_line: int                         # line of the call in the caller (0 for the main program)
    stack: list                            # live scope list of this frame
    scopes: list = field(default_factory=list)   # snapshot taken before each statement (survives unwinding)
    line: int = 0


@dataclass(eq=False)
class Watch:
    num: int
    text: str
    node: dict
    frame: Frame
    last: str


def fmt_scalar(ty: str, x) -> str:
    if ty == "int":
        return str(x)
    if ty == "float":
        return fmt_g(x)
    if ty == "bool":
        return "nijam" if x else "abaddham"
    if ty == "char":
        c = x & 0xFF
        return f"{c} '{chr(c)}'" if 32 <= c < 127 else str(c)
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fmt_array(a: Arr, limit: int = 24) -> str:
    def rec(depth: int, off: int) -> str:
        n = a.dims[depth]
        if n is None:
            return "[...]"
        stride = 1
        for d in a.dims[depth + 1:]:
            stride *= d
        parts = []
        for i in range(min(n, limit)):
            if depth + 1 == len(a.dims):
                parts.append(fmt_scalar(a.elem, a.data[a.offset + off + i]))
            else:
                parts.append(rec(depth + 1, off + i * stride))
        if n > limit:
            parts.append(f"... ({n} elements)")
        return "[" + ", ".join(parts) + "]"

    return rec(0, 0)


def fmt_cell(cell) -> str:
    if isinstance(cell, Arr):
        return fmt_array(cell)
    return fmt_scalar(cell[0], cell[1])


def fmt_value(v) -> str:
    """Format an interpreter value (a pair (type, value), or ("array", Arr))."""
    if v is None:
        return "(void)"
    return fmt_array(v[1]) if v[0] == "array" else fmt_scalar(v[0], v[1])


def statement_lines(program: dict) -> list[int]:
    """Lines on which a statement starts and that the interpreter reports to the hook (so can hold a breakpoint)."""
    lines: set[int] = set()

    def walk(n, top=False):
        if isinstance(n, dict):
            kind = n.get("_node")
            if kind == "FunctionDeclaration":
                walk(n["body"])
                return
            if kind in _STMT_NODES and not (top and kind == "Declaration"):
                lines.add(n["span"]["start_line"])
            for k, v in n.items():
                if k != "span":
                    walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)

    for item in program["items"]:
        walk(item, top=True)
    return sorted(lines)


class Debugger:
    def __init__(self, program: dict, source: str, filename: str, stdin: bytes = b"",
                 commands=None, max_steps: int | None = DEFAULT_MAX_STEPS, out=None):
        self.program = program
        self.src_lines = source.split("\n")
        self.filename = filename
        self.cmds = commands                    # None: read from stdin (prompting); else an iterator of lines
        self.out = out or sys.stdout
        self.interp = Interp(stdin, max_steps, hook=self)
        self.valid_lines = statement_lines(program)
        self.frames: list[Frame] = [Frame("main", 0, self.interp.stack)]
        self.sel = 0                            # selected frame, counted from the innermost
        self.breaks: dict[int, tuple[int, str | None]] = {}     # number -> (line, condition text)
        self.watches: list[Watch] = []
        self.next_id = 1
        self.mode = "step"                      # step | next | continue | finish
        self.depth0 = 0
        self.finish_depth = 0
        self.flushed = 0
        self.last_cmd = ""
        self.prev_pos: tuple[int, int] | None = None   # (depth, line) of the previously executed statement
        self.shown_frame: Frame | None = None
        self.dead = False
        self.in_eval = False
        self.list_next = 0
        self.interactive = commands is None and sys.stdin.isatty()

    # ------------------------------------------------------------------ output
    def say(self, text: str = "") -> None:
        self.flush_program()
        self.out.write(text + "\n")
        self.out.flush()

    def flush_program(self) -> None:
        buf = self.interp.out
        if len(buf) > self.flushed:
            self.out.flush()
            data = bytes(buf[self.flushed:])
            self.flushed = len(buf)
            try:
                self.out.buffer.write(data)
                self.out.buffer.flush()
            except AttributeError:               # an in-memory stream (tests): decode instead
                self.out.write(data.decode("latin-1"))

    def source_line(self, n: int) -> str:
        return self.src_lines[n - 1] if 1 <= n <= len(self.src_lines) else ""

    def show_line(self, n: int, marker: str = "=>") -> None:
        self.say(f"{marker} {n:>4} | {self.source_line(n)}")

    # ------------------------------------------------------------------ the interpreter's hook
    def before_stmt(self, it: Interp, stmt: dict) -> None:
        if stmt["_node"] == "Block" or self.in_eval:
            return
        fr = self.frames[-1]
        fr.stack = it.stack
        fr.scopes = list(it.stack)
        line = stmt["span"]["start_line"]
        fr.line = line
        pos = (len(self.frames), line)
        repeat = pos == self.prev_pos
        self.prev_pos = pos
        reason = self.check_watches()
        if reason is None:
            reason = self.stop_reason(line, repeat)
        if reason is not None:
            self.stop(reason)

    def stop_reason(self, line: int, repeat: bool) -> str | None:
        depth = len(self.frames)
        if self.mode == "step":
            return ""
        if self.mode == "next" and depth <= self.depth0:
            return ""
        if self.mode in ("continue", "next", "finish") and not repeat:
            for num, (bl, cond) in self.breaks.items():
                if bl != line:
                    continue
                if cond is not None:
                    ok, shown = self.try_eval(cond)
                    if not ok:
                        return f"Breakpoint {num}: condition error: {shown}"
                    if shown in ("abaddham", "0", "0.0"):
                        continue
                return f"Breakpoint {num}, line {line}"
        return None

    def on_call(self, it: Interp, name: str, call: dict, caller_stack: list) -> None:
        if self.in_eval:
            return
        self.frames[-1].stack = caller_stack
        self.frames.append(Frame(name, call["span"]["start_line"], it.stack))

    def on_return(self, it: Interp, name: str, value) -> None:
        if self.in_eval:
            return
        self.frames.pop()
        if self.mode == "finish" and len(self.frames) < self.finish_depth:
            self.prev_pos = None
            self.stop(f"Run till exit: {name} returned {fmt_value(value)}")

    # ------------------------------------------------------------------ evaluating expressions
    def parse_expr(self, text: str):
        toks, diags = driver.run_lex(text + " ni chupi\n", "<expr>")
        prog = None
        if not diags:
            prog, diags = driver.run_parse(toks, "<expr>")
        if diags:
            raise ValueError(diags[0].message)
        items = serialize.to_data(prog)["items"]
        if len(items) != 1 or items[0]["_node"] != "Output":
            raise ValueError("not an expression")
        return items[0]["value"]

    def eval_node(self, node: dict, frame: Frame):
        it = self.interp
        saved_stack, saved_hook, saved_in = it.stack, it.hook, self.in_eval
        saved_steps, saved_max = it.steps, it.max_steps
        it.stack, it.hook, self.in_eval, it.max_steps = frame.scopes or frame.stack, None, True, None
        try:
            return it.eval(node)
        except KeyError as e:
            raise ValueError(f"no symbol {e.args[0]!r} in the current context") from None
        except RuntimeErr as e:
            raise ValueError(f"runtime error: {e}") from None
        finally:
            it.stack, it.hook, self.in_eval = saved_stack, saved_hook, saved_in
            it.steps, it.max_steps = saved_steps, saved_max

    def try_eval(self, text: str, frame: Frame | None = None) -> tuple[bool, str]:
        try:
            node = self.parse_expr(text)
            return True, fmt_value(self.eval_node(node, frame or self.frames[-1]))
        except ValueError as e:
            return False, str(e)

    def check_watches(self) -> str | None:
        hits = []
        for w in list(self.watches):
            if w.frame not in self.frames:
                self.watches.remove(w)
                self.say(f"Watchpoint {w.num} ({w.text}) deleted: its function has returned")
                continue
            try:
                now = fmt_value(self.eval_node(w.node, w.frame))
            except ValueError as e:
                now = f"<{e}>"
            if now != w.last:
                hits.append(f"Watchpoint {w.num}: {w.text}\n  old: {w.last}\n  new: {now}")
                w.last = now
        return "\n".join(hits) if hits else None

    # ------------------------------------------------------------------ stopping and the command loop
    def stop(self, reason: str) -> None:
        self.sel = 0
        fr = self.frames[-1]
        if reason:
            self.say(reason)
        if fr is not self.shown_frame or reason:
            self.say(self.describe_frame(len(self.frames) - 1))
        self.shown_frame = fr
        self.show_line(fr.line)
        self.list_next = max(fr.line - 4, 1)
        self.repl()

    def describe_frame(self, idx: int) -> str:
        fr = self.frames[idx]
        args = ""
        f = self.interp.funcs.get(fr.name) if fr.name != "main" else None
        if f:
            scope = (fr.scopes or fr.stack or [{}])[0]
            args = ", ".join(f"{p['name']['name']}={fmt_cell(scope[p['name']['name']])}"
                             for p in f["parameters"] if p["name"]["name"] in scope)
        return f"{fr.name}({args}) at {self.filename}:{fr.line}"

    def repl(self) -> None:
        while True:
            line = self.read_command()
            if line is None:
                raise _Quit()
            line = line.strip() or self.last_cmd
            if not line:
                continue
            self.last_cmd = line
            if self.command(line):
                return

    def read_command(self) -> str | None:
        self.flush_program()
        if self.cmds is None:
            self.out.write(PROMPT)
            self.out.flush()
            text = sys.stdin.readline()
            if text == "":
                self.out.write("\n")
                return None
            return text
        try:
            text = next(self.cmds).rstrip("\n")
        except StopIteration:
            return None
        self.out.write(PROMPT + text + "\n")
        return text

    def frame_at(self) -> Frame:
        return self.frames[len(self.frames) - 1 - self.sel]

    # ------------------------------------------------------------------ commands
    def command(self, line: str) -> bool:
        """Run one command; True when execution should resume."""
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        w = word.lower()
        table = {
            "help": self.c_help, "h": self.c_help, "?": self.c_help,
            "print": self.c_print, "p": self.c_print, "inspect": self.c_print,
            "break": self.c_break, "b": self.c_break,
            "delete": self.c_delete, "d": self.c_delete,
            "watch": self.c_watch,
            "backtrace": self.c_bt, "bt": self.c_bt, "where": self.c_bt,
            "frame": self.c_frame, "f": self.c_frame,
            "up": self.c_up, "down": self.c_down,
            "info": self.c_info, "i": self.c_info,
            "list": self.c_list, "l": self.c_list,
        }
        if w in ("quit", "q", "exit"):
            raise _Quit()
        if w in table:
            table[w](rest)
            return False
        resume = {"continue": "continue", "c": "continue", "run": "continue", "r": "continue",
                  "step": "step", "s": "step", "next": "next", "n": "next", "finish": "finish", "fin": "finish"}
        if w in resume:
            if self.dead:
                self.say("The program is not being run.")
                return False
            self.mode = resume[w]
            self.depth0 = len(self.frames) - self.sel
            if self.mode == "finish":
                if len(self.frames) == 1:
                    self.say('"finish" is not meaningful in the outermost frame.')
                    return False
                self.finish_depth = len(self.frames) - self.sel
            return True
        self.say(f"Undefined command: {word!r}. Try 'help'.")
        return False

    def c_help(self, _rest: str) -> None:
        self.say("""Commands (an empty line repeats the last one):
  step, s            run the next statement, entering function calls
  next, n            run the next statement, stepping over function calls
  finish, fin        run until the current function returns
  continue, c        run until a breakpoint or watchpoint (run, r: same)
  break N [if EXPR]  stop before the statement on line N (when EXPR is true)
  watch EXPR         stop when the value of EXPR changes
  delete [N]         delete breakpoint/watchpoint number N (all if omitted)
  print EXPR, p      evaluate any Devara expression in the selected frame
  backtrace, bt      show the call stack; frame N / up / down select a frame
  info locals|args|globals|break|frame
  list [N | A,B]     show source lines
  quit, q""")

    def c_print(self, rest: str) -> None:
        if not rest:
            self.say("print what? give an expression, e.g.  p total + 1")
            return
        ok, shown = self.try_eval(rest, self.frame_at())
        self.say(shown if ok else f"error: {shown}")

    def c_break(self, rest: str) -> None:
        spec, _, cond = rest.partition(" if ")
        spec = spec.strip()
        if not spec:
            line = self.frame_at().line
        else:
            try:
                line = int(spec)
            except ValueError:
                self.say("usage: break LINE [if EXPR]")
                return
        later = [n for n in self.valid_lines if n >= line]
        if not later:
            self.say(f"No statement at or after line {line}.")
            return
        cond = cond.strip() or None
        if cond is not None:
            try:
                self.parse_expr(cond)
            except ValueError as e:
                self.say(f"bad condition: {e}")
                return
        num = self.next_id
        self.next_id += 1
        self.breaks[num] = (later[0], cond)
        extra = f" if {cond}" if cond else ""
        moved = f" (no statement on line {line})" if later[0] != line else ""
        self.say(f"Breakpoint {num} at line {later[0]}{extra}{moved}")

    def c_watch(self, rest: str) -> None:
        if not rest:
            self.say("usage: watch EXPR")
            return
        fr = self.frame_at()
        try:
            node = self.parse_expr(rest)
            cur = fmt_value(self.eval_node(node, fr))
        except ValueError as e:
            self.say(f"error: {e}")
            return
        num = self.next_id
        self.next_id += 1
        self.watches.append(Watch(num, rest, node, fr, cur))
        self.say(f"Watchpoint {num}: {rest}   (now {cur})")

    def c_delete(self, rest: str) -> None:
        if not rest:
            self.breaks.clear()
            self.watches.clear()
            self.say("Deleted all breakpoints and watchpoints.")
            return
        try:
            num = int(rest)
        except ValueError:
            self.say("usage: delete [N]")
            return
        if self.breaks.pop(num, None) is not None:
            self.say(f"Deleted breakpoint {num}")
            return
        for w in self.watches:
            if w.num == num:
                self.watches.remove(w)
                self.say(f"Deleted watchpoint {num}")
                return
        self.say(f"No breakpoint or watchpoint number {num}.")

    def c_bt(self, _rest: str) -> None:
        for i in range(len(self.frames) - 1, -1, -1):
            fr = self.frames[i]
            mark = "*" if len(self.frames) - 1 - i == self.sel else " "
            self.say(f"{mark}#{len(self.frames) - 1 - i}  {self.describe_frame(i)}"
                     + (f"   called from line {fr.call_line}" if fr.call_line else ""))

    def select(self, n: int) -> None:
        if not 0 <= n < len(self.frames):
            self.say(f"No frame number {n}.")
            return
        self.sel = n
        fr = self.frame_at()
        self.say(f"#{n}  {self.describe_frame(len(self.frames) - 1 - n)}")
        self.show_line(fr.line, " >" if n else "=>")

    def c_frame(self, rest: str) -> None:
        try:
            self.select(int(rest) if rest else self.sel)
        except ValueError:
            self.say("usage: frame N")

    def c_up(self, _rest: str) -> None:
        if self.sel + 1 < len(self.frames):
            self.select(self.sel + 1)
        else:
            self.say("Initial frame selected; you cannot go up.")

    def c_down(self, _rest: str) -> None:
        if self.sel > 0:
            self.select(self.sel - 1)
        else:
            self.say("Bottom (innermost) frame selected; you cannot go down.")

    def c_info(self, rest: str) -> None:
        what = rest.split()[0].lower() if rest else ""
        fr = self.frame_at()
        scopes = fr.scopes or fr.stack
        if what in ("locals", "local"):
            shown = False
            for depth, sc in enumerate(reversed(scopes)):
                is_args = fr.name != "main" and depth == len(scopes) - 1
                for name, cell in sc.items():
                    if is_args and self.is_param(fr, name):
                        continue
                    self.say(f"{name} = {fmt_cell(cell)}")
                    shown = True
            if not shown:
                self.say("No locals.")
        elif what in ("args", "arg"):
            f = self.interp.funcs.get(fr.name)
            if fr.name == "main" or not f:
                self.say("No arguments.")
                return
            for p in f["parameters"]:
                n = p["name"]["name"]
                self.say(f"{n} = {fmt_cell(scopes[0][n])}" if scopes and n in scopes[0] else f"{n} = <unset>")
        elif what in ("globals", "global"):
            if not self.interp.globals:
                self.say("No globals.")
            for name, cell in self.interp.globals.items():
                self.say(f"{name} = {fmt_cell(cell)}")
        elif what in ("break", "breakpoints", "watch", "watchpoints"):
            if not self.breaks and not self.watches:
                self.say("No breakpoints or watchpoints.")
            for num, (line, cond) in self.breaks.items():
                self.say(f"{num}  breakpoint  line {line}" + (f"  if {cond}" if cond else ""))
            for w in self.watches:
                self.say(f"{w.num}  watchpoint  {w.text}   (now {w.last})")
        elif what == "frame":
            self.c_frame("")
        else:
            self.say("info what? locals | args | globals | break | frame")

    def is_param(self, fr: Frame, name: str) -> bool:
        f = self.interp.funcs.get(fr.name)
        return bool(f) and any(p["name"]["name"] == name for p in f["parameters"])

    def c_list(self, rest: str) -> None:
        try:
            if "," in rest:
                a, b = (int(x) for x in rest.split(",", 1))
            elif rest:
                a = max(int(rest) - 4, 1)
                b = a + 9
            else:
                a = self.list_next or 1
                b = a + 9
        except ValueError:
            self.say("usage: list [N | A,B]")
            return
        b = min(b, len(self.src_lines))
        if a > b:
            self.say("Line number out of range.")
            return
        cur = self.frame_at().line
        for n in range(a, b + 1):
            self.say(f"{'=>' if n == cur else '  '} {n:>4} | {self.source_line(n)}")
        self.list_next = b + 1

    # ------------------------------------------------------------------ driving the program
    def run(self) -> int:
        self.say(f"Devara debugger: {self.filename}  (type 'help'; the program is stopped before its first statement)")
        status = 0
        try:
            try:
                self.interp.run_program(self.program)
                self.stop_watch_at_end()
                self.say("Program exited normally.")
            except RuntimeErr as e:
                status = 1
                self.after_failure(f"Runtime error: {e}")
            except StepLimit:
                status = 1
                self.after_failure(f"Stopped: the program ran more than {self.interp.max_steps} statements/expressions "
                                   "(possible infinite loop).")
        except _Quit:
            self.flush_program()
            return status
        self.flush_program()
        return status

    def stop_watch_at_end(self) -> None:
        reason = self.check_watches()
        if reason:
            self.say(reason)

    def after_failure(self, message: str) -> None:
        self.dead = True
        fr = self.frames[-1]
        self.say(message)
        self.say(self.describe_frame(len(self.frames) - 1))
        self.show_line(fr.line)
        self.say("The program has stopped; you can inspect variables (print, info, bt, list) and then quit.")
        self.sel = 0
        self.repl_dead()

    def repl_dead(self) -> None:
        try:
            self.repl()
        except _Quit:
            pass


def debug(program: dict, source: str, filename: str, stdin: bytes = b"", commands=None,
          max_steps: int | None = DEFAULT_MAX_STEPS, out=None) -> int:
    """Debug ``program`` (the parser's AST as plain data, i.e. ``serialize.to_data``). Returns 0, or 1 after a run-time error."""
    return Debugger(program, source, filename, stdin, commands, max_steps, out).run()
