# -*- coding: utf-8 -*-
"""
Unit tests for the modify scratchpad: path recognition and the writable carve-out inside the read-only session dir.

Run with: python -m unittest test.simulator_scratchpad_test
          python test/simulator_scratchpad_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import unittest
import uuid

from pathlib import Path

from src.constants import *
from src.context.agent_context import AgentContext
from src.tool.file_io_support import check_read_only
from src.tool.simulator_support import DesignManager
from test.simulator_test_utils import SimulatorTestBase


class TestScratchpadWriteCarveOut(SimulatorTestBase):
    """the scratchpad is the only writable folder inside the system read-only session dir"""

    def setUp(self):
        super().setUp()
        self.init_design()
        self.ctx = AgentContext()
        self.ctx.design_man = self.design_man
        self.ctx.system_read_only_paths.append(Path(self.tmpdir))

    def is_scratchpad(self, path: str) -> bool:
        return self.design_man.is_scratchpad_path(path)

    def test_no_scratchpad_before_modify(self):
        self.assertFalse(self.is_scratchpad(os.path.join(self.design_dir(1, 1), "panel_param.json")))

    def test_scratchpad_paths_are_writable(self):
        self.assertTrue(self.modify_design(1, 1)[0])
        scratchpad = self.scratchpad_dir(1, 2)
        for path in (os.path.join(scratchpad, "panel_param.json"), scratchpad,
                     os.path.join(scratchpad, "sub", "new.json")):
            with self.subTest(path=path):
                self.assertTrue(self.is_scratchpad(path))
                blocked, _ = check_read_only(path, self.ctx)
                self.assertFalse(blocked, "scratchpad must be writable")

    def test_non_scratchpad_paths_stay_read_only(self):
        self.assertTrue(self.modify_design(1, 1)[0])
        blocked_paths = (os.path.join(self.design_dir(1, 1), "panel_param.json"),
                         os.path.join(self.session_dir, MESSAGES_NAME),
                         os.path.join(self.session_dir, DESIGNS_NAME),
                         os.path.join(self.session_dir, f"{SIM_DESIGN_NAME}1", "2", "x.json"),
                         os.path.join(self.session_dir, f"{SIM_DESIGN_NAME}1", "2.pad", "x.json"),
                         os.path.join(self.session_dir, f"{SIM_DESIGN_NAME}1", "9.scratchpad", "x.json"),
                         os.path.join(self.scratchpad_dir(1, 2), "..", "..", MESSAGES_NAME))
        for path in blocked_paths:
            with self.subTest(path=path):
                self.assertFalse(self.is_scratchpad(path))
                blocked, _ = check_read_only(path, self.ctx)
                self.assertTrue(blocked, "path must stay read-only")

    def test_other_session_scratchpad_is_not_writable(self):
        self.assertTrue(self.modify_design(1, 1)[0])
        other = DesignManager()
        other.session_uuid = str(uuid.uuid4())
        other.simulator_path = self.sim_path
        self.assertFalse(other.is_scratchpad_path(os.path.join(self.scratchpad_dir(1, 2), "panel_param.json")))

    def test_carve_out_disappears_after_submit(self):
        self.assertTrue(self.modify_design(1, 1)[0])
        path = os.path.join(self.scratchpad_dir(1, 2), "panel_param.json")
        self.assertFalse(check_read_only(path, self.ctx)[0])
        self.assertTrue(self.submit_design(1, 2)[0])
        self.assertFalse(self.is_scratchpad(path))
        self.assertTrue(check_read_only(path, self.ctx)[0])



if __name__ == "__main__":
    unittest.main(verbosity=2)
