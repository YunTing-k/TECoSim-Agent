# -*- coding: utf-8 -*-
"""
Unit tests for match_line_ranges and merge_intervals in file_io_support.
Run with: python -m unittest test.match_str_test
           python test/match_str_test.py
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tool.file_io_support import match_line_ranges, merge_intervals


class TestMatchLineRanges(unittest.TestCase):
    def test_repeated_char_exact(self):
        content = "a\na\na\na\na\na\na\na\na\n"
        target = "a\na"
        result = match_line_ranges(content, target, True)
        self.assertEqual(
            result,
            [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)]
        )

    def test_merge_repeated(self):
        intervals = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)]
        result = merge_intervals(intervals)
        self.assertEqual(result, [(1, 9)])

    def test_scattered_match(self):
        content = "Hello World\n1\n2\n3\n4\nHello World\na\nb\nHello World\n"
        result = match_line_ranges(content, "Hello World", False)
        # inexact match returns first occurrence only
        self.assertEqual(result, [(1, 1)])

    def test_scattered_exact(self):
        content = "Hello World\n1\n2\n3\n4\nHello World\na\nb\nHello World\n"
        result = match_line_ranges(content, "Hello World", True)
        self.assertEqual(result, [(1, 1), (6, 6), (9, 9)])

    def test_merge_scattered(self):
        intervals = [(1, 1), (6, 6), (9, 9)]
        result = merge_intervals(intervals)
        self.assertEqual(result, [(1, 1), (6, 6), (9, 9)])

    def test_trailing_newline_in_target(self):
        content = "Hello World\n1\n2\n3\n4\nHello World\na\nb\nHello World\n"
        result = match_line_ranges(content, "Hello World\n", True)
        self.assertEqual(result, [(1, 1), (6, 6), (9, 9)])

    def test_empty_target(self):
        content = "a\nb\nc\n"
        result = match_line_ranges(content, "\n", True)
        self.assertEqual(result, [(1, 1), (2, 2), (3, 3)])

    def test_no_match(self):
        content = "a\nb\nc\n"
        result = match_line_ranges(content, "xyz", True)
        self.assertEqual(result, [])

    def test_no_match_merged(self):
        result = merge_intervals([])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
