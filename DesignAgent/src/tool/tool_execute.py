# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.14\n
Description: Tools execution for TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.14      Yu Huang     1.0               First implementation\n
2026.4.16      Yu Huang     1.1               Agent context realization with logic merge\n
2026.4.19      Yu Huang     1.2               tools of init/copy/query design, launch simulator, query run, read logs,
                                              general read/write file\n
2026.4.22      Yu Huang     1.3               Bash support\n

Details:
Tools execution of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import json
import subprocess
import logging
import time

from src.tool import tool_def
from typing import Dict, Any
from src.context.session import AgentContext
from rich.console import Console
from rich.progress import Progress
from src.constants import *

sys_log = logging.getLogger('logger')


def execute_tools(tool_calls, ctx: AgentContext, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls with AgentContext"""
    messages = []
    for tool_call in tool_calls:
        func_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        sys_log.debug(f"Using tool: {func_name}")
        progress.console.print(f"[bright_black]Using tool: {func_name}[/bright_black]")
        results = call_tools(func_name, arguments, ctx, progress)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(results),
        })
    return messages


def call_tools(func_name: str, arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """actual top tools call with func name, arguments and AgentContext"""
    try:
        if func_name == "get_agent_version":
            results = tool_def.get_agent_version(progress)
        elif func_name == "check_simulator":
            results = tool_def.check_simulator(ctx, progress)
        elif func_name == "init_design":
            results = tool_def.init_design(arguments, ctx, progress)
        elif func_name == "copy_design":
            results = tool_def.copy_design(arguments, ctx, progress)
        elif func_name == "query_design_list":
            results = tool_def.query_design_list(ctx, progress)
        elif func_name == "launch_simulator":
            results = tool_def.launch_simulator(arguments, ctx, progress)
        elif func_name == "query_run_num":
            results = tool_def.query_run_num(ctx, progress)
        elif func_name == "read_log":
            results = tool_def.read_log(arguments, ctx, progress)
        elif func_name == "read_file":
            results = tool_def.read_file(arguments, ctx, progress)
        elif func_name == "write_file":
            results = tool_def.write_file(arguments, progress)
        elif func_name == "bash":
            results = tool_def.bash(arguments, progress)
        else:
            sys_log.warning(f"Undefined tool: {func_name}")
            progress.console.print(f"[bold_yellow]Undefined tool: {func_name}[/bold_yellow]\r")
            results = {"status": "FAIL", "info": f"Undefined tool: {func_name}"}
        return results
    except Exception as e:
        sys_log.error(f"Tool {func_name} execution failed with error: {e}")
        progress.console.print(f"[bold_red]Tool {func_name} execution failed with error: {e}[/bold_red]\r")
        results = {"status": "FAIL", "info": f"Tool {func_name} execution failed with error: {e}"}
        return results
