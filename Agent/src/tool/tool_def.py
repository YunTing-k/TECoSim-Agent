# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.14\n
Description: Tools prompts for TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.14      Yu Huang     1.0               First implementation\n
2026.4.16      Yu Huang     1.1               Agent context realization with logic merge\n
2026.4.19      Yu Huang     1.2               tools of init/copy/query design, launch simulator, query run, read logs,
                                              general read/write file\n
2026.4.22      Yu Huang     1.3               Bash support\n
2026.4.25-26   Yu Huang     1.4               Ask user support\n
2026.4.28      Yu Huang     1.5               Permission request & Exit TUI support\n
2026.4.29      Yu Huang     1.6               Builtin commands support\n

Details:
Prompts and realization of tools that TECoSim agent can call
------------------------------------------------------------------------------------------------------------------------
"""
import os
import subprocess
import logging
import shutil
import re
import shlex

from typing import Any
from rich.progress import Progress
from src.constants import *
from src.context.agent_context import AgentContext
from src.utility.ui_info import ask_permission_tui
from src.tool.ask_question import ask_user_question_tui, AskUserCancelled, OTHER_LABEL, RECOMMEND_LABEL

sys_log = logging.getLogger('logger')


def create_tools_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """create prompts of all available tools"""
    prompts: list[dict[str, Any]] = [
        tool_check_simulator_def(),
        tool_init_design_def(),
        tool_copy_design_def(),
        tool_query_design_list_def(),
        tool_launch_simulator_def(),
        (tool_query_run_num_def()),
        (tool_read_log_def()),
        (tool_read_file_def()),
        (tool_write_file_def()),
        (tool_bash_def()),
        (tool_ask_user_question_def())
    ]
    tool_num = len(prompts)
    ctx.tools_prompts = tool_num
    sys_log.debug(f"{tool_num} tools prompts assembled")
    return prompts


def tool_get_agent_version_def() -> dict[str, Any]:
    """tool definition of getting current version of TECoSim Agent (get_agent_version)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "get_agent_version",
            "description": "Get the current version of the TECoSim Agent",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def get_agent_version(progress: Progress) -> dict[str, Any]:
    """tool realization of getting the dev version of TECoSim agent"""
    progress.console.print(f"get_agent_version SUCCESS: "
                           f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}",
                           style="bright_black")
    return {"status": "SUCCESS",
            "version": f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"}


def tool_check_simulator_def() -> dict[str, Any]:
    """tool definition of checking the simulator (check_simulator)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "check_simulator",
            "description": "Check if the simulator is available. Only recheck when needed.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def check_simulator(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of checking if the simulator is available with AgentContext"""
    try:
        """check the path"""
        if not os.path.exists(ctx.agent_configs["SIMULATOR_PATH"]):
            sys_log.error(f"check_simulator FAIL: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in SIMULATOR_PATH does not exist")
            progress.console.print(f"check_simulator FAIL: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} "
                                   f"defined in SIMULATOR_PATH does not exist", style="bold red")
            return {"status": "FAIL",
                    "info": f"Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in SIMULATOR_PATH does not exist"}

        """check the executable"""
        results = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/TECoSim.exe'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results.returncode != 0 and results.stdout is not None:
            sys_log.debug("check_simulator SUCCESS: Simulator is available")
            progress.console.print("check_simulator SUCCESS: Simulator is available", style="bright_black")
            return {"status": "SUCCESS", "info": "Simulator is available"}
        else:
            sys_log.error("check_simulator FAIL: Simulator is unavailable")
            progress.console.print(f"check_simulator FAIL: Simulator is unavailable", style="bold red")
            return {"status": "FAIL", "info": "Simulator is unavailable"}
    except Exception as e:
        sys_log.error(f"check_simulator FAIL: Check simulator failed with error: {e}")
        progress.console.print(f"Check_simulator FAIL: check simulator failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Check simulator failed with error: {e}"}


def tool_init_design_def() -> dict[str, Any]:
    """tool definition of initializing the design (init_design)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "init_design",
            "description": "Create and initialize a design in default value with given id",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The id of the design to be created",
                    }
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def init_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of initializing a design with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "init_design",
                                   f"initialize a new design with id {arguments["id"]}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """initialize design"""
        design_id = arguments["id"]
        path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        if os.path.exists(path):
            sys_log.error(f"init_design FAIL: Design with id: {design_id} already exists")
            progress.console.print(f"init_design FAIL: Design with id: {design_id} already exists", style="bold red")
            return {"status": "FAIL", "info": f"Design with id: {design_id} already exists"}
        os.makedirs(path)
        source_path = ctx.agent_configs["SIMULATOR_PATH"] + "/config"
        shutil.copytree(src=source_path, dst=path, dirs_exist_ok=True)
        ctx.design_created.append(design_id)
        sys_log.debug(f"init_design SUCCESS: Design with id: {design_id} initialized")
        progress.console.print(f"init_design SUCCESS: Design with id: {design_id} initialized", style="bright_black")
        return {"status": "SUCCESS", "info": f"Design with id: {design_id} initialized"}
    except Exception as e:
        sys_log.error(f"init_design FAIL: Initialize design failed with error: {e}")
        progress.console.print(f"init_design FAIL: Initialize design failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Initialize design failed with error: {e}"}


def tool_copy_design_def() -> dict[str, Any]:
    """tool definition of copying a design (copy_design)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "copy_design",
            "description": "Create a new design by copying an existed design with given id",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The id of the source design to be copied",
                    },
                    "target_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The id of the target design to be created",
                    }
                },
                "required": ["source_id", "target_id"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def copy_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of copying a design with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "copy_design",
                                   f"copy design with id {arguments["source_id"]} to create a new design with "
                                   f"id {arguments["target_id"]}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """copy design"""
        source_id = arguments["source_id"]
        target_id = arguments["target_id"]
        source_path = "./session/" + ctx.session_uuid + f"/design{source_id}"
        target_path = "./session/" + ctx.session_uuid + f"/design{target_id}"
        if not os.path.exists(source_path):
            sys_log.error(f"copy_design FAIL: Source design with id: {source_id} doesn't exist")
            progress.console.print(f"copy_design FAIL: Source design with id: {source_id} doesn't exist", style="bold red")
            return {"status": "FAIL", "info": f"Source design with id: {source_id} doesn't exist"}
        if os.path.exists(target_path):
            sys_log.error(f"copy_design FAIL: Target design with id: {target_id} already exists")
            progress.console.print(f"copy_design FAIL: Target design with id: {target_id} already exists", style="bold red")
            return {"status": "FAIL", "info": f"Target design with id: {target_id} already exists"}
        os.makedirs(target_path)
        shutil.copytree(src=source_path, dst=target_path, dirs_exist_ok=True)
        ctx.design_created.append(target_id)
        sys_log.debug(f"copy_design SUCCESS: Design with id: {target_id} created by design with id: {source_id}")
        progress.console.print(f"copy_design SUCCESS: Design with id: {target_id} created by design with id: {source_id}", style="bright_black")
        return {"status": "SUCCESS", "info": f"Design with id: {target_id} created by design with id: {source_id}"}
    except Exception as e:
        sys_log.error(f"copy_design FAIL: Create design by copying failed with error: {e}")
        progress.console.print(f"copy_design FAIL: Create design by copying failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Create design by copying failed with error: {e}"}


def tool_query_design_list_def() -> dict[str, Any]:
    """tool definition of querying the list of created designs (query_design_list)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "query_design_list",
            "description": "Get the amount of the created designs and the list of ids",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_design_list(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the list of created designs with AgentContext"""
    sys_log.debug(f"query_design_list SUCCESS: Total num: {len(ctx.design_created)}, list: {ctx.design_created}")
    progress.console.print(f"query_design_list SUCCESS: Total num: {len(ctx.design_created)}, "
                           f"list: {ctx.design_created}", style="bright_black")
    return {"status": "SUCCESS",
            "total_num": f"{len(ctx.design_created)}",
            "list": f"{ctx.design_created}"}


def tool_launch_simulator_def() -> dict[str, Any]:
    """tool definition of launching the simulator (launch_simulator)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "launch_simulator",
            "description": "Launch the simulator with given id of existed design",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The id of the design for simulation",
                    }
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def launch_simulator(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of launching the simulator with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "launch_simulator",
                                   f"launch simulation run under design with id: {arguments["id"]}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """check the design"""
        design_id = arguments["id"]
        design_path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        if not os.path.exists(design_path):
            sys_log.error(f"launch_simulator FAIL: "
                          f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed")
            progress.console.print(f"launch_simulator FAIL: "
                                   f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed", style="bold red")
            return {"status": "FAIL",
                    "info": f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed"}
        """clean up"""
        results1 = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/clean.bat', "1"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results1.returncode != 0 or results1.stdout is None:
            sys_log.error("launch_simulator FAIL: "
                          "Clean up script exits with error. Run is not created. Launch is not performed")
            progress.console.print("launch_simulator FAIL: "
                                   "Clean up script exits with error. Run is not created. Launch is not performed", style="bold red")
            return {"status": "FAIL", "info": f"Clean up script exits with error. Run is not created. Launch is not performed"}
        sys_log.debug(f"launch_simulator: clean up done")
        progress.console.print(f"launch_simulator: clean up done", style="bright_black")
        """create run"""
        ctx.simulation_launched += 1
        run_path = "./session/" + ctx.session_uuid + f"/run{ctx.simulation_launched}"
        if os.path.exists(run_path):
            sys_log.error(f"launch_simulator FAIL: "
                          f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed")
            progress.console.print(f"launch_simulator FAIL: "
                                   f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed", style="bold red")
            return {"status": "FAIL",
                    "run_id": ctx.simulation_launched,
                    "info": f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed"}
        os.makedirs(run_path)
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} created")
        progress.console.print(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} created", style="bright_black")
        """launch simulation"""
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} start")
        progress.console.print(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} start", style="bright_black")
        configs = design_path + "/"
        proc = subprocess.Popen([ctx.agent_configs["SIMULATOR_PATH"] + '/TECoSim.exe', configs],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=ctx.agent_configs["SIMULATOR_TIMEOUT_S"])
            results2 = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            sys_log.error(f"launch_simulator FAIL: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} is cancelled by user. Simulator interrupted")
            progress.console.print(f"launch_simulator FAIL: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} is cancelled by user. Simulator interrupted", style="bold red")
            return {"status": "CANCELLED",
                    "run_id": ctx.simulation_launched,
                    "design_id": design_id,
                    "info": f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                            f"{design_id} is cancelled by user. Simulator interrupted"}
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            # stdout = stdout.decode('utf-8')
            # with open(run_path + "/stdout.log", "w", encoding="utf-8", newline='') as f:
            #     if stdout is not None:
            #         f.write(stdout)
            #     else:
            #         f.write("(stdout is empty!)")
            log_path = ctx.agent_configs["SIMULATOR_PATH"] + "/logs/"
            log_files = [f for f in os.listdir(log_path) if f.endswith('.txt')]
            log_files_sorted = sorted(log_files, key=lambda x: os.path.getmtime(os.path.join(log_path, x)), reverse=True)
            log_file = log_path + log_files_sorted[0]
            shutil.copy(log_file, run_path + "/stdout.log")
            stderr = stderr.decode('utf-8')
            with open(run_path + "/stderr.log", "w", encoding="utf-8", newline='') as f:
                if stderr is not None:
                    f.write(stderr)
                else:
                    f.write("(stderr is empty!)")
            sys_log.debug(f"launch_simulator: logs write/copy done")
            sys_log.error(f"launch_simulator FAIL: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                          f"Check logs for details if needed")
            progress.console.print(f"launch_simulator FAIL: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                                   f"Check logs for details if needed", style="bold red")
            return {"status": "TIMEOUT",
                    "run_id": ctx.simulation_launched,
                    "design_id": design_id,
                    "return code": proc.returncode,
                    "info": f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                            f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                            f"Check logs for details if needed"}
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} stop")
        progress.console.print(f"launch_simulator: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} stop", style="bright_black")
        """write/copy logs"""
        # stdout = results2.stdout.decode('utf-8')
        # with open(run_path + "/stdout.log", "w", encoding="utf-8", newline='') as f:
        #     if stdout is not None:
        #         f.write(stdout)
        #     else:
        #         f.write("(stdout is empty!)")
        log_path = ctx.agent_configs["SIMULATOR_PATH"] + "/logs/"
        log_files = [f for f in os.listdir(log_path) if f.endswith('.txt')]
        log_files_sorted = sorted(log_files, key=lambda x: os.path.getmtime(os.path.join(log_path, x)), reverse=True)
        log_file = log_path + log_files_sorted[0]
        shutil.copy(log_file, run_path + "/stdout.log")
        stderr = results2.stderr.decode('utf-8')
        with open(run_path + "/stderr.log", "w", encoding="utf-8", newline='') as f:
            if stderr is not None:
                f.write(stderr)
            else:
                f.write("(stderr is empty!)")
        sys_log.debug(f"launch_simulator: logs write/copy done")
        progress.console.print(f"launch_simulator: logs write/copy done", style="bright_black")
        """check status"""
        if results2.returncode != 0:
            sys_log.error(f"launch_simulator FAIL: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} failed with error. Check logs for details if needed")
            progress.console.print(f"launch_simulator FAIL: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} failed with error. Check logs for details if needed", style="bold red")
            return {"status": "FAIL",
                    "run_id": ctx.simulation_launched,
                    "design_id": design_id,
                    "info": f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                            f"{design_id} failed with error. Check logs for details if needed"}
        """copy raw results, video and design"""
        data_path = ctx.agent_configs["SIMULATOR_PATH"] + "/data"
        shutil.copytree(src=data_path, dst=run_path + "/data")
        video_path = ctx.agent_configs["SIMULATOR_PATH"] + "/video"
        shutil.copytree(src=video_path, dst=run_path + "/video")
        shutil.copytree(src=design_path, dst=run_path + "/design")
        sys_log.debug(f"launch_simulator SUCCESS: "
                      f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without error. Results are ready")
        progress.console.print(f"launch_simulator SUCCESS: "
                               f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without error. Results are ready", style="bright_black")
        return {"status": "SUCCESS",
                "run_id": ctx.simulation_launched,
                "design_id": design_id,
                "info": f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without "
                        f"error. Results are ready"}
    except Exception as e:
        sys_log.error(f"launch_simulator FAIL: Launch simulator failed with error: {e}")
        progress.console.print(f"launch_simulator FAIL: Launch simulator failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Launch simulator failed with error: {e}"}


def tool_query_run_num_def() -> dict[str, Any]:
    """tool definition of querying the amount of launched run (query_run_num)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "query_run_num",
            "description": "Get the amount of launched run",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_run_num(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the amount of launched run with AgentContext"""
    sys_log.debug(f"query_run_num SUCCESS: Total num: {ctx.simulation_launched}")
    progress.console.print(f"query_run_num SUCCESS: Total num: {ctx.simulation_launched}", style="bright_black")
    return {"status": "SUCCESS",
            "total_num": f"{ctx.simulation_launched}"}


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


def tool_read_log_def() -> dict[str, Any]:
    """tool definition of reading the log of the given run (read_log)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "read_log",
            "description": "Read the stdout or stderr log of the simulation run with given id, reading method and line num. "
                           "This tool will also return the total line num of the log",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "The id of the simulation run",
                    },
                    "log_type": {
                        "type": "string",
                        "enum": ["stdout", "stderr"],
                        "description": "The type of log to read. stdout or stderr",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["from_top", "from_bottom", "offset", "all"],
                        "description": "The method to read the log. Method 'from_top' reads the lines from top, method "
                                       "'from_bottom' reads the lines from bottom, method 'offset' reads the lines with "
                                       "given offset (include the offset line) to read any part of a very long logs or when "
                                       "needed. Method 'all' reads all the lines.",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The num of read-in lines when method is 'from_top', 'from_bottom' or 'offset' (min 1). "
                                       "If the method is 'all', this argument is ignored.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The offset of read-in lines when method is 'offset' (min 1). If the method is not "
                                       "'offset', this argument is ignored.",
                    }
                },
                "required": ["id", "log_type", "method"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def read_log(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of reading the log with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "read_log",
                                   f"run id: {arguments["id"]}, "
                                   f"type: {arguments["log_type"]}, "
                                   f"method: {arguments["method"]}, "
                                   f"read-in line: {arguments.get("line_num", "None")}, "
                                   f"offset: {arguments.get("offset", "None")}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """check the run"""
        run_id = arguments["id"]
        run_path = "./session/" + ctx.session_uuid + f"/run{run_id}"
        if not os.path.exists(run_path):
            sys_log.error(f"read_log FAIL: Run with id: {run_id} doesn't exist")
            progress.console.print(f"read_log FAIL: Run with id: {run_id} doesn't exist", style="bold red")
            return {"status": "FAIL",
                    "info": f"Run with id: {run_id} doesn't exist"}
        """read the log"""
        log_type = str(arguments["log_type"]).lower()
        log_path = run_path + "/" + log_type + ".log"
        with open(log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
        if log_type == "stdout":
            log_line = clean_stdout_log(log_content)
        elif log_type == "stderr":
            log_line = clean_stderr_log(log_content)
        else:
            sys_log.error(f"read_log FAIL: Invalid log type: {log_type}")
            progress.console.print(f"read_log FAIL: Invalid log type: {log_type}", style="bold red")
            raise RuntimeError(f"Invalid log type: {log_type}")
        total_line_num = len(log_line)
        """prepare the content"""
        read_line_num = arguments.get("line_num", 0)
        offset_line_num = arguments.get("offset", 0)
        method = str(arguments["method"]).lower()
        if method == "from_top":
            if read_line_num < 1:
                sys_log.error(f"read_log FAIL: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"read_log FAIL: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                log_str = "\n".join(log_line)
            else:
                log_str = "\n".join(log_line[0:read_line_num])
        elif method == "from_bottom":
            if read_line_num < 1:
                sys_log.error(f"read_log FAIL: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"read_log FAIL: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                log_str = "\n".join(log_line)
            else:
                log_str = "\n".join(log_line[-read_line_num:])
        elif method == "offset":
            if offset_line_num < 1:
                sys_log.error(f"read_log FAIL: Invalid offset: {offset_line_num} < 1")
                progress.console.print(f"read_log FAIL: Invalid offset: {offset_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} < 1")
            if offset_line_num > total_line_num:
                sys_log.error(f"read_log FAIL: Invalid offset: {offset_line_num} > total line num {total_line_num}")
                progress.console.print(f"read_log FAIL: Invalid offset: {offset_line_num} > total line num {total_line_num}", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} > total line num {total_line_num}")
            if (read_line_num + offset_line_num - 1) <= total_line_num:
                log_str = "\n".join(log_line[offset_line_num - 1:offset_line_num - 1 + read_line_num])
            else:
                log_str = "\n".join(log_line[offset_line_num - 1:])
        elif method == "all":
            log_str = "\n".join(log_line)
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        sys_log.debug(f"read_log SUCCESS: Run id: {run_id} "
                      f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, offset: {offset_line_num}")
        progress.console.print(f"read_log SUCCESS: Run id: {run_id} "
                               f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, offset: {offset_line_num}", style="bright_black")
        return {"status": "SUCCESS",
                "total_line": total_line_num,
                "log_content": log_str}
    except Exception as e:
        sys_log.error(f"read_log FAIL: Read log failed with error: {e}")
        progress.console.print(f"read_log FAIL: Read log failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Read log failed with error: {e}"}


def tool_read_file_def() -> dict[str, Any]:
    """tool definition of reading the file (read_file)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads a file from the local filesystem with given path, method, line num and encoding method. "
                           "You can access any file directly by using this tool. This tool will also return the line num "
                           "of the file. You can optionally specify a offset (especially handy for long files). However, "
                           "it's recommended to use other methods ('from_top', 'from_bottom', 'all') unless offset-based "
                           "reading is specifically needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (must to be absolute, not relative).",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["from_top", "from_bottom", "offset", "all"],
                        "description": "The method to read the file. Method 'from_top' reads the lines from top, method "
                                       "'from_bottom' reads the lines from bottom, method 'offset' reads the lines with "
                                       "given offset (include the offset line) to read any part of a very long file or when "
                                       "needed. Method 'all' reads all the lines.",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "description": "The num of read-in lines when method is 'from_top', 'from_bottom' or 'offset' "
                                       "(min 1, max 10000). If the method is 'all', this argument is ignored.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The offset of read-in lines when method is 'offset' (min 1). If the method is not "
                                       "'offset', this argument is ignored.",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (e.g., 'utf-8', 'gbk', 'ascii'). Default 'utf-8'.",
                        "default": "utf-8",
                    }
                },
                "required": ["path", "method"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def read_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of reading the file with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "read_file",
                                   f"path: {arguments["path"]}, "
                                   f"method: {arguments["method"]}, "
                                   f"read-in line: {arguments.get("line_num", "None")}, "
                                   f"offset: {arguments.get("offset", "None")}, "
                                   f"encoding: {arguments.get("encoding", "None")}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """check the path"""
        file_path = arguments["path"]
        if not os.path.exists(file_path):
            sys_log.error(f"read_file FAIL: Path: {file_path} doesn't exist.")
            progress.console.print(f"read_file FAIL: Path: {file_path} doesn't exist", style="bold red")
            return {"status": "FAIL",
                    "info": f"Path: {file_path} doesn't exist"}
        """check the file"""
        if not os.path.isfile(file_path):
            sys_log.error(f"read_file FAIL: Path: {file_path} is not a file")
            progress.console.print(f"read_file FAIL: Path: {file_path} is not a file", style="bold red")
            return {"status": "FAIL",
                    "info": f"Path: {file_path} is not a file"}
        """check the file size"""
        file_size = os.path.getsize(file_path)
        if file_size > ctx.agent_configs["READ_FILE_MB_LIMIT"] * 1024 * 1024:
            sys_log.error(f"read_file FAIL: "
                          f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB")
            progress.console.print(f"read_file FAIL: "
                                   f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB", style="bold red")
            return {"status": "FAIL",
                    "info": f"File is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB"}
        """read the file"""
        encoding = arguments.get("encoding", "utf-8")
        with open(file_path, 'r', encoding=encoding) as f:
            file_line = f.readlines()
        total_line_num = len(file_line)
        """prepare the content"""
        read_line_num = arguments.get("line_num", 0)
        offset_line_num = arguments.get("offset", 0)
        method = str(arguments["method"]).lower()
        if method == "from_top":
            if read_line_num < 1 or read_line_num is None:
                sys_log.error(f"read_file FAIL: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"read_file FAIL: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                file_str = "".join(file_line)
            else:
                file_str = "".join(file_line[0:read_line_num])
        elif method == "from_bottom":
            if read_line_num < 1 or read_line_num is None:
                sys_log.error(f"read_file FAIL: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"read_file FAIL: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                file_str = "".join(file_line)
            else:
                file_str = "".join(file_line[-read_line_num:])
        elif method == "offset":
            if offset_line_num < 1:
                sys_log.error(f"read_file FAIL: Invalid offset: {offset_line_num} < 1")
                progress.console.print(f"read_file FAIL: Invalid offset: {offset_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} < 1")
            if offset_line_num > total_line_num:
                sys_log.error(f"read_file FAIL: Invalid offset: {offset_line_num} > total line num {total_line_num}")
                progress.console.print(f"read_file FAIL: Invalid offset: {offset_line_num} > total line num {total_line_num}", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} > total line num {total_line_num}")
            if (read_line_num + offset_line_num - 1) <= total_line_num:
                file_str = "".join(file_line[offset_line_num - 1:offset_line_num - 1 + read_line_num])
            else:
                file_str = "".join(file_line[offset_line_num - 1:])
        elif method == "all":
            file_str = "".join(file_line)
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        sys_log.debug(f"read_file SUCCESS: "
                      f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, offset: {offset_line_num}, encoding: {encoding}")
        progress.console.print(f"read_file SUCCESS: "
                               f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, offset: {offset_line_num}, encoding: {encoding}", style="bright_black")
        return {"status": "SUCCESS",
                "total_line": total_line_num,
                "log_content": file_str}
    except UnicodeDecodeError as e:
        sys_log.error(f"read_file FAIL: Can't read file with given encoding, error: {e}")
        progress.console.print(f"read_file FAIL: Can't read file with given encoding, error: {e}", style="bold red")
        return {"status": "FAIL",
                "info": f"Can't read file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"read_file FAIL: Can't read file, permission denied: {e}")
        progress.console.print(f"read_file FAIL: Can't read file, permission denied: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Can't read file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"read_file FAIL: Can't read file, OS error: {e}")
        progress.console.print(f"read_file FAIL: Can't read file, OS error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Can't read file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"read_file FAIL: Read file failed with error: {e}")
        progress.console.print(f"read_file FAIL: Read file failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Read file failed with error: {e}"}


def tool_write_file_def() -> dict[str, Any]:
    """tool definition of writing the file (write_file)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a file or append content to a file to the local filesystem with given path, contents, writing "
                           "mode and encoding method. Supports creating parent directories automatically",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (must to be absolute, not relative).",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file. Can be plain text, json, html, code, etc."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append"],
                        "description": "Optional write mode: 'write' overwrites the file (default), 'append' adds content "
                                       "to the end.",
                        "default": "write"
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "Optional flag. If true (default), automatically create missing parent directories.",
                        "default": True
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Optional encoding type (e.g., 'utf-8', 'gbk', 'ascii'). Default 'utf-8'.",
                        "default": "utf-8",
                    }
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def write_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of writing the file with arguments and AgentContext"""
    try:
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, "write_file",
                                   f"path: {arguments["path"]}, "
                                   f"mode: {arguments.get("mode", "None")}, "
                                   f"create_dirs: {arguments.get("create_dirs", "None")}, "
                                   f"encoding: {arguments.get("encoding", "None")}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """check the path"""
        file_path = arguments["path"]
        create_dirs = arguments.get("create_dirs", True)
        if create_dirs:
            parent_dir = os.path.dirname(file_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                sys_log.debug(f"write_file: Parent directory: {parent_dir} created")
                progress.console.print(f"write_file: Parent directory: {parent_dir} created", style="bright_black")
        """write the file"""
        mode = arguments.get("mode", "write")
        w_mode = 'w' if mode == "write" else 'a'
        encoding = arguments.get("encoding", "utf-8")
        content: str = arguments["content"]
        with open(file=file_path, mode=w_mode, encoding=encoding) as f:
            f.write(content)
        content_bytes = content.encode(encoding)
        byte_count = len(content_bytes)
        sys_log.debug(f"write_file SUCCESS: "
                      f"Path: {file_path}, mode: {mode}, create_dirs: {create_dirs}, encoding: {encoding}, bytes: {byte_count}")
        progress.console.print(f"write_file SUCCESS: "
                               f"Path: {file_path}, mode: {mode}, create_dirs: {create_dirs}, encoding: {encoding}, bytes: {byte_count}", style="bright_black")
        return {"status": "SUCCESS",
                "bytes_written": byte_count,
                "info": f"Write content to {file_path} done successfully"}
    except UnicodeDecodeError as e:
        sys_log.error(f"write_file FAIL: Can't write file with given encoding, error: {e}")
        progress.console.print(f"write_file FAIL: Can't write file with given encoding, error: {e}", style="bold red")
        return {"status": "FAIL",
                "info": f"Can't write file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"write_file FAIL: Can't write file, permission denied: {e}")
        progress.console.print(f"write_file FAIL: Can't write file, permission denied: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Can't write file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"write_file FAIL: Can't write file, OS error: {e}")
        progress.console.print(f"write_file FAIL: Can't write file, OS error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Can't write file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"write_file FAIL: Write file failed with error: {e}")
        progress.console.print(f"write_file FAIL: Write file failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Write file failed with error: {e}"}


def tool_bash_def() -> dict[str, Any]:
    """tool definition of bash (bash)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Executes a given bash command and returns its output. The working directory persists between "
                           "commands, but shell state does not. The shell environment is initialized from the user's profile.\n"
                           "IMPORTANT: Avoid using this tool to run `cat`, `head`, `tail`, or `echo` commands, unless explicitly "
                           "instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, "
                           "use the appropriate dedicated tool as this will provide a much better experience for the user.\n"
                           " - Read files: Use read_file (NOT cat/head/tail)\n"
                           " - Write files: Use write_file(NOT echo >/cat <<EOF)\n"
                           " - Communication: Output text directly (NOT echo/printf)\n"
                           "While the Bash tool can do similar things, it’s better to use the built-in tools as they provide "
                           "a better user experience and make it easier to review tool calls and give permission.\n"
                           "# Instructions\n"
                           " - If your command will create new directories or files, first use this tool to run `ls` to "
                           "verify the parent directory exists and is the correct location.\n"
                           " - Always quote file paths that contain spaces with double quotes in your command (e.g., cd "
                           "\"path with spaces/file.txt\")\n"
                           " - Try to maintain your current working directory throughout the session by using absolute "
                           "paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.\n"
                           " - You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). By default, "
                           "your command will timeout after 120000ms (2 minutes).\n"
                           " - When issuing multiple commands:\n"
                           "  - If the commands are independent and can run in parallel, make multiple Bash tool calls in"
                           " a single message. Example: if you need to run \"git status\" and \"git diff\", send a single "
                           "message with two Bash tool calls in parallel.\n"
                           "  - If the commands depend on each other and must run sequentially, use a single Bash call with "
                           "'&&' to chain them together.\n"
                           "  - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail.\n"
                           "  - DO NOT use newlines to separate commands (newlines are ok in quoted strings).\n"
                           " - Avoid unnecessary `sleep` commands:\n"
                           "  - Do not sleep between commands that can run immediately — just run them.\n"
                           "  - Do not retry failing commands in a sleep loop — diagnose the root cause.\n"
                           "  - If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user.\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    },
                    "description": {
                        "type": "string",
                        "description": "Clear, concise description of what this command does in active voice. Never use "
                                       "words like \"complex\" or \"risk\" in the description - just describe what it does. "
                                       "For simple commands (git, npm, standard CLI tools), keep it brief (5-10 words):\n"
                                       "- ls → \"List files in current directory\"\n"
                                       "- git status → \"Show working tree status\"\n"
                                       "- npm install → \"Install package dependencies\"\n\n"
                                       "For commands that are harder to parse at a glance (piped commands, obscure flags, etc.), "
                                       "add enough context to clarify what it does:\n"
                                       "- find . -name \"*.tmp\" -exec rm {} \\; → \"Find and delete all .tmp files recursively\"\n"
                                       "- git reset --hard origin/main → \"Discard all local changes and match remote main\"\n"
                                       "- curl -s url | jq '.data[]' → \"Fetch JSON from URL and extract data array elements\"",
                    },
                    "timeout": {
                        "type": "integer",
                        "maximum": 600000,
                        "description": "Optional timeout in milliseconds (max 600000, default 120000)",
                        "default": 120000,
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def split_commands(command: str) -> list[str]:
    """split a bash command using separators (| & ; && ||) as delimiters,
    discarding the separators while preserving the original whitespace
    inside each fragment. Redirections (>, >>, <, <<) are kept"""
    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split = False
    lex.quotes = '"\''
    lex.commenters = ''
    lex.wordchars += './'      # ensure ./path stays as one token

    # Get tokens together with their original positions
    tokens_with_pos = []
    while True:
        pos = lex.instream.tell() if hasattr(lex.instream, 'tell') else None
        token = lex.get_token()
        if token == '' or token is None:
            break
        # approximate start position (shlex doesn't give exact positions easily)
        # For accuracy we need to scan, but this works for most cases
        start = command.find(token, pos if pos else 0)
        end = start + len(token) if start != -1 else -1
        tokens_with_pos.append((token, start, end))

    # Merge multi-character operators
    merged_tokens = []
    i = 0
    while i < len(tokens_with_pos):
        tok, s, e = tokens_with_pos[i]
        if i + 1 < len(tokens_with_pos):
            next_tok = tokens_with_pos[i+1][0]
            if tok + next_tok in {'>>', '<<', '&&', '||'}:
                merged_tokens.append((tok+next_tok, s, tokens_with_pos[i+1][2]))
                i += 2
                continue
        merged_tokens.append((tok, s, e))
        i += 1

    sep_operators = {'|', '&', ';', '&&', '||'}
    fragments = []
    current_start = 0
    in_fragment = False

    for tok, s, e in merged_tokens:
        if tok in sep_operators:
            if in_fragment:
                # End fragment at the character before the separator
                fragments.append(command[current_start:s].strip())
                in_fragment = False
        else:
            if not in_fragment:
                current_start = s
                in_fragment = True

    if in_fragment:
        fragments.append(command[current_start:].strip())

    # Remove empty fragments
    fragments = [f for f in fragments if f]
    return fragments


def get_bash_risk(cmd: str) -> tuple[str, str, int]:
    """Assess the risk level of a single bash command string"""
    if cmd is None or cmd.strip() == "":
        return BASH_EMPTY_LABEL, "Empty command", 9
    """high risk commands handling"""
    high_risk_patterns = [
        (r'sudo\s+', "Uses sudo – privilege escalation"),
        (r'rm\s+-rf\s+/?', "Destructive recursive removal"),
        (r'chmod\s+7{3,4}', "Overly permissive chmod"),
        (r'chown\s+7{3,4}', "Overly permissive chown"),
        (r'dd\s+if=', "Raw disk operation"),
        (r'mkfs', "Filesystem creation"),
        (r'curl.*\|\s*(sh|bash)', "Download and execute pattern (curl … | sh)"),
        (r'wget.*-O-.*\|.*sh', "Download and execute pattern (wget … | sh)"),
        (r'>\s*/dev/|dd\s+of=|\|sh\b|\|bash\b', "Pipeline to shell or raw write"),
        (r'\|\s*sudo\s+', "Pipeline with sudo"),
        (r'ssh-keygen', "SSH key manipulation"),
        (r'passwd|chpasswd', "Password modification"),
        (r'iptables|ufw\s+(allow|deny)', "Firewall changes"),
        (r'systemctl\s+(stop|disable|mask|enable)', "Service control"),
        (r'docker\s+(rm|system\s+prune)', "Docker destructive operations"),
    ]
    for pattern, reason in high_risk_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            risk = BASH_HIGH_RISK_LABEL
            full_reason = reason
            return risk, full_reason, 0

    # package management commands handling
    package_commands = ["apt", "apt-get", "yum", "dnf", "pacman", "brew", "pip", "npm", "yarn"]
    package_modify_operations = ("install", "uninstall", "remove", "purge", "update", "upgrade")
    package_check_operations = ("list", "search", "show", "outdated", "info")
    if any(cmd.startswith(cmd_name + " ") or cmd == cmd_name for cmd_name in package_commands):
        for op in package_modify_operations:
            if op in cmd:
                risk = BASH_PACKAGE_LABEL
                reason = f"Package management operation '{cmd}' affects system"
                return risk, reason, 0
        for op in package_check_operations:
            if op in cmd:
                risk = BASH_SAFE_LABEL
                reason = f"Safe package check operation '{cmd}'"
                return risk, reason, 8

    # network commands handling
    network_commands = ("curl", "wget", "nc", "telnet", "ssh")
    for op in network_commands:
        if op in cmd:
            return BASH_NETWORK_LABEL, f"Network command '{cmd}' in pipeline/chain may execute remote content", 0

    """medium risk commands handling"""
    # other risk commands handling
    other_risk_commands = {
        "mkdir", "touch", "cp", "rm", "mv", "ln", "chmod", "chown",
        "rmdir", "nano", "vim", "code"
    }

    for op in other_risk_commands:
        if op in cmd:
            if re.search(r'(^|\s)rm(\s|$)', cmd):
                has_recursive = bool(re.search(r'(^|\s)(-r|-R|--recursive)(\s|$)', cmd))
                has_force = bool(re.search(r'(^|\s)(-f|--force)(\s|$)', cmd))
                if has_recursive and has_force:
                    risk = BASH_REMOVAL_RF_LABEL
                    reason = "Recursive forced removal (rm/rmdir -rf)"
                    level = 1
                elif has_recursive:
                    risk = BASH_REMOVAL_R_LABEL
                    reason = "Recursive removal (rm/rmdir -r)"
                    level = 2
                elif has_force:
                    risk = BASH_REMOVAL_F_LABEL
                    reason = "Forced removal (rm/rmdir -f)"
                    level = 2
                else:
                    risk = BASH_REMOVAL_LABEL
                    reason = "Low-risk file removal"
                    level = 3
            elif "chmod" in cmd:
                risk = BASH_CHMOD_LABEL
                reason = f"Low-risk chmod {cmd} operation"
                level = 4
            elif "chown" in cmd:
                risk = BASH_CHOWN_LABEL
                reason = f"Low-risk chown {cmd} operation"
                level = 4
            else:
                risk = BASH_FILE_LABEL
                reason = f"Low-risk file operation: {cmd}"
                level = 4
            return risk, reason, level

    # git commands handling
    medium_risk_git_command = ("push", "pull", "commit", "merge", "rebase", "checkout", "reset")
    low_risk_git_command = ("add", "rm", "mv")
    if "git" in cmd:
        for op in medium_risk_git_command:
            if op in cmd:
                risk = BASH_REPOSITORY_MODIFY_LABEL
                reason = f"Git operation '{op}' modifies repository history/remote"
                return risk, reason, 5
        for op in low_risk_git_command:
            if op in cmd:
                risk = BASH_STAGE_CHANGE_LABEL
                reason = f"Git operation '{op}' stages changes"
                return risk, reason, 6
        risk = BASH_SAFE_LABEL
        reason = f"Safe git operation '{cmd}'"
        return risk, reason, 8

    """safe commands handling"""
    safe_commands = {
        "ls", "dir", "pwd", "echo", "printf", "cat", "head", "tail", "wc",
        "uname", "grep", "egrep", "fgrep", "find", "diff", "cmp", "df",
        "which", "type", "realpath", "basename", "dirname",
        "date", "cal", "yes", "true", "false", "test", "[", "printf"
    }

    for op in safe_commands:
        if op in cmd:
            risk = BASH_SAFE_LABEL
            reason = f"Safe command: {cmd}"
            return risk, reason, 8

    """un classified commands handling"""
    return BASH_UNKNOWN_LABEL, f"Command not classified: {cmd}", 7


def evaluate_bash_risk(commands: str, ctx: AgentContext):
    """evaluate the risk of given bash commands"""
    cmd_list = split_commands(commands)
    if len(cmd_list) == 0:
        return BASH_EMPTY_LABEL, "Empty command", 9
    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []
    for idx, cmd in enumerate(cmd_list):
        risk, reason, level = get_bash_risk(cmd)
        if risk in ctx.permissions:
            if ctx.permissions[risk]:
                continue
            cmd_risk_list.append(risk)
            cmd_reason_list.append(reason)
            cmd_level_list.append(level)
        else:
            raise RuntimeError(f"Unknown bash command risk: {risk}")
    idx = min(range(len(cmd_level_list)), key=lambda i: cmd_level_list[i])
    return cmd_risk_list[idx], cmd_reason_list[idx], cmd_level_list[idx]


def bash(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of bash command execution with arguments and AgentContext"""
    try:
        """evaluate the risk of bash command"""
        risk, reason, level = evaluate_bash_risk(arguments["command"], ctx)
        """request permission"""
        progress.stop()
        token = ask_permission_tui(ctx, risk, f"bash description: {arguments["description"]}, "
                                   f"risk level: {level} with reason: {reason}. Full command: {arguments["command"]}", progress.console)
        progress.start()
        if not token:
            return {"status": "FAIL",
                    "info": f"Permission request denied by user"}
        """execute command"""
        command = arguments["command"]
        description = arguments.get("description", "")
        timeout = arguments.get("timeout", 120000)
        sys_log.debug(f"bash: {description} start")
        progress.console.print(f"bash: {description} start", style="bright_black")
        proc = subprocess.Popen(["bash", "-c", command],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=timeout / 1000)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            sys_log.error(f"bash FAIL: {description} with command {command} is cancelled by user. Command interrupted")
            progress.console.print(f"bash FAIL: {description} with command {command} is cancelled by user. Command interrupted", style="bold red")
            return {"status": "CANCELLED",  # no need to return results if user cancel
                    "info": "bash command is cancelled by user. Command interrupted"}
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            sys_log.error(f"bash FAIL: "
                          f"{description} with command {command} timeout > {timeout / 1000} s. Command interrupted")
            progress.console.print(f"bash FAIL: "
                                   f"{description} with command {command} timeout > {timeout / 1000} s. Command interrupted", style="bold red")
            return {"status": "TIMEOUT",
                    "return code": proc.returncode,
                    "stdout": stdout.decode('utf-8'),
                    "stderr": stderr.decode('utf-8')}
        sys_log.debug(f"bash: {description} with command {command} done")
        progress.console.print(f"bash: {description} with command {command} done", style="bright_black")
        return {"status": "DONE",
                "return code": proc.returncode,
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8')}
    except Exception as e:
        sys_log.error(f"bash FAIL: Command execute with error: {e}")
        progress.console.print(f"bash FAIL: Command execute with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Command execute with error: {e}"}


def tool_ask_user_question_def() -> dict[str, Any]:
    """tool definition of asking structured questions to the user (ask_user_question)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": "Use this tool to ask the user questions when you need. This allows you to:\n"
                           "1. Gather user preferences or requirements\n"
                           "2. Clarify ambiguous instructions\n"
                           "3. Get decisions on implementation choices as you work\n"
                           "4. Offer choices to the user about what direction to take.\n"
                           "Usage notes:\n"
                           f"- User will always be able to select '{OTHER_LABEL}' to provide custom text input\n"
                           f"- Use multi_select: true to allow multiple answers to be selected for a question\n"
                           f"- If you recommend a specific option, make that the first option in the list and add '({RECOMMEND_LABEL})' "
                           f"at the end of the label\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "description": "Questions to ask the user (1-4 questions).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The full question shown to the user."
                                },
                                "header": {
                                    "type": "string",
                                    "description": "Very short label displayed as a tag."
                                },
                                "options": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 4,
                                    "description": "The available options for this question. Must have 2-4 options. Each "
                                                   "option should be a distinct, mutually exclusive choice (unless multi_select "
                                                   f"is enabled). There should be no '{OTHER_LABEL}' option, that will be "
                                                   f"provided automatically.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {
                                                "type": "string",
                                                "description": "The display text for this option that the user will see "
                                                               "and select. Should be concise and clearly describe the choice."
                                            },
                                            "description": {
                                                "type": "string",
                                                "description": "Explanation of what this option means or what will happen "
                                                               "if chosen. Useful for providing context about trade-offs "
                                                               "or implications."
                                            }
                                        },
                                        "required": ["label", "description"],
                                        "additionalProperties": False
                                    }
                                },
                                "multi_select": {
                                    "type": "boolean",
                                    "description": "Set to true to allow the user to select multiple options instead of "
                                                   "just one. Use when choices are not mutually exclusive",
                                    "default": False
                                }
                            },
                            "required": ["question", "header", "options", "multi_select"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["questions"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def ask_user_question(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of asking structured questions to the user"""
    try:
        questions = arguments.get("questions", [])
        if len(questions) == 0:
            sys_log.error("ask_user_question FAIL: questions is empty")
            progress.console.print("ask_user_question FAIL: questions is empty", style="bold red")
            return {"status": "FAIL", "info": "questions is empty"}
        if ctx.agent_session is None:
            sys_log.error("ask_user_question FAIL: agent session is unavailable")
            progress.console.print("ask_user_question FAIL: agent session is unavailable", style="bold red")
            return {"status": "FAIL", "info": "agent session is unavailable"}
        for idx, question in enumerate(questions, start=1):
            options = question.get("options", [])
            if len(options) == 0:
                sys_log.error(f"ask_user_question FAIL: question {idx} has no options")
                progress.console.print(f"ask_user_question FAIL: question {idx} has no options", style="bold red")
                return {"status": "FAIL", "info": f"question {idx} has no options"}
        progress.stop()
        sys_log.debug(f"ask_user_question: waiting for user selection")
        try:
            answers = ask_user_question_tui(questions, progress.console, ctx.agent_session)
        finally:
            progress.start()
        sys_log.debug(f"ask_user_question SUCCESS: {len(answers)} answers collected")
        progress.console.print(f"ask_user_question SUCCESS: {len(answers)} answers collected", style="bright_black")
        return {
            "status": "SUCCESS",
            "answers": answers,
            "info": f"Collected {len(answers)} answers from user"
        }
    except AskUserCancelled as e:
        sys_log.warning(f"ask_user_question FAIL: {e}")
        progress.console.print(f"ask_user_question FAIL: {e}", style="bold yellow")
        return {"status": "FAIL", "info": str(e)}
    except KeyboardInterrupt:
        sys_log.warning("ask_user_question FAIL: user cancelled")
        progress.console.print("ask_user_question FAIL: user cancelled", style="bold yellow")
        return {"status": "FAIL", "info": "user cancelled"}
    except Exception as e:
        sys_log.error(f"ask_user_question FAIL: Ask user question failed with error: {e}")
        progress.console.print(f"ask_user_question FAIL: Ask user question failed with error: {e}", style="bold red")
        return {"status": "FAIL", "info": f"Ask user question failed with error: {e}"}
