# -*- coding: utf-8 -*-
"""
Unit tests for stream/non-stream response message construction and validation.

Covers:
 - collected_content / collected_reasoning sentinel (None vs "")
 - message dict construction consistency with non-stream model_dump
 - validation: reasoning-only messages patched to API-valid format
 - deepseek_support interaction

Run:  python test/stream_message_test.py
"""
import sys, os, unittest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from context.agent_context import AgentContext
from context.prompt import deepseek_support, get_reasoning


def make_agent_ctx(enable_deepseek: bool = True) -> AgentContext:
    ctx = AgentContext()
    ctx.api_configs = {
        "MAIN_MODEL_NAME": "test-model",
        "MAIN_MODEL_DEEPSEEK_SUPPORT": enable_deepseek,
        "MAIN_MODEL_STREAM": True,
        "MAIN_MODEL_CONTEXT": 1000000,
        "MAIN_MODEL_MAX_TOKENS": 8192,
        "TIMEOUT_MS": 1000000,
    }
    ctx.agent_configs = {
        "CONTEXT_THRESHOLD": 0.9,
        "RENDER_RESPONSE_AS_MD": False,
        "DISPLAY_RESPONSE_REASON": False,
    }
    ctx.messages = []
    ctx.total_input_tokens = 0
    ctx.total_output_tokens = 0
    ctx.total_tokens = 0
    ctx.total_uncached_tokens = 0
    ctx.last_input_tokens = 0
    ctx.last_output_tokens = 0
    ctx.last_tokens = 0
    ctx.reasoning_prompts = 0
    ctx.content_prompts = 0
    return ctx


def build_stream_message(collected_content, collected_reasoning, converted_tool_calls, ctx):
    """
    Replicate the message-building logic from llm_stream_manage (lines 868-874).
    """
    dumped_msg = {
        "role": "assistant",
        "content": collected_content,
        "reasoning": collected_reasoning,
        "tool_calls": converted_tool_calls if converted_tool_calls else None,
    }
    if ctx.api_configs["MAIN_MODEL_DEEPSEEK_SUPPORT"]:
        dumped_msg = deepseek_support(dumped_msg)
    return dumped_msg


def validate_and_patch(dumped_msg, converted_tool_calls):
    """
    Replicate the validation logic from llm_stream_manage (lines 887-894).
    Returns (dumped_msg, should_raise, warning_issued).
    """
    assistant_chat = dumped_msg.get("content")
    assistant_reasoning = get_reasoning(dumped_msg)
    warning = False

    if (assistant_chat is None or assistant_chat == "") and (converted_tool_calls is None):
        if assistant_reasoning is None or assistant_reasoning == "":
            return dumped_msg, True, False  # should raise
        else:
            dumped_msg["content"] = ""
            warning = True

    return dumped_msg, False, warning


