# -*- coding: utf-8 -*-
"""
Unit tests for run maintenance: the launch status gate, the run registry and the run log files.

Run with: python -m unittest test.simulator_run_test
          python test/simulator_run_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import shutil
import unittest

from unittest.mock import MagicMock, patch

from src.constants import *
from src.tool import simulator_support as ss
from src.tool.simulator_support import RunStatus, launch_sim_impl
from test.simulator_test_utils import FakeProc, SimulatorTestBase


class TestLaunchGating(SimulatorTestBase):
    """launch_sim refuses anything that is not a ready design, without side effects"""

    def test_launch_rejects_unknown_design(self):
        self.init_design()
        with patch.object(ss.subprocess, "Popen") as popen, patch.object(ss.subprocess, "run") as run:
            ok, label, info = launch_sim_impl({"design_id": 9, "design_rev": 1, "subject": "s", "description": "d"},
                                              self.design_man, self.run_man, self.console)
        self.assertFalse(ok)
        self.assertIn("is not found", info)
        self.assert_no_subprocess(popen, run)
        self.assertEqual(self.run_man.get_num(), 0)

    def test_launch_rejects_editing_design(self):
        self.init_design()
        self.assertTrue(self.modify_design(1, 1)[0])
        with patch.object(ss.subprocess, "Popen") as popen, patch.object(ss.subprocess, "run") as run:
            ok, label, info = launch_sim_impl({"design_id": 1, "design_rev": 2, "subject": "s", "description": "d"},
                                              self.design_man, self.run_man, self.console)
        self.assertFalse(ok)
        self.assertIn(f"is in status `{DESIGN_EDITING_LABEL}`", info)
        self.assertIn(f"Only a design in status `{DESIGN_READY_LABEL}` can be simulated", info)
        self.assert_no_subprocess(popen, run)
        self.assertEqual(self.run_man.get_num(), 0)

    def test_launch_rejects_missing_design_dir(self):
        self.init_design()
        shutil.rmtree(self.design_dir(1, 1))
        with patch.object(ss.subprocess, "Popen") as popen, patch.object(ss.subprocess, "run") as run:
            ok, label, info = launch_sim_impl({"design_id": 1, "design_rev": 1, "subject": "s", "description": "d"},
                                              self.design_man, self.run_man, self.console)
        self.assertFalse(ok)
        self.assertIn("path doesn't exist", info)
        self.assert_no_subprocess(popen, run)

    def test_launch_accepts_ready_design(self):
        self.init_design()
        with patch.object(ss.subprocess, "Popen", return_value=FakeProc()) as popen, \
                patch.object(ss.subprocess, "run", return_value=MagicMock(returncode=0, stdout=b"cleaned")):
            ok, label, info = launch_sim_impl({"design_id": 1, "design_rev": 1, "subject": "run 1",
                                               "description": "smoke"},
                                              self.design_man, self.run_man, self.console)
        self.assertTrue(ok, info)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(self.run_man.get_num(), 1)
        self.assertEqual(self.run_man.get_run(1)[1]["status"], RunStatus.DONE)
        run_dir = os.path.join(self.session_dir, f"{SIM_RUN_NAME}1")
        self.assertEqual(sorted(os.listdir(run_dir)), ["stderr.log", "stdout.log"])

    def test_submitted_revision_can_be_launched(self):
        self.init_design()
        self.assertTrue(self.modify_design(1, 1)[0])
        self.assertTrue(self.submit_design(1, 2)[0])
        with patch.object(ss.subprocess, "Popen", return_value=FakeProc()) as popen, \
                patch.object(ss.subprocess, "run", return_value=MagicMock(returncode=0, stdout=b"cleaned")):
            ok, label, info = launch_sim_impl({"design_id": 1, "design_rev": 2, "subject": "s", "description": "d"},
                                              self.design_man, self.run_man, self.console)
        self.assertTrue(ok, info)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(self.run_man.get_run(1)[1]["design_rev"], 2)



if __name__ == "__main__":
    unittest.main(verbosity=2)
