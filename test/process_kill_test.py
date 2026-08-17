# -*- coding: utf-8 -*-
"""
Unit tests for process_kill — cross-platform process tree management.

Covers:
- BUG REPRODUCTION: plain Popen + kill(direct child) LEAKS the grandchild
  (the exact bug kill_tree fixes) — asserted alive before the fix exists.
- spawn_managed_proc + kill_tree: the whole tree dies (grandchild included).
- kill_tree bounded drain returns partial output.
- finish(): normal completion path releases resources without killing.
- POSIX branch (mocked os.name="posix"): start_new_session + killpg sequence.

Real-process tests use sys.executable (cross-platform, no bash dependency).

Run:  python test/process_kill_test.py
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging
logging.basicConfig(level=logging.CRITICAL)

import io
import time
import signal
import tempfile
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from src.utility.process_kill import spawn_managed_proc


def _is_windows() -> bool:
    return os.name == "nt"


def _pid_alive(pid: int) -> bool:
    """Check whether a process with the given pid is alive (cross-platform)."""
    if _is_windows():
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=10)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _spawn_child_with_grandchild(pid_file: str) -> subprocess.Popen:
    """child starts a grandchild (writes its pid to pid_file, sleeps 30s),
    then the child itself sleeps 30s. Returns the child process."""
    gc_code = (f"import os,time;"
               f"open({pid_file!r},'w').write(str(os.getpid()));"
               f"time.sleep(30)")
    child_code = (f"import subprocess,sys,time;"
                  f"subprocess.Popen([sys.executable,'-u','-c',{gc_code!r}],"
                  f"stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                  f"time.sleep(30)")
    return subprocess.Popen([sys.executable, "-u", "-c", child_code],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wait_grandchild_pid(pid_file: str, timeout: float = 8.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                return int(f.read().strip())
        time.sleep(0.1)
    raise AssertionError("grandchild pid file was never created")


class TestGrandchildLeakBugReproduction(unittest.TestCase):
    """The bug this module fixes, made visible: killing only the direct child
    leaves the grandchild running. Uses PLAIN Popen (legacy behavior)."""

    def test_legacy_kill_leaks_grandchild(self):
        """Regression proof: with plain Popen + kill(direct child), the
        grandchild is STILL ALIVE afterwards."""
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = os.path.join(tmp, "gc.pid")
            child = _spawn_child_with_grandchild(pid_file)
            try:
                gc_pid = _wait_grandchild_pid(pid_file)
                # legacy behavior: kill only the direct child
                child.kill()
                child.wait()
                time.sleep(0.5)  # give the system a moment to settle
                self.assertTrue(
                    _pid_alive(gc_pid),
                    "grandchild must survive a direct-child-only kill "
                    "(this is the leak bug being reproduced)")
            finally:
                # cleanup: kill the leaked grandchild
                try:
                    os.kill(gc_pid if 'gc_pid' in dir() else 0, signal.SIGTERM if not _is_windows() else 0)
                except OSError:
                    pass
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(gc_pid), "/F"],
                                   capture_output=True, timeout=10) if 'gc_pid' in dir() else None
                try:
                    child.kill()
                except OSError:
                    pass
                child.wait()


class TestKillTree(unittest.TestCase):
    """spawn_managed_proc + kill_tree must kill the WHOLE tree."""

    def test_kill_tree_kills_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = os.path.join(tmp, "gc.pid")
            gc_code = (f"import os,time;"
                       f"open({pid_file!r},'w').write(str(os.getpid()));"
                       f"time.sleep(30)")
            child_code = (f"import subprocess,sys,time;"
                          f"subprocess.Popen([sys.executable,'-u','-c',{gc_code!r}],"
                          f"stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                          f"time.sleep(30)")
            mp = spawn_managed_proc([sys.executable, "-u", "-c", child_code],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                gc_pid = _wait_grandchild_pid(pid_file)
                mp.kill_tree(grace_s=2.0)
                time.sleep(0.5)
                self.assertFalse(_pid_alive(gc_pid),
                                 "grandchild must be killed by kill_tree")
            finally:
                try:
                    mp.proc.kill()
                except OSError:
                    pass

    def test_kill_tree_bounded_and_returns_partial_output(self):
        code = ("import time\nprint('START', flush=True)\ntime.sleep(30)\n")
        mp = spawn_managed_proc([sys.executable, "-u", "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)  # let START be printed
        t0 = time.time()
        out, err = mp.kill_tree(grace_s=1.0)
        self.assertLess(time.time() - t0, 10.0)  # bounded, not full 30s
        self.assertIn(b"START", out)  # partial output recovered

    def test_kill_tree_already_exited(self):
        mp = spawn_managed_proc([sys.executable, "-u", "-c", "pass"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mp.proc.wait(timeout=10)
        out, err = mp.kill_tree(grace_s=1.0)
        self.assertIsInstance(out, bytes)
        self.assertIsInstance(err, bytes)


class TestNormalPath(unittest.TestCase):
    """finish(): normal completion path — no kill, resources released."""

    def test_normal_completion_with_finish(self):
        mp = spawn_managed_proc([sys.executable, "-u", "-c", "print('hi')"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = mp.proc.communicate(timeout=10)
        self.assertIn(b"hi", out)
        self.assertEqual(mp.proc.returncode, 0)
        mp.finish()  # must not kill anything (process already exited)

    def test_finish_without_communicate_then_kill_tree(self):
        # finish() then kill_tree() should both be safe no-ops / bounded
        mp = spawn_managed_proc([sys.executable, "-u", "-c", "import time; time.sleep(30)"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mp.finish()
        mp.kill_tree(grace_s=1.0)
        mp.proc.wait(timeout=10)

    def test_finish_while_running_does_not_kill(self):
        """finish() while the process is still running must NOT kill it
        (KILL_ON_JOB_CLOSE would kill the tree if the handle were closed)."""
        mp = spawn_managed_proc([sys.executable, "-u", "-c", "import time; time.sleep(30)"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertIsNone(mp.proc.poll())  # still running
            mp.finish()                        # must not kill the running tree
            time.sleep(0.3)
            self.assertIsNone(mp.proc.poll(), "finish() killed a still-running process!")
            if _is_windows():
                self.assertIsNotNone(mp._job, "handle should be leaked, not closed")
        finally:
            mp.kill_tree(grace_s=1.0)


class TestPosixBranch(unittest.TestCase):
    """POSIX branch logic verified via mocks (no Linux host available)."""

    def test_spawn_posix_uses_start_new_session(self):
        with patch("src.utility.process_kill.os.name", "posix"), \
             patch("src.utility.process_kill.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            mp = spawn_managed_proc(["echo", "hi"], stdout=subprocess.PIPE)
            _, kwargs = mock_popen.call_args
            self.assertTrue(kwargs["start_new_session"])
            self.assertEqual(mp.proc.pid, 12345)
            self.assertIsNone(mp._job)

    def test_kill_tree_posix_escalates_sigterm_to_sigkill(self):
        mp = MagicMock()
        mp.proc = MagicMock(pid=999)
        mp.proc.communicate.return_value = (b"", b"")  # drain_after_kill happy path
        mp._job = None
        mp.proc.wait.side_effect = [subprocess.TimeoutExpired("x", 1), None]
        import src.utility.process_kill as pk
        with patch("src.utility.process_kill.os.name", "posix"), \
             patch.object(pk.os, "killpg", create=True) as mock_killpg, \
             patch.object(pk.os, "getpgid", create=True, return_value=999), \
             patch.object(pk.signal, "SIGKILL", create=True, new=9):
            pk._kill_tree_posix(mp, grace_s=0.5)
        calls = [c.args for c in mock_killpg.call_args_list]
        # 9 is SIGKILL's numeric value (signal.SIGKILL is absent on Windows)
        self.assertEqual(calls, [(999, signal.SIGTERM), (999, 9)])

    def test_kill_tree_posix_no_sigkill_after_exit(self):
        mp = MagicMock()
        mp.proc = MagicMock(pid=999)
        mp.proc.communicate.return_value = (b"", b"")
        mp._job = None
        mp.proc.wait.side_effect = [subprocess.TimeoutExpired("x", 1), None]
        import src.utility.process_kill as pk
        with patch("src.utility.process_kill.os.name", "posix"), \
             patch.object(pk.os, "killpg", create=True,
                          side_effect=[None, ProcessLookupError]) as mock_killpg, \
             patch.object(pk.os, "getpgid", create=True, return_value=999), \
             patch.object(pk.signal, "SIGKILL", create=True, new=9):
            pk._kill_tree_posix(mp, grace_s=0.5)
        # SIGTERM ok, SIGKILL raised ProcessLookupError (already gone) — no crash
        self.assertEqual(mock_killpg.call_count, 2)


if __name__ == "__main__":
    unittest.main()
