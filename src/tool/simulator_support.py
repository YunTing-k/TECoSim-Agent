# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.27
Description: Design, run management and simulator launch/log-read implementations

Revision:
---------
2026.5.27      Yu Huang      1.0      First implementation
2026.6.8       Yu Huang      1.1      Remove simulator params to simulator_param.py & Simulator run management support
2026.6.9       Yu Huang      1.2      Add design and run support for simulator & Revise the highlight of the IO console print
2026.6.11      Yu Huang      1.3      Adopt XML-wrapped pipe-format in read_log_impl via format_file_for_llm

Details:
---------
Core backend for TECoSim simulation toolchain. (1) DesignManager — thread-safe design CRUD with revision tracking
(init/get/list/save/load), each design identified by (design_id, revision_id). (2) RunManager — thread-safe simulation run registry
with id auto-increment, status tracking (PENDING/DONE/CANCELLED/TIMEOUT/RUNTIME_ERROR), and persist to JSON. (3) Tool
implementations: init_design copies default configs from simulator path; launch_sim spawns TECoSim.exe as subprocess with
timeout/cancel/error handling, saves stdout/stderr logs on exit; read_log reads cleaned logs with byte-limit enforcement
and three access methods (from_top/from_bottom/offset). (4) Helper formatting functions for user-facing info strings.
"""
import os
import re
import shutil
import uuid
import json
import logging
import threading
import subprocess

from enum import Enum
from typing import Any, TypedDict
from rich.console import Console
from src.utility.basic_utils import read_line_with_limit, format_file_for_llm
from src.constants import *

sys_log = logging.getLogger('logger')


def clean_stdout_log(content: str) -> list[str]:
    """remove the redundancy in the input stdout log str"""
    pattern = re.compile(r'\[(debug|info|warning|error)]', re.IGNORECASE)
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        if not line.strip():
            continue
        if "print_start_banner" in line:
            continue
        if "print_end_banner" in line:
            continue
        if "print_error_banner" in line:
            continue
        if "print_abort_banner" in line:
            continue
        match = pattern.search(line)
        if match:
            start = match.start()
            line = line[start:]
        cleaned_lines.append(line)
    # return "\n".join(cleaned_lines)
    return cleaned_lines


def clean_stderr_log(content: str) -> list[str]:
    """remove the redundancy in the input stderr log str"""
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        if not line.strip():
            continue
        if "libx264 @" in line:
            continue
        if "psnr @" in line:
            continue
        if "ssim @" in line:
            continue
        if "vmaf @" in line:
            continue
        if "std::cerr abort_banner" in line:
            continue
        cleaned_lines.append(line)
    # return "\n".join(cleaned_lines)
    return cleaned_lines


class DesignInit(TypedDict):
    """Design information to update into list (initialize a new one)"""
    subject: str
    description: str


class Design(TypedDict):
    """Design information"""
    design_uuid: int  # unique ID
    design_id: int  # different Design can own same design ID
    design_rev: int  # revision ID is different in same design ID
    subject: str
    description: str
    copy_id: int | None
    copy_rev: int | None


class Revision(TypedDict):
    """Revision information"""
    design_id: int
    revision_uuids: dict[int, int]  # {revision ID, unique ID}
    next_rev_id: int  # revision ID


class DesignManager:
    """Shared, thread-safe simulation design manager for multi-agent coordination.

    TODO: modify design, copy design
    """
    def __init__(self):
        self.session_uuid: str = ""  # don't dump
        self.simulator_path: str = ""  # don't dump
        self._lock = threading.Lock()
        self._designs: dict[int, Design] = {}  # {uuid, Design}
        self._revisions: dict[int, Revision] = {}  # {Design ID, Revision}
        self._next_design_id: int = 1
        self._next_design_uuid: int = 1


    def init_design(self, design_init: DesignInit) -> tuple[bool, int, str]:
        """insert a brand-new design"""
        with self._lock:
            try:
                # create empty revision
                revision = Revision(
                    design_id=self._next_design_id,
                    revision_uuids={},
                    next_rev_id=1
                )
                # create design according to revision
                design = Design(
                    design_uuid=self._next_design_uuid,
                    design_id=self._next_design_id,
                    design_rev=revision["next_rev_id"],
                    subject=design_init["subject"],
                    description=design_init["description"],
                    copy_id=None,
                    copy_rev=None,
                )
                # update revision
                revision["revision_uuids"][design["design_rev"]] = design["design_uuid"]
                revision["next_rev_id"] += 1
                # insert a new design
                self._designs[self._next_design_uuid] = design
                # insert a new revision
                self._revisions[self._next_design_id] = revision
                self._next_design_uuid += 1
                self._next_design_id += 1
                return True, design["design_id"], f"Design with id {design["design_id"]} initialized. Revision start from 1"
            except Exception as e:
                return False, -1, f"Initialize design failed with error: {e}"


    def list_revisions(self) -> list[Revision]:
        """list all revisions in manager"""
        with self._lock:
            return [revision for revision in self._revisions.values()]


    def list_designs(self) -> list[Design]:
        """list all unstructured designs in manager"""
        with self._lock:
            return [design for design in self._designs.values()]


    def get_design_uuid(self, design_uuid: int) -> tuple[bool, Design | None, str]:
        """get a design by design uuid"""
        with self._lock:
            if design_uuid not in self._designs:
                return False, None, f"Design with uuid: {design_uuid} not found in designs"
            design = self._designs[design_uuid]
            return True, design, SUCCESS_LABEL


    def get_design(self, design_id: int, design_rev: int) -> tuple[bool, Design | None, str]:
        """get a design by design id and revision id"""
        with self._lock:
            if design_id not in self._revisions:
                return False, None, f"Design with id: {design_id} not found"
            if design_rev not in self._revisions[design_id]["revision_uuids"]:
                return False, None, f"Design with id: {design_id} has no revision {design_rev}"
            uuid_map = self._revisions[design_id]["revision_uuids"]
            design_uuid = uuid_map[design_rev]
            if design_uuid not in self._designs:
                return False, None, f"Design (id: {design_uuid}, rev: {design_rev}) logged in revision but not found in designs"
            design = self._designs[design_uuid]
            return True, design, SUCCESS_LABEL


    def list_design_revision(self, design_id: int) -> tuple[bool, list[Design], str]:
        """list all revisions under a design ID"""
        with self._lock:
            if design_id not in self._revisions:
                return False, [], f"Design with id: {design_id} not found"
            designs: list[Design] = []
            uuid_map = self._revisions[design_id]["revision_uuids"]
            for design_uuid in uuid_map.values():
                if design_uuid not in self._designs:
                    continue
                designs.append(self._designs[design_uuid])
            return True, designs, SUCCESS_LABEL


    def list_latest_revisions(self) -> list[Design]:
        """list latest revision of all designs"""
        with self._lock:
            designs: list[Design] = []
            for revision in self._revisions.values():
                latest_revision = revision["next_rev_id"] - 1
                uuid_map = revision["revision_uuids"]
                if latest_revision not in uuid_map:
                    continue
                design_uuid = uuid_map[latest_revision]
                if design_uuid not in self._designs:
                    continue
                designs.append(self._designs[design_uuid])
            return designs


    def save_to_file(self, console: Console, mute: bool = False):
        """save all designs info to a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                designs_data = []
                for design in self._designs.values():
                    design_copy = dict(design)
                    designs_data.append(design_copy)
                revisions_data = []
                for revision in self._revisions.values():
                    revision_copy = dict(revision)
                    revisions_data.append(revision_copy)

                data = {
                    "next_design_uuid": self._next_design_uuid,
                    "next_design_id": self._next_design_id,
                    "designs": designs_data,
                    "revisions": revisions_data,
                }
                path = os.path.join(SESSION_PATH, uuid_str, DESIGNS_NAME)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if not mute:
                    sys_log.debug(f"Designs information of session {self.session_uuid} saved")
                    console.print(f"[{MAJOR_COLOR2}]Designs information[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                                  f"[/bright_black] saved")
            except Exception as e:
                sys_log.error(f"Failed to save session {self.session_uuid}'s designs information with error: {e}")
                console.print(f"Failed to save session {self.session_uuid}'s designs information with error: {e}",
                              style="bold red")
                raise RuntimeError(e)


    def load_from_file(self, console: Console, mute: bool = False):
        """load designs info from a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                path = os.path.join(SESSION_PATH, uuid_str, DESIGNS_NAME)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._designs.clear()
                self._revisions.clear()
                for design_data in data["designs"]:
                    design = Design(**design_data)
                    self._designs[design["design_uuid"]] = design
                for revision_data in data["revisions"]:
                    revision_copy = dict(revision_data)
                    revision_copy["revision_uuids"] = {int(k): v for k, v in revision_data["revision_uuids"].items()}
                    revision = Revision(**revision_copy)
                    self._revisions[revision["design_id"]] = revision
                self._next_design_uuid = data["next_design_uuid"]
                self._next_design_id = data["next_design_id"]
                if not mute:
                    sys_log.debug(f"Designs information of session {self.session_uuid} loaded")
                    console.print(f"[{MAJOR_COLOR2}]Designs information[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                                  f"[/bright_black] loaded")
            except Exception as e:
                sys_log.error(f"Failed to load session {self.session_uuid}'s designs information with error: {e}")
                console.print(f"Failed to load session {self.session_uuid}'s designs information with error: {e}",
                              style="bold red")
                raise RuntimeError(e)


def design_to_info(design: Design) -> str:
    """convert design to info string"""
    info = ""
    info += f"Subject: {design["subject"]}\n"
    info += f"Description: {design["description"]}\n"
    if design["copy_id"] is None:
        info += f"Copy from: (None)"
    else:
        info += f"Copy from: {design['copy_id']} (rev: {design['copy_rev']})"
    return info


def designs_to_info(designs: list[Design]) -> str:
    """convert designs to info string"""
    info = ""
    for design in designs:
        info += f"Design ID: {design["design_id"]} (rev: {design["design_rev"]})\n"
        info += f" - Subject: {design["subject"]}\n"
        # info += f" - Description: {design["description"]}\n"
        if design["copy_id"] is None:
            info += f" - Copy from: (None)\n"
        else:
            info += f" - Copy from: {design['copy_id']} (rev: {design['copy_rev']})\n"
    if len(designs) == 0:
        info = f"(Design list is empty)"
    return info


class RunStatus(str, Enum):
    """Simulation run status enum"""
    PENDING = RUN_PENDING_LABEL
    CANCELLED = RUN_CANCELLED_LABEL
    TIMEOUT = RUN_TIMEOUT_LABEL
    RUNTIME_ERROR = RUN_RUNTIME_ERROR_LABEL
    DONE = RUN_DONE_LABEL


class RunInsert(TypedDict):
    """Run information to update into list (insert a launched run)"""
    design_id: int
    design_rev: int
    subject: str
    description: str
    status: RunStatus


class Run(TypedDict):
    """Run information"""
    run_id: int
    design_id: int
    design_rev: int
    subject: str
    description: str
    status: RunStatus


class RunManager:
    """Shared, thread-safe simulation run manager for multi-agent coordination.

    can insert run, can't modify one
    """
    def __init__(self):
        self.session_uuid: str = ""  # don't dump
        self.simulator_path: str = ""  # don't dump
        self.time_out: int = 0  # don't dump
        self._lock = threading.Lock()
        self._runs: dict[int, Run] = {}
        self._next_id: int = 1


    def insert_run(self, run_insert: RunInsert) -> tuple[bool, int, str]:
        """insert a given run"""
        with self._lock:
            try:
                run = Run(
                    run_id=self._next_id,
                    design_id=run_insert["design_id"],
                    design_rev=run_insert["design_rev"],
                    subject=run_insert["subject"],
                    description=run_insert["description"],
                    status=run_insert["status"],
                )
                self._runs[self._next_id] = run
                self._next_id += 1
                return True, run["run_id"], f"Run with id {run["run_id"]} inserted"
            except Exception as e:
                return False, -1, f"Run insert failed with error: {e}"

    def get_num(self):
        """get the number of runs"""
        return len(self._runs)


    def get_run(self, run_id: int) -> tuple[bool, Run | None, str]:
        """get a run from the manager"""
        with self._lock:
            """check if run exists"""
            if run_id not in self._runs:
                return False, None, f"Run with id {run_id} not found"
            """get the run"""
            try:
                run = self._runs[run_id]
                return True, run, SUCCESS_LABEL
            except Exception as e:
                return False, None, f"Get run failed with error: {e}"


    def list_runs(self) -> list[Run]:
        """list all runs in manager"""
        with self._lock:
            return [run for run in self._runs.values()]


    def save_to_file(self, console: Console, mute: bool = False):
        """save all runs info to a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                runs_data = []
                for run in self._runs.values():
                    run_copy = dict(run)
                    runs_data.append(run_copy)

                data = {
                    "next_id": self._next_id,
                    "runs": runs_data,
                }
                path = os.path.join(SESSION_PATH, uuid_str, RUNS_NAME)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if not mute:
                    sys_log.debug(f"Runs information of session {self.session_uuid} saved")
                    console.print(f"[{MAJOR_COLOR2}]Runs information[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                                  f"[/bright_black] saved")
            except Exception as e:
                sys_log.error(f"Failed to save session {self.session_uuid}'s runs information with error: {e}")
                console.print(f"Failed to save session {self.session_uuid}'s runs information with error: {e}",
                              style="bold red")
                raise RuntimeError(e)


    def load_from_file(self, console: Console, mute: bool = False):
        """load runs info from a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                path = os.path.join(SESSION_PATH, uuid_str, RUNS_NAME)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._runs.clear()
                for run_data in data["runs"]:
                    run_data["status"] = RunStatus(run_data["status"])
                    run = Run(**run_data)
                    self._runs[run["run_id"]] = run
                self._next_id = data["next_id"]
                if not mute:
                    sys_log.debug(f"Runs information of session {self.session_uuid} loaded")
                    console.print(f"[{MAJOR_COLOR2}]Runs information[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                                  f"[/bright_black] loaded")
            except Exception as e:
                sys_log.error(f"Failed to load session {self.session_uuid}'s runs information with error: {e}")
                console.print(f"Failed to load session {self.session_uuid}'s runs information with error: {e}",
                              style="bold red")
                raise RuntimeError(e)


def run_to_info(run: Run) -> str:
    """convert run to info string"""
    info = ""
    info += f"Input design: {run["design_id"]} (rev {run["design_rev"]})\n"
    info += f"Subject: {run["subject"]}\n"
    info += f"Description: {run["description"]}\n"
    info += f"Status: {run["status"].value}"
    return info


def runs_to_info(runs: list[Run]) -> str:
    """convert runs list to info string"""
    info = ""
    for run in runs:

        info += f"Run ID: {run["run_id"]}\n"
        info += f" - Subject: {run["subject"]}\n"
        # info += f" - Description: {run["description"]}\n"
        info += f" - Status: {run["status"].value}\n"
    if len(runs) == 0:
        info = f"(Run list is empty)"
    return info


def init_design_impl(arguments: dict[str, Any], design_man: DesignManager, console: Console) -> tuple[bool, str, str]:
    """initialize design implementation"""
    func_name = TOOL_NAME_INIT_DESIGN
    try:
        """create design"""
        design = DesignInit(
            subject=arguments["subject"],
            description=arguments["description"],
        )
        if_success, design_id, init_info = design_man.init_design(design)
        if not if_success:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {init_info}")
            console.print(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {init_info}", style="bold red")
            return False, FAIL_LABEL, f"Initialize design failed with error: {init_info}"
        path = os.path.join(SESSION_PATH, design_man.session_uuid, f"{SIM_DESIGN_NAME}{design_id}", f"{1}")
        os.makedirs(path, exist_ok=True)
        source_path = design_man.simulator_path + "/config"
        shutil.copytree(src=source_path, dst=path, dirs_exist_ok=True)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Design with id: {design_id} (rev 1) initialized")
        console.print(f"{func_name} {SUCCESS_LABEL}: Design with id: {design_id} (rev 1) initialized", style="bright_black")
        return True, SUCCESS_LABEL, f"Design with id: {design_id} (rev 1) initialized"
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}")
        console.print(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}", style="bold red")
        return False, FAIL_LABEL, e.__str__()


def save_simulator_logs(run_path: str, stdout: bytes, stderr: bytes):
    """save stdout and stderr logs of simulator"""
    stdout_str = stdout.decode('utf-8')
    with open(run_path + "/stdout.log", "w", encoding="utf-8", newline='') as f:
        if stdout_str is not None and stdout_str.strip():
            f.write(stdout_str)
        else:
            f.write("(stdout is empty)")
    stderr_str = stderr.decode('utf-8')
    with open(run_path + "/stderr.log", "w", encoding="utf-8", newline='') as f:
        if stderr_str is not None and stderr_str.strip():
            f.write(stderr_str)
        else:
            f.write("(stderr is empty)")


def launch_sim_impl(arguments: dict[str, Any], run_man: RunManager, console: Console) -> tuple[bool, str, str]:
    """launch simulator implementation"""
    func_name = TOOL_NAME_LAUNCH_SIM
    try:
        design_id = arguments["design_id"]
        design_rev = arguments["design_rev"]
        design_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_DESIGN_NAME}{design_id}", f"{design_rev}")
        """check the design"""
        if not os.path.exists(design_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Design (id: {design_id}, rev: {design_rev})'s path doesn't exist. `{SIM_RUN_NAME}` is not created. "
                          f"Launch failed")
            console.print(f"{func_name} {FAIL_LABEL}: "
                          f"Design (id: {design_id}, rev: {design_rev})'s path doesn't exist. `{SIM_RUN_NAME}` is not created. "
                          f"Launch failed", style="bold red")
            return False, FAIL_LABEL, (f"Design (id: {design_id}, rev: {design_rev})'s path doesn't exist. `{SIM_RUN_NAME}` "
                                       f"is not created. Launch failed")
        """clean up"""
        clean_up_re = subprocess.run([run_man.simulator_path + "/clean.bat", "1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if clean_up_re.returncode != 0 or clean_up_re.stdout is None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Clean up script exits with error. `{SIM_RUN_NAME}` is not created. Launch failed")
            console.print(f"{func_name} {FAIL_LABEL}: "
                          f"Clean up script exits with error. `{SIM_RUN_NAME}` is not created. Launch failed",
                          style="bold red")
            return False, FAIL_LABEL, f"Clean up script exits with error. `{SIM_RUN_NAME}` is not created. Launch failed"
        sys_log.debug(f"{func_name}: clean up done")
        console.print(f"{func_name}: clean up done", style="bright_black")
        """create run"""
        run = RunInsert(
            design_id=design_id,
            design_rev=design_rev,
            subject=arguments["subject"],
            description=arguments["description"],
            status = RunStatus.PENDING
        )
        sys_log.debug(f"{func_name}: {SIM_RUN_NAME} object created")
        console.print(f"{func_name}: {SIM_RUN_NAME} object created", style="bright_black")
        """launch simulation"""
        sys_log.debug(f"{func_name}: simulation with design (id: {design_id}, rev: {design_rev}) start")
        console.print(f"{func_name}: simulation with design (id: {design_id}, rev: {design_rev}) start", style="bright_black")
        if design_path.endswith("/"):
            configs = design_path
        else:
            configs = design_path + "/"
        proc = subprocess.Popen([run_man.simulator_path + '/TECoSim.exe', configs], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=run_man.time_out)
            sim_re = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
        # user cancel simulation
        # only dump the log (if insert run succeed)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            run["status"] = RunStatus.CANCELLED
            if_success, run_id, insert_info = run_man.insert_run(run)
            if not if_success:
                sys_log.error(f"{func_name} {CANCELLED_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) is cancelled "
                              f"by user. Simulator interrupted. Manage run failed with error: {insert_info}")
                console.print(f"{func_name} {CANCELLED_LABEL}: "
                              f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) is cancelled "
                              f"by user. Simulator interrupted. Manage run failed with error: {insert_info}", style="bold red")
                return False, CANCELLED_LABEL, (f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) "
                                                f"is cancelled by user. Simulator interrupted. Manage run failed with error: {insert_info}")
            run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
            os.makedirs(run_path, exist_ok=True)
            save_simulator_logs(run_path, stdout, stderr)
            sys_log.error(f"{func_name} {CANCELLED_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) is cancelled "
                          f"by user. Simulator interrupted")
            console.print(f"{func_name} {CANCELLED_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) is cancelled "
                          f"by user. Simulator interrupted", style="bold red")
            return False, CANCELLED_LABEL, (f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) "
                                            f"is cancelled by user. Simulator interrupted")
        # simulation time out
        # 1) dump the log (if insert run succeed)
        # 2) TODO: manage other raw data (if insert run succeed)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            run["status"] = RunStatus.TIMEOUT
            if_success, run_id, insert_info = run_man.insert_run(run)
            if not if_success:
                sys_log.error(f"{func_name} {TIMEOUT_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) is timeout > {run_man.time_out} s. "
                              f"Simulator interrupted. Manage run failed with error: {insert_info}")
                console.print(f"{func_name} {TIMEOUT_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) is timeout > {run_man.time_out} s. "
                              f"Simulator interrupted. Manage run failed with error: {insert_info}", style="bold red")
                return False, TIMEOUT_LABEL, (f"Simulation run with design (id: {design_id}, rev: {design_rev}) is timeout > "
                                              f"{run_man.time_out} s. Simulator interrupted. Manage run failed with error: {insert_info}")
            run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
            os.makedirs(run_path, exist_ok=True)
            save_simulator_logs(run_path, stdout, stderr)
            sys_log.error(f"{func_name} {TIMEOUT_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) is timeout > "
                          f"{run_man.time_out} s. Simulator interrupted")
            console.print(f"{func_name} {TIMEOUT_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) is timeout > "
                          f"{run_man.time_out} s. Simulator interrupted", style="bold red")
            return False, TIMEOUT_LABEL, (f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) "
                                          f"is timeout > {run_man.time_out} s. Simulator interrupted")
        # python wrapper runtime error
        # 1) dump the log (if insert run succeed)
        # 2) TODO: manage other raw data (if insert run succeed)
        except Exception as e:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            run["status"] = RunStatus.RUNTIME_ERROR
            if_success, run_id, insert_info = run_man.insert_run(run)
            if not if_success:
                sys_log.error(f"{func_name} {FAIL_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with python wrapper "
                              f"runtime error {e}. Simulator interrupted. Manage run failed with error: {insert_info}")
                console.print(f"{func_name} {FAIL_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with python wrapper "
                              f"runtime error {e}. Simulator interrupted. Manage run failed with error: {insert_info}", style="bold red")
                return False, FAIL_LABEL, (f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with "
                                           f"python wrapper runtime error {e}. Simulator interrupted. Manage run failed "
                                           f"with error: {insert_info}")
            run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
            os.makedirs(run_path, exist_ok=True)
            save_simulator_logs(run_path, stdout, stderr)
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) failed with "
                          f"python wrapper runtime error {e}. Simulator interrupted")
            console.print(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) failed with "
                          f"python wrapper runtime error {e}. Simulator interrupted", style="bold red")
            return False, FAIL_LABEL, (f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) "
                                       f"failed with python wrapper runtime error {e}. Simulator interrupted")
        """check status"""
        sys_log.debug(f"{func_name}: Simulation run with design (id: {design_id}, rev: {design_rev}) end")
        console.print(f"{func_name}: Simulation run with design (id: {design_id}, rev: {design_rev}) end", style="bright_black")
        # simulator runtime error
        # 1) dump the log (if insert run succeed)
        # 2) TODO: manage other raw data (if insert run succeed)
        if sim_re.returncode != 0:
            run["status"] = RunStatus.RUNTIME_ERROR
            if_success, run_id, insert_info = run_man.insert_run(run)
            if not if_success:
                sys_log.error(f"{func_name} {FAIL_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with simulator "
                              f"runtime error. Simulator interrupted. Manage run failed with error: {insert_info}")
                console.print(f"{func_name} {FAIL_LABEL}: "
                              f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with simulator "
                              f"runtime error. Simulator interrupted. Manage run failed with error: {insert_info}", style="bold red")
                return False, FAIL_LABEL, (f"Simulation run with design (id: {design_id}, rev: {design_rev}) failed with "
                                           f"simulator runtime error. Simulator interrupted. Manage run failed with error: {insert_info}")
            run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
            os.makedirs(run_path, exist_ok=True)
            save_simulator_logs(run_path, stdout, stderr)
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) failed with "
                          f"simulator runtime error. Simulator interrupted")
            console.print(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) failed with "
                          f"simulator runtime error. Simulator interrupted", style="bold red")
            return False, FAIL_LABEL, (f"Simulation run (id: {run_id}) with design (id: {design_id}, rev: {design_rev}) "
                                       f"failed with simulator runtime error. Simulator interrupted")
        # no error
        # 1) dump the log (if insert run succeed)
        # 2) TODO: manage other raw data (if insert run succeed)
        run["status"] = RunStatus.DONE
        if_success, run_id, insert_info = run_man.insert_run(run)
        if not if_success:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error. Manage "
                          f"run failed with error: {insert_info}")
            console.print(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error. Manage "
                          f"run failed with error: {insert_info}", style="bold red")
            return False, FAIL_LABEL, (f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error. "
                                       f"Manage run failed with error: {insert_info}")
        run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
        os.makedirs(run_path, exist_ok=True)
        save_simulator_logs(run_path, stdout, stderr)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: "
                      f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error")
        console.print(f"{func_name} {SUCCESS_LABEL}: "
                      f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error", style="bright_black")
        return True, SUCCESS_LABEL, f"Simulation run with design (id: {design_id}, rev: {design_rev}) exits without error"

    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}")
        console.print(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}", style="bold red")
        return False, FAIL_LABEL, e.__str__()


def read_log_impl(arguments: dict[str, Any], run_man: RunManager, file_mb_limit: int, llm_kb_limit: int, console: Console)\
        -> tuple[bool, str, str, int, str]:
    """implementation of reading log of simulator run"""
    func_name = TOOL_NAME_READ_LOG
    try:
        """check the run"""
        run_id = arguments["run_id"]
        if not (1 <= run_id <= run_man.get_num()):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} doesn't exist")
            console.print(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} doesn't exist", style="bold red")
            return False, FAIL_LABEL, f"Run with id: {run_id} doesn't exist", -1, "(None)"
        run_path = os.path.join(SESSION_PATH, run_man.session_uuid, f"{SIM_RUN_NAME}{run_id}")
        if not os.path.exists(run_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} exists, but its path doesn't exist")
            console.print(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} exists, but its path doesn't exist", style="bold red")
            return False, FAIL_LABEL, f"Run with id: {run_id} exists, but its path doesn't exist", -1, "(None)"
        """check the file size"""
        log_type = str(arguments["log_type"]).lower()
        log_path = run_path + "/" + log_type + ".log"
        file_size = os.path.getsize(log_path)
        if file_size > file_mb_limit * 1024 * 1024:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Log with type: {log_type} is larger than {file_mb_limit} MB, please modify the `READ_FILE_MB_LIMIT` "
                          f"in {AGENT_CONFIGS_PATH}")
            console.print(f"{func_name} {FAIL_LABEL}:"
                          f"Log with type: {log_type} is larger than {file_mb_limit} MB, please modify the `READ_FILE_MB_LIMIT` "
                          f"in {AGENT_CONFIGS_PATH}", style="bold red")
            return False, FAIL_LABEL, (f"Log with type: {log_type} is larger than {file_mb_limit} MB, user should modify the "
                                       f"`READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}"), -1, "(None)"
        """read the log"""
        with open(log_path, 'r', encoding=READ_LOG_ENCODING_DEFAULT) as f:
            log_content = f.read()
        if log_type == "stdout":
            clean_line = clean_stdout_log(log_content)
        elif log_type == "stderr":
            clean_line = clean_stderr_log(log_content)
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid log type: {log_type}")
            console.print(f"{func_name} {FAIL_LABEL}: Invalid log type: {log_type}", style="bold red")
            return False, FAIL_LABEL, f"Invalid log type: {log_type}", -1, "(None)"
        total_line_num = len(clean_line)
        """prepare the content"""
        read_line_num: int | None = arguments.get("line_num")
        if read_line_num is not None and read_line_num > READ_LOG_MAX_LINE:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}")
            console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}",
                          style="bold red")
            return False, FAIL_LABEL, f"Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}", -1, "(None)"
        offset_line_num = arguments.get("offset", 0)
        method = str(arguments["method"]).lower()
        byte_limit = llm_kb_limit * 1024
        start_line = 1
        line_truncated = False
        if method == "from_top":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                return False, FAIL_LABEL, f"Line num can't be empty", -1, "(None)"
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                return False, FAIL_LABEL, f"Invalid line num: {read_line_num} < 1", -1, "(None)"
            start_line = 1
            if total_line_num > read_line_num:
                line_truncated = True
            end_idx = min(read_line_num, total_line_num) - 1
            log_str, byte_truncated, read_lines = read_line_with_limit(clean_line, 0, end_idx, byte_limit, 'utf-8')
        elif method == "from_bottom":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                return False, FAIL_LABEL, f"Line num can't be empty", -1, "(None)"
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                return False, FAIL_LABEL, f"Invalid line num: {read_line_num} < 1", -1, "(None)"
            if total_line_num <= read_line_num:
                start_line = 1
                end_idx = total_line_num - 1
            else:
                start_line = total_line_num - read_line_num + 1
                end_idx = total_line_num - 1
                line_truncated = True
            log_str, byte_truncated, read_lines = read_line_with_limit(clean_line, start_line - 1, end_idx, byte_limit, 'utf-8')
        elif method == "offset":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                return False, FAIL_LABEL, f"Line num can't be empty", -1, "(None)"
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                return False, FAIL_LABEL, f"Invalid line num: {read_line_num} < 1", -1, "(None)"
            if offset_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} < 1")
                console.print(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} < 1", style="bold red")
                return False, FAIL_LABEL, f"Invalid offset: {offset_line_num} < 1", -1, "(None)"
            if offset_line_num > total_line_num:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} > total line num {total_line_num}")
                console.print(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} > total line num {total_line_num}",
                              style="bold red")
                return False, FAIL_LABEL, f"Invalid offset: {offset_line_num} > total line num {total_line_num}", -1, "(None)"
            start_line = offset_line_num
            end_idx = min(offset_line_num - 1 + read_line_num, total_line_num) - 1
            if end_idx < total_line_num - 1:
                line_truncated = True
            log_str, byte_truncated, read_lines = read_line_with_limit(clean_line, start_line - 1, end_idx, byte_limit, 'utf-8')
        elif method == "all":
            log_str, byte_truncated, read_lines = read_line_with_limit(clean_line, 0, total_line_num - 1, byte_limit, 'utf-8')
        else:
            return False, FAIL_LABEL, f"Invalid method type: {method}", -1, "(None)"

        truncated = byte_truncated or line_truncated
        # TODO: log path is hidden to LLM because maybe manage simulation to avoid the concept of this session?
        formatted = format_file_for_llm(clean_line, "(Hidden)", start_line, read_lines, total_line_num, truncated)
        if not byte_truncated:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Run id: {run_id} "
                          f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}")
            console.print(f"{func_name} {SUCCESS_LABEL}: Run id: {run_id} "
                                   f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                                   f"offset: {offset_line_num}", style="bright_black")
            return True, SUCCESS_LABEL, "", total_line_num, formatted
        else:
            sys_log.warning(f"{func_name} {TRUNCATED_LABEL}: Run id: {run_id} "
                            f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                            f"offset: {offset_line_num}, actual read-in line: {read_lines}. Target read-in part is larger than "
                            f"{llm_kb_limit} KB and truncated, please modify the `READ_FILE_LLM_KB_LIMIT` "
                            f"in {AGENT_CONFIGS_PATH}")
            console.print(f"{func_name} {TRUNCATED_LABEL}: Run id: {run_id} "
                          f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}, actual read-in line: {read_lines}. Target read-in part is "
                          f"larger than {llm_kb_limit} KB and truncated, please modify the `READ_FILE_LLM_KB_LIMIT` "
                          f"in {AGENT_CONFIGS_PATH}", style="bold yellow")
            return True, TRUNCATED_LABEL, (f"Target read-in part is larger than {llm_kb_limit} KB and truncated, user should "
                                           f"modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}"), read_lines, formatted
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}")
        console.print(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}", style="bold red")
        return False, FAIL_LABEL, e.__str__(), -1, "(None)"
