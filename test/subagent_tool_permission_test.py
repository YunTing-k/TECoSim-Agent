# -*- coding: utf-8 -*-
"""
Unit tests for subagent tool allowlists and permission presets: no subagent may see a tool it is never allowed to
call, and the explorer must only get read-only tools.

Run with: python -m unittest test.subagent_tool_permission_test
          python test/subagent_tool_permission_test.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)  # tool implementations log expected failures at ERROR level

import unittest

from argparse import Namespace

from src.agent.agent_types import (
    EXPLORER_AGENT_LABEL, PERMISSION_PRESETS, SCHEDULER_AGENT_LABEL, SUPPORTED_TYPES, SUPPORTED_TYPES_DESC,
    WORKER_AGENT_LABEL)
from src.agent.subagent import SubAgent
from src.constants import *
from src.context.agent_context import AgentContext
from test.simulator_test_utils import DESIGN_TOOLS, READONLY_SIM_TOOLS, SimulatorTestBase


class TestSubagentToolPermissionConsistency(SimulatorTestBase):
    """subagent tool allowlists and permission presets must agree: no tool visible but always denied"""

    def build_subagent_tools(self, subagent_type: str):
        parent = AgentContext()
        parent.args = Namespace(dangerously_allow_all=False, nosimtools=False)
        # minimal api configs: SubAgent.__init__ only reads "<MODEL_TYPE>_MODEL_NAME"
        parent.api_configs = {"MAIN_MODEL_NAME": "test-main", "MEDIUM_MODEL_NAME": "test-medium",
                              "FAST_MODEL_NAME": "test-fast"}
        agent = SubAgent(parent_ctx=parent, subagent_type=subagent_type, subject="audit", prompt="audit",
                         agent_id="0" * AGENT_ID_LEN, console=None)
        agent.build_tools()
        return [t["function"]["name"] for t in agent.ctx.tools], agent.ctx.permissions

    def test_explorer_has_read_only_simulation_tools(self):
        names, _ = self.build_subagent_tools(EXPLORER_AGENT_LABEL)
        for tool in READONLY_SIM_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, names)

    def test_explorer_cannot_modify_designs(self):
        names, _ = self.build_subagent_tools(EXPLORER_AGENT_LABEL)
        for tool in DESIGN_TOOLS:
            with self.subTest(tool=tool):
                self.assertNotIn(tool, names)

    def test_worker_has_design_tools_granted(self):
        names, permissions = self.build_subagent_tools(WORKER_AGENT_LABEL)
        for tool in DESIGN_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, names)
                self.assertTrue(permissions.get(tool, False), f"{tool} must be granted for worker")

    def test_worker_has_read_image_and_skill_granted(self):
        names, permissions = self.build_subagent_tools(WORKER_AGENT_LABEL)
        for tool in (TOOL_NAME_READ_IMAGE, TOOL_NAME_SKILL):
            with self.subTest(tool=tool):
                self.assertIn(tool, names)
                self.assertTrue(permissions.get(tool, False))

    def test_worker_cannot_spawn_or_send_wechat_files(self):
        names, _ = self.build_subagent_tools(WORKER_AGENT_LABEL)
        self.assertNotIn(TOOL_NAME_SPAWN_AGENT, names)
        self.assertNotIn(TOOL_NAME_WECHAT_SEND_FILE, names)

    def test_no_visible_but_denied_tool(self):
        """every permission-gated tool a subagent can see must be granted (bash is gated per risk label instead)"""
        gated_tools = (DESIGN_TOOLS + (TOOL_NAME_READ_IMAGE, TOOL_NAME_SKILL, TOOL_NAME_WECHAT_SEND_FILE,
                                       TOOL_NAME_READ_LOG, TOOL_NAME_GLOB_FILE, TOOL_NAME_GREP_FILE,
                                       TOOL_NAME_READ_FILE, TOOL_NAME_WRITE_FILE, TOOL_NAME_WEB_FETCH,
                                       TOOL_NAME_WEB_SEARCH))
        for subagent_type in (EXPLORER_AGENT_LABEL, WORKER_AGENT_LABEL, SCHEDULER_AGENT_LABEL):
            names, permissions = self.build_subagent_tools(subagent_type)
            for tool in gated_tools:
                if tool in names:
                    with self.subTest(subagent_type=subagent_type, tool=tool):
                        self.assertTrue(permissions.get(tool, False))

    def test_type_descriptions_match_allowlists(self):
        """the LLM-facing description of explorer must mention the read-only simulation tools it actually has"""
        for tool in READONLY_SIM_TOOLS:
            with self.subTest(tool=tool, where="allowlist"):
                self.assertIn(tool, SUPPORTED_TYPES[EXPLORER_AGENT_LABEL])
            with self.subTest(tool=tool, where="description"):
                self.assertIn(tool, SUPPORTED_TYPES_DESC[EXPLORER_AGENT_LABEL])

    def test_presets_only_reference_known_tools(self):
        known = set(SUPPORTED_TYPES_DESC.keys())
        for subagent_type, perms in PERMISSION_PRESETS.items():
            with self.subTest(subagent_type=subagent_type):
                self.assertIn(subagent_type, known)
                self.assertIsInstance(perms, tuple)


if __name__ == "__main__":
    unittest.main(verbosity=2)



if __name__ == "__main__":
    unittest.main(verbosity=2)
