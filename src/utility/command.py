# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.29
Description: Builtin command

Revision:
---------
2026.4.29      Yu Huang      1.0      First implementation
2026.5.12      Yu Huang      1.1      Add builtin command of querying read file
2026.5.15      Yu Huang      1.2      Revise builtin command management
2026.5.15      Yu Huang      1.3      Agent skills support
2026.5.19      Yu Huang      1.4      Webpage fetch support
2026.5.21-22   Yu Huang      1.5      Agent MCPs support & Revise the name of builtin commands
2026.5.22      Yu Huang      1.6      Summarize session title support & Builtin command of list sessions
2026.5.28      Yu Huang      1.7      Add read-only paths support & Add log for non-readonly builtin cmd
2026.5.31      Yu Huang      1.8      Add builtin cmd for session removal & Define used file/dir. paths in constants.py
2026.6.2       Yu Huang      1.9      Revise session list's layout and add usage info
2026.6.3       Yu Huang      2.0      Add cron tasks support & Add configurable title in yes or no request TUI
2026.6.7       Yu Huang      2.1      Support of tasks query in Scoreboard
2026.6.9       Yu Huang      2.2      Add design and run support for simulator

Details:
---------
Builtin command system starting with "/". `BuiltinCommands` class registers and dispatches commands including: design/run
query, context statistics, session management (list/remove), read-only path management, permission toggle, skill loading,
cron list/remove, URL cache query, MCP info, and session title update. Skills are auto-registered as commands for manual loading.
"""
import os
import json
import shutil
import logging

from pathlib import Path
from functools import partial
from typing import Callable, Any
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from src.utility import ui_info, basic_utils
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard, TaskStatus
from src.tool import summarize_support
from src.tool.skills_support import load_skill_content, get_skill_description
from src.constants import *

sys_log = logging.getLogger('logger')
BUILTIN_UNKNOWN = "UNKNOWN"


def cmd_unknown(console: Console):
    """unknown builtin commands"""
    cmd_str = Text()
    cmd_str.append("Unknown command ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("called, nothing happen\n", style=f"white")
    console.print(cmd_str)


def cmd_design_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the list of current designs"""
    revisions = ctx.design_man.list_revisions()
    title = f"Current Designs ({len(revisions)})"
    cmd_str = Text()
    for revision in revisions:
        design_id = revision["design_id"]
        uuid_map = revision["revision_uuids"]
        cmd_str.append(f"Design ID: ", style=f"white")
        cmd_str.append(f"{design_id}\n", style=f"bold {MAJOR_COLOR1}")
        for design_uuid in uuid_map.values():
            if_success, design, get_info = ctx.design_man.get_design_uuid(design_uuid)
            if not if_success or design is None:
                continue
            cmd_str.append(f"Revision ID: ", style=f"white")
            cmd_str.append(f"{design["design_rev"]}\n", style=f"{MAJOR_COLOR2}")
            cmd_str.append(f" - Subject: ", style=f"white")
            cmd_str.append(f"{design["subject"]}\n", style=f"{MAJOR_COLOR2}")
            cmd_str.append(f" - Description: ", style=f"white")
            cmd_str.append(f"{design["description"]}\n", style=f"bright_black")
            if design["copy_id"] is not None:
                cmd_str.append(f" - Copy from: ", style=f"white")
                cmd_str.append(f"{design["copy_id"]} (rev {design["copy_rev"]})\n", style=f"{MAJOR_COLOR2}")
            else:
                cmd_str.append(f" - Copy from: ", style=f"white")
                cmd_str.append(f"(None)\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append("\n")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_run_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the amount of launched simulation"""
    runs = ctx.run_man.list_runs()
    title = f"Launched Runs ({len(runs)})"
    cmd_str = Text()
    for run in runs:
        run_id = run["run_id"]
        design_id = run["design_id"]
        design_rev = run["design_rev"]
        subject = run["subject"]
        description = run["description"]
        status = run["status"].value
        cmd_str.append(f"Run ID: ", style=f"white")
        cmd_str.append(f"{run_id}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f", Design: ", style=f"white")
        cmd_str.append(f"{design_id} (rev {design_rev})\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f"Subject: ", style=f"white")
        cmd_str.append(f"{subject}\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f"Description: ", style=f"white")
        cmd_str.append(f"{description}\n", style=f"bright_black")
        cmd_str.append(f"Status: ", style=f"white")
        cmd_str.append(f"{status}\n\n", style=f"{MAJOR_COLOR2}")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_context(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the token usage, message and API requests statistics"""
    title = "TECoSim Agent Context Usage"
    if ctx.total_input_tokens <= 0:
        uncached_rate = 100
    else:
        uncached_rate = 100 * ctx.total_uncached_tokens / ctx.total_input_tokens
    if ctx.api_configs["MAIN_MODEL_CONTEXT"] <= 0:
        ctx_usage = 100
    else:
        ctx_usage = 100 * ctx.last_input_tokens / ctx.api_configs["MAIN_MODEL_CONTEXT"]
    cmd_str = Text()
    cmd_str.append("Session UUID: ", style=f"white")
    cmd_str.append(f"{ctx.session_uuid}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total input tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_input_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total output tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_output_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total uncached tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_uncached_tokens / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", uncached: ", style=f"white")
    cmd_str.append(f"{uncached_rate:.3f} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", cached: ", style=f"white")
    cmd_str.append(f"{100 - uncached_rate:.3f} %\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total tokens consumption of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue input tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue output tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_output_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue total tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue's context usage of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx_usage:.3f} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" out of ", style=f"white")
    cmd_str.append(f"{ctx.api_configs["MAIN_MODEL_CONTEXT"] / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" were used\n", style=f"white")

    cmd_str.append("\nTotal LLM API request num: ", style=f"white")
    cmd_str.append(f"{ctx.total_llm_requests}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total messages num (main model): ", style=f"white")
    cmd_str.append(f"{len(ctx.messages)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("System prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.system_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tools prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tools_prompts}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" (", style=f"white")
    cmd_str.append(f"{len(ctx.tools) - len(ctx.mcp_router.reg_tools)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" agent tools, ", style=f"white")
    cmd_str.append(f"{len(ctx.mcp_router.reg_tools)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" MCP tools)\n", style=f"white")
    cmd_str.append("User prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.user_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant content prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.content_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant reasoning content prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.reasoning_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant tool calls prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tool_calls_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tool results prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tool_results_prompts}\n", style=f"bold {MAJOR_COLOR2}")

    cmd_str.append("\nAvailable skills amount: ", style=f"white")
    cmd_str.append(f"{len(ctx.skills)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Available skills: ", style=f"white")
    for skill in ctx.skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", ", style=f"white")
    if cmd_str.plain.endswith(", "):
        cmd_str.right_crop(2)
    cmd_str.append("\nLoaded skills amount: ", style=f"white")
    cmd_str.append(f"{len(ctx.loaded_skills)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Loaded skills: ", style=f"white")
    for skill in ctx.loaded_skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f" ,", style=f"white")
    if cmd_str.plain.endswith(" ,"):
        cmd_str.right_crop(2)

    cmd_str.append("\nAvailable MCPs amount: ", style=f"white")
    cmd_str.append(f"{len(ctx.mcps_configs)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" (", style=f"white")
    cmd_str.append(f"{len(ctx.mcp_router.clients)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" MCPs active)\n", style=f"white")
    for config in ctx.mcps_configs:
        cmd_str.append(f"   - {config["name"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", MCP transport type: ", style=f"white")
        cmd_str.append(f"{config["type"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", if enabled: ", style=f"white")
        if not config["if_disabled"]:
            cmd_str.append("True", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(", Registered tools: ", style=f"white")
            cmd_str.append(f"{len(ctx.mcp_router.mcps_tools[config["name"]])}\n", style=f"bold {MAJOR_COLOR2}")
        else:
            cmd_str.append("False\n", style="bright_black")

    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_fread_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the absolute paths of all read files"""
    title = "TECoSim Agent Files Read"
    cmd_str = Text()
    cmd_str.append(f"{len(ctx.files_read)} ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" files read by TECoSim Agent\n\n", style=f"white")

    cmd_str.append("File list: \n", style=f"bold {MAJOR_COLOR2}")
    for path, amount in ctx.files_read.items():
        cmd_str.append(f"{path}: ", style=f"white")
        cmd_str.append(f"{amount}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(" times\n", style=f"white")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_readonly_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the absolute paths of all readonly paths"""
    title = (f"TECoSim Agent Readonly Paths "
             f"({len(ctx.system_read_only_paths)} system, {len(ctx.read_only_paths)} custom)")
    cmd_str = Text()
    cmd_str.append(f"System readonly paths (can not edit):\n", style=f"bold {MAJOR_COLOR2}")
    for path in ctx.system_read_only_paths:
        if path.exists():
            cmd_str.append(f"{path.resolve()}", style=f"white")
            cmd_str.append(f" (exists)\n", style=f"bold {MAJOR_COLOR2}")
        else:
            cmd_str.append(f"{path}", style=f"white")
            cmd_str.append(f" (nonexists)\n", style=f"bright_black")
    cmd_str.append("\n")

    cmd_str.append(f"Customizable readonly paths:\n", style=f"bold {MAJOR_COLOR2}")
    for idx, path in enumerate(ctx.read_only_paths):
        cmd_str.append(f"[", style=f"white")
        cmd_str.append(f"{idx}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f"] ", style=f"white")
        if path.exists():
            cmd_str.append(f"{path.resolve()}", style=f"white")
            cmd_str.append(f" (exists)\n", style=f"bold {MAJOR_COLOR2}")
        else:
            cmd_str.append(f"{path}", style=f"white")
            cmd_str.append(f" (nonexists)\n", style=f"bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can add custom readonly path with following builtin command: ", style=f"bright_black")
    hint.append(f"/readonly_add ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[PATH1] [PATH2] [PATH3] ...\n", style=f"bold {MAJOR_COLOR1}")
    hint.append(f"        You can remove custom readonly path with following builtin command: ", style=f"bright_black")
    hint.append(f"/readonly_remove ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[idx1] [idx2] [idx3] ...", style=f"bold {MAJOR_COLOR1}")

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")


def cmd_readonly_add(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """add a readonly path into list (converted to absolute path)"""
    if len(args) == 0:
        sys_log.warning(f"Unable to add readonly path, target path is empty")
        console.print(f"Unable to add readonly path, target path is empty", style=f"bold yellow")
        return

    skipped_list: list[int] = []
    for idx, arg in enumerate(args):
        arg_path = Path(arg)
        if not arg_path.exists():
            skipped_list.append(idx)
            continue

        resolved_arg_path = arg_path.resolve()
        ctx.read_only_paths.append(resolved_arg_path)

    sys_log.debug(f"Added {len(args) - len(skipped_list)} readonly paths, {len(skipped_list)} paths are ignored with index: "
                  f"{skipped_list}")
    cmd_str = Text()
    cmd_str.append(f"Added ", style=f"white")
    cmd_str.append(f"{len(args) - len(skipped_list)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" readonly paths, ", style=f"white")
    cmd_str.append(f"{len(skipped_list)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" paths are ignored with index: ", style=f"white")
    cmd_str.append(f"{skipped_list}\n", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_readonly_remove(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """remove a readonly path from list"""
    if len(args) == 0:
        sys_log.warning(f"Unable to remove readonly path, target index is empty")
        console.print(f"Unable to remove readonly path, target index is empty", style=f"bold yellow")
        return

    skipped_list: list[int] = []
    del_list: list[int] = []
    path_len = len(ctx.read_only_paths)
    for idx, arg in enumerate(args):
        try:
            index = int(arg)
        except Exception:
            skipped_list.append(idx)
            continue

        if index >= path_len or index < 0:
            skipped_list.append(idx)
            continue

        del_list.append(index)

    for idx in sorted(del_list, reverse=True):
        del ctx.read_only_paths[idx]

    sys_log.debug(f"Removed {len(del_list)} readonly paths, {len(skipped_list)} paths are ignored with index: "
                  f"{skipped_list}")
    cmd_str = Text()
    cmd_str.append(f"Removed ", style=f"white")
    cmd_str.append(f"{len(del_list)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" readonly paths, ", style=f"white")
    cmd_str.append(f"{len(skipped_list)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" paths are ignored with index: ", style=f"white")
    cmd_str.append(f"{skipped_list}\n", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_permission_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query the configs of always-allowed-configurable tool calls permission token"""
    title = "TECoSim Agent Tool Call Permission"
    cmd_str = Text()
    cmd_str.append(f"{len(ctx.permissions)} ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f"types of ", style=f"white")
    cmd_str.append(f"always-allowed-configurable", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" tool calls permission: \n\n", style=f"white")

    cmd_str.append("Dangerously allow all: ", style=f"bold {MAJOR_COLOR2}")
    if ctx.args.dangerously_allow_all:
        cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
    else:
        cmd_str.append("False\n", style="bright_black")
    for name, token in ctx.permissions.items():
        cmd_str.append(f"{name}: ", style=f"white")
        if ctx.args.dangerously_allow_all:
            cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
        else:
            if token:
                cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
            else:
                cmd_str.append("False\n", style="bright_black")

    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can also toggle the permission config with following builtin command: \n", style=f"bright_black")
    hint.append(f"        /permission_toggle ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[NAME OF PERMISSION]", style=f"bold {MAJOR_COLOR1}")
    hint.append(f" (Swap ", style=f"white")
    hint.append(f"True", style=f"bold {MAJOR_COLOR1}")
    hint.append(f" and ", style=f"white")
    hint.append(f"False", style=f"bright_black")
    hint.append(f")\n", style=f"white")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")


def cmd_permission_toggle(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """toggle the permission token of the tool calls permission with given name"""
    cmd_str = Text()
    if ctx.args.dangerously_allow_all:
        cmd_str.append("You can't toggle any permission token, since ", style=f"white")
        cmd_str.append("dangerously_allow_all", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(" is ", style=f"white")
        cmd_str.append("enabled", style=f"bold {MAJOR_COLOR1}")
        console.print(cmd_str)
        return

    try:
        arg_name = args[0]
    except Exception as e:
        sys_log.warning(f"Unable to toggle the permission, target name is invalid with error {e}")
        console.print(f"Unable to toggle the permission, target name is invalid with error {e}", style=f"bold yellow")
        return

    for name, token in ctx.permissions.items():
        if arg_name == name:
            ctx.permissions[name] = not token
            sys_log.debug(f"Permission {name} toggled from {"True" if token else "False"} to {"False" if token else "True"} successfully")
            cmd_str.append(f"Permission ", style=f"white")
            cmd_str.append(f"{name}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f" toggled from ", style=f"white")
            cmd_str.append(f"{"True" if token else "False"}", style=f"bold {MAJOR_COLOR1}" if token else f"bright_black")
            cmd_str.append(f" to ", style=f"white")
            cmd_str.append(f"{"False" if token else "True"}", style=f"bright_black" if token else f"bold {MAJOR_COLOR1}")
            cmd_str.append(f" successfully\n", style=f"white")
            console.print(cmd_str)
            return
    sys_log.warning(f"Unknown permission name {arg_name}, toggle failed")
    console.print(f"Unknown permission name {arg_name}, toggle failed", style=f"bold yellow")


def cmd_skill_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all available skills (truncate)"""
    title = f"Available Skills ({len(ctx.skills)})"
    limit = ctx.agent_configs["SKILL_DESC_CHAR_LIMIT"]
    cmd_str = Text()
    for skill in ctx.skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        if len(skill["description"]) > limit:
            cmd_str.append(f"{skill["description"][:limit]}...\n\n", style=f"white")
        else:
            cmd_str.append(f"{skill["description"]}\n\n", style=f"white")
    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_skills_loaded(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all loaded skills (no truncate)"""
    title = f"Loaded Skills ({len(ctx.loaded_skills)})"
    cmd_str = Text()
    for skill in ctx.loaded_skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        cmd_str.append(f" {skill["description"]}\n\n", style=f"white")
    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def skill_bound_command(name: str, func: Callable, *args, **kwargs):
    """crete a partial function for loading skills"""
    bound_func = partial(func, *args, **kwargs)
    bound_func.__name__ = name
    return bound_func


def cmd_load_skills(skill_name: str, args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """manually load the full prompts of skill to context immediately"""
    try:
        content = load_skill_content(SKILLS_PATH, skill_name, console, True)
        if content is None:
            sys_log.warning(f"Load skill {skill_name} manually failed")
            console.print(f"Load skill {skill_name} manually failed", style=f"bold yellow")
            ctx.messages.append(
                {"role": "user", "content": f"<Load skill {skill_name} manually by user failed>"})
        else:
            ctx.messages.append({"role": "user", "content": json.dumps(content)})
        if not any(item.get("name") == skill_name for item in ctx.loaded_skills):  # registered skills must be available
            ctx.loaded_skills.append({
                "name": skill_name,
                "description": str(get_skill_description(skill_name, ctx.skills)),
            })
    except Exception as e:
        sys_log.warning(f"Load skill {skill_name} manually failed with error {e}")
        console.print(f"Load skill {skill_name} manually failed with error {e}", style=f"bold yellow")
        ctx.messages.append(
            {"role": "user", "content": f"<Load skill {skill_name} manually by user failed with error {e}>"})


def cmd_url_caches(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all cached URLs"""
    title = f"Cached URLs ({len(ctx.url_caches)})"
    cmd_str = Text()
    view_limit = URL_CACHE_VIEW_MAX
    char_limit = URL_CACHE_CONTENT_CHAR_MAX
    view_left = len(ctx.url_caches) - view_limit if len(ctx.url_caches) >= view_limit else  0
    for idx, url_cache in enumerate(ctx.url_caches):
        cmd_str.append(f"URL: ", style=f"white")
        cmd_str.append(f"{url_cache["url"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", timestamp: ", style=f"white")
        cmd_str.append(f"{url_cache["time"].strftime("%Y-%m-%d %H:%M:%S")}\n", style=f"bold {MAJOR_COLOR2}")
        content = url_cache["content"]
        if len(content) > char_limit:
            content = content[:char_limit] + "..."
        cmd_str.append(f"Cached content: ", style=f"white")
        cmd_str.append(f"{content}\n\n", style=f"bright_black")
        if idx + 1 >= view_limit:
            break
    cmd_str.append(f"Remaining cached URLs not-displayed: ", style=f"white")
    cmd_str.append(f"{view_left}", style=f"bold {MAJOR_COLOR2}")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_mcp_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query MCPs info"""
    mcps_configs = ctx.mcps_configs
    mcps_ini_info = ctx.mcp_router.mcps_ini_info
    mcps_tools = ctx.mcp_router.mcps_tools
    title = f"MCP Info ({len(mcps_configs)} available, {len(ctx.mcp_router.clients)} active)"

    cmd_str = Text()
    for config in mcps_configs:
        # if the MCP is disabled
        if config["if_disabled"]:
            cmd_str.append(f"{config["name"]}", style=f"bold {MAJOR_COLOR1}")
            cmd_str.append(f", MCP transport type: ", style=f"white")
            cmd_str.append(f"{config["type"]}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f", if enabled: ", style=f"white")
            cmd_str.append("False\n\n", style="bright_black")
        # if the MCP is not disabled (list version info and tools info)
        else:
            cmd_str.append(f"{config["name"]}", style=f"bold {MAJOR_COLOR1}")
            cmd_str.append(f", MCP transport type: ", style=f"white")
            cmd_str.append(f"{config["type"]}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f", if enabled: ", style=f"white")
            cmd_str.append("True", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(", Registered tools: ", style=f"white")
            cmd_str.append(f"{len(mcps_tools[config["name"]])}\n", style=f"bold {MAJOR_COLOR2}")

            mcp_ini_info = mcps_ini_info[config["name"]]
            cmd_str.append(f"MCP initialize information: \n", style=f"bold {MAJOR_COLOR2}")
            for key, value in mcp_ini_info.items():
                cmd_str.append(f"  - {key}: ", style=f"white")
                cmd_str.append(f"{value}\n", style=f"bright_black")

            mcp_tools = mcps_tools[config["name"]]
            cmd_str.append(f"MCP tools description: \n", style=f"bold {MAJOR_COLOR2}")
            for tool in mcp_tools:
                tool_desc = tool["description"]
                if len(tool_desc) > MCP_TOOL_DESC_CHAR_LIMIT:
                    tool_desc = tool_desc[:MCP_TOOL_DESC_CHAR_LIMIT] + "..."
                cmd_str.append(f"  - {tool["name"]}: ", style=f"bold {MAJOR_COLOR1}")
                cmd_str.append(f"{tool_desc}\n", style=f"white")
            cmd_str.append("\n")

    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can manage the MCPs with following command in shell: ", style=f"bright_black")
    hint.append(f"python -m src.main mcp ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[list | add | toggle | remove]\n", style=f"bold {MAJOR_COLOR1}")
    hint.append(f"        You can also manage the MCPs by manually editing the config file: ", style=f"bright_black")
    hint.append(f"{MCPS_CONFIGS_PATH}", style=f"bold {MAJOR_COLOR2}")

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")


def cmd_update_title(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """update title of this session with history immediately"""
    title = summarize_support.summarize_session(ctx=ctx, console=console)
    ctx.session_title = title if title else ERROR_SESSION_TITLE
    ui_info.set_terminal_title(ctx.session_title)
    sys_log.debug("Session title updated")
    console.print("Session title updated", style="bright_black")


def cmd_session_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all sessions"""
    session_dir = SESSION_PATH
    if not os.path.exists(session_dir):
        sys_log.error(f"Session directory {session_dir} does not exist")
        console.print(f"Session directory {session_dir} does not exist", style="bold red")
        return

    sessions_list:list[dict[str, Any]] = []
    current_uuid = ctx.session_uuid
    for item in os.listdir(session_dir):
        item_path = os.path.join(session_dir, item)
        if not os.path.isdir(item_path):
            continue
        if not basic_utils.is_valid_uuid(item):
            continue

        context_file = os.path.join(item_path, CONTEXT_NAME)
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)
            # only append other sessions (up-to-date status of current session may not sync with file)
            if item != current_uuid:
                sessions_list.append({"uuid": item,
                                      "title": context.get("session_title", UNKNOWN_SESSION_TITLE),
                                      "input_tokens": context.get("last_input_tokens", "N/A")})
        except Exception as e:
            sys_log.error(f"Failed to load session {item}'s context with error {e}")
            console.print(f"Failed to load session {item}'s context with error {e}", style="bold red")

    title = f"Available Sessions ({len(sessions_list) + 1})"
    cmd_str = Text()
    cmd_str.append(f"UUID: ", style=f"white")
    cmd_str.append(f"{current_uuid}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f"  Title: ", style=f"white")
    cmd_str.append(f"{ctx.session_title}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" ({ctx.last_input_tokens / 1000.0:.1f} K tokens) ", style=f"bright_black")
    cmd_str.append(f"({AGENT_CONSOLE_ICON} Current)\n", style=f"bold {MAJOR_COLOR1}")
    for session in sessions_list:
        cmd_str.append(f"UUID: ", style=f"white")
        cmd_str.append(f"{session["uuid"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Title: ", style=f"white")
        cmd_str.append(f"{session["title"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f" ({session["input_tokens"] / 1000.0:.1f} K tokens)\n", style=f"bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can resume any session with following command in shell: ", style=f"bright_black")
    hint.append(f"python -m src.main -r ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[Session UUID]", style=f"bold {MAJOR_COLOR1}")

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")


def cmd_session_remove(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """remove a session with UUID"""
    session_dir = SESSION_PATH
    if not os.path.exists(session_dir):
        sys_log.error(f"Session directory {session_dir} does not exist")
        console.print(f"Session directory {session_dir} does not exist", style="bold red")
        return

    try:
        """validate UUID"""
        uuid_str: str = args[0]
        if not basic_utils.is_valid_uuid(uuid_str):
            sys_log.error(f"Session UUID: {uuid_str} is not valid")
            console.print(f"Session UUID: {uuid_str} is not valid", style="bold red")
            return

        """check if the UUID is the current one"""
        if uuid_str == ctx.session_uuid:
            sys_log.error(f"Can not delete current session: {uuid_str}")
            console.print(f"Can not delete current session: {uuid_str}", style="bold red")
            return

        """check the path"""
        if not os.path.exists(os.path.join(session_dir, uuid_str)):
            sys_log.error(f"Session with UUID: {uuid_str} not exists")
            console.print(f"Session with UUID: {uuid_str} not exists", style="bold red")
            return
        if os.path.isfile(os.path.join(session_dir, uuid_str)):
            sys_log.error(f"Session with UUID: {uuid_str} is a file, not a directory")
            console.print(f"Session with UUID: {uuid_str} is a file, not a directory", style="bold red")
            return

        """delete the session folder"""
        token = ui_info.request_tui(console=console, title="Remove Session", request_desc=f"remove the session: {uuid_str}",
                                    request_detail=f"This session will be deleted forever",
                                    cancel_str=f"Session remove cancelled")
        if token:
            shutil.rmtree(os.path.join(session_dir, uuid_str))
            sys_log.debug(f"Session with UUID: {uuid_str} has been removed")
            console.print(f"Session with UUID: [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] has been removed")
        else:
            sys_log.debug(f"Session with UUID: {uuid_str} remove cancelled")
            console.print(f"Session with UUID: [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] remove cancelled")
            return

    except Exception as e:
        sys_log.error(f"Remove session with args: {args} failed with error: {e}")
        console.print(f"Remove session with args: {args} failed with error: {e}", style="bold red")


def cmd_cron_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all cron tasks"""
    title = f"Available Cron Tasks ({len(ctx.cron_tasks)} total, {ctx.active_cron} active)"
    cmd_str = Text()
    for cron_task in ctx.cron_tasks:
        cmd_str.append(f"ID: ", style=f"white")
        cmd_str.append(f"{cron_task["id"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Pattern: ", style=f"white")
        cmd_str.append(f"{cron_task["cron_str"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Durable: ", style=f"white")
        if not cron_task["durable"]:
            cmd_str.append(f"False", style=f"bright_black")
        else:
            cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f"  Repetitive: ", style=f"white")
        if not cron_task["if_repeat"]:
            cmd_str.append(f"False", style=f"bright_black")
        else:
            cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f"  Active: ", style=f"white")
        if not cron_task["if_repeat"] and cron_task["if_end"]:
            cmd_str.append(f"False", style=f"bright_black")
        else:
            cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f"\nPrompt: ", style=f"white")
        cmd_str.append(f"{cron_task["prompt"]}\n\n", style=f"bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can remove any cron task with following builtin command: ", style=f"bright_black")
    hint.append(f"/cron_remove ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[Cron ID]", style=f"bold {MAJOR_COLOR1}")

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")


def cmd_cron_remove(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """remove a cron task with ID"""
    try:
        id_str: str = args[0]
        token = ui_info.request_tui(console=console, title="Remove Cron Task", request_desc=f"remove the cron: {id_str}",
                                    request_detail=f"This cron task will be deleted forever",
                                    cancel_str=f"Cron task remove cancelled")
        if not token:
            sys_log.debug(f"Cron with ID: {id_str} remove cancelled")
            console.print(f"Cron with ID: [{MAJOR_COLOR2}]{id_str}[/{MAJOR_COLOR2}] remove cancelled")
            return

        if_success, remove_info = ctx.remove_cron_task(id_str)
        if not if_success:
            sys_log.error(f"Remove cron task with id: {id_str} failed with error, details: {remove_info}")
            console.print(f"Remove cron task with id: {id_str} failed with error, details: {remove_info}", style="bold red")
        else:
            sys_log.debug(f"Remove cron task with id: {id_str} successfully")
            console.print(f"Remove cron task with id: [{MAJOR_COLOR2}]{id_str}[/{MAJOR_COLOR2}] successfully", style="bright_black")
    except Exception as e:
        sys_log.error(f"Remove cron task with args: {args} failed with error: {e}")
        console.print(f"Remove cron task with args: {args} failed with error: {e}", style="bold red")


def cmd_task_list(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all non-archived agent tasks"""
    tasks = board.list_tasks()
    title = f"Non-archived Agent Tasks ({len(tasks)})"
    cmd_str = Text()
    for task in tasks:
        subject = task["subject"]
        status = task["status"].value
        owner = task["owner"]
        cmd_str.append(f"Task ID: ", style=f"white")
        cmd_str.append(f"{task["task_id"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Owner ID: ", style=f"white")
        if owner is None:
            cmd_str.append(f"(None)", style=f"{MAJOR_COLOR2}")
        else:
            cmd_str.append(f"{task["owner"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Status: ", style=f"white")
        cmd_str.append(f"{status}\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f"Subject: ", style=f"white")
        if status == TaskStatus.PENDING:
            if owner is None:
                cmd_str.append(
                    f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITHOUT_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                    style=TASK_PENDING_WITHOUT_OWNER_ICON_STYLE)
                cmd_str.append(f"{subject}\n", style=TASK_PENDING_WITHOUT_OWNER_STYLE)
            else:
                cmd_str.append(
                    f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                    style=f"bold {TASK_PENDING_COLOR_END}")
                cmd_str.append(f"{subject}\n", style=f"{TASK_PENDING_COLOR_END}")
        elif status == TaskStatus.IN_PROGRESS:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_IN_PROGRESS_COLOR_END}")
            cmd_str.append(f"{subject}\n", style=f"{TASK_IN_PROGRESS_COLOR_END}")
        elif status == TaskStatus.COMPLETED:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_COMPLETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_COMPLETED_COLOR}")
            cmd_str.append(f"{subject}\n", style=TASK_COMPLETED_COLOR)
        elif status == TaskStatus.DELETED:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_DELETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_DELETED_COLOR}")
            cmd_str.append(f"{subject}\n", style=f"strike {TASK_DELETED_COLOR}")
        cmd_str.append(f"Description: ", style=f"white")
        cmd_str.append(f"{task["description"]}\n", style=f"bright_black")
        cmd_str.append(f"Blocks: ", style=f"white")
        cmd_str.append(f"{task["blocks"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Blocked By: ", style=f"white")
        cmd_str.append(f"{task["blocked_by"]}\n\n", style=f"{MAJOR_COLOR2}")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: Resolved agent tasks will be archived after {TASK_DISPLAYS_BEFORE_ARCHIVED} times of displays.\n", style=f"bright_black")
    hint.append(f"        You can query all history agent tasks with following builtin command: ", style=f"bright_black")
    hint.append(f"/task_list_all ", style=f"bold {MAJOR_COLOR2}")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)
    console.print("\n")



def cmd_task_list_all(args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
    """query all history agent tasks"""
    tasks = board.list_all_tasks()
    title = f"History Agent Tasks ({len(tasks)})"
    cmd_str = Text()
    for task in tasks:
        subject = task["subject"]
        status = task["status"].value
        owner = task["owner"]
        cmd_str.append(f"Task ID: ", style=f"white")
        cmd_str.append(f"{task["task_id"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Owner ID: ", style=f"white")
        if owner is None:
            cmd_str.append(f"(None)", style=f"{MAJOR_COLOR2}")
        else:
            cmd_str.append(f"{task["owner"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Status: ", style=f"white")
        cmd_str.append(f"{status}\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f"Subject: ", style=f"white")
        if status == TaskStatus.PENDING:
            if owner is None:
                cmd_str.append(
                    f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITHOUT_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                    style=TASK_PENDING_WITHOUT_OWNER_ICON_STYLE)
                cmd_str.append(f"{subject}\n", style=TASK_PENDING_WITHOUT_OWNER_STYLE)
            else:
                cmd_str.append(
                    f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                    style=f"bold {TASK_PENDING_COLOR_END}")
                cmd_str.append(f"{subject}\n", style=f"{TASK_PENDING_COLOR_END}")
        elif status == TaskStatus.IN_PROGRESS:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_IN_PROGRESS_COLOR_END}")
            cmd_str.append(f"{subject}\n", style=f"{TASK_IN_PROGRESS_COLOR_END}")
        elif status == TaskStatus.COMPLETED:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_COMPLETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_COMPLETED_COLOR}")
            cmd_str.append(f"{subject}\n", style=TASK_COMPLETED_COLOR)
        elif status == TaskStatus.DELETED:
            cmd_str.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_DELETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_DELETED_COLOR}")
            cmd_str.append(f"{subject}\n", style=f"strike {TASK_DELETED_COLOR}")
        cmd_str.append(f"Description: ", style=f"white")
        cmd_str.append(f"{task["description"]}\n", style=f"bright_black")
        cmd_str.append(f"Blocks: ", style=f"white")
        cmd_str.append(f"{task["blocks"]}", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f", Blocked By: ", style=f"white")
        cmd_str.append(f"{task["blocked_by"]}\n\n", style=f"{MAJOR_COLOR2}")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


class BuiltinCommands:
    """builtin command class"""
    def __init__(self, console: Console):
        self._commands: dict[str, tuple[Callable[..., Any], str, str]] = {
            "help": (self.cmd_help, "help info", "print all available builtin commands"),
            "design_list": (cmd_design_list, "query all designs", "query the list of current designs"),
            "run_list": (cmd_run_list, "query all runs", "query the list of all launched simulation"),
            "context": (cmd_context, "query context info", "query the token usage, message and API requests statistics"),
            "fread_list": (cmd_fread_list, "query all read files", "query the absolute paths of all read files"),
            "readonly_list": (cmd_readonly_list, "query all readonly paths", "query the absolute paths of all readonly paths"),
            "readonly_add": (cmd_readonly_add, "add readonly path", "add readonly paths into list (converted to absolute path)"),
            "readonly_remove": (cmd_readonly_remove, "remove readonly path", "remove readonly path from list with indexes list"),
            "permission_list": (cmd_permission_list, "query permission info",
                                "query the configs of always-allowed-configurable tool calls permission token"),
            "permission_toggle": (cmd_permission_toggle, "toggle the permission with given name",
                                "toggle the permission token of the tool calls permission with given name"),
            "skill_list": (cmd_skill_list, "query all available skills",
                                               "query all the available skills with name and truncated description"),
            "skills_loaded": (cmd_skills_loaded, "query all loaded skills",
                                               "query all the loaded skills with name and full description"),
            "url_caches": (cmd_url_caches, "query all cached URLs",
                                               "query all the cached URLs with timestamp and truncated content"),
            "mcp_list": (cmd_mcp_list, "query MCPs info", "query information of all available MCPs"),
            "update_title": (cmd_update_title, "update session title", "update title of this session with history immediately"),
            "session_list": (cmd_session_list, "query all sessions", "query all sessions with UUID and title"),
            "session_remove": (cmd_session_remove, "remove a session", "remove a session with given UUID"),
            "cron_list": (cmd_cron_list, "query all cron tasks", "query all scheduled tasks with ID, pattern and prompt"),
            "cron_remove": (cmd_cron_remove, "remove a cron task", "remove a scheduled tasks with ID"),
            "task_list": (cmd_task_list, "list agent tasks", "list all agent tasks that are not archived"),
            "task_list_all": (cmd_task_list_all, "list all agent tasks", "list all history agent tasks"),
        }
        self._request_commands: list[str] = []
        sys_log.debug(f"{len(self._commands)} builtin commands initialized")
        console.print(f"[{MAJOR_COLOR2}]{len(self._commands)}[/{MAJOR_COLOR2}] builtin commands initialized")


    def get_all_commands(self) -> dict[str, tuple[Callable, str, str]]:
        """get copy of all available commands"""
        return self._commands.copy()


    def register(self, name: str, func: Callable, short_desc: str, long_desc: str, request_llm: bool):
        """register a new command, raise error if function already exists"""
        if name in self._commands:
            raise ValueError(f"Command '{name}' already registered")

        for cmd_name, (existing_func, _, _) in self._commands.items():
            if existing_func.__name__ == func.__name__:
                raise ValueError(f"Function '{func.__name__}' already registered as command '{cmd_name}'")
        self._commands[name] = (func, short_desc, long_desc)
        if request_llm:
            self._request_commands.append(name)


    def unregister(self, name: str):
        """unregister a command"""
        self._commands.pop(name, None)
        if name in self._request_commands:
            self._request_commands.remove(name)


    def register_skills(self, skills: list[dict[str, str]], console: Console):
        """register skills as builtin commands"""
        registered_skills = 0
        for skill in skills:
            if skill["name"] in self._commands:
                sys_log.warning(f"Skill with '{skill['name']}' is already registered")
                console.print(f"Skill with '{skill['name']}' is already registered", style="bold yellow")
            else:
                self.register(skill["name"], skill_bound_command(skill["name"], cmd_load_skills, skill["name"]),
                              "load this skill immediately",
                              f"load the skill {skill['name']} immediately to context", True)
                registered_skills += 1
        sys_log.debug(f"{registered_skills} skills registered as builtin commands, "
                      f"{len(self._commands)} builtin commands available")
        console.print(f"[{MAJOR_COLOR2}]{registered_skills}[/{MAJOR_COLOR2}] skills registered as builtin commands, "
                      f"[{MAJOR_COLOR2}]{len(self._commands)}[/{MAJOR_COLOR2}] builtin commands available")


    def cmd_help(self, args: list[str], ctx: AgentContext, board: Scoreboard, console: Console):
        """print all available commands"""
        title = "Available Commands"
        cmd_str = Text()
        for cmd, (func, label, desc) in self._commands.items():
            cmd_str.append(f"/{cmd}", style=f"bold {MAJOR_COLOR1}")
            cmd_str.append(f": ", style=f"white")
            cmd_str.append(f"{label}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f", {desc}\n", style=f"white")
        if cmd_str.plain.endswith("\n"):
            cmd_str.rstrip()
        console.print(Panel.fit(cmd_str, title=title, title_align="left",
                                padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
        console.print("\n")


    def execute_cmd(self, cmd: str, args: list[str], ctx: AgentContext, board: Scoreboard, console: Console) -> bool:
        """execute builtin command, return if goto the LLM request"""
        if cmd == BUILTIN_UNKNOWN:
            sys_log.debug("Unknown command called, nothing happen")
            cmd_unknown(console)
            return False
        else:
            sys_log.debug(f"Command call: {cmd} with args {args} start")
            self._commands[cmd][0](args, ctx, board, console)
            sys_log.debug(f"Command call: {cmd} done")
            if cmd in self._request_commands:
                return True
            else:
                return False


    def __contains__(self, name: str) -> bool:
        """in operations"""
        return name in self._commands


    def __iter__(self):
        """iterator"""
        return iter(self._commands.items())
