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

Details:
Prompts of available tools of TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import subprocess
import logging
import shutil
import re

from typing import Dict, Any, List
from rich.console import Console
from rich.progress import Progress
from src.constants import *
from src.context.session import AgentContext

sys_log = logging.getLogger('logger')


def create_tools_prompts(console: Console) -> list[dict[str, Any]]:
    """create prompts of all available tools"""
    prompts: list[dict[str, Any]] = []
    # prompts.append(tool_get_agent_version_def())  # for tool test
    prompts.append(tool_check_simulator_def())
    prompts.append(tool_init_design_def())
    prompts.append(tool_copy_design_def())
    prompts.append(tool_query_design_list_def())
    prompts.append(tool_launch_simulator_def())
    prompts.append((tool_query_run_num_def()))
    prompts.append((tool_read_log_def()))
    prompts.append((tool_read_file_def()))
    prompts.append((tool_write_file_def()))
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
    progress.console.print(f"[bright_black]get_agent_version SUCCESS: "
                           f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"
                           f"[/bright_black]")
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


def check_simulator(ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of checking if the simulator is available with AgentContext"""
    try:
        """check the path"""
        if not os.path.exists(ctx.agent_configs["SIMULATOR_PATH"]):
            sys_log.error(f"check_simulator FAIL: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in SIMULATOR_PATH does not exist")
            progress.console.print(f"[bold red]check_simulator FAIL: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} "
                                   f"defined in SIMULATOR_PATH does not exist[/bold red]: ")
            return {"status": "FAIL",
                    "info": f"Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in SIMULATOR_PATH does not exist"}

        """check the executable"""
        results = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/TECoSim.exe'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results.returncode != 0 and results.stdout is not None:
            sys_log.debug("check_simulator SUCCESS: Simulator is available")
            progress.console.print("[bright_black]check_simulator SUCCESS: Simulator is available[/bright_black]")
            return {"status": "SUCCESS", "info": "Simulator is available"}
        else:
            sys_log.error("check_simulator FAIL: Simulator is unavailable")
            progress.console.print(f"[bold red]check_simulator FAIL: Simulator is unavailable[/bold red]")
            return {"status": "FAIL", "info": "Simulator is unavailable"}
    except Exception as e:
        sys_log.error(f"check_simulator FAIL: Check simulator failed with error: {e}")
        progress.console.print(f"[bold red]Check_simulator FAIL: check simulator failed with error: {e}[/bold red]")
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


def init_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of initializing a design with arguments and AgentContext"""
    try:
        design_id = arguments["id"]
        path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        if os.path.exists(path):
            sys_log.error(f"init_design FAIL: Design with id: {design_id} already exists")
            progress.console.print(f"[bold red]init_design FAIL: Design with id: {design_id} already exists[/bold red]")
            return {"status": "FAIL", "info": f"Design with id: {design_id} already exists"}
        os.makedirs(path)
        source_path = ctx.agent_configs["SIMULATOR_PATH"] + "/config"
        shutil.copytree(src=source_path, dst=path, dirs_exist_ok=True)
        ctx.design_created.append(design_id)
        sys_log.debug(f"init_design SUCCESS: Design with id: {design_id} initialized")
        progress.console.print(f"[bright_black]init_design SUCCESS: Design with id: {design_id} initialized[/bright_black]")
        return {"status": "SUCCESS", "info": f"Design with id: {design_id} initialized"}
    except Exception as e:
        sys_log.error(f"init_design FAIL: Initialize design failed with error: {e}")
        progress.console.print(f"[bold red]init_design FAIL: Initialize design failed with error: {e}[/bold red]")
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


def copy_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of copying a design with arguments and AgentContext"""
    try:
        source_id = arguments["source_id"]
        target_id = arguments["target_id"]
        source_path = "./session/" + ctx.session_uuid + f"/design{source_id}"
        target_path = "./session/" + ctx.session_uuid + f"/design{target_id}"
        if not os.path.exists(source_path):
            sys_log.error(f"copy_design FAIL: Source design with id: {source_id} doesn't exist")
            progress.console.print(f"[bold red]copy_design FAIL: Source design with id: {source_id} doesn't exist[/bold red]")
            return {"status": "FAIL", "info": f"Source design with id: {source_id} doesn't exist"}
        if os.path.exists(target_path):
            sys_log.error(f"copy_design FAIL: Target design with id: {target_id} already exists")
            progress.console.print(f"[bold red]copy_design FAIL: Target design with id: {target_id} already exists[/bold red]")
            return {"status": "FAIL", "info": f"Target design with id: {target_id} already exists"}
        os.makedirs(target_path)
        shutil.copytree(src=source_path, dst=target_path, dirs_exist_ok=True)
        ctx.design_created.append(target_id)
        sys_log.debug(f"copy_design SUCCESS: Design with id: {target_id} created by design with id: {source_id}")
        progress.console.print(f"[bright_black]copy_design SUCCESS: Design with id: {target_id} created by design with id: {source_id}[/bright_black]")
        return {"status": "SUCCESS", "info": f"Design with id: {target_id} created by design with id: {source_id}"}
    except Exception as e:
        sys_log.error(f"copy_design FAIL: Create design by copying failed with error: {e}")
        progress.console.print(f"[bold red]copy_design FAIL: Create design by copying failed with error: {e}[/bold red]")
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


def query_design_list(ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of querying the list of created designs with AgentContext"""
    sys_log.debug(f"query_design_list SUCCESS: Total num: {len(ctx.design_created)}, list: {ctx.design_created}")
    progress.console.print(f"[bright_black]query_design_list SUCCESS: Total num: {len(ctx.design_created)}, "
                           f"list: {ctx.design_created}[/bright_black]")
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


def launch_simulator(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of launching the simulator with arguments and AgentContext"""
    try:
        """check the design"""
        design_id = arguments["id"]
        design_path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        if not os.path.exists(design_path):
            sys_log.error(f"launch_simulator FAIL: "
                          f"Design with id: {design_id} doesn't exist. Launch is not performed")
            progress.console.print(f"[bold red]launch_simulator FAIL: "
                                   f"Design with id: {design_id} doesn't exist. Launch is not performed[/bold red]")
            return {"status": "FAIL",
                    "info": f"Design with id: {design_id} doesn't exist. Launch is not performed"}
        """clean up"""
        results1 = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/clean.bat', "1"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results1.returncode != 0 or results1.stdout is None:
            sys_log.error("launch_simulator FAIL: "
                          "Clean up script exits with error. Launch is not performed")
            progress.console.print("[bold red]launch_simulator FAIL: "
                                   "Clean up script exits with error. Launch is not performed[/bold red]")
            return {"status": "FAIL", "info": f"Clean up script exits with error. Launch is not performed"}
        sys_log.debug(f"launch_simulator: clean up done")
        progress.console.print(f"[bright_black]launch_simulator: clean up done[/bright_black]")
        """create run"""
        ctx.simulation_launched += 1
        run_path = "./session/" + ctx.session_uuid + f"/run{ctx.simulation_launched}"
        if os.path.exists(run_path):
            sys_log.error(f"launch_simulator FAIL: "
                          f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed")
            progress.console.print(f"[bold red]launch_simulator FAIL: "
                                   f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed[/bold red]")
            return {"status": "FAIL",
                    "info": f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed"}
        os.makedirs(run_path)
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} created")
        progress.console.print(f"[bright_black]launch_simulator: simulation run with id: {ctx.simulation_launched} created[/bright_black]")
        """launch simulation"""
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} start")
        progress.console.print(f"[bright_black]launch_simulator: simulation run with id: {ctx.simulation_launched} start[/bright_black]")
        configs = design_path + "/"
        results2 = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/TECoSim.exe', configs],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sys_log.debug(f"launch_simulator: simulation run with id: {ctx.simulation_launched} stop")
        progress.console.print(f"[bright_black]launch_simulator: simulation run with id: {ctx.simulation_launched} stop[/bright_black]")
        """write/copy logs"""
        stderr = results2.stderr.decode('utf-8')
        with open(run_path + "/stderr.log", "w", encoding="utf-8") as f:
            if stderr is not None:
                f.write(stderr)
            else:
                f.write("stderr is empty!")
        log_path = ctx.agent_configs["SIMULATOR_PATH"] + "/logs/"
        log_files = [f for f in os.listdir(log_path) if f.endswith('.txt')]
        log_files_sorted = sorted(log_files, key=lambda x: os.path.getmtime(os.path.join(log_path, x)), reverse=True)
        log_file = log_path + log_files_sorted[0]
        shutil.copy(log_file, run_path + "/stdout.log")
        sys_log.debug(f"launch_simulator: logs write/copy done")
        progress.console.print(f"[bright_black]launch_simulator: logs write/copy done[/bright_black]")
        """check status"""
        if results2.returncode != 0:
            sys_log.error(f"launch_simulator FAIL: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} failed with error. Check logs for details if needed")
            progress.console.print(f"[bold red]launch_simulator FAIL: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} failed with error. Check logs for details if needed[/bold red]")
            return {"status": "FAIL",
                    "run_id": ctx.simulation_launched,
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
        progress.console.print(f"[bright_black]launch_simulator SUCCESS: "
                               f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without error. Results are ready[/bright_black]")
        return {"status": "SUCCESS",
                "run_id": ctx.simulation_launched,
                "info": f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without "
                        f"error. Results are ready"}
    except Exception as e:
        sys_log.error(f"launch_simulator FAIL: Launch simulator failed with error: {e}")
        progress.console.print(f"[bold red]launch_simulator FAIL: Launch simulator failed with error: {e}[/bold red]")
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


def query_run_num(ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of querying the amount of launched run with AgentContext"""
    sys_log.debug(f"query_run_num SUCCESS: Total num: {ctx.simulation_launched}")
    progress.console.print(f"[bright_black]query_run_num SUCCESS: Total num: {ctx.simulation_launched}[/bright_black]")
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
            "description": "Read the stdout log of the simulation run with given id, reading method and line num",
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
                        "enum": ["from_top", "from_bottom", "all"],
                        "description": "The method to read the log. Method 'from_top' reads the lines from top, method "
                                       "'from_bottom' reads the lines from bottom. Method 'all' reads all the lines.",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The num of read-in lines when method is 'from_top' or 'from_bottom'. If the method "
                                       "is 'all', this argument is ignored.",
                    }
                },
                "required": ["id", "log_type", "method"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def read_log(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of reading the log with arguments and AgentContext"""
    try:
        """check the run"""
        run_id = arguments["id"]
        run_path = "./session/" + ctx.session_uuid + f"/run{run_id}"
        if not os.path.exists(run_path):
            sys_log.error(f"read_log FAIL: Run with id: {run_id} doesn't exist")
            progress.console.print(f"[bold red]read_log FAIL: Run with id: {run_id} doesn't exist[/bold red]")
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
            progress.console.print(f"[bold red]read_log FAIL: Invalid log type: {log_type}[/bold red]")
            raise RuntimeError(f"Invalid log type: {log_type}")
        total_line_num = len(log_line)
        """prepare the content"""
        target_line_num = arguments.get("line_num", 0)
        method = str(arguments["method"]).lower()
        if method == "from_top":
            if target_line_num < 1 or target_line_num is None:
                sys_log.error(f"read_log FAIL: Invalid line num: {target_line_num} < 1")
                progress.console.print(f"[bold red]read_log FAIL: Invalid line num: {target_line_num} < 1[/bold red]")
                raise RuntimeError(f"Invalid line num: {target_line_num} < 1")
            if total_line_num <= target_line_num:
                log_str = "\n".join(log_line)
            else:
                log_str = "\n".join(log_line[0:target_line_num])
        elif method == "from_bottom":
            if target_line_num < 1 or target_line_num is None:
                sys_log.error(f"read_log FAIL: Invalid line num: {target_line_num} < 1")
                progress.console.print(f"[bold red]read_log FAIL: Invalid line num: {target_line_num} < 1[/bold red]")
                raise RuntimeError(f"Invalid line num: {target_line_num} < 1")
            if total_line_num <= target_line_num:
                log_str = "\n".join(log_line)
            else:
                log_str = "\n".join(log_line[-target_line_num:])
        elif method == "all":
            log_str = "\n".join(log_line)
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        sys_log.debug(f"read_log SUCCESS: Run id: {run_id} "
                      f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {target_line_num}")
        progress.console.print(f"[bright_black]read_log SUCCESS: Run id: {run_id} "
                               f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {target_line_num}[/bright_black]")
        return {"status": "SUCCESS",
                "total_line": total_line_num,
                "log_content": log_str}
    except Exception as e:
        sys_log.error(f"read_log FAIL: Read log failed with error: {e}")
        progress.console.print(f"[bold red]read_log FAIL: Read log failed with error: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Read log failed with error: {e}"}


def tool_read_file_def() -> dict[str, Any]:
    """tool definition of reading the file (read_file)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file as text with given path, method, line num and encoding method",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (absolute or relative to current working directory). Relative path "
                                       "of the current path should be start with './'",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["from_top", "from_bottom", "all"],
                        "description": "The method to read the file. Method 'from_top' reads the lines from top, method "
                                       "'from_bottom' reads the lines from bottom. Method 'all' reads all the lines.",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "description": "The num of read-in lines when method is 'from_top' or 'from_bottom'. If the method "
                                       "is 'all', this argument is ignored.",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (e.g., 'utf-8', 'gbk', 'ascii'). Default 'utf-8'.",
                        "default": "utf-8",
                    }
                },
                "required": ["path", "method", "encoding"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def read_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> Dict[str, Any]:
    """tool realization of reading the file with arguments and AgentContext"""
    try:
        """check the path"""
        file_path = arguments["path"]
        if not os.path.exists(file_path):
            sys_log.error(f"read_file FAIL: Path: {file_path} doesn't exist.")
            progress.console.print(f"[bold red]read_file FAIL: Path: {file_path} doesn't exist[/bold red]")
            return {"status": "FAIL",
                    "info": f"Path: {file_path} doesn't exist"}
        """check the file"""
        if not os.path.isfile(file_path):
            sys_log.error(f"read_file FAIL: Path: {file_path} is not a file")
            progress.console.print(f"[bold red]read_file FAIL: Path: {file_path} is not a file[/bold red]")
            return {"status": "FAIL",
                    "info": f"Path: {file_path} is not a file"}
        """read the file"""
        file_size = os.path.getsize(file_path)
        if file_size > ctx.agent_configs["READ_FILE_MB_LIMIT"] * 1024 * 1024:
            sys_log.error(f"read_file FAIL: "
                          f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB")
            progress.console.print(f"[bold red]read_file FAIL: "
                                   f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB[/bold red]")
            return {"status": "FAIL",
                    "info": f"File is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB"}
        encoding = arguments.get("encoding", "utf-8")
        with open(file_path, 'r', encoding=encoding) as f:
            file_line = f.readlines()
        total_line_num = len(file_line)
        """prepare the content"""
        target_line_num = arguments.get("line_num", 0)
        method = str(arguments["method"]).lower()
        if method == "from_top":
            if target_line_num < 1 or target_line_num is None:
                sys_log.error(f"read_file FAIL: Invalid line num: {target_line_num} < 1")
                progress.console.print(f"[bold red]read_file FAIL: Invalid line num: {target_line_num} < 1[/bold red]")
                raise RuntimeError(f"Invalid line num: {target_line_num} < 1")
            if total_line_num <= target_line_num:
                file_str = "\n".join(file_line)
            else:
                file_str = "\n".join(file_line[0:target_line_num])
        elif method == "from_bottom":
            if target_line_num < 1 or target_line_num is None:
                sys_log.error(f"read_file FAIL: Invalid line num: {target_line_num} < 1")
                progress.console.print(f"[bold red]read_file FAIL: Invalid line num: {target_line_num} < 1[/bold red]")
                raise RuntimeError(f"Invalid line num: {target_line_num} < 1")
            if total_line_num <= target_line_num:
                file_str = "\n".join(file_line)
            else:
                file_str = "\n".join(file_line[-target_line_num:])
        elif method == "all":
            file_str = "\n".join(file_line)
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        sys_log.debug(f"read_file SUCCESS: "
                      f"Path: {file_path}, method: {method}, encoding: {encoding}, total line: {total_line_num}, read-in line: {target_line_num}")
        progress.console.print(f"[bright_black]read_file SUCCESS: "
                               f"Path: {file_path}, method: {method}, encoding: {encoding}, total line: {total_line_num}, read-in line: {target_line_num}[/bright_black]")
        return {"status": "SUCCESS",
                "total_line": total_line_num,
                "log_content": file_str}
    except UnicodeDecodeError as e:
        sys_log.error(f"read_file FAIL: Can't read file with given encoding, error: {e}")
        progress.console.print(f"[bold red]read_file FAIL: Can't read file with given encoding, error: {e}[/bold red]")
        return {"status": "FAIL",
                "info": f"Can't read file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"read_file FAIL: Can't read file, permission denied: {e}")
        progress.console.print(f"[bold red]read_file FAIL: Can't read file, permission denied: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Can't read file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"read_file FAIL: Can't read file, OS error: {e}")
        progress.console.print(f"[bold red]read_file FAIL: Can't read file, OS error: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Can't read file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"read_file FAIL: Read file failed with error: {e}")
        progress.console.print(f"[bold red]read_file FAIL: Read file failed with error: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Read file failed with error: {e}"}


def tool_write_file_def() -> dict[str, Any]:
    """tool definition of writing the file (write_file)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or append content to a file with given path, contents, writing mode and encoding method. "
                           "Supports creating parent directories automatically",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (absolute or relative to current working directory). Relative path "
                                       "of the current path should be start with './'",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file. Can be plain text, JSON, html, code, etc."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append"],
                        "description": "Write mode: 'write' overwrites the file (default), 'append' adds content to the end.",
                        "default": "write"
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "If true, automatically create missing parent directories. Default true.",
                        "default": True
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (e.g., 'utf-8', 'gbk', 'ascii'). Default 'utf-8'.",
                        "default": "utf-8",
                    }
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def write_file(arguments: dict[str, Any], progress: Progress) -> Dict[str, Any]:
    """tool realization of writing the file with arguments"""
    try:
        """check the path"""
        file_path = arguments["path"]
        create_dirs = arguments.get("create_dirs", True)
        if create_dirs:
            parent_dir = os.path.dirname(file_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                sys_log.debug(f"write_file: Parent directory: {parent_dir} created")
                progress.console.print(f"[bright_black]write_file: Parent directory: {parent_dir} created[/bright_black]")
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
        progress.console.print(f"[bright_black]write_file SUCCESS: "
                               f"Path: {file_path}, mode: {mode}, create_dirs: {create_dirs}, encoding: {encoding}, bytes: {byte_count}[/bright_black]")
        return {"status": "SUCCESS",
                "bytes_written": byte_count,
                "info": f"Write content to {file_path} done successfully"}
    except UnicodeDecodeError as e:
        sys_log.error(f"write_file FAIL: Can't write file with given encoding, error: {e}")
        progress.console.print(f"[bold red]write_file FAIL: Can't write file with given encoding, error: {e}[/bold red]")
        return {"status": "FAIL",
                "info": f"Can't write file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"write_file FAIL: Can't write file, permission denied: {e}")
        progress.console.print(f"[bold red]write_file FAIL: Can't write file, permission denied: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Can't write file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"write_file FAIL: Can't write file, OS error: {e}")
        progress.console.print(f"[bold red]write_file FAIL: Can't write file, OS error: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Can't write file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"write_file FAIL: Write file failed with error: {e}")
        progress.console.print(f"[bold red]write_file FAIL: Write file failed with error: {e}[/bold red]")
        return {"status": "FAIL", "info": f"Write file failed with error: {e}"}
