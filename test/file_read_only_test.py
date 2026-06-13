# -*- coding: utf-8 -*-
"""
Unit tests for read-only path checking.
Run with: python -m unittest test.file_read_only_test
           python test/file_read_only_test.py
"""
import sys
import os
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.context.agent_context import AgentContext
from src.tool.file_io_support import check_read_only

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestCheckReadOnly(unittest.TestCase):
    def setUp(self):
        self.ctx = AgentContext()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.ro_path = os.path.join(self.tmpdir.name, "readonly")
        os.makedirs(self.ro_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_not_read_only(self):
        blocked, info = check_read_only(self.ro_path, self.ctx)
        self.assertFalse(blocked)

    def test_system_read_only(self):
        self.ctx.system_read_only_paths.append(Path(self.ro_path))
        blocked, info = check_read_only(self.ro_path, self.ctx)
        self.assertTrue(blocked)

    def test_user_read_only(self):
        self.ctx.read_only_paths.append(Path(self.ro_path))
        blocked, info = check_read_only(self.ro_path, self.ctx)
        self.assertTrue(blocked)

    def test_subpath_protected(self):
        sub = os.path.join(self.ro_path, "subdir", "file.txt")
        self.ctx.system_read_only_paths.append(Path(self.ro_path))
        blocked, info = check_read_only(sub, self.ctx)
        self.assertTrue(blocked)

    def test_normalized_path(self):
        self.ctx.system_read_only_paths.append(Path(self.ro_path))
        blocked, info = check_read_only(self.ro_path + os.sep, self.ctx)
        self.assertTrue(blocked)

    def test_resolved_path(self):
        self.ctx.system_read_only_paths.append(Path(self.ro_path).resolve())
        blocked, info = check_read_only(os.path.realpath(self.ro_path), self.ctx)
        self.assertTrue(blocked)

    def test_project_src_not_read_only_by_default(self):
        blocked, info = check_read_only(os.path.join(PROJECT_ROOT, "src"), self.ctx)
        self.assertFalse(blocked)

    def test_info_string_returned(self):
        self.ctx.read_only_paths.append(Path(self.ro_path))
        blocked, info = check_read_only(self.ro_path, self.ctx)
        self.assertIsInstance(info, str)
        self.assertGreater(len(info), 0)


if __name__ == "__main__":
    unittest.main()