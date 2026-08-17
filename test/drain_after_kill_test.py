# -*- coding: utf-8 -*-
"""
Unit tests for drain_after_kill — bounded pipe drain after proc.kill().

Covers: normal completion (full output), timeout give-up (bounded wait, no
infinite block), partial output recovery, and mocked blocking-communicate
paths (bounded give-up returns empty bytes).

Real-process tests use sys.executable (cross-platform, no bash dependency).

Run:  python test/drain_after_kill_test.py
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging
logging.basicConfig(level=logging.CRITICAL)

import time
import threading
import subprocess
import unittest
from unittest.mock import patch

from src.utility.basic_utils import drain_after_kill


def _norm(b: bytes) -> bytes:
    """Normalize CRLF produced by Windows console pipes."""
    return b.replace(b"\r\n", b"\n")


class TestDrainNormalPath(unittest.TestCase):
    """Child exits normally — full output returned, no give-up branch hit."""

    def test_full_output_returned(self):
        p = subprocess.Popen([sys.executable, "-u", "-c", "print('hello')"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = drain_after_kill(p, grace_s=5.0)
        self.assertEqual(_norm(out), b"hello\n")
        self.assertEqual(err, b"")

    def test_empty_output(self):
        p = subprocess.Popen([sys.executable, "-u", "-c", "pass"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = drain_after_kill(p, grace_s=5.0)
        self.assertEqual(out, b"")
        self.assertEqual(err, b"")

    def test_stderr_captured(self):
        p = subprocess.Popen([sys.executable, "-u", "-c",
                              "import sys; print('err', file=sys.stderr)"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = drain_after_kill(p, grace_s=5.0)
        self.assertEqual(out, b"")
        self.assertEqual(_norm(err), b"err\n")

    def test_large_output_not_truncated(self):
        p = subprocess.Popen([sys.executable, "-u", "-c",
                              "print('x' * 100000)"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = drain_after_kill(p, grace_s=5.0)
        self.assertEqual(len(_norm(out)), 100001)  # 100000 x's + newline


class TestDrainTimeoutGiveUp(unittest.TestCase):
    """Pipe EOF never comes (child still holds the write end) — bounded give-up."""

    def test_gives_up_within_grace(self):
        p = subprocess.Popen([sys.executable, "-u", "-c", "import time; time.sleep(5)"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        t0 = time.time()
        try:
            out, err = drain_after_kill(p, grace_s=0.5)
            # Must return (give up) well before the 5s child lifetime.
            self.assertLess(time.time() - t0, 4.0)
            self.assertEqual(out, b"")
            self.assertEqual(err, b"")
        finally:
            p.kill()  # cleanup the still-running child
            p.wait()

    def test_gives_up_with_small_grace(self):
        p = subprocess.Popen([sys.executable, "-u", "-c", "import time; time.sleep(5)"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        t0 = time.time()
        try:
            drain_after_kill(p, grace_s=0.1)
            self.assertLess(time.time() - t0, 3.0)
        finally:
            p.kill()
            p.wait()


class TestDrainPartialOutput(unittest.TestCase):
    """Kill the direct child while it still runs — already-printed output recovered."""

    def test_partial_output_after_kill(self):
        code = ("import sys, time\n"
                "print('START', flush=True)\n"
                "time.sleep(5)\n")
        p = subprocess.Popen([sys.executable, "-u", "-c", code],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(0.5)  # let the child print START before we kill it
            p.kill()
            out, err = drain_after_kill(p, grace_s=2.0)
            self.assertIn(b"START", out)  # already-printed output survives
        finally:
            p.kill()
            p.wait()


class _BlockingFakeProc:
    """Popen stand-in whose communicate() blocks until released."""

    def __init__(self):
        self._release = threading.Event()
        self.stdout = None
        self.stderr = None

    def communicate(self):
        self._release.wait(timeout=10)  # block like a hung pipe
        return b"", b""

    def release(self):
        self._release.set()


class TestDrainMocked(unittest.TestCase):
    """Blocking-communicate handling without spawning real processes."""

    def test_blocking_communicate_gives_up_bounded(self):
        p = _BlockingFakeProc()
        t0 = time.time()
        out, err = drain_after_kill(p, grace_s=0.2)
        self.assertLess(time.time() - t0, 3.0)
        self.assertEqual((out, err), (b"", b""))
        p.release()

    def test_grace_s_controls_join(self):
        p = _BlockingFakeProc()
        t0 = time.time()
        drain_after_kill(p, grace_s=0.05)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 3.0)
        p.release()

    def test_normal_communicate_passthrough(self):
        p = subprocess.Popen([sys.executable, "-u", "-c", "print('ok')"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = drain_after_kill(p, grace_s=5.0)
        self.assertEqual(_norm(out), b"ok\n")

    def test_communicate_exception_propagates(self):
        p = _BlockingFakeProc()
        with patch.object(p, "communicate", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                drain_after_kill(p, grace_s=1.0)


if __name__ == "__main__":
    unittest.main()
