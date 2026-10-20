"""Textual peephole pass over one function's assembly lines (-O1).

Rules (each is a local, flag- and register-safe rewrite):

* ``mov r, r`` / ``movaps x, x`` are dropped;
* a store followed by a reload of the same stack slot becomes just the store (same register) or
  the store plus a register move;
* ``jmp L`` immediately before ``L:`` is dropped, and so is dead code between an unconditional
  transfer (``jmp``/``ret``) and the next label;
* ``jcc A; jmp B; A:`` becomes ``jncc B; A:``;
* ``cmp r, 0`` becomes ``test r, r``.
"""

from __future__ import annotations

import re

_MOV = re.compile(r"^    mov (\w+), (\w+)$")
_MOVAPS = re.compile(r"^    movaps (xmm\d+), (xmm\d+)$")
_STORE = re.compile(r"^    (mov|movsd) (QWORD PTR \[rbp [-+] \d+\]), (\w+)$")
_LOAD = re.compile(r"^    (mov|movsd) (\w+), (QWORD PTR \[rbp [-+] \d+\])$")
_JMP = re.compile(r"^    jmp (\.L\w+)$")
_JCC = re.compile(r"^    j(n?[a-z]+) (\.L\w+)$")
_CMP0 = re.compile(r"^    cmp (\w+), 0$")
_LABEL = re.compile(r"^(\.L\w+):$")

def _prev(out: list[str]) -> int:
    """Index of the last line that is not a ``.loc`` directive (those never get in the way of a rewrite)."""
    p = len(out) - 1
    while p >= 0 and out[p].startswith("    .loc "):
        p -= 1
    return p


_INV = {"e": "ne", "ne": "e", "l": "ge", "ge": "l", "le": "g", "g": "le",
        "a": "be", "be": "a", "ae": "b", "b": "ae", "z": "nz", "nz": "z"}
_GPR = {"rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp", *(f"r{n}" for n in range(8, 16))}


def _is_gpr(name: str) -> bool:
    return name in _GPR


def peephole(lines: list[str]) -> list[str]:
    for _ in range(4):
        new = _pass(lines)
        if new == lines:
            break
        lines = new
    return lines


def _pass(lines: list[str]) -> list[str]:
    out: list[str] = []
    dead = False                       # after jmp/ret, until the next label
    n = len(lines)
    k = 0
    while k < n:
        ln = lines[k]
        k += 1
        if _LABEL.match(ln):
            dead = False
            out.append(ln)
            continue
        if dead:
            if not ln.startswith("    ."):          # keep directives, drop instructions
                continue
        m = _MOV.match(ln)
        if m and m.group(1) == m.group(2):
            continue
        m = _MOVAPS.match(ln)
        if m and m.group(1) == m.group(2):
            continue
        m = _CMP0.match(ln)
        if m and _is_gpr(m.group(1)):
            ln = f"    test {m.group(1)}, {m.group(1)}"
        # store then reload of the same slot
        m = _LOAD.match(ln)
        if m and out:
            s = _STORE.match(out[_prev(out)]) if _prev(out) >= 0 else None
            if s and s.group(1) == m.group(1) and s.group(2) == m.group(3):
                if s.group(3) == m.group(2):
                    continue
                if m.group(1) == "mov" and _is_gpr(s.group(3)) and _is_gpr(m.group(2)):
                    out.append(f"    mov {m.group(2)}, {s.group(3)}")
                    continue
        # jump to the immediately following label
        m = _JMP.match(ln)
        if m:
            j = k
            falls = False
            while j < n and _LABEL.match(lines[j]):
                if lines[j][:-1] == m.group(1):
                    falls = True
                    break
                j += 1
            if falls:
                continue
            # jcc A ; jmp B ; A:   ->   jncc B ; A:
            if out and _prev(out) >= 0:
                c = _JCC.match(out[_prev(out)])
                if c and c.group(1) in _INV and k < n and lines[k] == f"{c.group(2)}:":
                    out[_prev(out)] = f"    j{_INV[c.group(1)]} {m.group(1)}"
                    continue
            dead = True
            out.append(ln)
            continue
        if ln == "    ret":
            dead = True
        out.append(ln)
    return out
