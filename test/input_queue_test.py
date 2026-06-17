# -*- coding: utf-8 -*-
"""
Unit tests for InputQueue (type-ahead user message queuing).

Covers: queue operations (enqueue / drain / queue_size), key polling,
        check_trigger detection, start/stop/pause/resume lifecycle,
        render_status output, and thread safety.

Run:  python test/input_queue_test.py
"""
import sys, os, unittest, threading
from unittest.mock import MagicMock

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from context.agent_context import AgentContext
from src.utility.input_queue import InputQueue
from src.constants import *


def make_agent_ctx() -> AgentContext:
    ctx = AgentContext()
    ctx.agent_configs = {
        "RENDER_RESPONSE_AS_MD": False,
        "DISPLAY_RESPONSE_REASON": True,
    }
    return ctx


class TestInputQueueOperations(unittest.TestCase):

    def setUp(self):
        self.ctx = make_agent_ctx()
        self.console = MagicMock()
        self.iq = InputQueue(self.ctx, self.console)

    def test_enqueue_single(self):
        self.iq.enqueue("hello world")
        self.assertEqual(self.iq.queue_size(), 1)

    def test_enqueue_multiple(self):
        self.iq.enqueue("msg1")
        self.iq.enqueue("msg2")
        self.iq.enqueue("msg3")
        self.assertEqual(self.iq.queue_size(), 3)

    def test_enqueue_empty_string_ignored(self):
        self.iq.enqueue("")
        self.iq.enqueue("   ")
        self.assertEqual(self.iq.queue_size(), 0)

    def test_drain_returns_and_clears(self):
        self.iq.enqueue("a")
        self.iq.enqueue("b")
        result = self.iq.drain()
        self.assertEqual(result, ["a", "b"])
        self.assertEqual(self.iq.queue_size(), 0)

    def test_drain_empty_queue(self):
        self.assertEqual(self.iq.drain(), [])


class TestInputQueuePolling(unittest.TestCase):

    def setUp(self):
        self.ctx = make_agent_ctx()
        self.console = MagicMock()
        self.iq = InputQueue(self.ctx, self.console)

    def test_poll_keys_returns_empty_when_not_started(self):
        self.assertEqual(self.iq.poll_keys(), [])

    def test_poll_keys_returns_empty_when_paused(self):
        self.iq.start()
        self.iq.pause()
        self.assertEqual(self.iq.poll_keys(), [])
        self.iq.stop()

    def test_check_trigger_false_when_not_started(self):
        self.assertFalse(self.iq.check_trigger())

    def test_check_trigger_false_when_paused(self):
        self.iq.start()
        self.iq.pause()
        self.assertFalse(self.iq.check_trigger())
        self.iq.stop()


class TestInputQueueThreadSafety(unittest.TestCase):

    def setUp(self):
        self.ctx = make_agent_ctx()
        self.console = MagicMock()
        self.iq = InputQueue(self.ctx, self.console)

    def test_concurrent_enqueue(self):
        num_threads = 10
        msgs_per_thread = 100
        errors = []

        def worker(tid):
            try:
                for i in range(msgs_per_thread):
                    self.iq.enqueue(f"t{tid}-m{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(self.iq.queue_size(), num_threads * msgs_per_thread)
        self.assertEqual(len(self.iq.drain()), num_threads * msgs_per_thread)


class TestInputQueueLifecycle(unittest.TestCase):

    def setUp(self):
        self.ctx = make_agent_ctx()
        self.console = MagicMock()
        self.iq = InputQueue(self.ctx, self.console)

    def test_initial_state_not_active(self):
        self.assertFalse(self.iq.is_active())

    def test_double_start_noop(self):
        self.iq.start()
        self.assertTrue(self.iq.is_active())
        self.iq.start()
        self.assertTrue(self.iq.is_active())
        self.iq.stop()

    def test_stop_when_not_active_noop(self):
        self.assertFalse(self.iq.is_active())
        self.iq.stop()
        self.assertFalse(self.iq.is_active())

    def test_stop_preserves_queued_messages(self):
        self.iq.start()
        self.iq.enqueue("saved")
        self.iq.stop()
        self.assertEqual(self.iq.queue_size(), 1)
        self.assertEqual(self.iq.drain(), ["saved"])

    def test_pause_resume(self):
        self.iq.start()
        self.assertFalse(self.iq.is_paused())
        self.iq.pause()
        self.assertTrue(self.iq.is_paused())
        self.iq.resume()
        self.assertFalse(self.iq.is_paused())
        self.iq.stop()

    def test_pause_when_stopped_noop(self):
        self.iq.pause()
        self.assertFalse(self.iq.is_paused())


class TestInputQueueRender(unittest.TestCase):

    def setUp(self):
        self.ctx = make_agent_ctx()
        self.console = MagicMock()
        self.iq = InputQueue(self.ctx, self.console)

    def test_render_empty_returns_none(self):
        self.assertIsNone(self.iq.render_status())

    def test_render_with_queued_messages(self):
        self.iq.enqueue("msg1")
        self.iq.enqueue("msg2")
        r = self.iq.render_status()
        self.assertIsNotNone(r)
        self.assertIn("Queued: 2", r.plain)

    def test_render_idle_returns_none(self):
        self.assertIsNone(self.iq.render_status())


if __name__ == '__main__':
    unittest.main()
