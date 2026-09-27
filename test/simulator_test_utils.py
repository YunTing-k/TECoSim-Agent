# -*- coding: utf-8 -*-
"""
Shared fixtures for the simulation design/run test modules (not a test module itself: the name does not match
`*_test.py`, so it is never collected by pytest / unittest discovery).

The fixtures are hermetic and side-effect free:
- `SESSION_PATH` is redirected to a temporary directory, so nothing is written under the real `session/` folder.
- The simulator path points at a synthetic config set built from `simulator_param.DESIGN_CONFIG_SCHEMAS`, so no
  TECoSim installation is required.
- `subprocess` is always replaced by a fake in the tests that need it, so `TECoSim.exe` / `clean.bat` never run.
Temporary files are removed in `addCleanup`, so they are cleaned up even when an assertion fails.
"""
import io
import json
import os
import shutil
import tempfile
import unittest
import uuid

from unittest.mock import patch

from rich.console import Console
from src.constants import *
from src.tool import simulator_support as ss
from src.tool.simulator_param import DESIGN_CONFIG_SCHEMAS
from src.tool.simulator_support import (
    DesignManager, RunManager, DesignStatus, fork_design_impl, init_design_impl, modify_design_impl,
    submit_design_impl)

DESIGN_TOOLS = (TOOL_NAME_INIT_DESIGN, TOOL_NAME_FORK_DESIGN, TOOL_NAME_MODIFY_DESIGN, TOOL_NAME_SUBMIT_DESIGN,
                TOOL_NAME_LAUNCH_SIM)
READONLY_SIM_TOOLS = (TOOL_NAME_CHECK_SIMULATOR, TOOL_NAME_QUERY_DESIGN, TOOL_NAME_QUERY_RUN, TOOL_NAME_READ_LOG)


def build_design_configs(dst: str, **overrides) -> None:
    """materialize a complete design config set from the schemas (field values are placeholders: only names matter)"""
    os.makedirs(dst, exist_ok=True)
    for config_name, schema in DESIGN_CONFIG_SCHEMAS.items():
        data = {field: 0 for field in schema.__required_keys__}
        data.update(overrides.get(config_name, {}))
        with open(os.path.join(dst, config_name), "w", encoding="utf-8") as f:
            json.dump(data, f)


def write_config(path: str, data: dict) -> None:
    """overwrite one design config file with the given raw content"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def read_config(path: str) -> dict:
    """read one design config file as a JSON object"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class FakeProc:
    """stand-in for subprocess.Popen so the simulator is never actually launched"""
    returncode = 0
    args = ["TECoSim.exe"]

    def communicate(self, timeout=None):
        return b"[info] fake stdout", b"[info] fake stderr"


class SimulatorTestBase(unittest.TestCase):
    """shared fixture: temporary session root, synthetic simulator configs, design/run managers"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="tesi_sim_")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        # redirect every session path into the temporary directory (Path / absolute -> absolute)
        patcher = patch.object(ss, "SESSION_PATH", self.tmpdir)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.console = Console(file=io.StringIO(), width=120)
        self.session_uuid = str(uuid.uuid4())
        self.session_dir = os.path.join(self.tmpdir, self.session_uuid)
        os.makedirs(self.session_dir, exist_ok=True)

        self.sim_path = os.path.join(self.tmpdir, "sim")
        build_design_configs(os.path.join(self.sim_path, "config"))

        self.design_man = DesignManager()
        self.design_man.session_uuid = self.session_uuid
        self.design_man.simulator_path = self.sim_path
        self.run_man = RunManager()
        self.run_man.session_uuid = self.session_uuid
        self.run_man.simulator_path = self.sim_path
        self.run_man.time_out = 5

    # ---------- helpers ----------

    def design_dir(self, design_id: int, design_rev) -> str:
        return os.path.join(self.session_dir, f"{SIM_DESIGN_NAME}{design_id}", str(design_rev))

    def scratchpad_dir(self, design_id: int, design_rev: int) -> str:
        return os.path.join(self.session_dir, f"{SIM_DESIGN_NAME}{design_id}",
                            f"{design_rev}{SIM_SCRATCHPAD_SUFFIX}")

    def init_design(self, subject: str = "baseline", description: str = "default") -> int:
        ok, label, info = init_design_impl({"subject": subject, "description": description},
                                           self.design_man, self.console)
        self.assertTrue(ok, info)
        return self.design_man.list_revisions()[0]["design_id"]

    def modify_design(self, design_id: int, design_rev: int, subject: str = "wip", description: str = "edit"):
        return modify_design_impl({"design_id": design_id, "design_rev": design_rev, "subject": subject,
                                   "description": description}, self.design_man, self.console)

    def fork_design(self, design_id: int, design_rev: int, subject: str = "branch", description: str = "fork"):
        return fork_design_impl({"design_id": design_id, "design_rev": design_rev, "subject": subject,
                                 "description": description}, self.design_man, self.console)

    def submit_design(self, design_id: int, design_rev: int):
        return submit_design_impl({"design_id": design_id, "design_rev": design_rev}, self.design_man, self.console)

    def add_editing_rev(self, design_id: int, design_rev: int) -> None:
        """allocate an editing revision with its scratchpad through the real modify path"""
        ok, label, info = self.modify_design(design_id, design_rev - 1)
        self.assertTrue(ok, info)
        self.assertEqual(self.design_man.get_design(design_id, design_rev)[1]["status"], DesignStatus.EDITING)

    def status_of(self, design_id: int, design_rev: int) -> DesignStatus:
        return self.design_man.get_design(design_id, design_rev)[1]["status"]

    def assert_no_subprocess(self, popen_mock, run_mock):
        """a refused launch must not clean up or spawn anything"""
        self.assertEqual(popen_mock.call_count, 0)
        self.assertEqual(run_mock.call_count, 0)
