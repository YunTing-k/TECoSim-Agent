# -*- coding: utf-8 -*-
"""
Unit tests for print_messages resume-display preview switches.

Covers: RESUME_DISPLAY_WRITE_PREVIEW, RESUME_DISPLAY_BASH_PREVIEW,
        RESUME_DISPLAY_BASH_RESULT — show/hide write/bash tool previews
        during session resume history replay.

Run:  python test/resume_display_test.py
"""
import sys, os, unittest, io, json, re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)

from unittest.mock import patch
from rich.console import Console
from src.context.agent_context import AgentContext
from src.context.prompt import print_messages


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _make_ctx(with_write: bool = False, with_bash: bool = False,
              with_bash_result: bool = False) -> AgentContext:
    ctx = AgentContext()
    ctx.agent_configs = {
        "RENDER_RESPONSE_AS_MD": False,
        "RESUME_DISPLAY_SYS_REMINDER": False,
        "RESUME_DISPLAY_SKILLS": False,
        "RESUME_DISPLAY_CRONS": False,
        "RESUME_DISPLAY_WRITE_PREVIEW": with_write,
        "RESUME_DISPLAY_BASH_PREVIEW": with_bash,
        "RESUME_DISPLAY_BASH_RESULT": with_bash_result,
        "RESUME_DISPLAY_SUBAGENT": False,
        "RESUME_DISPLAY_SUBAGENT_AS_MD": False,
    }
    return ctx


def _capture_output(ctx, messages, terminal_width=120):
    """run print_messages and return stripped string output."""
    import os as _os
    f = io.StringIO()
    console = Console(file=f, force_terminal=True, width=terminal_width, height=40)
    with patch('os.get_terminal_size', return_value=_os.terminal_size((terminal_width, 40))):
        print_messages(messages, ctx, console)
    return _strip_ansi(f.getvalue())


class TestResumeWritePreview(unittest.TestCase):
    """Tests for RESUME_DISPLAY_WRITE_PREVIEW switch."""

    def _make_write_msg(self):
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_write_1",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": json.dumps({"path": "test.py", "content": "x = 1\ny = 2\n"})
                }
            }]
        }

    def test_write_preview_on(self):
        ctx = _make_ctx(with_write=True)
        msg = self._make_write_msg()
        output = _capture_output(ctx, [msg])
        self.assertIn("x = 1", output)
        self.assertIn("$write", output)

    def test_write_preview_off_default(self):
        ctx = _make_ctx(with_write=False)
        msg = self._make_write_msg()
        output = _capture_output(ctx, [msg])
        self.assertIn("Tool used", output)
        self.assertNotIn("$write", output)
        self.assertNotIn("x = 1", output)

    def test_write_preview_malformed_args(self):
        ctx = _make_ctx(with_write=True)
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_w2",
                "type": "function",
                "function": {"name": "write_file", "arguments": "not-json"}
            }]
        }
        output = _capture_output(ctx, [msg])
        self.assertIn("Tool used", output)
        self.assertIn("$write", output)  # render still called, just with empty defaults


class TestResumeBashPreview(unittest.TestCase):
    """Tests for RESUME_DISPLAY_BASH_PREVIEW switch."""

    def _make_bash_msg(self):
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_bash_1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": json.dumps({"command": "ls -la", "description": "list files"})
                }
            }]
        }

    def test_bash_preview_on(self):
        ctx = _make_ctx(with_bash=True)
        msg = self._make_bash_msg()
        output = _capture_output(ctx, [msg])
        self.assertIn("ls -la", output)
        self.assertIn("$bash", output)

    def test_bash_preview_off_default(self):
        ctx = _make_ctx(with_bash=False)
        msg = self._make_bash_msg()
        output = _capture_output(ctx, [msg])
        self.assertIn("Tool used", output)
        self.assertNotIn("$bash", output)
        self.assertNotIn("ls -la", output)


class TestResumeBashResult(unittest.TestCase):
    """Tests for RESUME_DISPLAY_BASH_RESULT switch."""

    def _make_bash_result_msg(self):
        return {
            "role": "tool",
            "tool_call_id": "call_bash_1",
            "content": json.dumps({"status": "success", "stdout": "total 42\n", "stderr": ""})
        }

    def _make_bash_assistant_msg(self):
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_bash_1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": json.dumps({"command": "ls -la"})
                }
            }]
        }

    def test_bash_result_on(self):
        ctx = _make_ctx(with_bash_result=True)
        msgs = [self._make_bash_assistant_msg(), self._make_bash_result_msg()]
        output = _capture_output(ctx, msgs)
        self.assertIn("total 42", output)
        self.assertIn("$ out", output)

    def test_bash_result_off_default(self):
        ctx = _make_ctx(with_bash_result=False)
        msgs = [self._make_bash_assistant_msg(), self._make_bash_result_msg()]
        output = _capture_output(ctx, msgs)
        self.assertNotIn("total 42", output)
        self.assertNotIn("$ out", output)

    def test_non_bash_result_skipped(self):
        ctx = _make_ctx(with_bash_result=True)
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_edit_1",
                    "type": "function",
                    "function": {"name": "edit_file", "arguments": "{}"}
                }]
            },
            {
                "role": "tool",
                "tool_call_id": "call_edit_1",
                "content": json.dumps({"status": "success"})
            }
        ]
        output = _capture_output(ctx, msgs)
        self.assertNotIn("$ out", output)

    def test_bash_result_empty_stdout(self):
        ctx = _make_ctx(with_bash_result=True)
        msgs = [
            self._make_bash_assistant_msg(),
            {
                "role": "tool",
                "tool_call_id": "call_bash_1",
                "content": json.dumps({"status": "success", "stdout": "", "stderr": ""})
            }
        ]
        output = _capture_output(ctx, msgs)
        self.assertNotIn("$ out", output)

    def test_bash_result_malformed_json(self):
        ctx = _make_ctx(with_bash_result=True)
        result_msg = {
            "role": "tool",
            "tool_call_id": "call_bash_1",
            "content": "not-json"
        }
        msgs = [self._make_bash_assistant_msg(), result_msg]
        output = _capture_output(ctx, msgs)
        self.assertNotIn("$ out", output)  # shouldn't crash


class TestResumeDefaultAllOff(unittest.TestCase):
    """Default config: all three previews disabled."""

    def test_no_previews_by_default(self):
        ctx = _make_ctx()
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_w1",
                        "type": "function",
                        "function": {"name": "write_file",
                                     "arguments": json.dumps({"path": "t.py", "content": "x=1\n"})}
                    },
                    {
                        "id": "call_b1",
                        "type": "function",
                        "function": {"name": "bash",
                                     "arguments": json.dumps({"command": "ls"})}
                    }
                ]
            },
            {
                "role": "tool",
                "tool_call_id": "call_b1",
                "content": json.dumps({"stdout": "out\n", "stderr": ""})
            }
        ]
        output = _capture_output(ctx, msgs)
        self.assertIn("Tool used", output)
        self.assertNotIn("$write", output)
        self.assertNotIn("$bash", output)
        self.assertNotIn("$ out", output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
