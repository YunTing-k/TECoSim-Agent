# -*- coding: utf-8 -*-
"""
Unit tests for LLM-facing file read formatting (format_file_for_llm).

Covers: pipe-separated line numbers, XML wrapper, truncation footer,
        line-length cap, edge cases.

Run:  python test/file_read_format_test.py
"""
import sys, os, unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)

from src.utility.basic_utils import format_file_for_llm


class TestFormatFileForLlm(unittest.TestCase):
    """Tests for format_file_for_llm."""

    def test_basic_output(self):
        lines = ["import os\n", "import sys\n", "\n", "def main():\n", "    pass\n"]
        result = format_file_for_llm(lines, "/src/foo.py", 1, 5, 5, False)
        self.assertIn('<file path="/src/foo.py" lines="1-5" total="5" truncated="false">', result)
        self.assertIn("1│import os\n", result)
        self.assertIn("5│    pass\n", result)
        self.assertIn("(End of file - total 5 lines)\n</file>", result)

    def test_truncated_footer(self):
        lines = [f"line{i}\n" for i in range(100)]
        result = format_file_for_llm(lines, "/big.txt", 1, 20, 100, True)
        self.assertIn('truncated="true"', result)
        self.assertIn("(80 lines not shown, use offset=21 to continue)", result)

    def test_offset_start(self):
        lines = [f"line{i}\n" for i in range(100)]
        result = format_file_for_llm(lines, "/big.txt", 51, 50, 100, False)
        self.assertIn('lines="51-100"', result)
        self.assertIn("51│line50\n", result)
        self.assertIn("(End of file - total 100 lines)", result)

    def test_partial_show_truncated(self):
        lines = [f"line{i}\n" for i in range(30)]
        result = format_file_for_llm(lines, "/big.txt", 10, 10, 30, True)
        self.assertIn('lines="10-19"', result)
        self.assertIn("(11 lines not shown, use offset=20 to continue)", result)

    def test_empty_snippet(self):
        lines = ["x\n"]
        result = format_file_for_llm(lines, "/empty.txt", 1, 0, 1, False)
        self.assertIn('lines="0-0"', result)
        self.assertIn("(End of file - total 1 lines)\n</file>", result)

    def test_pipe_separator_visible(self):
        lines = ["hello world\n"]
        result = format_file_for_llm(lines, "/t.txt", 1, 1, 1, False)
        self.assertIn("\u2502", result)
        self.assertIn("1\u2502hello world", result)

    def test_large_file_digit_width(self):
        total = 200
        lines = [f"L{i}\n" for i in range(total)]
        result = format_file_for_llm(lines, "/t.txt", 195, 3, total, False)
        self.assertIn("195│L194\n", result)
        self.assertIn("196│L195\n", result)
        self.assertIn("197│L196\n", result)

    def test_line_char_truncation(self):
        from unittest.mock import patch
        long_line = "x" * 3000 + "\n"
        lines = [long_line]
        with patch('src.utility.basic_utils.READ_FILE_LINE_CHAR_LIMIT', 100):
            result = format_file_for_llm(lines, "/long.txt", 1, 1, 1, False)
        self.assertIn("... (line truncated to 100 chars)", result)
        self.assertNotIn("x" * 101, result.split("...")[0])

    def test_single_line_file(self):
        lines = ["hello\n"]
        result = format_file_for_llm(lines, "/one.txt", 1, 1, 1, False)
        self.assertIn('lines="1-1" total="1"', result)
        self.assertIn("1│hello\n", result)
        self.assertIn("(End of file - total 1 lines)", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
