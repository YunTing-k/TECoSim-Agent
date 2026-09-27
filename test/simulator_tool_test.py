# -*- coding: utf-8 -*-
"""
Unit tests for the LLM-facing exposure of the design tools: registration, --nosimtools gating, permission map and
tool schemas.

Run with: python -m unittest test.simulator_tool_test
          python test/simulator_tool_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import json
import unittest

from argparse import Namespace

from src.context.agent_context import AgentContext, PERMISSION_LABEL_TO_NAME_MAP
from src.tool.tool_def import create_tools_prompts
from test.simulator_test_utils import DESIGN_TOOLS, READONLY_SIM_TOOLS, SimulatorTestBase


class TestToolRegistration(SimulatorTestBase):
    """the new design tools are exposed to the LLM, gated by --nosimtools and registered in the permission map"""

    def build_tools(self, nosimtools: bool = False):
        ctx = AgentContext()
        ctx.args = Namespace(nosimtools=nosimtools)
        return [t["function"]["name"] for t in create_tools_prompts(ctx)]

    def test_design_tools_registered(self):
        names = self.build_tools()
        for tool in DESIGN_TOOLS + READONLY_SIM_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, names)

    def test_nosimtools_hides_design_tools(self):
        names = self.build_tools(nosimtools=True)
        for tool in DESIGN_TOOLS + READONLY_SIM_TOOLS:
            with self.subTest(tool=tool):
                self.assertNotIn(tool, names)

    def test_tools_in_permission_map(self):
        for tool in DESIGN_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, PERMISSION_LABEL_TO_NAME_MAP.values())
                self.assertIn(tool, AgentContext().permissions)

    def test_tool_schemas_are_valid(self):
        ctx = AgentContext()
        ctx.args = Namespace(nosimtools=False)
        for tool_def in create_tools_prompts(ctx):
            if tool_def["function"]["name"] in DESIGN_TOOLS:
                with self.subTest(tool=tool_def["function"]["name"]):
                    json.dumps(tool_def)
                    parameters = tool_def["function"]["parameters"]
                    self.assertEqual(parameters["type"], "object")
                    self.assertTrue(parameters["required"])
                    self.assertFalse(parameters["additionalProperties"])



if __name__ == "__main__":
    unittest.main(verbosity=2)
