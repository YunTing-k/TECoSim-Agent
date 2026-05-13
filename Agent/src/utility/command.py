# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.29\n
Description: Builtin command

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.29      Yu Huang     1.0               First implementation\n
2026.5.12      Yu Huang     1.1               Add builtin command of querying read file\n

Details:
Realization of builtin commands
------------------------------------------------------------------------------------------------------------------------
"""
import logging
from typing import Callable, Any

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')
BUILTIN_COMMANDS: dict[str, tuple[Callable[..., Any], str, str]]
BUILTIN_UNKNOWN = "UNKNOWN"


def cmd_unknown(console: Console):
    """unknown builtin commands"""
    cmd_str = Text()
    cmd_str.append("Unknown command ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("called, nothing happen", style=f"white")
    console.print(cmd_str)


def cmd_help(args: Any, ctx: AgentContext, console: Console):
    """print all available commands"""
    title = "Available Commands"
    cmd_str = Text()
    for cmd, (func, label, desc) in BUILTIN_COMMANDS.items():
        cmd_str.append(f"/{cmd}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        cmd_str.append(f"{label}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", {desc}\n", style=f"white")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_query_design(args: Any, ctx: AgentContext, console: Console):
    """query the list of current designs"""
    cmd_str = Text()
    cmd_str.append("query_design", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f":\n    total design num: ", style=f"white")
    cmd_str.append(f"{len(ctx.design_created)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f", list of design id: ", style=f"white")
    cmd_str.append(f"{ctx.design_created}", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_query_run(args: Any, ctx: AgentContext, console: Console):
    """query the amount of launched simulation"""
    cmd_str = Text()
    cmd_str.append("query_run", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f":\n    total launched run: ", style=f"white")
    cmd_str.append(f"{ctx.simulation_launched}", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_context(args: Any, ctx: AgentContext, console: Console):
    """query the token usage, message and API requests statistics"""
    title = "TECoSim Agent Context Usage"
    if ctx.total_input_tokens <= 0:
        uncached_rate = 100
    else:
        uncached_rate = 100 * ctx.total_uncached_tokens / ctx.total_input_tokens
    if ctx.api_configs["MODEL_CONTEXT"] <= 0:
        ctx_usage = 100
    else:
        ctx_usage = 100 * ctx.last_input_tokens / ctx.api_configs["MODEL_CONTEXT"]
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
    cmd_str.append(f"{uncached_rate} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", cached: \n", style=f"white")
    cmd_str.append(f"{100 - uncached_rate} %\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total tokens consumption of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue input tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue output tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.last_output_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue total tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.last_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("LLM API context usage based (last dialogue) of this session: ", style=f"white")
    cmd_str.append(f"{ctx_usage} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" out of ", style=f"white")
    cmd_str.append(f"{ctx.api_configs["MODEL_CONTEXT"] / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" were used\n", style=f"white")

    cmd_str.append("\nTotal LLM API request num: ", style=f"white")
    cmd_str.append(f"{ctx.total_llm_requests}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total messages num: ", style=f"white")
    cmd_str.append(f"{len(ctx.messages)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("System prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.system_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tools prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.tools_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("User prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.user_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant content prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.content_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant reasoning content prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.reasoning_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant tool calls prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.tool_calls_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tool results prompts num: ", style=f"white")
    cmd_str.append(f"{ctx.tool_results_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_query_fread(args: Any, ctx: AgentContext, console: Console):
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


def cmd_permission_list(args: Any, ctx: AgentContext, console: Console):
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
    cmd_str.append(f"\nYou can also toggle the permission config with following command: \n", style=f"white")
    cmd_str.append(f"    /permission_toggle ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f"[NAME OF PERMISSION]", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f" (Swap ", style=f"white")
    cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f" and ", style=f"white")
    cmd_str.append(f"False", style=f"bright_black")
    cmd_str.append(f")\n", style=f"white")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_permission_toggle(args: Any, ctx: AgentContext, console: Console):
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
        arg_name = str(args[0])
    except Exception as e:
        sys_log.warning(f"Unable to toggle the permission, target name is invalid with error {e}")
        console.print(f"Unable to toggle the permission, target name is invalid with error {e}", style=f"bold yellow")
        return

    for name, token in ctx.permissions.items():
        if arg_name == name:
            ctx.permissions[name] = not token
            cmd_str.append(f"Permission ", style=f"white")
            cmd_str.append(f"{name}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f" toggled from ", style=f"white")
            cmd_str.append(f"{"True" if token else "False"}", style=f"bold {MAJOR_COLOR1}" if token else f"bright_black")
            cmd_str.append(f" to ", style=f"white")
            cmd_str.append(f"{"False" if token else "True"}", style=f"bright_black" if token else f"bold {MAJOR_COLOR1}")
            cmd_str.append(f" successfully", style=f"white")
            console.print(cmd_str)
            return
    sys_log.warning(f"Unknown permission name {arg_name}, toggle failed")
    console.print(f"Unknown permission name {arg_name}, toggle failed", style=f"bold yellow")


"""builtin cmd definitions"""
BUILTIN_COMMANDS = {
    "help": (cmd_help, "help info", "print all available builtin commands"),
    "query_design": (cmd_query_design, "list designs", "query the list of current designs"),
    "query_run": (cmd_query_run, "list runs", "query the amount of launched simulation"),
    "context": (cmd_context, "query context info", "query the token usage, message and API requests statistics"),
    "query_fread": (cmd_query_fread, "query all read files", "query the absolute paths of all read files"),
    "permission_list": (cmd_permission_list, "query permission info",
                        "query the configs of always-allowed-configurable tool calls permission token"),
    "permission_toggle": (cmd_permission_toggle, "toggle the permission with given name",
                        "toggle the permission token of the tool calls permission with given name"),
}


def execute_cmd(cmd: str, args: list[str], ctx: AgentContext, console: Console):
    """execute builtin command"""
    if cmd == BUILTIN_UNKNOWN:
        sys_log.debug("Unknown command called, nothing happen")
        cmd_unknown(console)
    else:
        sys_log.debug(f"Command call: {cmd} with args {args} start")
        BUILTIN_COMMANDS[cmd][0](args, ctx, console)
        sys_log.debug(f"Command call: {cmd} done")
