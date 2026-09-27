# -*- coding: utf-8 -*-
"""
Unit tests for design maintenance: the DesignManager lifecycle (status, fork, modify, submit).

Run with: python -m unittest test.simulator_design_test
          python test.simulator_design_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import json
import shutil
import unittest

from src.constants import *
from src.tool.simulator_param import DESIGN_CONFIG_SCHEMAS
from src.tool.simulator_support import (
    DesignManager, DesignStatus, design_to_info, designs_to_info)
from test.simulator_test_utils import SimulatorTestBase, read_config, write_config


class TestDesignStatus(SimulatorTestBase):
    """status field: init is ready, persistence round-trips the enum"""

    def test_status_labels(self):
        self.assertEqual(DESIGN_EDITING_LABEL, "EDITING")
        self.assertEqual(DESIGN_READY_LABEL, "READY")
        self.assertEqual(DesignStatus.EDITING.value, DESIGN_EDITING_LABEL)
        self.assertEqual(DesignStatus.READY.value, DESIGN_READY_LABEL)

    def test_init_design_is_ready(self):
        design_id = self.init_design()
        self.assertEqual(self.status_of(design_id, 1), DesignStatus.READY)

    def test_status_shown_in_info(self):
        self.init_design()
        design = self.design_man.get_design(1, 1)[1]
        self.assertIn(f"Status: {DESIGN_READY_LABEL}", design_to_info(design))
        self.assertIn(f" - Status: {DESIGN_READY_LABEL}", designs_to_info([design]))

    def test_save_load_round_trip(self):
        self.init_design()
        self.add_editing_rev(1, 2)
        self.design_man.save_to_file(self.console, mute=True)
        with open(os.path.join(self.session_dir, DESIGNS_NAME), encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual([d["status"] for d in raw["designs"]], [DESIGN_READY_LABEL, DESIGN_EDITING_LABEL])

        loaded = DesignManager()
        loaded.session_uuid = self.session_uuid
        loaded.simulator_path = self.sim_path
        loaded.load_from_file(self.console, mute=True)
        self.assertEqual(loaded.get_design(1, 1)[1]["status"], DesignStatus.READY)
        self.assertEqual(loaded.get_design(1, 2)[1]["status"], DesignStatus.EDITING)
        self.assertIsInstance(loaded.get_design(1, 2)[1]["status"], DesignStatus)


class TestForkDesign(SimulatorTestBase):
    """fork: new design id, revision starts at 1, ready, configs copied, source untouched"""

    def test_fork_creates_new_ready_design(self):
        self.init_design()
        ok, label, info = self.fork_design(1, 1, subject="branch A")
        self.assertTrue(ok, info)
        self.assertIn("forked from design 1 (rev 1)", info)
        self.assertEqual(self.design_man.get_design(2, 1)[1]["design_id"], 2)
        self.assertEqual(self.status_of(2, 1), DesignStatus.READY)

    def test_fork_records_copy_from(self):
        self.init_design()
        self.fork_design(1, 1)
        design = self.design_man.get_design(2, 1)[1]
        self.assertEqual((design["copy_id"], design["copy_rev"]), (1, 1))
        self.assertIn("Copy from: 1 (rev: 1)", design_to_info(design))

    def test_fork_copies_configs(self):
        self.init_design()
        self.fork_design(1, 1)
        source, target = self.design_dir(1, 1), self.design_dir(2, 1)
        self.assertEqual(sorted(os.listdir(target)), sorted(os.listdir(source)))
        for name in os.listdir(source):
            self.assertEqual(read_config(os.path.join(source, name)), read_config(os.path.join(target, name)))

    def test_fork_keeps_source_untouched(self):
        self.init_design()
        self.fork_design(1, 1)
        write_config(os.path.join(self.design_dir(2, 1), "panel_param.json"), {"touched": True})
        self.assertIn("p_width", read_config(os.path.join(self.design_dir(1, 1), "panel_param.json")))

    def test_fork_rejects_non_ready_source(self):
        self.init_design()
        self.add_editing_rev(1, 2)
        os.makedirs(self.scratchpad_dir(1, 2), exist_ok=True)
        ok, label, info = self.fork_design(1, 2)
        self.assertFalse(ok)
        self.assertIn(f"is in status `{DESIGN_EDITING_LABEL}`", info)
        self.assertIn(f"Only a design in status `{DESIGN_READY_LABEL}` can be forked", info)
        self.assertFalse(os.path.exists(self.design_dir(2, 1)))

    def test_fork_rejects_unknown_design_and_revision(self):
        self.init_design()
        ok, _, info = self.fork_design(9, 1)
        self.assertFalse(ok)
        self.assertIn("Design with id: 9 not found", info)
        ok, _, info = self.fork_design(1, 5)
        self.assertFalse(ok)
        self.assertIn("has no revision 5", info)

    def test_fork_does_not_register_on_failure(self):
        self.init_design()
        self.fork_design(9, 1)
        self.assertEqual(len(self.design_man.list_revisions()), 1)
        self.assertFalse(self.design_man.get_design(2, 1)[0])


class TestModifyDesign(SimulatorTestBase):
    """modify: new revision under the SAME design id, editing status, scratchpad populated"""

    def test_modify_allocates_editing_revision(self):
        self.init_design()
        ok, label, info = self.modify_design(1, 1, subject="rev2 WIP")
        self.assertTrue(ok, info)
        design = self.design_man.get_design(1, 2)[1]
        self.assertEqual(design["design_id"], 1)
        self.assertEqual(design["design_rev"], 2)
        self.assertEqual(design["status"], DesignStatus.EDITING)
        self.assertEqual((design["copy_id"], design["copy_rev"]), (1, 1))

    def test_modify_creates_populated_scratchpad(self):
        self.init_design()
        self.modify_design(1, 1)
        scratchpad, source = self.scratchpad_dir(1, 2), self.design_dir(1, 1)
        self.assertTrue(os.path.isdir(scratchpad))
        self.assertEqual(sorted(os.listdir(scratchpad)), sorted(os.listdir(source)))
        self.assertFalse(os.path.exists(self.design_dir(1, 2)))

    def test_modify_returns_scratchpad_path_to_llm(self):
        self.init_design()
        ok, _, info = self.modify_design(1, 1)
        self.assertIn(self.scratchpad_dir(1, 2), info)
        self.assertIn("is allocated for modification", info)
        self.assertIn("can NOT be simulated until it is submitted", info)

    def test_modify_rejects_non_ready_source(self):
        self.init_design()
        self.add_editing_rev(1, 2)
        os.makedirs(self.scratchpad_dir(1, 2), exist_ok=True)
        ok, _, info = self.modify_design(1, 2)
        self.assertFalse(ok)
        self.assertIn(f"Only a design in status `{DESIGN_READY_LABEL}` can be modified", info)
        self.assertEqual(len(self.design_man.list_design_revision(1)[1]), 2)

    def test_modify_rejects_unknown_design_and_revision(self):
        self.init_design()
        ok, _, info = self.modify_design(9, 1)
        self.assertFalse(ok)
        self.assertIn("Design with id: 9 not found", info)
        ok, _, info = self.modify_design(1, 7)
        self.assertFalse(ok)
        self.assertIn("has no revision 7", info)

    def test_modify_rejects_missing_source_dir(self):
        self.init_design()
        shutil.rmtree(self.design_dir(1, 1))
        ok, _, info = self.modify_design(1, 1)
        self.assertFalse(ok)
        self.assertIn("path doesn't exist", info)

    def test_second_modify_on_same_source_is_allowed(self):
        """by design, only the source status is checked, so several in-flight revisions may coexist"""
        self.init_design()
        self.assertTrue(self.modify_design(1, 1)[0])
        self.assertTrue(self.modify_design(1, 1)[0])
        self.assertEqual(self.status_of(1, 2), DesignStatus.EDITING)
        self.assertEqual(self.status_of(1, 3), DesignStatus.EDITING)
        self.assertTrue(os.path.isdir(self.scratchpad_dir(1, 2)))
        self.assertTrue(os.path.isdir(self.scratchpad_dir(1, 3)))


class TestSubmitDesign(SimulatorTestBase):
    """submit: completeness gate, config copy of the listed files only, status flip"""

    def setUp(self):
        super().setUp()
        self.init_design()
        self.assertTrue(self.modify_design(1, 1)[0])

    def test_submit_flips_status_to_ready(self):
        ok, label, info = self.submit_design(1, 2)
        self.assertTrue(ok, info)
        self.assertEqual(self.status_of(1, 2), DesignStatus.READY)

    def test_submit_copies_only_listed_configs(self):
        scratchpad = self.scratchpad_dir(1, 2)
        write_config(os.path.join(scratchpad, "stray.json"), {"stray": True})
        with open(os.path.join(scratchpad, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("notes")
        ok, _, info = self.submit_design(1, 2)
        self.assertTrue(ok, info)
        copied = sorted(os.listdir(self.design_dir(1, 2)))
        self.assertEqual(copied, sorted(DESIGN_CONFIG_SCHEMAS.keys()))
        self.assertNotIn("stray.json", copied)
        self.assertNotIn("notes.txt", copied)

    def test_submit_keeps_scratchpad(self):
        self.submit_design(1, 2)
        self.assertTrue(os.path.isdir(self.scratchpad_dir(1, 2)))

    def test_submit_copies_optional_but_present_config(self):
        """heat_flux.json is not required when extra_hflux is false, but it is in the list and present, so it is copied"""
        panel = read_config(os.path.join(self.scratchpad_dir(1, 2), "panel_param.json"))
        panel["extra_hflux"] = False
        write_config(os.path.join(self.scratchpad_dir(1, 2), "panel_param.json"), panel)
        self.assertTrue(self.submit_design(1, 2)[0])
        self.assertTrue(os.path.isfile(os.path.join(self.design_dir(1, 2), "heat_flux.json")))

    def test_submit_rejects_ready_revision(self):
        ok, _, info = self.submit_design(1, 1)
        self.assertFalse(ok)
        self.assertIn(f"is in status `{DESIGN_READY_LABEL}`", info)
        self.assertIn(f"Only a design in status `{DESIGN_EDITING_LABEL}` can be submitted", info)

    def test_submit_rejects_unknown_design(self):
        ok, _, info = self.submit_design(9, 1)
        self.assertFalse(ok)
        self.assertIn("Design with id: 9 not found", info)

    def test_submit_rejects_missing_scratchpad(self):
        shutil.rmtree(self.scratchpad_dir(1, 2))
        ok, _, info = self.submit_design(1, 2)
        self.assertFalse(ok)
        self.assertIn("scratchpad path doesn't exist", info)

    def test_submit_rejects_incomplete_configs_and_keeps_editing(self):
        os.remove(os.path.join(self.scratchpad_dir(1, 2), "model_param.json"))
        ok, _, info = self.submit_design(1, 2)
        self.assertFalse(ok)
        self.assertIn("configs are incomplete", info)
        self.assertIn("model_param.json", info)
        self.assertEqual(self.status_of(1, 2), DesignStatus.EDITING)
        self.assertFalse(os.path.exists(self.design_dir(1, 2)))

    def test_submit_rejects_missing_field_and_keeps_editing(self):
        panel_path = os.path.join(self.scratchpad_dir(1, 2), "panel_param.json")
        panel = read_config(panel_path)
        panel.pop("p_height")
        write_config(panel_path, panel)
        ok, _, info = self.submit_design(1, 2)
        self.assertFalse(ok)
        self.assertIn("panel_param.json -> p_height", info)
        self.assertEqual(self.status_of(1, 2), DesignStatus.EDITING)

    def test_failed_submit_then_fixed_submit_succeeds(self):
        panel_path = os.path.join(self.scratchpad_dir(1, 2), "panel_param.json")
        panel = read_config(panel_path)
        panel.pop("p_height")
        write_config(panel_path, panel)
        self.assertFalse(self.submit_design(1, 2)[0])

        panel["p_height"] = 1080
        write_config(panel_path, panel)
        self.assertTrue(self.submit_design(1, 2)[0])
        self.assertEqual(self.status_of(1, 2), DesignStatus.READY)
        self.assertIn("p_height", read_config(os.path.join(self.design_dir(1, 2), "panel_param.json")))



if __name__ == "__main__":
    unittest.main(verbosity=2)
