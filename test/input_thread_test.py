# -*- coding: utf-8 -*-
"""
Unit tests for InputThread (busy-phase input collection).
Run: python -m unittest test.input_thread_test
"""
import sys
import os
import time
import unittest
import contextlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.key_processor import KeyPress

from src.context.agent_context import AgentContext
from src.utility.input_thread import InputThread


def char(c):
    """KeyPress for a printable character"""
    return KeyPress(c, c)


def special(key):
    """KeyPress for a special key (Keys enum)"""
    return KeyPress(key, "")


class FakeInput:
    """Mock of prompt_toolkit Input: scripted key frames + read counting"""

    def __init__(self, frames=None):
        self._frames = list(frames) if frames else []
        self.read_count = 0
        self.flush_count = 0
        self.closed = False
        self.raw_mode_entered = False

    def raw_mode(self):
        @contextlib.contextmanager
        def _raw():
            self.raw_mode_entered = True
            yield
        return _raw()

    def read_keys(self):
        self.read_count += 1
        if self._frames:
            return self._frames.pop(0)
        return []

    def flush_keys(self):
        self.flush_count += 1
        return []

    def close(self):
        self.closed = True


class TestInputStateMachine(unittest.TestCase):
    """Key handling logic, tested directly (no real terminal)."""

    def setUp(self):
        self.ctx = AgentContext()
        self.cancelled = []
        self.thread = InputThread(cancel_handler=lambda: self.cancelled.append(1))

    def _keys(self, *kps):
        self.thread._handle_keys(list(kps))

    # ------------------------------------------------------------- append

    def test_append_ascii(self):
        self._keys(char("a"), char("b"), char("c"))
        self.assertEqual(self.thread.draft, "abc")

    def test_append_space(self):
        self._keys(char("h"), char(" "), char("i"))
        self.assertEqual(self.thread.draft, "h i")

    def test_append_cjk(self):
        self._keys(char("中"), char("文"))
        self.assertEqual(self.thread.draft, "中文")

    def test_append_emoji(self):
        self._keys(char("😀"))
        self.assertEqual(self.thread.draft, "😀")

    def test_paste_frame_multiple_keys(self):
        self._keys(char("h"), char("e"), char("l"), char("l"), char("o"))
        self.assertEqual(self.thread.draft, "hello")

    # ------------------------------------------------------------- backspace

    def test_backspace_ascii(self):
        self._keys(char("a"), char("b"), special(Keys.Backspace))
        self.assertEqual(self.thread.draft, "a")

    def test_backspace_control_h(self):
        self._keys(char("a"), char("b"), special(Keys.ControlH))
        self.assertEqual(self.thread.draft, "a")

    def test_backspace_cjk(self):
        self._keys(char("你"), char("好"), special(Keys.Backspace))
        self.assertEqual(self.thread.draft, "你")

    def test_backspace_emoji(self):
        self._keys(char("😀"), special(Keys.Backspace))
        self.assertEqual(self.thread.draft, "")

    def test_backspace_empty_draft(self):
        self._keys(special(Keys.Backspace))
        self.assertEqual(self.thread.draft, "")

    def test_backspace_lone_surrogate(self):
        # defensive path: raw surrogate pair split into two code points
        self.thread.draft = "a\ud83d\ude00"
        self.thread._backspace()
        self.assertEqual(self.thread.draft, "a")

    # ------------------------------------------------------------- submit (Enter)

    def test_submit_enqueues_and_clears_draft(self):
        self._keys(char("h"), char("i"), special(Keys.ControlM))
        self.assertEqual(self.thread.draft, "")
        self.assertEqual(self.thread.drain_msg_queue(), ["hi"])

    def test_submit_control_j(self):
        self._keys(char("o"), char("k"), special(Keys.ControlJ))
        self.assertEqual(self.thread.drain_msg_queue(), ["ok"])

    def test_submit_strips_whitespace(self):
        self._keys(char(" "), char("x"), char(" "), special(Keys.ControlM))
        self.assertEqual(self.thread.drain_msg_queue(), ["x"])

    def test_submit_empty_ignored(self):
        self._keys(special(Keys.ControlM))
        self.assertEqual(self.thread.drain_msg_queue(), [])

    def test_submit_blank_ignored(self):
        self._keys(char(" "), char(" "), special(Keys.ControlM))
        self.assertEqual(self.thread.drain_msg_queue(), [])
        self.assertEqual(self.thread.draft, "")

    def test_submit_command_like_dropped(self):
        self._keys(char("/"), char("e"), char("x"), char("i"), char("t"), special(Keys.ControlM))
        self.assertEqual(self.thread.drain_msg_queue(), [])
        self.assertEqual(self.thread.draft, "")

    def test_submit_multiple_messages_ordered(self):
        self._keys(char("a"), special(Keys.ControlM), char("b"), special(Keys.ControlM))
        self.assertEqual(self.thread.drain_msg_queue(), ["a", "b"])

    # ------------------------------------------------------------- escape

    def test_escape_clears_draft(self):
        self._keys(char("a"), char("b"), special(Keys.Escape))
        self.assertEqual(self.thread.draft, "")

    # ------------------------------------------------------------- ctrl+c

    def test_ctrl_c_clears_draft_only(self):
        self._keys(char("a"), char("b"), special(Keys.ControlC))
        self.assertEqual(self.thread.draft, "")
        self.assertEqual(self.cancelled, [])

    def test_ctrl_c_empty_draft_forwards_cancel(self):
        self._keys(special(Keys.ControlC))
        self.assertEqual(self.cancelled, [1])

    def test_ctrl_c_twice_clears_then_forwards(self):
        self._keys(char("a"), special(Keys.ControlC), special(Keys.ControlC))
        self.assertEqual(self.thread.draft, "")
        self.assertEqual(self.cancelled, [1])

    def test_ctrl_c_no_handler_no_busy_thread(self):
        t = InputThread()  # no cancel_handler, busy_thread_ident None
        t._handle_keys([special(Keys.ControlC)])  # must not raise
        self.assertEqual(self.thread.draft, "")

    # ------------------------------------------------------------- ignored keys

    def test_arrow_keys_ignored(self):
        self._keys(char("a"), special(Keys.Left), special(Keys.Right), char("b"))
        self.assertEqual(self.thread.draft, "ab")

    def test_unknown_enum_key_ignored(self):
        self._keys(special(Keys.F5), char("x"))
        self.assertEqual(self.thread.draft, "x")


