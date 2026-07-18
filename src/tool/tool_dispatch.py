# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.12
Description: Tool call dispatch for TECoSim agent

Revision:
---------
2026.6.12      Yu Huang      1.0      First implementation
2026.7.15-16   Yu Huang      1.1      Add WeChat bot interaction support
2026.7.18      Yu Huang      1.2      Add tool of checking WeChat status

Details:
---------
Name-based tool dispatch mapping (call_tools) and ToolCallsCancelled exception. Extracted from tool_execute.py to break
circular imports with subagent.py.
"""
import logging

from typing import Any
from rich.progress import Progress
from src.context.agent_context import AgentContext
from src.tool import tool_def
from src.tool.scoreboard import Scoreboard
from src.constants import *

sys_log = logging.getLogger('logger')


class ToolCallsCancelled(Exception):
    """Raised when user cancels tool calls (but this should never happen, because each tool should handle Ctrl+C int)"""


def if_tool_mute(func_name: str) -> bool:
    """check if tool is muted"""
    if MUTE_TASK_OP_INFO:
        if func_name in (TOOL_NAME_CREATE_TASK, TOOL_NAME_UPDATE_TASK, TOOL_NAME_QUERY_TASK):
            return True
    return False


def call_tools(func_name: str, arguments: dict[str, Any], ctx: AgentContext, board: Scoreboard, progress: Progress)\
        -> tuple[dict[str, Any], dict[str, Any] | None]:
    """actual top tools call with func name, arguments and AgentContext"""
    try:
        if func_name == TOOL_NAME_VERSION:
            results = tool_def.agent_version(progress)
            user_addon = None
        elif func_name == TOOL_NAME_ASK_QUESTION:
            results = tool_def.ask_user_question(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_CREATE_TASK:
            results = tool_def.create_task(arguments, board, progress)
            user_addon = None
        elif func_name == TOOL_NAME_UPDATE_TASK:
            results = tool_def.update_task(arguments, ctx, board, progress)
            user_addon = None
        elif func_name == TOOL_NAME_QUERY_TASK:
            results = tool_def.query_task(arguments, ctx, board, progress)
            user_addon = None
        elif func_name == TOOL_NAME_CREATE_CRON:
            results = tool_def.create_cron(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_QUERY_CRON:
            results = tool_def.query_cron(ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_REMOVE_CRON:
            results = tool_def.remove_cron(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_BASH:
            results = tool_def.bash(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_GLOB_FILE:
            results = tool_def.glob_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_GREP_FILE:
            results = tool_def.grep_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_READ_FILE:
            results = tool_def.read_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_WRITE_FILE:
            results = tool_def.write_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_EDIT_FILE:
            results = tool_def.edit_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_SKILL:
            results, user_addon = tool_def.skill(arguments, ctx, progress)
        elif func_name == TOOL_NAME_WEB_FETCH:
            results = tool_def.web_fetch(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_WEB_SEARCH:
            results = tool_def.web_search(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_WECHAT_STATUS:
            results = tool_def.wechat_status(ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_WECHAT_SEND_FILE:
            results = tool_def.wechat_send_file(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_CHECK_SIMULATOR:
            results = tool_def.check_simulator(ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_INIT_DESIGN:
            results = tool_def.init_design(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_QUERY_DESIGN:
            results = tool_def.query_design(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_LAUNCH_SIM:
            results = tool_def.launch_sim(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_QUERY_RUN:
            results = tool_def.query_run(arguments, ctx, progress)
            user_addon = None
        elif func_name == TOOL_NAME_READ_LOG:
            results = tool_def.read_log(arguments, ctx, progress)
            user_addon = None
        elif func_name in ctx.mcp_router.tool_registry:
            results = tool_def.call_mcp(func_name, arguments, ctx, progress)
            user_addon = None
        else:
            sys_log.warning(f"Tool: {func_name} is undefined")
            progress.console.print(f"Tool: {func_name} is undefined", style="bold yellow")
            results = {"status": FAIL_LABEL, "info": f"Tool: {func_name} is undefined"}
            user_addon = None
        return results, user_addon
    except Exception as e:
        sys_log.error(f"Tool {func_name} execution failed with error: {e}")
        progress.console.print(f"Tool {func_name} execution failed with error: {e}", style="bold red")
        results = {"status": FAIL_LABEL, "info": f"Tool {func_name} execution failed with error: {e}"}
        return results, None
