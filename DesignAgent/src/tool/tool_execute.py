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
from rich.console import Console
from rich.progress import Progress
from src.constants import *

sys_log = logging.getLogger('logger')


def execute_tools(tool_calls, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls"""
    messages = []
    for tool_call in tool_calls:
        func_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        sys_log.debug(f"Using tool: {func_name}")
        progress.console.print(f"[bright_black]Using tool: {func_name}[/bright_black]")
        results = call_tools(func_name, arguments, progress)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": results,
        })
    return messages


def call_tools(func_name: str, arguments: dict[str, Any], progress: Progress) -> Any:
    """actual top tools call"""
    if func_name == "get_agent_version":
        results = tool_def.get_agent_version()
    else:
        sys_log.warning(f"Undefined tool: {func_name}")
        progress.console.print(f"[bold_yellow]Undefined tool: {func_name}[/bold_yellow]\r")
        results = f"Undefined tool: {func_name}"
    return results