class TestInputThreadRuntime(unittest.TestCase):
    """Thread loop, pause/resume and stop semantics with a fake key source."""

    def setUp(self):
        self.ctx = AgentContext()
        self.fake = FakeInput()
        self.thread = InputThread(key_source=self.fake)

    def tearDown(self):
        if self.thread.is_alive:
            self.thread.stop()

    def _wait_reads(self, min_reads, timeout=1.0):
        deadline = time.time() + timeout
        while self.fake.read_count < min_reads and time.time() < deadline:
            time.sleep(0.01)
        self.assertGreaterEqual(self.fake.read_count, min_reads)

    def test_start_reads_keys_and_stop_cleans_up(self):
        self.fake._frames = [[char("h"), char("i")]]
        self.thread.start()
        self.assertTrue(self.thread.is_alive)
        self.assertTrue(self.fake.raw_mode_entered)
        deadline = time.time() + 1.0
        while self.thread.draft != "hi" and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.thread.draft, "hi")
        self.thread.stop()
        self.assertFalse(self.thread.is_alive)
        self.assertTrue(self.fake.closed)

    def test_start_idempotent(self):
        self.thread.start()
        self.thread.start()  # second start must be a no-op
        self.assertTrue(self.thread.is_alive)
        self.thread.stop()
        self.assertTrue(self.fake.closed)

    def test_pause_stops_reading_and_resume_restores(self):
        self.thread.start()
        self._wait_reads(2)
        self.thread.pause()
        count_at_pause = self.fake.read_count
        time.sleep(0.15)
        self.assertEqual(self.fake.read_count, count_at_pause)  # no reads while is_paused
        self.thread.resume()
        self._wait_reads(count_at_pause + 2)
        self.assertGreater(self.fake.read_count, count_at_pause)

    def test_paused_draft_still_accumulates_after_resume(self):
        self.fake._frames = [[char("a")], [char("b")]]
        self.thread.start()
        deadline = time.time() + 1.0
        while self.thread.draft != "a" and time.time() < deadline:
            time.sleep(0.01)
        self.thread.pause()
        time.sleep(0.05)
        self.thread.resume()
        deadline = time.time() + 1.0
        while self.thread.draft != "ab" and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.thread.draft, "ab")
        self.thread.stop()


if __name__ == "__main__":
    unittest.main()
