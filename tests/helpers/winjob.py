"""Windows stand-in for `ulimit -v`: run a program inside a job object with a per-process memory (commit) limit.

POSIX tests cap address space with RLIMIT_AS / `ulimit -v`; Windows has no equivalent, but a job object's
ProcessMemoryLimit makes allocations fail (malloc returns NULL) once the process has committed that much.
"""
from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path

JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x100
JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9
CREATE_SUSPENDED = 0x4


class _Basic(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class _Io(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]


class _Extended(ctypes.Structure):
    _fields_ = [("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


def run_with_memory_limit(exe: Path | str, stdin: bytes, limit_bytes: int, env: dict,
                          timeout: float) -> subprocess.CompletedProcess:
    """Run ``exe`` with at most ``limit_bytes`` of committed memory. The process starts suspended and is resumed
    only after it is in the job, so it never runs uncapped. Windows only."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = ctypes.c_void_p
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = _Extended()
        info.Basic.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = limit_bytes
        if not k32.SetInformationJobObject(job, JOBOBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                           ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, creationflags=CREATE_SUSPENDED)
        try:
            handle = ctypes.c_void_p(int(proc._handle))
            if not k32.AssignProcessToJobObject(job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
            if ntdll.NtResumeProcess(handle) != 0:
                raise OSError("NtResumeProcess failed")
            out, err = proc.communicate(stdin, timeout=timeout)
        except BaseException:
            proc.kill()
            proc.communicate()
            raise
    finally:
        k32.CloseHandle(job)
    return subprocess.CompletedProcess([str(exe)], proc.returncode, out, err)
