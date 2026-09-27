# -*- coding: utf-8 -*-
"""
Unit tests for the design input contract: `check_design_completeness` (required files, conditional files, required
fields). Field types and field values are intentionally not checked by the implementation.

Run with: python -m unittest test.simulator_design_config_test
          python test/simulator_design_config_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import shutil
import unittest

from src.tool.simulator_param import (
    COUPLE_TYPES_WITH_IRD, DESIGN_CONFIG_REQUIRED, DESIGN_CONFIG_SCHEMAS)
from src.tool.simulator_support import check_design_completeness
from test.simulator_test_utils import SimulatorTestBase, build_design_configs, read_config, write_config


class TestDesignCompleteness(SimulatorTestBase):
    """check_design_completeness: required files (unconditional + conditional) and required fields"""

    def setUp(self):
        super().setUp()
        self.design_path = os.path.join(self.tmpdir, "completeness")
        build_design_configs(self.design_path)

    def check(self):
        return check_design_completeness(self.design_path)

    def test_complete_configs_pass(self):
        self.assertEqual(self.check(), (True, ""))

    def test_unconditional_required_list(self):
        self.assertEqual(DESIGN_CONFIG_REQUIRED,
                         ["run.json", "model_param.json", "panel_param.json", "simulation_param.json"])

    def test_missing_unconditional_file(self):
        for name in DESIGN_CONFIG_REQUIRED:
            with self.subTest(name=name):
                os.remove(os.path.join(self.design_path, name))
                ok, info = self.check()
                self.assertFalse(ok)
                self.assertIn(f"Required config file(s) missing: {name}", info)
                build_design_configs(self.design_path)

    def test_missing_all_files(self):
        shutil.rmtree(self.design_path)
        os.makedirs(self.design_path)
        ok, info = self.check()
        self.assertFalse(ok)
        for name in DESIGN_CONFIG_REQUIRED:
            self.assertIn(name, info)

    def test_conditional_heat_contact_required_by_flag(self):
        os.remove(os.path.join(self.design_path, "heat_contact.json"))
        panel = read_config(os.path.join(self.design_path, "panel_param.json"))
        panel["extra_hcontact"] = True
        write_config(os.path.join(self.design_path, "panel_param.json"), panel)
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("heat_contact.json", info)

    def test_conditional_heat_flux_required_by_flag(self):
        os.remove(os.path.join(self.design_path, "heat_flux.json"))
        panel = read_config(os.path.join(self.design_path, "panel_param.json"))
        panel["extra_hflux"] = True
        write_config(os.path.join(self.design_path, "panel_param.json"), panel)
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("heat_flux.json", info)

    def test_conditional_files_not_required_when_disabled(self):
        """extra_hflux / extra_hcontact stay false (0) and couple_type stays 0, so only the 4 core files are needed"""
        os.remove(os.path.join(self.design_path, "heat_contact.json"))
        os.remove(os.path.join(self.design_path, "heat_flux.json"))
        os.remove(os.path.join(self.design_path, "pdn_injection.json"))
        self.assertEqual(self.check(), (True, ""))

    def test_pdn_injection_required_by_couple_type(self):
        self.assertIn(5, COUPLE_TYPES_WITH_IRD)
        os.remove(os.path.join(self.design_path, "pdn_injection.json"))
        for couple_type in (0, 1):
            with self.subTest(couple_type=couple_type):
                sim = read_config(os.path.join(self.design_path, "simulation_param.json"))
                sim["couple_type"] = couple_type
                write_config(os.path.join(self.design_path, "simulation_param.json"), sim)
                self.assertEqual(self.check(), (True, ""))
        for couple_type in COUPLE_TYPES_WITH_IRD:
            with self.subTest(couple_type=couple_type):
                sim = read_config(os.path.join(self.design_path, "simulation_param.json"))
                sim["couple_type"] = couple_type
                write_config(os.path.join(self.design_path, "simulation_param.json"), sim)
                ok, info = self.check()
                self.assertFalse(ok)
                self.assertIn("pdn_injection.json", info)

    def test_flag_truthiness_controls_conditional_files(self):
        """the flag is evaluated by truthiness, so a truthy non-boolean counts as enabled (documented behavior)"""
        os.remove(os.path.join(self.design_path, "heat_flux.json"))
        panel_path = os.path.join(self.design_path, "panel_param.json")
        for value, expect_required in ((0, False), (1, True), (True, True), (False, False)):
            with self.subTest(extra_hflux=value):
                panel = read_config(panel_path)
                panel["extra_hflux"] = value
                write_config(panel_path, panel)
                ok, info = self.check()
                if expect_required:
                    self.assertFalse(ok)
                    self.assertIn("heat_flux.json", info)
                else:
                    self.assertEqual((ok, info), (True, ""))

    def test_missing_fields_are_reported(self):
        panel_path = os.path.join(self.design_path, "panel_param.json")
        panel = read_config(panel_path)
        panel.pop("p_width")
        panel.pop("th_c")
        write_config(panel_path, panel)
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("panel_param.json -> p_width, th_c", info)

    def test_missing_fields_in_several_files_are_all_reported(self):
        panel_path = os.path.join(self.design_path, "panel_param.json")
        panel = read_config(panel_path)
        panel.pop("p_width")
        write_config(panel_path, panel)
        run_path = os.path.join(self.design_path, "run.json")
        run = read_config(run_path)
        run.pop("cuda_device")
        write_config(run_path, run)
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("panel_param.json -> p_width", info)
        self.assertIn("run.json -> cuda_device", info)

    def test_every_schema_field_is_required(self):
        """the checker derives required fields from the schemas, so a field added to simulator_param.py is checked too"""
        # enable every conditional config file so that all schemas are part of the required set
        panel_path = os.path.join(self.design_path, "panel_param.json")
        panel = read_config(panel_path)
        panel["extra_hcontact"] = True
        panel["extra_hflux"] = True
        write_config(panel_path, panel)
        sim_path = os.path.join(self.design_path, "simulation_param.json")
        sim = read_config(sim_path)
        sim["couple_type"] = COUPLE_TYPES_WITH_IRD[0]
        write_config(sim_path, sim)
        self.assertEqual(self.check(), (True, ""))

        for config_name, schema in DESIGN_CONFIG_SCHEMAS.items():
            with self.subTest(config_name=config_name):
                path = os.path.join(self.design_path, config_name)
                backup = read_config(path)
                for field in sorted(schema.__required_keys__):
                    data = dict(backup)
                    data.pop(field)
                    write_config(path, data)
                    ok, info = self.check()
                    self.assertFalse(ok, f"{config_name}:{field} should be reported as missing")
                    self.assertIn(field, info)
                write_config(path, backup)

    def test_invalid_json_is_reported_with_file_name(self):
        with open(os.path.join(self.design_path, "run.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("run.json", info)
        self.assertIn("not valid JSON", info)

    def test_non_object_json_is_reported(self):
        write_config(os.path.join(self.design_path, "run.json"), {"unused": True})
        with open(os.path.join(self.design_path, "run.json"), "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")
        ok, info = self.check()
        self.assertFalse(ok)
        self.assertIn("run.json", info)
        self.assertIn("not a JSON object", info)



if __name__ == "__main__":
    unittest.main(verbosity=2)
