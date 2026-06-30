# -*- coding: utf-8 -*-
"""
Unit tests for truncate_tool_result — iterative field-level JSON-safe truncation.

Covers: single/multi-field truncation, non-dict fallback, budget exhaustion,
        JSON validity after truncation, empty/edge inputs.

Run:  python test/truncate_tool_result_test.py
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging
logging.basicConfig(level=logging.CRITICAL)

import json
import unittest

from src.utility.basic_utils import truncate_tool_result
from src.constants import TOOL_RESULT_TRUNCATION_START_LABEL, TOOL_RESULT_TRUNCATION_END_LABEL


ROUNDS = 6


class TestFitsWithinLimit(unittest.TestCase):
    """Dict that already fits inside limit — returned unchanged."""

    def test_small_dict_unchanged(self):
        d = {"status": "ok", "data": "hello"}
        raw = json.dumps(d, ensure_ascii=False)
        result = truncate_tool_result(d, 500, ROUNDS)
        self.assertEqual(result, raw)

    def test_empty_dict(self):
        d = {}
        raw = json.dumps(d, ensure_ascii=False)
        result = truncate_tool_result(d, 10, ROUNDS)
        self.assertEqual(result, raw)

    def test_no_string_fields(self):
        d = {"count": 42, "flag": True, "score": 3.14}
        result = truncate_tool_result(d, 25, ROUNDS)
        self.assertLessEqual(len(result), 25)


class TestSingleLargeField(unittest.TestCase):
    """Single large string field — truncated, JSON stays valid."""

    def test_truncates_and_json_valid(self):
        d = {"stdout": "x" * 2000}
        limit = 1200
        result = truncate_tool_result(d, limit, ROUNDS)
        self.assertLessEqual(len(result), limit)
        parsed = json.loads(result)
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stdout"])
        self.assertIn(TOOL_RESULT_TRUNCATION_END_LABEL, parsed["stdout"])

    def test_marker_position(self):
        d = {"result": "A" * 3000}
        limit = 1500
        result = truncate_tool_result(d, limit, ROUNDS)
        parsed = json.loads(result)
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["result"])
        self.assertIn(TOOL_RESULT_TRUNCATION_END_LABEL, parsed["result"])


class TestMultipleLargeFields(unittest.TestCase):
    """Multiple large fields — longest truncated first each round."""

    def test_longest_field_trimmed_first(self):
        d = {"stdout": "A" * 3000, "stderr": "B" * 1000, "x": 1}
        limit = 2500
        result = truncate_tool_result(d, limit, 4)
        parsed = json.loads(result)
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stdout"])
        self.assertNotIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stderr"])

    def test_both_trimmed_when_needed(self):
        d = {"stdout": "X" * 5000, "stderr": "Y" * 5000}
        limit = 4000
        result = truncate_tool_result(d, limit, 6)
        parsed = json.loads(result)
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stdout"])
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stderr"])


class TestNonDictFallback(unittest.TestCase):
    """Non-dict results — hard JSON cut, always <= limit."""

    def test_list_hard_cut(self):
        r = ["a" * 100, "b" * 100, "c" * 100]
        result = truncate_tool_result(r, 50, ROUNDS)
        self.assertLessEqual(len(result), 50)

    def test_string_hard_cut(self):
        result = truncate_tool_result("plain text" * 20, 30, ROUNDS)
        self.assertLessEqual(len(result), 30)


class TestRoundLimitExhaustion(unittest.TestCase):
    """max_rounds exhausted without fitting — hard cut, always <= limit."""

    def test_zero_rounds(self):
        d = {"data": "very long string here" * 10}
        limit = 80
        result = truncate_tool_result(d, limit, 0)
        self.assertLessEqual(len(result), limit)

    def test_one_round_not_enough(self):
        d = {"a": "X" * 3000, "b": "Y" * 3000}
        limit = 1500
        result = truncate_tool_result(d, limit, 1)
        self.assertLessEqual(len(result), limit)


class TestJsonValidity(unittest.TestCase):
    """All truncated results must produce parseable JSON or at least not crash."""

    def test_every_scenario_parseable(self):
        scenarios = [
            ({"stdout": "A" * 5000, "stderr": "B" * 3000}, 4000),
            ({"file_content": "C" * 2000, "status": "DONE"}, 1500),
            ({"info": "small", "log_content": "D" * 6000}, 3000),
            ({"results": "E" * 2000, "content": "F" * 2000}, 1800),
            ({"a": "G" * 3000, "b": "H" * 3000, "c": "I" * 3000}, 4000),
            ({"stdout": "J" * 500}, 600),
            ({}, 10),
            ({"x": True, "y": 42}, 10),
        ]
        for d, limit in scenarios:
            with self.subTest(dict=str(d)[:40], limit=limit):
                result = truncate_tool_result(dict(d), limit, ROUNDS)
                try:
                    json.loads(result)
                except json.JSONDecodeError:
                    self.assertTrue(
                        result.startswith("{") and not result.endswith("}"),
                        f"unexpected invalid JSON: {result[:60]}"
                    )

    def test_bash_like_result_valid_after_truncation(self):
        """Simulate a real bash result with large stdout."""
        lines = "\n".join(
            f"test_result_line_{str(i).zfill(3)} ... ok" for i in range(200)
        )
        d = {
            "status": "DONE",
            "return code": 0,
            "stdout": lines,
            "stderr": "",
        }
        limit = 5000
        result = truncate_tool_result(d, limit, ROUNDS)
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "DONE")
        self.assertEqual(parsed["return code"], 0)
        self.assertEqual(parsed["stderr"], "")
        self.assertIn(TOOL_RESULT_TRUNCATION_START_LABEL, parsed["stdout"])
        self.assertIn(TOOL_RESULT_TRUNCATION_END_LABEL, parsed["stdout"])


if __name__ == "__main__":
    unittest.main()
