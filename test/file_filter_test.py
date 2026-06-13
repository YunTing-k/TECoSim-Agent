# -*- coding: utf-8 -*-
"""
Unit tests for file filtering support (grep_impl, glob_impl).
grep_impl tests require ripgrep (rg) available and are skipped if not found.

Run with: python -m unittest test.file_filter_test
           python test/file_filter_test.py
"""
import sys
import os
import unittest
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.constants import *
from src.tool.file_filter_support import grep_impl, glob_impl

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RG_PATH = shutil.which("rg") or shutil.which("ripgrep") or "rg"
RG_AVAILABLE = shutil.which(RG_PATH) is not None


class TestGlobImpl(unittest.TestCase):
    def test_basic_py_glob(self):
        results, flag, info = glob_impl({"pattern": "*.py", "path": PROJECT_ROOT})
        self.assertTrue(flag)
        self.assertIsInstance(results, str)
        self.assertGreater(len(results), 0)

    def test_recursive_py_glob(self):
        results, flag, info = glob_impl({"pattern": "**/*.py", "path": os.path.join(PROJECT_ROOT, "src")})
        self.assertTrue(flag)
        self.assertIn("main.py", results)

    def test_json_glob(self):
        results, flag, info = glob_impl({"pattern": "**/*.json", "path": os.path.join(PROJECT_ROOT, "config")})
        self.assertTrue(flag)
        self.assertIn(".json", results)

    def test_test_files_glob(self):
        results, flag, info = glob_impl({"pattern": "**/*_test.py", "path": os.path.join(PROJECT_ROOT, "test")})
        self.assertTrue(flag)

    def test_no_match(self):
        results, flag, info = glob_impl({"pattern": "nonexistent_xyz789", "path": PROJECT_ROOT})
        self.assertTrue(flag)

    def test_empty_pattern(self):
        results, flag, info = glob_impl({"pattern": ""})
        self.assertFalse(flag)

    def test_default_path(self):
        results, flag, info = glob_impl({"pattern": "*.py"})
        self.assertTrue(flag)

    def test_entry_limit(self):
        results, flag, info = glob_impl({"pattern": "**/*.py", "path": os.path.join(PROJECT_ROOT, "src"), "entry_limit": 2})
        self.assertTrue(flag)

    def test_wildcard_pattern(self):
        results, flag, info = glob_impl({"pattern": "bash_ris?_test.py", "path": os.path.join(PROJECT_ROOT, "test")})
        self.assertTrue(flag)
        self.assertIn("bash_risk_test", results)


@unittest.skipUnless(RG_AVAILABLE, "ripgrep (rg) not available")
class TestGrepImpl(unittest.TestCase):
    def test_search_returns_tuple(self):
        results, flag, info = grep_impl(
            {"pattern": "def", "path": os.path.join(PROJECT_ROOT, "src", "main.py"),
             "output_mode": "content", "head_limit": 2},
            rg_path=RG_PATH, timeout=20)
        self.assertIsInstance(results, str)
        self.assertIsInstance(flag, bool)
        self.assertIsInstance(info, str)

    def test_files_with_matches_mode(self):
        results, flag, info = grep_impl(
            {"pattern": "def", "path": os.path.join(PROJECT_ROOT, "src", "main.py"),
             "output_mode": "files_with_matches"},
            rg_path=RG_PATH, timeout=20)
        self.assertTrue(flag)

    def test_count_mode(self):
        results, flag, info = grep_impl(
            {"pattern": "def", "path": os.path.join(PROJECT_ROOT, "src", "main.py"),
             "output_mode": "count"},
            rg_path=RG_PATH, timeout=20)
        self.assertTrue(flag)

    def test_no_match_does_not_crash(self):
        results, flag, info = grep_impl(
            {"pattern": "nonexistent_xyz789", "path": PROJECT_ROOT, "output_mode": "content"},
            rg_path=RG_PATH, timeout=20)
        self.assertIsInstance(results, str)
        self.assertIsInstance(info, str)

    def test_missing_pattern(self):
        results, flag, info = grep_impl(
            {"output_mode": "content"}, rg_path=RG_PATH, timeout=20)
        self.assertFalse(flag)


if __name__ == "__main__":
    unittest.main()
