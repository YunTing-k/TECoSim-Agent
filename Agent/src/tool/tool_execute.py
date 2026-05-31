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
2026.4.25-26   Yu Huang     1.4               Ask user support\n
2026.5.13      Yu Huang     1.5               Edit file support\n
2026.5.15      Yu Huang     1.6               Agent skills support\n
2026.5.19      Yu Huang     1.7               Webpage fetch support & fix non-ASCII results dump bug\n
2026.5.20      Yu Huang     1.8               Web search support\n
2026.5.21      Yu Huang     1.9               Agent MCPs support\n
2026.5.27      Yu Huang     2.0               Glob and grep file support\n
2026.5.30      Yu Huang     2.1               Random spinner title support & Revise spinner logic with SIGINT pass through\n

Details:
Execution of tools that TECoSim agent can call
------------------------------------------------------------------------------------------------------------------------
"""
import json
import random
import logging

from typing import Callable, Any
from rich.progress import Progress
from src.tool import tool_def
from src.utility.ui_info import loading_spinner_rap
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


class ToolCallsCancelled(Exception):
    """Raised when user cancels tool calls (but this should never happen, because each tool should handle Ctrl+C int)"""


def tool_calls_with_spinner(func: Callable, *args,
                             waiting_desc: str | None = None, done_desc: str | None = None,
                             intrp_desc: str | None = None, fail_desc: str | None = None,
                             spinner: str | None = None, if_random: bool, **kwargs) -> Any:
    """Tool calls with spinner through loading_spinner_rap"""
    if waiting_desc is not None:
        waiting_title = waiting_desc
    else:
        if if_random:
            waiting_title = random.choice(TOOLS_EXECUTION_TITLE_LIST)
        else:
            waiting_title = TOOLS_EXECUTION_TITLE_LIST[0]
    if done_desc is not None:
        done_title = done_desc
    else:
        done_title = TOOLS_EXECUTION_DONE_TITLE
    if intrp_desc is not None:
        intrp_title = intrp_desc
    else:
        intrp_title = TOOLS_EXECUTION_INTRP_TITLE
    if fail_desc is not None:
        fail_title = fail_desc
    else:
        fail_title = TOOLS_EXECUTION_FAIL_TITLE
    if spinner is not None:
        spinner_choice = spinner
    else:
        spinner_choice = TOOLS_EXECUTION_SPINNER
    result = loading_spinner_rap(func, *args,
                                 waiting_desc=waiting_title, done_desc=done_title,
                                 intrp_desc=intrp_title, fail_desc=fail_title,
                                 spinner=spinner_choice,
                                 out_except=ToolCallsCancelled("Tool call is cancelled by user"),
                                 with_progress=True,  # add progress to target function
                                 **kwargs)
    return result


def execute_tools(tool_calls: list[dict[str, Any]], ctx: AgentContext, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls with AgentContext"""
    messages = []
    for tool_call in tool_calls:
        func_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        sys_log.debug(f"Using tool: {func_name}")
        progress.console.print(f"Using tool: [{MAJOR_COLOR1}]{func_name}[/{MAJOR_COLOR1}]", style="bright_black")
        [results, user_addons] = call_tools(func_name, arguments, ctx, progress)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(results, ensure_ascii=False),
        })
        if user_addons is not None:
            messages.append({
                "role": "user",
                "content": json.dumps(user_addons, ensure_ascii=False),
            })
    return messages


def call_tools(func_name: str, arguments: dict[str, Any], ctx: AgentContext, progress: Progress)\
        -> tuple[dict[str, Any], dict[str, Any] | None]:
    """actual top tools call with func name, arguments and AgentContext"""
    try:
        if func_name.lower() == "agent_version":
            results = tool_def.agent_version(progress)
            user_addons = None
        elif func_name.lower() == "ask_user_question":
            results = tool_def.ask_user_question(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "bash":
            results = tool_def.bash(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "glob_file":
            results = tool_def.glob_file(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "grep_file":
            results = tool_def.grep_file(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "read_file":
            results = tool_def.read_file(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "write_file":
            results = tool_def.write_file(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "edit_file":
            results = tool_def.edit_file(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "skill":
            results, user_addons = tool_def.skill(arguments, ctx, progress)
        elif func_name.lower() == "web_fetch":
            results = tool_def.web_fetch(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "web_search":
            results = tool_def.web_search(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "check_simulator":
            results = tool_def.check_simulator(ctx, progress)
            user_addons = None
        elif func_name.lower() == "init_design":
            results = tool_def.init_design(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "copy_design":
            results = tool_def.copy_design(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "query_design_list":
            results = tool_def.query_design_list(ctx, progress)
            user_addons = None
        elif func_name.lower() == "launch_simulator":
            results = tool_def.launch_simulator(arguments, ctx, progress)
            user_addons = None
        elif func_name.lower() == "query_run_num":
            results = tool_def.query_run_num(ctx, progress)
            user_addons = None
        elif func_name.lower() == "read_log":
            results = tool_def.read_log(arguments, ctx, progress)
            user_addons = None
        elif func_name in ctx.mcp_router.tool_registry:
            results = tool_def.call_mcp(func_name, arguments, ctx, progress)
            user_addons = None
        else:
            sys_log.warning(f"Tool: {func_name} is undefined")
            progress.console.print(f"Tool: {func_name} is undefined\r", style="bold yellow")
            results = {"status": "FAIL", "info": f"Tool: {func_name} is undefined"}
            user_addons = None
        return results, user_addons
    except Exception as e:
        sys_log.error(f"Tool {func_name} execution failed with error: {e}")
        progress.console.print(f"Tool {func_name} execution failed with error: {e}\r", style="bold red")
        results = {"status": "FAIL", "info": f"Tool {func_name} execution failed with error: {e}"}
        return results, None
