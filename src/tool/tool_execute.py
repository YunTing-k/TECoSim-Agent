# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.14
Description: Tools execution for TECoSim agent

Revision:
---------
2026.4.14      Yu Huang      1.0      First implementation
2026.4.16      Yu Huang      1.1      Agent context realization with logic merge
2026.4.19      Yu Huang      1.2      tools of init/copy/query design, launch simulator, query run, read logs, general read/write file
2026.4.22      Yu Huang      1.3      Bash support
2026.4.25-26   Yu Huang      1.4      Ask user support
2026.5.13      Yu Huang      1.5      Edit file support
2026.5.15      Yu Huang      1.6      Agent skills support
2026.5.19      Yu Huang      1.7      Webpage fetch support & fix non-ASCII results dump bug
2026.5.20      Yu Huang      1.8      Web search support
2026.5.21      Yu Huang      1.9      Agent MCPs support
2026.5.27      Yu Huang      2.0      Glob and grep file support
2026.5.30      Yu Huang      2.1      Random spinner title support & Revise spinner logic with SIGINT pass through
2026.6.1       Yu Huang      2.2      Define all used status labels in constants.py
2026.6.3       Yu Huang      2.3      Add cron tasks support
2026.6.6       Yu Huang      2.4      Basic support of agent tasks as Scoreboard with lock
2026.6.7       Yu Huang      2.5      Support of task displays in scoreboard
2026.6.9       Yu Huang      2.6      Add design and run support for simulator

Details:
---------
Tool execution dispatcher. `execute_tools()` routes LLM tool-call requests to the appropriate handler in `tool_def.py` via
a name-based dispatch chain, collects results as tool-role messages, and handles skill content as user-addon messages.
Integrates with Scoreboard for task management (create/update/query) during execution. Wrapped with spinner UI displaying
task progress and interrupt support.
"""
import json
import random
import logging

from typing import Callable, Any
from rich.progress import Progress
from src.tool import tool_def
from src.utility.ui_info import loading_spinner, loading_spinner_with_board
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.constants import *

sys_log = logging.getLogger('logger')


class ToolCallsCancelled(Exception):
    """Raised when user cancels tool calls (but this should never happen, because each tool should handle Ctrl+C int)"""


def tool_calls_spinner(func: Callable, *args,
                       waiting_desc: str | None = None, done_desc: str | None = None,
                       intrp_desc: str | None = None, fail_desc: str | None = None,
                       spinner: str | None = None, if_random: bool, **kwargs) -> Any:
    """Tool calls with spinner through loading_spinner"""
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
    result = loading_spinner(func, *args,
                             waiting_desc=waiting_title, done_desc=done_title,
                             intrp_desc=intrp_title, fail_desc=fail_title,
                             spinner=spinner_choice,
                             out_except=ToolCallsCancelled("Tool call is cancelled by user"),
                             with_progress=True,  # add progress to target function
                             **kwargs)
    return result


def tool_calls_spinner_board(func: Callable, *args,
                             board: Scoreboard,
                             waiting_desc: str | None = None, done_desc: str | None = None,
                             intrp_desc: str | None = None, fail_desc: str | None = None,
                             spinner: str | None = None, if_random: bool, **kwargs) -> Any:
    """Tool calls with spinner and scoreboard through loading_spinner_with_board"""
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
    result = loading_spinner_with_board(func, *args,
                                        board=board,
                                        waiting_desc=waiting_title, done_desc=done_title,
                                        intrp_desc=intrp_title, fail_desc=fail_title,
                                        spinner=spinner_choice,
                                        out_except=ToolCallsCancelled("Tool call is cancelled by user"),
                                        with_progress=True,  # add progress to target function
                                        **kwargs)
    return result


def if_tool_mute(func_name: str) -> bool:
    """check if tool is muted"""
    if MUTE_TASK_OP_INFO:
        if func_name in (TOOL_NAME_CREATE_TASK, TOOL_NAME_UPDATE_TASK, TOOL_NAME_QUERY_TASK):
            return True
    return False


def execute_tools(tool_calls: list[dict[str, Any]], ctx: AgentContext, board: Scoreboard, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls with AgentContext"""
    messages = []
    for tool_call in tool_calls:
        func_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        sys_log.debug(f"Using tool: {func_name}")
        if not if_tool_mute(func_name):
            progress.console.print(f"Using tool: [{MAJOR_COLOR1}]{func_name}[/{MAJOR_COLOR1}]", style="bright_black")
        [results, user_addons] = call_tools(func_name, arguments, ctx, board, progress)
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


def call_tools(func_name: str, arguments: dict[str, Any], ctx: AgentContext, board: Scoreboard, progress: Progress)\
        -> tuple[dict[str, Any], dict[str, Any] | None]:
    """actual top tools call with func name, arguments and AgentContext"""
    try:
        if func_name == TOOL_NAME_VERSION:
            results = tool_def.agent_version(progress)
            user_addons = None
        elif func_name == TOOL_NAME_ASK_QUESTION:
            results = tool_def.ask_user_question(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_CREATE_TASK:
            results = tool_def.create_task(arguments, board, progress)
            user_addons = None
        elif func_name == TOOL_NAME_UPDATE_TASK:
            results = tool_def.update_task(arguments, ctx, board, progress)
            user_addons = None
        elif func_name == TOOL_NAME_QUERY_TASK:
            results = tool_def.query_task(arguments, ctx, board, progress)
            user_addons = None
        elif func_name == TOOL_NAME_CREATE_CRON:
            results = tool_def.create_cron(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_QUERY_CRON:
            results = tool_def.query_cron(ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_REMOVE_CRON:
            results = tool_def.remove_cron(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_BASH:
            results = tool_def.bash(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_GLOB_FILE:
            results = tool_def.glob_file(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_GREP_FILE:
            results = tool_def.grep_file(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_READ_FILE:
            results = tool_def.read_file(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_WRITE_FILE:
            results = tool_def.write_file(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_EDIT_FILE:
            results = tool_def.edit_file(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_SKILL:
            results, user_addons = tool_def.skill(arguments, ctx, progress)
        elif func_name == TOOL_NAME_WEB_FETCH:
            results = tool_def.web_fetch(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_WEB_SEARCH:
            results = tool_def.web_search(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_CHECK_SIMULATOR:
            results = tool_def.check_simulator(ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_INIT_DESIGN:
            results = tool_def.init_design(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_QUERY_DESIGN:
            results = tool_def.query_design(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_LAUNCH_SIM:
            results = tool_def.launch_sim(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_QUERY_RUN:
            results = tool_def.query_run(arguments, ctx, progress)
            user_addons = None
        elif func_name == TOOL_NAME_READ_LOG:
            results = tool_def.read_log(arguments, ctx, progress)
            user_addons = None
        elif func_name in ctx.mcp_router.tool_registry:
            results = tool_def.call_mcp(func_name, arguments, ctx, progress)
            user_addons = None
        else:
            sys_log.warning(f"Tool: {func_name} is undefined")
            progress.console.print(f"Tool: {func_name} is undefined\r", style="bold yellow")
            results = {"status": FAIL_LABEL, "info": f"Tool: {func_name} is undefined"}
            user_addons = None
        return results, user_addons
    except Exception as e:
        sys_log.error(f"Tool {func_name} execution failed with error: {e}")
        progress.console.print(f"Tool {func_name} execution failed with error: {e}\r", style="bold red")
        results = {"status": FAIL_LABEL, "info": f"Tool {func_name} execution failed with error: {e}"}
        return results, None
