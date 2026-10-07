"""Target / ABI description (object format and calling convention).

Everything that differs between the supported platforms lives here so the code
generator itself stays ABI-neutral:

* ``linux``   -- System V AMD64 ABI, ELF, GNU ``as`` (``.intel_syntax noprefix``).
* ``windows`` -- Microsoft x64 ABI, PE/COFF, MinGW-w64 ``gcc``/``as``.

The runtime helpers are all non-variadic with at most two scalar arguments, so
no varargs handling (``al`` = number of vector registers, home area for
variadics) is ever required on either ABI.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

__all__ = ["Target", "LINUX", "WINDOWS", "TARGETS", "host_target", "get_target"]


@dataclass(frozen=True)
class Target:
    name: str
    exe_suffix: str
    # argument passing
    int_args: tuple[str, ...]
    float_args: tuple[str, ...]
    positional: bool            # Win64: argument i uses register i of *either* class
    shadow_space: int           # bytes the caller reserves above the return address
    # register classes (rbp is the frame pointer and handled separately)
    callee_saved_int: tuple[str, ...]
    callee_saved_xmm: tuple[str, ...]
    # allocatable caller-saved registers (the rest -- rax, rcx, rdx, r10, xmm0, xmm1 -- are scratch)
    alloc_caller_int: tuple[str, ...]
    alloc_caller_xmm: tuple[str, ...]
    page_probe: bool            # frames > 4 KiB must be probed (Windows guard page)
    rodata_directive: str
    elf: bool

    @property
    def is_windows(self) -> bool:
        return self.name == "windows"

    # ── assembly text ──

    def preamble(self) -> list[str]:
        return ["    .intel_syntax noprefix", "    .text"]

    def function_header(self, symbol: str, *, export: bool = True) -> list[str]:
        out = ["    .p2align 4"]
        if export:
            out.append(f"    .globl {symbol}")
        if not self.elf:
            out += [f"    .def {symbol}", "    .scl 2", "    .type 32", "    .endef"]
        out.append(f"{symbol}:")
        return out

    def rodata(self) -> list[str]:
        return [f"    {self.rodata_directive}", "    .balign 8"]

    def footer(self) -> list[str]:
        if self.elf:
            return ['    .section .note.GNU-stack,"",@progbits']
        return []

    def probe_stack(self, frame: int) -> list[str]:
        """Instructions making a ``frame``-byte allocation safe (Windows only)."""
        if self.page_probe and frame > 4096:
            return [f"    mov rax, {frame}", "    call ___chkstk_ms"]
        return []


LINUX = Target(
    name="linux", exe_suffix="",
    int_args=("rdi", "rsi", "rdx", "rcx", "r8", "r9"),
    float_args=tuple(f"xmm{i}" for i in range(8)),
    positional=False, shadow_space=0,
    callee_saved_int=("rbx", "r12", "r13", "r14", "r15"),
    callee_saved_xmm=(),
    alloc_caller_int=("rsi", "rdi", "r8", "r9", "r11"),
    alloc_caller_xmm=tuple(f"xmm{i}" for i in range(2, 16)),
    page_probe=False,
    rodata_directive=".section .rodata",
    elf=True,
)

WINDOWS = Target(
    name="windows", exe_suffix=".exe",
    int_args=("rcx", "rdx", "r8", "r9"),
    float_args=("xmm0", "xmm1", "xmm2", "xmm3"),
    positional=True, shadow_space=32,
    callee_saved_int=("rbx", "rdi", "rsi", "r12", "r13", "r14", "r15"),
    callee_saved_xmm=tuple(f"xmm{i}" for i in range(6, 16)),
    alloc_caller_int=("r8", "r9", "r11"),
    alloc_caller_xmm=tuple(f"xmm{i}" for i in range(2, 6)),
    page_probe=True,
    rodata_directive='.section .rdata,"dr"',
    elf=False,
)

TARGETS = {"linux": LINUX, "windows": WINDOWS}


def host_target() -> Target:
    return WINDOWS if (sys.platform in ("win32", "cygwin", "msys") or os.name == "nt") else LINUX


def get_target(name: "str | Target | None") -> Target:
    if name is None:
        return host_target()
    if isinstance(name, Target):
        return name
    try:
        return TARGETS[name]
    except KeyError:
        raise ValueError(f"unknown target {name!r} (expected one of: {', '.join(TARGETS)})") from None
