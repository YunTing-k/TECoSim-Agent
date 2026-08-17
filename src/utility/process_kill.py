# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.8.17
Description: Cross-platform process tree management (kill whole tree)

Revision:
---------
2026.8.17      Yu Huang      1.0      First implementation

Details:
---------
One source tree, no platform-specific code changes:
- Windows: Job Object (ctypes kernel32) — whole tree killed with a single TerminateJobObject call; KILL_ON_JOB_CLOSE guards
against stray children.
- POSIX:   start_new_session (process group leader) + os.killpg, escalating SIGTERM -> SIGKILL.

Pure stdlib (ctypes). All platform-specific API calls live inside function bodies so that merely importing this module works
on every platform.
"""
import logging
import os
import signal
import subprocess

from src.utility.basic_utils import drain_after_kill

sys_log = logging.getLogger('logger')

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_CREATE_SUSPENDED = 0x4
_JobObjectExtendedLimitInformation = 9


class ManagedProc:
    """A process created with whole-tree kill support (platform-agnostic handle).

    Usage:
        mp = spawn_managed_proc([...], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = mp.proc.communicate(timeout=...)   # normal path
        mp.finish()                                   # release Job handle
        # or on timeout/cancel/error:
        out, err = mp.kill_tree(grace_s=1.0)          # kill whole tree
    """

    __slots__ = ("proc", "_job")

    def __init__(self, proc: subprocess.Popen, job: int | None):
        self.proc = proc
        self._job = job

    def finish(self) -> None:
        """Normal completion path: release the Job handle (Windows).

        With KILL_ON_JOB_CLOSE the handle must stay open while the child may
        still run (closing it would kill the tree); call this only after the
        process has exited. No-op on POSIX.

        Guard: if the process is STILL RUNNING when finish() is called, the
        handle is intentionally leaked (with a warning) instead of closed —
        closing it would kill the whole tree via KILL_ON_JOB_CLOSE, which
        would be an accidental kill. Leaking one handle is safer than killing.
        """
        if os.name != "nt" or self._job is None:
            return
        if self.proc.poll() is None:
            sys_log.warning(f"ManagedProc.finish() called while process (pid={self.proc.pid}) is still running; Job handle "
                            f"leaked to avoid KILL_ON_JOB_CLOSE killing the tree")
            return
        _kernel32().CloseHandle(self._job)
        self._job = None

    def kill_tree(self, grace_s: float = 1.0) -> tuple[bytes, bytes]:
        """Kill the whole process tree, then bounded-drain pipes.

        Returns ``(stdout, stderr)`` bytes — possibly partial or empty.
        """
        if os.name == "nt":
            return _kill_tree_windows(self, grace_s)
        return _kill_tree_posix(self, grace_s)


def spawn_managed_proc(argv: list[str], env: dict | None = None, **kw) -> ManagedProc:
    """Spawn a process whose whole tree can be killed later.

    - Windows: assigns the child to a Job Object right after Popen returns.
      (A CREATE_SUSPENDED + assign + resume dance would eliminate the tiny
      race where the child spawns grandchildren before assignment, but the
      main-thread handle is not exposed by this Python build; the residual
      window is milliseconds, far shorter than typical child initialization.)
    - POSIX:   starts the child in a new session (process group leader).
    Always passes ``stdin=subprocess.DEVNULL`` unless overridden, so children
    never inherit the agent's terminal handle (see rich_pitfalls.md #18).
    """
    kw.setdefault("stdin", subprocess.DEVNULL)
    if os.name == "nt":
        return _spawn_windows(argv, env, kw)
    return _spawn_posix(argv, env, kw)


def _kernel32():
    import ctypes
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _spawn_windows(argv: list[str], env: dict | None, kw: dict) -> ManagedProc:
    import ctypes
    from ctypes import wintypes

    kernel32 = _kernel32()

    class JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IOCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", wintypes.ULARGE_INTEGER),
            ("WriteOperationCount", wintypes.ULARGE_INTEGER),
            ("OtherOperationCount", wintypes.ULARGE_INTEGER),
            ("ReadTransferCount", wintypes.ULARGE_INTEGER),
            ("WriteTransferCount", wintypes.ULARGE_INTEGER),
            ("OtherTransferCount", wintypes.ULARGE_INTEGER),
        ]

    class JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JobObjectBasicLimitInformation),
            ("IoInfo", IOCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            proc = subprocess.Popen(argv, env=env, **kw)
        except Exception:
            kernel32.CloseHandle(job)
            raise
        if not kernel32.AssignProcessToJobObject(job, getattr(proc, "_handle")):
            proc.kill()
            kernel32.CloseHandle(job)
            raise ctypes.WinError(ctypes.get_last_error())
        return ManagedProc(proc, job)
    except Exception:
        kernel32.CloseHandle(job)
        raise


def _spawn_posix(argv: list[str], env: dict | None, kw: dict) -> ManagedProc:
    proc = subprocess.Popen(argv, env=env, start_new_session=True, **kw)
    return ManagedProc(proc, None)


def _kill_tree_windows(mp: ManagedProc, grace_s: float) -> tuple[bytes, bytes]:
    # noinspection PyProtectedMember
    kernel32 = _kernel32()
    if mp._job is not None:
        kernel32.TerminateJobObject(mp._job, 1)  # kill the whole tree at once
        kernel32.CloseHandle(mp._job)
        mp._job = None
    return drain_after_kill(mp.proc, grace_s)


def _kill_tree_posix(mp: ManagedProc, grace_s: float) -> tuple[bytes, bytes]:
    proc = mp.proc
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return drain_after_kill(proc, grace_s)
    try:
        os.killpg(pgid, signal.SIGTERM)  # graceful, whole group
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)  # escalate
        except ProcessLookupError:
            pass
        proc.wait()
    except ProcessLookupError:
        pass
    return drain_after_kill(proc, grace_s)