class TestStreamMessageConstruction(unittest.TestCase):
    """Test message dict construction from stream collectors."""

    def setUp(self):
        self.ctx = make_agent_ctx()

    # ── Content sentinel ────────────────────────────────────────────

    def test_content_none_when_no_delta(self):
        """collected_content=None stays None → message content is None."""
        msg = build_stream_message(None, None, None, self.ctx)
        self.assertIsNone(msg["content"])

    def test_content_string_when_delta_received(self):
        """collected_content becomes a string when content deltas arrive."""
        msg = build_stream_message("Hello world", None, None, self.ctx)
        self.assertEqual(msg["content"], "Hello world")

    # ── Reasoning sentinel ──────────────────────────────────────────

    def test_reasoning_none_when_no_delta(self):
        """collected_reasoning=None → deepseek_support sets reasoning_content=None."""
        msg = build_stream_message("Hi", None, None, self.ctx)
        self.assertIsNone(msg.get("reasoning_content"))

    def test_reasoning_string_when_delta_received(self):
        """collected_reasoning becomes a string when reasoning deltas arrive."""
        msg = build_stream_message(None, "thinking...", None, self.ctx)
        self.assertNotIn("reasoning", msg)
        self.assertEqual(msg.get("reasoning_content"), "thinking...")

    # ── Tool calls ───────────────────────────────────────────────────

    def test_tool_calls_none_when_empty(self):
        msg = build_stream_message(None, None, {}, self.ctx)
        self.assertIsNone(msg["tool_calls"])

    def test_tool_calls_present(self):
        tc = [{"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]
        msg = build_stream_message(None, None, tc, self.ctx)
        self.assertEqual(msg["tool_calls"], tc)

    # ── Consistency with non-stream model_dump shape ────────────────

    def test_normal_response_matches_nonstream_shape(self):
        """Typical response (content + reasoning) has expected keys/types."""
        msg = build_stream_message("answer", "think", None, self.ctx)
        self.assertEqual(msg["role"], "assistant")
        self.assertIsInstance(msg["content"], str)
        self.assertIsNone(msg.get("reasoning"))
        self.assertIsInstance(msg.get("reasoning_content"), str)
        self.assertIsNone(msg["tool_calls"])

    def test_tool_call_response_matches_nonstream_shape(self):
        """Tool call with null content has expected shape."""
        tc = [{"id": "call_x", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]
        msg = build_stream_message(None, "think", tc, self.ctx)
        self.assertIsNone(msg["content"])
        self.assertIsNotNone(msg["tool_calls"])
        self.assertIsNotNone(msg.get("reasoning_content"))


class TestValidationAndPatch(unittest.TestCase):
    """Test the validation + patch logic for API-invalid messages."""

    def setUp(self):
        self.ctx = make_agent_ctx()

    # ── Normal cases (no patch needed) ──────────────────────────────

    def test_content_present_no_patch(self):
        msg = build_stream_message("answer", None, None, self.ctx)
        _, should_raise, warned = validate_and_patch(msg, None)
        self.assertFalse(should_raise)
        self.assertFalse(warned)
        self.assertEqual(msg["content"], "answer")

    def test_tool_calls_present_no_patch(self):
        tc = [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"}}]
        msg = build_stream_message(None, None, tc, self.ctx)
        _, should_raise, warned = validate_and_patch(msg, tc)
        self.assertFalse(should_raise)
        self.assertFalse(warned)

    def test_both_content_and_reasoning_no_patch(self):
        msg = build_stream_message("ans", "think", None, self.ctx)
        _, should_raise, warned = validate_and_patch(msg, None)
        self.assertFalse(should_raise)
        self.assertFalse(warned)

    # ── Truly empty → raise ─────────────────────────────────────────

    def test_all_empty_raises(self):
        msg = build_stream_message(None, None, None, self.ctx)
        _, should_raise, warned = validate_and_patch(msg, None)
        self.assertTrue(should_raise)
        self.assertFalse(warned)

    # ── Reasoning-only → patch ──────────────────────────────────────

    def test_reasoning_only_patches_content_to_empty_string(self):
        """When only reasoning exists, content is set to '' for API validity."""
        msg = build_stream_message(None, "long thinking...", None, self.ctx)
        self.assertIsNone(msg["content"])
        msg, should_raise, warned = validate_and_patch(msg, None)
        self.assertFalse(should_raise)
        self.assertTrue(warned)
        self.assertEqual(msg["content"], "")
        self.assertIsNotNone(msg.get("reasoning_content"))

    def test_reasoning_only_with_empty_content_stays_empty(self):
        """If content is '' already (edge case), patch is idempotent."""
        msg = build_stream_message("", "think", None, self.ctx)
        msg2, should_raise, warned = validate_and_patch(msg, None)
        self.assertFalse(should_raise)
        self.assertTrue(warned)
        self.assertEqual(msg2["content"], "")

    # ── No deepseek → reasoning stays as "reasoning" ────────────────

    def test_no_deepseek_reasoning_stays_in_reasoning_key(self):
        ctx_no_ds = make_agent_ctx(enable_deepseek=False)
        msg = build_stream_message(None, "raw think", None, ctx_no_ds)
        self.assertEqual(msg.get("reasoning"), "raw think")
        self.assertNotIn("reasoning_content", msg)


class TestDeepseekSupportInteraction(unittest.TestCase):
    """Test deepseek_support conversion affects validation path."""

    def setUp(self):
        self.ctx = make_agent_ctx()

    def test_reasoning_content_present_after_deepseek(self):
        msg = build_stream_message("ans", "think", None, self.ctx)
        self.assertNotIn("reasoning", msg)
        self.assertEqual(msg["reasoning_content"], "think")

    def test_get_reasoning_reads_reasoning_content(self):
        msg = build_stream_message(None, "think", None, self.ctx)
        r = get_reasoning(msg)
        self.assertEqual(r, "think")

    def test_get_reasoning_returns_none_for_empty(self):
        msg = build_stream_message("ans", None, None, self.ctx)
        r = get_reasoning(msg)
        self.assertIsNone(r)


if __name__ == '__main__':
    unittest.main()
