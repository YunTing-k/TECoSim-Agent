# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.14
Description: Agent tools for TECoSim agent

Revision:
---------
2026.4.14      Yu Huang      1.0      First implementation
2026.4.16      Yu Huang      1.1      Agent context realization with logic merge
2026.4.19      Yu Huang      1.2      tools of init/copy/query design, launch simulator, query run, read logs, general read/write file
2026.4.22      Yu Huang      1.3      Bash support
2026.4.25-26   Yu Huang      1.4      Ask user support
2026.4.28      Yu Huang      1.5      Permission request & Exit TUI support
2026.4.29      Yu Huang      1.6      Builtin commands support
2026.5.12      Yu Huang      1.7      Move bash support to bash_support.py
2026.5.12      Yu Huang      1.8      Edit file support
2026.5.13      Yu Huang      1.9      Read file with truncation
2026.5.14      Yu Huang      2.0      Move read lines/logs methods to file_io_support.py & revise tool defs
2026.5.15      Yu Huang      2.1      Agent skills support
2026.5.19      Yu Huang      2.2      Webpage fetch support
2026.5.20      Yu Huang      2.3      Web search support & Interrupt support for web fetch/search
2026.5.21-22   Yu Huang      2.4      Agent MCPs support & Revise tools prompts of read_file and skills
2026.5.27      Yu Huang      2.5      Glob and grep file support & Add terminate subprocess when exception
2026.5.28      Yu Huang      2.6      Add read-only paths support & Truncate bash command view if it is too long
2026.5.29      Yu Huang      2.7      Add toggle of if stop live progress
2026.5.31      Yu Huang      2.8      Define default params of all tools in constants.py & Define used file/dir. paths in constants.py
2026.6.1       Yu Huang      2.9      Define all used status labels in constants.py
2026.6.2       Yu Huang      3.0      All function names referred in log are defined as param
2026.6.3       Yu Huang      3.1      Add cron tasks support
2026.6.4       Yu Huang      3.2      Add support of comment when user deny permission request
2026.6.4       Yu Huang      3.3      Normalize old/new strings for CRLF and quote marks handling & add debug info on edit_file
                                      match failure & Fix the bug of encoding in bash tool & Manage all agent tools' names in constants.py
2026.6.5       Yu Huang      3.4      Add --nosystem, --notools, --nocrons support & Revise tools prompts of skill & Render bash
                                      command as Markdown support & Bugfix of submit action in all ask permission TUIs
2026.6.6       Yu Huang      3.5      Basic support of agent tasks as Scoreboard with lock
2026.6.7       Yu Huang      3.6      Add scoreboard display in tool execute spinner & Add fallback if bash encounter encoding error
2026.6.8       Yu Huang      3.7      Bash and ripgrep path configurable support
2026.6.9       Yu Huang      3.8      Add design and run support for simulator & Merge task get/list into task query & Revise the prompts
                                      of task tools & Revise the prompts simulation tools

Details:
---------
Tool definitions (OpenAI function-calling schema) and their realizations for all 25+ agent tools. Organized as: (1) basic
tools - ask user question, cron (create/query/remove), bash (with permission/per-subprocess/risk-eval), glob/grep,
read/write/edit file, skill, web fetch/search; (2) task tools - create/update/query task via Scoreboard with dependency
tracking; (3) simulation tools - check simulator, init/copy/query design, launch sim, query run, read log;
(4) MCP tool dispatch via TOOL_NAME_CALL_MCP. Each tool handles permission TUI, logging, and error reporting.
"""
import os
import subprocess
import logging
import tempfile

from typing import Any
from datetime import datetime
from rich.progress import Progress
from src.utility import ui_info
from src.utility.ui_info import pause_for_permission, resume_from_permission
from src.utility.basic_utils import read_line_with_limit
from src.context.agent_context import WebFetchCancelled, WebSearchCancelled, AgentContext
from src.tool.cron_support import get_cron_list, create_cron_impl
from src.tool.scoreboard import Scoreboard, args_to_taskupdate, task_to_info, tasks_to_info
from src.tool.file_filter_support import glob_impl, grep_impl
from src.tool.file_io_support import (
    match_line_ranges, get_match_debug_info, find_actual_string, ask_edit_tui, check_read_only)
from src.tool.simulator_support import (
    init_design_impl, launch_sim_impl, runs_to_info, run_to_info, read_log_impl, design_to_info, designs_to_info)
from src.tool.skills_support import load_skill_content, get_skill_description
from src.tool.web_support import check_url, web_single_fetch, web_fetch_process
from src.tool.web_support import web_search_top, web_search_process
from src.tool.ask_permission import ask_permission_tui
from src.tool.bash_support import evaluate_bash_risk, get_bash_render
from src.tool.ask_question import ask_user_question_tui, AskUserCancelled
from src.constants import *

sys_log = logging.getLogger('logger')


def create_tools_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """create prompts of all available tools"""
    # Agent tools
    prompts: list[dict[str, Any]] = [
        # basic tools
        tool_ask_user_question_def(),
        tool_create_task_def(),
        tool_update_task_def(),
        tool_query_task_def(),
        tool_create_cron_def(),
        tool_query_cron_def(),
        tool_remove_cron_def(),
        tool_bash_def(),
        tool_glob_file_def(),
        tool_grep_file_def(),
        tool_read_file_def(),
        tool_write_file_def(),
        tool_edit_file_def(),
        tool_skill_def(),
        tool_web_fetch_def(),
        tool_web_search_def(),
        # simulation tools
        tool_check_simulator_def(),
        tool_init_design_def(),
        tool_query_design_def(),
        tool_launch_sim_def(),
        tool_query_run_def(),
        tool_read_log_def(),
    ]
    # MCP tools
    prompts.extend(ctx.mcp_router.reg_tools)

    tool_num = len(prompts)
    ctx.tools_prompts = tool_num
    sys_log.debug(f"{tool_num} tools prompts assembled")
    return prompts


def tool_get_agent_version_def() -> dict[str, Any]:
    """tool definition of getting current version of TECoSim Agent ({TOOL_NAME_VERSION})"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_VERSION,
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


def agent_version(progress: Progress) -> dict[str, Any]:
    """tool realization of getting the dev version of TECoSim agent"""
    func_name = TOOL_NAME_VERSION
    sys_log.debug(f"{func_name} {SUCCESS_LABEL}: "
                  f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}")
    progress.console.print(f"{func_name} {SUCCESS_LABEL}: "
                           f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}",
                           style="bright_black")
    return {"status": SUCCESS_LABEL,
            "version": f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"}


def tool_ask_user_question_def() -> dict[str, Any]:
    """tool definition of asking structured questions to the user (TOOL_NAME_ASK_QUESTION)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_ASK_QUESTION,
            "description": "Use this tool to ask the user questions when you need. This allows you to:\n"
                           "1. Gather user preferences or requirements\n"
                           "2. Clarify ambiguous instructions\n"
                           "3. Get decisions on implementation choices as you work\n"
                           "4. Offer choices to the user about what direction to take.\n"
                           "Usage notes:\n"
                           f"- User will always be able to select option named \"{QUESTION_OTHER_LABEL}\" to provide custom "
                           f"text input under each question. That option will be provided automatically. You should not "
                           f"provide that option or similar one\n"
                           f"- Use `multi_select`: true to allow multiple answers to be selected for a question\n"
                           f"- If you recommend a specific option, make that the first option in the list and add \"({QUESTION_RECOMMEND_LABEL})\" "
                           f"at the end of the label\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": ASK_USER_QUESTION_MIN_QUESTION,
                        "maxItems": ASK_USER_QUESTION_MAX_QUESTION,
                        "description": f"Questions to ask the user ({ASK_USER_QUESTION_MIN_QUESTION}-{ASK_USER_QUESTION_MAX_QUESTION} questions).",
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
                                    "minItems": ASK_USER_QUESTION_MIN_OPTION,
                                    "maxItems": ASK_USER_QUESTION_MAX_OPTION,
                                    "description": f"The available options for this question. Must have "
                                                   f"{ASK_USER_QUESTION_MIN_OPTION}-{ASK_USER_QUESTION_MAX_OPTION} options. "
                                                   f"Each option should be a distinct, mutually exclusive choice (unless "
                                                   f"`multi_select` is enabled). There should be no \"{QUESTION_OTHER_LABEL}\" option "
                                                   f"or similar one, that will be provided automatically.",
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
    func_name = TOOL_NAME_ASK_QUESTION
    try:
        questions = arguments.get("questions", [])
        if len(questions) == 0:
            sys_log.error(f"{func_name} {FAIL_LABEL}: questions is empty")
            progress.console.print(f"{func_name} {FAIL_LABEL}: questions is empty", style="bold red")
            return {"status": FAIL_LABEL, "info": "questions is empty"}
        if ctx.agent_session is None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: agent session is unavailable")
            progress.console.print(f"{func_name} {FAIL_LABEL}: agent session is unavailable", style="bold red")
            return {"status": FAIL_LABEL, "info": "agent session is unavailable"}
        for idx, question in enumerate(questions, start=1):
            options = question.get("options", [])
            if len(options) == 0:
                sys_log.error(f"{func_name} {FAIL_LABEL}: question {idx} has no options "
                              f"({ASK_USER_QUESTION_MIN_OPTION}-{ASK_USER_QUESTION_MAX_OPTION} options exclude {QUESTION_OTHER_LABEL} "
                              f"are needed)")
                progress.console.print(f"{func_name} {FAIL_LABEL}: question {idx} has no options "
                                       f"({ASK_USER_QUESTION_MIN_OPTION}-{ASK_USER_QUESTION_MAX_OPTION} options exclude "
                                       f"{QUESTION_OTHER_LABEL} are needed)", style="bold red")
                return {"status": FAIL_LABEL, "info": f"question {idx} has no options"}
        sys_log.debug(f"{func_name}: waiting for user selection")
        pause_for_permission(progress)
        try:
            answers = ask_user_question_tui(questions, progress.console, ctx.agent_session)
        finally:
            resume_from_permission(progress)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: {len(answers)} answers collected")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: {len(answers)} answers collected", style="bright_black")
        return {
            "status": SUCCESS_LABEL,
            "answers": answers,
            "info": f"Collected {len(answers)} answers from user"
        }
    except AskUserCancelled:
        sys_log.warning(f"{func_name} {CANCELLED_LABEL}: user cancelled the response to the question")
        progress.console.print(f"{func_name} {CANCELLED_LABEL}: user cancelled the response to the question", style="bold yellow")
        return {"status": CANCELLED_LABEL, "info": "user cancelled the response to the question"}
    except KeyboardInterrupt:
        sys_log.warning(f"{func_name} {CANCELLED_LABEL}: user cancelled the response to the question")
        progress.console.print(f"{func_name} {CANCELLED_LABEL}: user cancelled the response to the question", style="bold yellow")
        return {"status": CANCELLED_LABEL, "info": "user cancelled the response to the question"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Ask user question failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Ask user question failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Ask user question failed with error: {e}"}


def tool_create_task_def() -> dict[str, Any]:
    """tool definition of creating a task (TOOL_NAME_CREATE_TASK)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_CREATE_TASK,
            "description": "Use this tool to create a structured task list for current session. This helps you track progress, "
                           "organize complex tasks, cooperation in agent teams, and demonstrate thoroughness to the user.\n"
                           "It also helps the user understand the progress of the task and overall progress of their requests.\n\n"
                           "## Task Fields\n\n"
                           "- `subject`: A brief, actionable title in imperative form (e.g., \"Fix authentication bug "
                           "in login flow\")\n"
                           "- `description`: What needs to be done\n"
                           f"All tasks are created with status `{TASK_PENDING_LABEL}` and a unique integer task id.\n\n"
                           "## Usage\n\n"
                           "- After receiving new instructions, immediately capture user requirements as tasks\n"
                           f"- Use `{TOOL_NAME_QUERY_TASK}` first to avoid creating duplicate tasks\n"
                           "- Create tasks with clear, specific subjects that describe the outcome\n"
                           f"- After creating tasks, use `{TOOL_NAME_UPDATE_TASK}` to set up dependencies (`add_blocks` / "
                           f"`add_blocked_by`) if needed\n"
                           f"- When you start working on a task, use `{TOOL_NAME_UPDATE_TASK}` to mark it as `{TASK_IN_PROGRESS_LABEL}` "
                           f"BEFORE beginning work\n"
                           f"- After completing a task, use `{TOOL_NAME_UPDATE_TASK}` to mark it as `{TASK_COMPLETED_LABEL}` "
                           f"and add any new follow-up tasks discovered during implementation\n"
                           "## When to Use This Tool\n\n"
                           "Use this tool proactively in these scenarios:\n\n"
                           "- Complex multi-step tasks "
                           "- When a task requires 3 or more distinct steps or actions\n"
                           "- Non-trivial and complex tasks: Tasks that require careful planning or multiple operations\n"
                           "- User explicitly requests todo list: When the user directly asks you to use the todo list\n"
                           "- User provides multiple tasks: When user provides a list of things to be done (numbered or "
                           "comma-separated)\n"
                           "A good rule of thumb: each task should represent a meaningful milestone "
                           "(e.g. \"Collect data\"), not individual tool calls (e.g. \"Read file A\").\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "A brief title for the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What needs to be done.",
                    },
                },
                "required": ["subject", "description"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def create_task(arguments: dict[str, Any], board: Scoreboard, progress: Progress) -> dict[str, Any]:
    """tool realization of creating a task with arguments"""
    func_name = TOOL_NAME_CREATE_TASK
    try:
        subject = str(arguments["subject"])
        description = str(arguments["description"])
        """creat task"""
        if_success, create_info = board.create_task(subject, description)
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Create task success with info: {create_info}")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: Create task success with info: {create_info}",
                                       style="bright_black")
            return {"status": SUCCESS_LABEL, "info": create_info}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Create task failed with error, details: {create_info}")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {FAIL_LABEL}: Create task failed with error, details: {create_info}",
                                       style="bold red")
            return {"status": FAIL_LABEL, "info": f"Create task failed with error, details: {create_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Create task failed with error: {e}")
        if not MUTE_TASK_OP_INFO:
            progress.console.print(f"{func_name} {FAIL_LABEL}: Create task failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Create task failed with error: {e}"}


def tool_update_task_def() -> dict[str, Any]:
    """tool definition of updating a task (TOOL_NAME_UPDATE_TASK)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_UPDATE_TASK,
            "description": "Use this tool to update a task in the task list.\n\n"
                           "## When to Use This Tool\n\n"
                           "**Claim a task:**\n"
                           "- All tasks are created without owner, claim the task with `if_claim` = true (default is false)\n"
                           "**Mark claimed tasks as resolved:**\n"
                           "Only task owner can mark their task as resolved when:\n"
                           "- You have completed the work described in a task\n"
                           "- A task is no longer needed or has been superseded\n"
                           "- IMPORTANT: Always mark your assigned & claimed tasks as resolved when you finish them\n"
                           f"- After resolving, call `{TOOL_NAME_QUERY_TASK}` to find your next task\n\n"
                           f"- ONLY mark a task as `{TASK_COMPLETED_LABEL}` when you have FULLY accomplished it\n"
                           f"- If you encounter errors, blockers, or cannot finish, keep the task as `{TASK_IN_PROGRESS_LABEL}`\n"
                           "- When blocked, create a new task describing what needs to be resolved\n"
                           f"- Never mark a task as `{TASK_COMPLETED_LABEL}` if:\n"
                           "  - Tests are failing\n"
                           "  - Implementation is partial\n"
                           "  - You encountered unresolved errors\n"
                           "  - You couldn't find necessary files or dependencies\n\n"
                           "**Delete claimed tasks:**\n"
                           "- Only task owner can delete tasks, if you want to delete a task without owner, you must claim it first\n"
                           f"- When a task is no longer relevant or was created in error. Setting status to `{TASK_DELETED_LABEL}`, "
                           f"and the task will be permanently removed automatically\n\n"
                           "**Update task details:**\n"
                           "- When requirements change or become clearer\n"
                           "- When establishing or updating dependencies between tasks\n\n"
                           "## Fields You Can Update\n\n"
                           "- **status**: The task status (claimer-only) (see Status Workflow below)\n"
                           "- **subject**: Change the task title (claimer-only) (imperative form, e.g., \"Run tests\")\n"
                           "- **description**: Change the task description (claimer-only)\n"
                           "- **add_blocks**: Mark tasks that cannot start until this one completes (any agent)\n"
                           "- **add_blocked_by**: Mark tasks that must complete before this one can start (any agent)\n\n"
                           "## Status Workflow\n\n"
                           f"Status progresses: `{TASK_PENDING_LABEL}` → `{TASK_IN_PROGRESS_LABEL}` → `{TASK_COMPLETED_LABEL}` "
                           f"(can not roll back status)\n\n"
                           f"Use `{TASK_DELETED_LABEL}` to permanently remove a task.\n\n"
                           "## Staleness\n\n"
                           f"Make sure to read a task's latest state using `{TOOL_NAME_QUERY_TASK}` before updating it.\n\n"
                           "## Examples\n\n"
                           "Mark task as in progress when starting work:\n"
                           f"`task_id`: 1, `status`: {TASK_IN_PROGRESS_LABEL}\n"
                           "Mark task as completed after finishing work:\n"
                           f"`taskId`: 1, `status`: {TASK_COMPLETED_LABEL}\n"
                           "Delete a task:\n"
                           f"`taskId`: 1, `status`: {TASK_DELETED_LABEL}\n"
                           "Claim a task:\n"
                           f"`taskId`: 1, `if_claim`: true\n"
                           "Set up task dependencies:\n"
                           "`taskId`: 3, `add_blocked_by`: [1, 2]\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The ID of the task to update.",
                    },
                    "if_claim": {
                        "type": "boolean",
                        "default": False,
                        "description": "If claim a task without owner.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "New subject for the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the task.",
                    },
                    "status": {
                        "type": "string",
                        "enum": [f"{TASK_PENDING_LABEL}", f"{TASK_IN_PROGRESS_LABEL}", f"{TASK_COMPLETED_LABEL}", f"{TASK_DELETED_LABEL}"],
                        "description": "New status for the task.",
                    },
                    "add_blocks": {
                        "description": "Task IDs that this task blocks",
                        "items": {
                            "type": "integer"
                        },
                        "type": "array"
                    },
                    "add_blocked_by": {
                        "description": "Task IDs that block this task",
                        "items": {
                            "type": "integer"
                        },
                        "type": "array"
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def update_task(arguments: dict[str, Any], ctx: AgentContext, board: Scoreboard, progress: Progress) -> dict[str, Any]:
    """tool realization of updating a task with arguments, AgentContext and Scoreboard"""
    func_name = TOOL_NAME_UPDATE_TASK
    try:
        """get data for update"""
        if_success, task, task_info = args_to_taskupdate(arguments, ctx.agent_id)
        if not if_success:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Update task failed with error, details: {task_info}")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {FAIL_LABEL}: Update task failed with error, details: {task_info}",
                                       style="bold red")
            return {"status": FAIL_LABEL, "info": f"Update task failed with error, details: {task_info}"}
        """update task"""
        assert task is not None
        if_success, update_info = board.update_task(task)
        if if_success:
            sys_log.debug(f"{func_name} {DONE_LABEL}: Update task done with info: {update_info}")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {DONE_LABEL}: Update task done with info: {update_info}",
                                       style="bright_black")
            return {"status": DONE_LABEL, "info": update_info}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Update task failed with error, details: {update_info}")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {FAIL_LABEL}: Update task failed with error, details: {update_info}",
                                       style="bold red")
            return {"status": FAIL_LABEL, "info": f"Update task failed with error, details: {update_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Update task failed with error: {e}")
        if not MUTE_TASK_OP_INFO:
            progress.console.print(f"{func_name} {FAIL_LABEL}: Update task failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Update task failed with error: {e}"}


def tool_query_task_def() -> dict[str, Any]:
    """tool definition of querying tasks (TOOL_NAME_QUERY_TASK)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_TASK,
            "description": "Use this tool to retrieve a task by its task ID to get full details or list brief "
                           "information of all tasks without params.\n\n"
                           "## Usage\n\n"
                           "- Get a task by its task ID (`task_id`), this tool will return:\n"
                           "  - subject: Task title\n"
                           "  - description: Detailed requirements and context\n"
                           "  - owner id: Agent ID of this task owner\n"
                           f"  - status: `{TASK_PENDING_LABEL}`, `{TASK_IN_PROGRESS_LABEL}`, "
                           f"`{TASK_COMPLETED_LABEL}` or `{TASK_DELETED_LABEL}`\n"
                           "  - blocks: Tasks waiting on this one to complete\n"
                           "  - blocked_by: Tasks that must complete before this one can start\n"
                           "- Get the full list without `task_id`, this tool will return a summary of each task:\n"
                           "  - task ID: Task identifier\n"
                           "  - subject: Brief description of the task\n"
                           "  - owner ID: Agent ID of this task owner\n"
                           f"  - status: `{TASK_PENDING_LABEL}`, `{TASK_IN_PROGRESS_LABEL}`, "
                           f"`{TASK_COMPLETED_LABEL}` or `{TASK_DELETED_LABEL}`\n"
                           "  - blocked_by: List of open task IDs that must be resolved first\n\n"
                           "## Tips\n\n"
                           "- After fetching a task, verify its `blocked_by` list is empty before beginning work.\n"
                           "- **Prefer working on tasks in ID order** (lowest ID first) when multiple tasks are "
                           "available, as earlier tasks often set up context for later ones\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The ID of the task to get. If this parameter is not given, return "
                                       "the list of all tasks.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_task(arguments: dict[str, Any], ctx: AgentContext, board: Scoreboard, progress: Progress) -> dict[str, Any]:
    """tool realization of querying tasks with arguments, AgentContext and Scoreboard"""
    func_name = TOOL_NAME_QUERY_TASK
    try:
        task_id = arguments.get("task_id")
        if task_id is not None:
            """get single task detail"""
            if not isinstance(task_id, int):
                sys_log.error(f"{func_name} {FAIL_LABEL}: Task ID to query is not an integer")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Task ID to query is not an integer",
                                       style="bold red")
                return {"status": FAIL_LABEL, "info": "Task ID to query is not an integer"}
            if_success, task, get_info = board.get_task(task_id)
            if if_success and task is not None:
                task_info = task_to_info(task, ctx.agent_id)
                sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Get task success")
                if not MUTE_TASK_OP_INFO:
                    progress.console.print(f"{func_name} {SUCCESS_LABEL}: Get task success",
                                           style="bright_black")
                return {"status": SUCCESS_LABEL, "info": task_info}
            elif not if_success:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Get task failed with error, details: {get_info}")
                if not MUTE_TASK_OP_INFO:
                    progress.console.print(f"{func_name} {FAIL_LABEL}: Get task failed with error, "
                                           f"details: {get_info}", style="bold red")
                return {"status": FAIL_LABEL, "info": f"Get task failed with error, details: {get_info}"}
            else:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Get empty task with unknown error")
                if not MUTE_TASK_OP_INFO:
                    progress.console.print(f"{func_name} {FAIL_LABEL}: Get empty task with unknown error",
                                           style="bold red")
                return {"status": FAIL_LABEL, "info": "Get empty task with unknown error"}
        else:
            """list all tasks"""
            tasks = board.list_tasks()
            tasks_info = tasks_to_info(tasks, ctx.agent_id)
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: List task success")
            if not MUTE_TASK_OP_INFO:
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: List task success",
                                       style="bright_black")
            return {"status": SUCCESS_LABEL, "info": tasks_info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Query task failed with error: {e}")
        if not MUTE_TASK_OP_INFO:
            progress.console.print(f"{func_name} {FAIL_LABEL}: Query task failed with error: {e}",
                                   style="bold red")
        return {"status": FAIL_LABEL, "info": f"Query task failed with error: {e}"}


def tool_create_cron_def() -> dict[str, Any]:
    """tool definition of creating a cron task (TOOL_NAME_CREATE_CRON)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_CREATE_CRON,
            "description": "Schedule a prompt to be enqueued at a future time. Use for both repetitive and one-shot tasks. "
                           "Uses standard 5-field cron in the user's local timezone: minute hour day-of-month month day-of-week. "
                           "\"0 9 * * *\" means 9am local — no timezone conversion needed.\n\n"
                           "## One-shot tasks\n"
                           "- Set `if_repeat` to false to only fire the task once (e.g., \"remind me at X\" or \"at <time>, "
                           "do Y\" requests)\n"
                           "- Pin minute/hour/day-of-month/month to specific values:\n"
                           "  \"remind me at 2:30pm today to check the deploy\" → cron: \"30 14 <today_dom> <today_month> *\", `if_repeat`: false\n"
                           "  \"tomorrow morning, run the smoke test\" → cron: \"57 8 <tomorrow_dom> <tomorrow_month> *\", `if_repeat`: false\n"
                           "## Repetitive tasks\n"
                           "- Set `if_repeat` to true (default) for repetitive tasks. Such as \"every N minutes\" / \"every hour\" / "
                           "\"weekdays at 9am\" requests:\n"
                           "  \"*/5 * * * *\" (every 5 min), \"0 * * * *\" (hourly), \"0 9 * * 1-5\" (weekdays at 9am local)\n"
                           "## Durability\n"
                           "- By default (`durable`: false) the task lives only in this session, it will be written to the "
                           "session folder\n"
                           f"- Pass `durable`: true to write to {CRON_CONFIGS_PATH} so the task survives across sessions\n"
                           f"- Only use `durable`: true when the user explicitly asks for the task to persist (\"keep doing "
                           f"this every day\", \"set this up permanently\")."
                           f"- Most \"remind me in 5 minutes\" / \"check back in an hour\" requests should stay session-only\n"
                           "- If one-shot task is not fired, it will be stored to file, otherwise, it won't be save\n"
                           f"## Runtime behavior\n\n"
                           f"- Tasks only fire while the REPL is idle (not mid-query, not user-typing). If cron task expires "
                           f"during the non-idle state, it will always be recalled when REPL is idle\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "cron": {
                        "type": "string",
                        "description": "Standard 5-field cron expression in local time: \"M H DoM Mon DoW\".",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to enqueue at each fire time.",
                    },
                    "if_repeat": {
                        "type": "boolean",
                        "description": "True (default) = fire on every cron match until deleted or finished as one-shot task. "
                                       "False = fire once at the next match. Use false for one-shot requests with pinned "
                                       "minute/hour/dom/month.",
                        "default": True,
                    },
                    "durable": {
                        "type": "boolean",
                        "description": f"False (default) = session only, true = persist to {CRON_CONFIGS_PATH} and survive "
                                       f"restarts. Use true only when the user asks the task to survive across sessions.",
                        "default": False,
                    },
                },
                "required": ["cron", "prompt"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def create_cron(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of creating a cron task with arguments and AgentContext"""
    func_name = TOOL_NAME_CREATE_CRON
    try:
        """check if cron tasks are disabled"""
        if ctx.args.nocrons:
            return {"status": DISABLED_LABEL, "info": f"All cron tasks are disabled by user in this launch of agent with "
                                                      f"`--nocrons` argument"}
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"cron pattern: {arguments.get("cron")}, "
                                         f"prompt: {arguments.get("prompt")}, "
                                         f"if_repeat: {arguments.get("if_repeat", True)}, "
                                         f"durable: {arguments.get("durable", False)},",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """creat cron task"""
        cron_task, if_success, create_info = create_cron_impl(arguments, ctx.cron_ids)
        if if_success and cron_task is not None:
            ctx.add_cron_task(cron_task)
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Create cron task with pattern: {arguments.get("cron")} and prompt: "
                          f"{arguments.get("prompt")} successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Create cron task with pattern: {arguments.get("cron")} and prompt: "
                                   f"{arguments.get("prompt")} successfully", style="bright_black")
            return {"status": SUCCESS_LABEL, "id": cron_task["id"]}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Create cron task with pattern: {arguments.get("cron")} and prompt: "
                          f"{arguments.get("prompt")} failed with error, details: {create_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Create cron task with pattern: {arguments.get("cron")} and prompt: "
                                   f"{arguments.get("prompt")} failed with error, details: {create_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Create cron task failed with error, details: {create_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Grep file failed with error: {e}"}


def tool_query_cron_def() -> dict[str, Any]:
    """tool definition of querying the list of existing cron tasks (TOOL_NAME_QUERY_CRON)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_CRON,
            "description": "Get the list of all existing scheduled cron tasks. This tool will return the task id, prompt, "
                           "cron pattern, if is durable across sessions, if is repetitive or one-shot",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_cron(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the list of existing cron tasks with AgentContext"""
    func_name = TOOL_NAME_QUERY_CRON
    cron_str = get_cron_list(ctx.cron_tasks)
    sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Total cron tasks {len(ctx.cron_tasks)}")
    progress.console.print(f"{func_name} {SUCCESS_LABEL}: Total cron tasks {len(ctx.cron_tasks)}", style="bright_black")
    return {"status": SUCCESS_LABEL,
            "total_tasks": len(ctx.cron_tasks),
            "task_list": cron_str}


def tool_remove_cron_def() -> dict[str, Any]:
    """tool definition of removing an existing cron task (TOOL_NAME_REMOVE_CRON)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_REMOVE_CRON,
            "description": f"Remove a cron task previously scheduled with `{TOOL_NAME_CREATE_CRON}` with given id. Remove it from {CRON_CONFIGS_PATH} "
                           f"(durable tasks) or session-only files (session-only tasks)",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": f"Cron task's ID to remove (returned by `{TOOL_NAME_CREATE_CRON}` or `{TOOL_NAME_QUERY_CRON}`).",
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def remove_cron(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of removing a cron task with arguments and AgentContext"""
    func_name = TOOL_NAME_REMOVE_CRON
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"task id: {arguments.get("id")}",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """remove cron task"""
        task_id = str(arguments.get("id"))
        if_success, remove_info = ctx.remove_cron_task(task_id)
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Remove cron task with id: {task_id} successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Remove cron task with id: {task_id} successfully",
                                   style="bright_black")
            return {"status": SUCCESS_LABEL, "info": f"Remove cron task with id: {task_id} successfully"}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Remove cron task with id: {task_id} failed with error, details: {remove_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Remove cron task with id: {task_id} failed with error, "
                                   f"details: {remove_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Remove cron task failed with error, details: {remove_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Grep file failed with error: {e}"}


def tool_bash_def() -> dict[str, Any]:
    """tool definition of bash (TOOL_NAME_BASH)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_BASH,
            "description": "Executes a given bash command and returns its output. The working directory persists between "
                           "commands, but shell state does not. The shell environment is initialized from the user's profile.\n"
                           "IMPORTANT: Avoid using this tool to run `grep`, `glob`, `cat`, `head`, `tail`, or `echo` commands, "
                           "unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish "
                           "your task. Instead, ALWAYS prefer using the appropriate dedicated tool as this will provide "
                           "a much better experience for the user.\n"
                           f" - File search: Prefer using `{TOOL_NAME_GLOB_FILE}` (NOT find/ls)\n"
                           f" - Content search: Prefer using `{TOOL_NAME_GREP_FILE}` (NOT grep/rg)\n"
                           f" - Read files: Prefer using `{TOOL_NAME_READ_FILE}` (NOT cat/head/tail)\n"
                           f" - Write files: Prefer using `{TOOL_NAME_WRITE_FILE}` (NOT echo >/cat <<EOF)\n"
                           f" - Edit files or Replace strings: Prefer using `{TOOL_NAME_EDIT_FILE}` (NOT sed/awk or other shell/script tools)\n"
                           f" - Fetch webpage: Prefer using `{TOOL_NAME_WEB_FETCH}` (NOT curl/wget or other shell/script tools)\n"
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
                           f" - You may specify an optional timeout in milliseconds "
                           f"(up to {BASH_TIMEOUT_MS_MAX} ms / {BASH_TIMEOUT_MS_MAX / 60000:.1f} minutes). "
                           f"By default, your command will timeout after "
                           f"{BASH_TIMEOUT_MS_DEFAULT} ms ({BASH_TIMEOUT_MS_DEFAULT / 60000:.1f} minutes).\n"
                           " - When issuing multiple commands:\n"
                           "  - If the commands are independent and can run in parallel, make multiple Bash tool calls in"
                           " a single message. Example: if you need to run `git status` and `git diff`, send a single "
                           "message with two Bash tool calls in parallel.\n"
                           "  - If the commands depend on each other and must run sequentially, use a single Bash call with "
                           "\"&&\" to chain them together.\n"
                           "  - Use \";\" only when you need to run commands sequentially but don't care if earlier commands fail.\n"
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
                        "maximum": BASH_TIMEOUT_MS_MAX,
                        "description": f"Optional timeout in milliseconds (max {BASH_TIMEOUT_MS_MAX}, default {BASH_TIMEOUT_MS_DEFAULT})",
                        "default": BASH_TIMEOUT_MS_DEFAULT,
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def bash(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of bash command execution with arguments and AgentContext"""
    func_name = TOOL_NAME_BASH
    try:
        """evaluate the risk of bash command"""
        risk, reason, level = evaluate_bash_risk(arguments["command"], ctx)
        """request permission"""
        pause_for_permission(progress)
        command = arguments["command"]
        progress.console.print(get_bash_render(command, ctx.agent_configs["RENDER_BASH_AS_MD"]))
        token, info = ask_permission_tui(ctx, risk, f"bash description: {arguments["description"]}, "
                                         f"risk level: {level} with reason: {reason}.\n(Full command is shown above)",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """execute command"""
        description = arguments.get("description", "")
        timeout = arguments.get("timeout", BASH_TIMEOUT_MS_DEFAULT)
        sys_log.debug(f"{func_name}: {description} start")
        progress.console.print(f"{func_name}: {description} start", style="bright_black")
        _tmp_script_path = None
        try:
            proc = subprocess.Popen([ctx.agent_configs["BASH_PATH"], "-c", command],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except (UnicodeEncodeError, OSError):
            # Windows gbk codec can't encode non-gbk chars (emoji, etc.) in command line.
            # Fallback: write command to a temp script and run `bash script.sh`.
            sys_log.debug(f"{func_name}: fallback to temp script for command containing non-gbk characters")
            progress.console.print(f"{func_name}: fallback to temp script for command containing non-gbk characters", style="bright_black")
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8')
            tmp.write("#!/bin/bash\n")
            tmp.write(command)
            tmp.close()
            _tmp_script_path = tmp.name
            proc = subprocess.Popen([ctx.agent_configs["BASH_PATH"], _tmp_script_path],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            try:
                stdout, stderr = proc.communicate(timeout=timeout / 1000)
            except KeyboardInterrupt:
                proc.terminate()
                try:
                    proc.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                sys_log.error(f"{func_name} {CANCELLED_LABEL}: {description} with command: {command} is cancelled by user. "
                              f"Command interrupted")
                progress.console.print(f"{func_name} {CANCELLED_LABEL}: {description} is "
                                       f"cancelled by user. Command interrupted", style="bold red")
                return {"status": CANCELLED_LABEL,  # no need to return results if user cancel
                        "info": "bash command is cancelled by user. Command interrupted"}
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                sys_log.error(f"{func_name} {TIMEOUT_LABEL}: "
                              f"{description} with command: {command} timeout > {timeout / 1000} s. Command interrupted")
                progress.console.print(f"{func_name} {TIMEOUT_LABEL}: "
                                       f"{description} timeout > {timeout / 1000} s. Command interrupted", style="bold red")
                return {"status": TIMEOUT_LABEL,
                        "return code": proc.returncode,
                        "stdout": stdout.decode('utf-8', errors='replace'),
                        "stderr": stderr.decode('utf-8', errors='replace')}
            except Exception as e:
                proc.terminate()
                try:
                    proc.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                raise RuntimeError(e)
            sys_log.debug(f"{func_name}: {description} with command {command} done")
            progress.console.print(f"{func_name}: {description} done", style="bright_black")
            return {"status": DONE_LABEL,
                    "return code": proc.returncode,
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace')}
        finally:
            if _tmp_script_path is not None:
                try:
                    os.unlink(_tmp_script_path)
                except OSError:
                    pass
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Command execute with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Command execute with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Command execute with error: {e}"}


def tool_glob_file_def() -> dict[str, Any]:
    """tool definition of globbing the file (TOOL_NAME_GLOB_FILE)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_GLOB_FILE,
            "description": "File pattern matching tool that works with any codebase size. Use this tool when you need to "
                           "find files by name patterns.\n"
                           "Usage:\n"
                           f"- ALWAYS use `{TOOL_NAME_GLOB_FILE}` for file search tasks. NEVER invoke `find` or `ls` as a Bash command. The "
                           f"`{TOOL_NAME_GLOB_FILE}` tool has been optimized for correct permissions and access\n"
                           "- Supports glob patterns like \"**/*.js\" or \"src/**/*.py\"\n"
                           "- Returns matching file paths sorted by modification time\n",
                           # "- When you are doing an open-ended search that may require multiple rounds of globbing and grepping, "
                           # "use the Agent tool instead"
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The glob pattern to match files against.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (must be absolute, not relative). If not specified, the current "
                                       "working directory will be used.",
                    },
                    "entry_limit": {
                        "type": "integer",
                        "default": GLOB_FILE_ENTRIES_DEFAULT,
                        "description": f"Limit output to first N paths. Defaults to {GLOB_FILE_ENTRIES_DEFAULT} when unspecified. "
                                       f"Pass 0 for unlimited (use sparingly — large result sets waste context).",
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def glob_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of globbing the file with arguments and AgentContext"""
    func_name = TOOL_NAME_GLOB_FILE
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name, f"pattern: {arguments.get("pattern")}, "
                                         f"path: {arguments.get("path", os.getcwd())}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """glob file"""
        results, if_success, grep_info = glob_impl(arguments)
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Glob file in path: {arguments.get("path", os.getcwd())} with pattern: "
                          f"{arguments.get("pattern")} successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Glob file in path: {arguments.get("path", os.getcwd())} "
                                   f"with pattern: {arguments.get("pattern")} successfully", style="bright_black")
            return {"status": SUCCESS_LABEL, "results": results}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Glob file in path: {arguments.get("path", os.getcwd())} with pattern: "
                          f"{arguments.get("pattern")} failed with error, details: {grep_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Glob file in path: {arguments.get("path", os.getcwd())} "
                                   f"with pattern: {arguments.get("pattern")} failed with error, details: {grep_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Glob file failed with error, details: {grep_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Glob file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Glob file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Glob file failed with error: {e}"}


def tool_grep_file_def() -> dict[str, Any]:
    """tool definition of grepping the file (TOOL_NAME_GREP_FILE)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_GREP_FILE,
            "description": "A powerful search tool built on ripgreg. Search specific text (in the pattern parameter) under "
                           "a specific directory.\n\n"
                           "Usage:\n"
                           f"- ALWAYS use `{TOOL_NAME_GREP_FILE}` for file content search tasks. NEVER invoke `grep` or `rg` as a Bash "
                           f"command. The `{TOOL_NAME_GREP_FILE}` tool has been optimized for correct permissions and access\n"
                           "- Supports full regex syntax (e.g., \"log.*Error\", \"function\\s+\\w+\"). Literal braces need "
                           "escaping (use `interface\\{\\}` to find `interface{}` in Go code)\n"
                           "- By default patterns match within single lines only. For cross-line patterns like `struct "
                           "\\{[\\s\\S]*?field`, set `multiline: true`\n"
                           "- Filter files with glob parameter (e.g., \"*.js\", \"**/*.tsx\") or type parameter (e.g., "
                           "\"js\", \"py\", \"rust\")\n"
                           "Output mode selection:\n"
                           "- Use \"files_with_matches\" (default) when you need to find which files contain a pattern\n"
                           "- Use \"content\" when you need to see the actual matching lines (supports `context` for surrounding lines)\n"
                           "- Use \"count\" when you need statistics on match frequency per file\n"
                           "Result control:\n"
                           f"- ALWAYS set `head_limit` to a reasonable value based on expected results. The default is {GREP_FILE_HEAD_LIMIT_DEFAULT}. "
                           "set to 0 only when you truly need unlimited results.\n"
                           "- Use `glob` parameter (e.g., \"*.js\", \"**/*.tsx\") or `type` (e.g., \"js\", \"py\", \"rust\") "
                           "to narrow down the search scope\n"
                           "Prefer `type` for standard file types as it's more efficient.\n"
                           "- Use `context` only with output_mode=\"content\" to see lines before and after each match\n",
                           # "- Use Agent tool for open-ended searches requiring multiple rounds\n"
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The regular expression pattern to search for in file contents.",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in (must be absolute, not relative). If not specified, "
                                       "the current working directory will be used.",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g. \"*.js\", \"*.{ts,tsx}\") - maps to rg --glob.",
                    },
                    "type": {
                        "type": "string",
                        "description": "File type to search (rg --type). Common types: js, py, rust, go, java, etc. More "
                                       "efficient than include for standard file types.",
                    },
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                        "default": "files_with_matches",
                        "description": "Output mode: \"content\" shows matching lines (supports -C context, -n line "
                                       "numbers, head_limit), \"files_with_matches\" shows file paths (supports head_limit), "
                                       "\"count\" shows match counts (supports head_limit). Defaults to \"files_with_matches\"",
                    },
                    "ignore_case": {
                        "type": "boolean",
                        "default": False,
                        "description": "Case insensitive search (rg -i), default false.",
                    },
                    "context": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each match (rg -C). Requires output_mode: "
                                       "\"content\", ignored otherwise.",
                    },
                    "head_limit": {
                        "type": "integer",
                        "default": GREP_FILE_HEAD_LIMIT_DEFAULT,
                        "description": "Limit output to first N lines/entries, equivalent to \"| head -N\". Works across "
                                       "all output modes: content (limits output lines), files_with_matches (limits file paths), "
                                       f"count (limits count entries). Defaults to {GREP_FILE_HEAD_LIMIT_DEFAULT} when "
                                       f"unspecified. Pass 0 for unlimited (use sparingly — large result sets waste context).",
                    },
                    "multiline": {
                        "type": "boolean",
                        "default": False,
                        "description": "Enable multiline mode where . matches newlines and patterns can span lines (rg -U "
                                       "--multiline-dotall). Default: false.",
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def grep_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of grepping the file with arguments and AgentContext"""
    func_name = TOOL_NAME_GREP_FILE
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"pattern: {arguments.get("pattern")}, "
                                         f"path: {arguments.get("path", os.getcwd())}, "
                                         f"glob: {arguments.get("glob")}, "
                                         f"type: {arguments.get("type")}, "
                                         f"output_mode: {arguments.get("output_mode", "files_with_matches")}, "
                                         f"ignore_case: {arguments.get("ignore_case", False)}, "
                                         f"context: {arguments.get("context")}, "
                                         f"head_limit: {arguments.get("head_limit", GREP_FILE_HEAD_LIMIT_DEFAULT)}, "
                                         f"multiline: {arguments.get("multiline", False)}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """grep file"""
        results, if_success, grep_info = grep_impl(arguments, ctx.agent_configs["RIPGREP_PATH"], ctx.agent_configs["RIPGREP_TIMEOUT_S"])
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Grep file in path: {arguments.get("path", os.getcwd())} with pattern: "
                          f"{arguments.get("pattern")} successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Grep file in path: {arguments.get("path", os.getcwd())} "
                                   f"with pattern: {arguments.get("pattern")} successfully", style="bright_black")
            return {"status": SUCCESS_LABEL, "results": results}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Grep file in path: {arguments.get("path", os.getcwd())} with pattern: "
                          f"{arguments.get("pattern")} failed with error, details: {grep_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Grep file in path: {arguments.get("path", os.getcwd())} "
                                   f"with pattern: {arguments.get("pattern")} failed with error, details: {grep_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Grep file failed with error, details: {grep_info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Grep file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Grep file failed with error: {e}"}


def tool_read_file_def() -> dict[str, Any]:
    """tool definition of reading the file (TOOL_NAME_READ_FILE)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_READ_FILE,
            "description": "Reads a file from the local filesystem with given path, method, line num and encoding method. "
                           "You can access any file directly by using this tool. Results are returned using cat -n format, "
                           "with line numbers starting from 1. This tool will also return the total line count of the file "
                           "(regardless of read method).\n"
                           "- IMPORTANT: Never start by reading the entire file (`all`) unless the file is known to be very "
                           "short or instructed to do so\n"
                           "- For any unfamiliar file, first use `from_top` with a moderate number of lines (e.g., 50-100) "
                           "to see the file's header and structure\n"
                           "- Once you know the total line count, you can use `from_top` or `from_bottom` to read additional "
                           "chunks, or `offset` to jump to a specific area as needed\n"
                           "- Literal vs real newlines: The output shows file bytes as-is, no escaping. If text appears "
                           "on the same line in the output, `\\n` is literal (backslash + \"n\"). Line breaks in the output "
                           "always indicate real newlines. Consecutive backslashes appear as-is: every `\\` in the output "
                           "is one literal backslash\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (must be absolute, not relative).",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["from_top", "from_bottom", "offset", "all"],
                        "description":  "How to read the file:\n"
                                        "- `from_top`: Reads the first N lines. Best for seeing file header, imports, or "
                                        "initial structure.\n"
                                        "- `from_bottom`: Reads the last N lines. Useful to check logs, trailing configuration, "
                                        "or end of code.\n"
                                        "- `offset`: Reads N lines starting at a given line number (1-based). Precise for "
                                        "targeting known areas. Useful for long file or exact string replacement in tool "
                                        f"`{TOOL_NAME_EDIT_FILE}`.\n"
                                        "- `all`: Reads the entire file. WARNING: Use only when you are certain the file "
                                        "is short or when you absolutely need every line. Otherwise, use the methods above "
                                        "to avoid filling the context.",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": READ_FILE_MAX_LINE,
                        "description": "Number of lines to read (for `from_top`, `from_bottom`, `offset`). "
                                       f"Min 1, max {READ_FILE_MAX_LINE}. "
                                       "When unsure, a value of 50-100 is typically safe for an initial scan.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The starting line number (1-based) when method is offset. Only used with the "
                                       "`offset` method",
                    },
                    "encoding": {
                        "type": "string",
                        "description": f"File encoding (e.g., `utf-8`, `gbk`, `ascii`). Default `{READ_FILE_ENCODING_DEFAULT}`.",
                        "default": READ_FILE_ENCODING_DEFAULT,
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
    func_name = TOOL_NAME_READ_FILE
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"path: {arguments["path"]}, "
                                         f"method: {arguments["method"]}, "
                                         f"read-in line: {arguments.get("line_num", "None")}, "
                                         f"offset: {arguments.get("offset", "None")}, "
                                         f"encoding: {arguments.get("encoding", READ_FILE_ENCODING_DEFAULT)}",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """check the path"""
        file_path = arguments["path"]
        if not os.path.exists(file_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Path: {file_path} doesn't exist.")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Path: {file_path} doesn't exist", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Path: {file_path} doesn't exist"}
        """check the file"""
        if not os.path.isfile(file_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Path: {file_path} is not a file")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Path: {file_path} is not a file", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Path: {file_path} is not a file"}
        """check the file size"""
        file_size = os.path.getsize(file_path)
        if file_size > ctx.agent_configs["READ_FILE_MB_LIMIT"] * 1024 * 1024:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please modify "
                          f"the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please "
                                   f"modify the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"File is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, user should modify the `READ_FILE_MB_LIMIT` "
                            f"in {AGENT_CONFIGS_PATH}"}
        """read the file"""
        encoding = arguments.get("encoding", READ_FILE_ENCODING_DEFAULT)
        with open(file_path, 'r', encoding=encoding) as f:
            raw_line = f.readlines()
        file_line: list[str] = []
        for i, line in enumerate(raw_line, start=1):
            file_line.append(f"{i}\t{line}")
        total_line_num = len(file_line)
        """prepare the content"""
        read_line_num: int | None = arguments.get("line_num")
        if read_line_num is not None and read_line_num > READ_FILE_MAX_LINE:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_FILE_MAX_LINE}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_FILE_MAX_LINE}", style="bold red")
            raise RuntimeError(f"Invalid line num: {read_line_num} > {READ_FILE_MAX_LINE}")
        offset_line_num = arguments.get("offset", 0)
        method = str(arguments["method"]).lower()
        byte_limit = ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"] * 1024
        if method == "from_top":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                raise RuntimeError(f"Line num can't be empty")
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                # file_str = "".join(file_line)
                file_str, truncated, read_lines = read_line_with_limit(file_line, 0, total_line_num - 1, byte_limit, encoding)
            else:
                # file_str = "".join(file_line[0:read_line_num])
                file_str, truncated, read_lines = read_line_with_limit(file_line, 0, read_line_num - 1, byte_limit, encoding)
        elif method == "from_bottom":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                raise RuntimeError(f"Line num can't be empty")
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if total_line_num <= read_line_num:
                # file_str = "".join(file_line)
                file_str, truncated, read_lines = read_line_with_limit(file_line, 0, total_line_num - 1, byte_limit, encoding)
            else:
                # file_str = "".join(file_line[-read_line_num:])
                file_str, truncated, read_lines = read_line_with_limit(file_line, total_line_num - read_line_num, total_line_num - 1, byte_limit, encoding)
        elif method == "offset":
            if read_line_num is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Line num can't be empty")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Line num can't be empty", style="bold red")
                raise RuntimeError(f"Line num can't be empty")
            if read_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid line num: {read_line_num} < 1")
            if offset_line_num < 1:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} < 1")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} < 1", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} < 1")
            if offset_line_num > total_line_num:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} > total line num {total_line_num}")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid offset: {offset_line_num} > total line num {total_line_num}", style="bold red")
                raise RuntimeError(f"Invalid offset: {offset_line_num} > total line num {total_line_num}")
            if (offset_line_num - 1 + read_line_num) <= total_line_num:
                # file_str = "".join(file_line[offset_line_num - 1:offset_line_num - 1 + read_line_num])
                file_str, truncated, read_lines = read_line_with_limit(file_line, offset_line_num - 1, offset_line_num - 2 + read_line_num, byte_limit, encoding)
            else:
                # file_str = "".join(file_line[offset_line_num - 1:])
                file_str, truncated, read_lines = read_line_with_limit(file_line, offset_line_num - 1, total_line_num - 1, byte_limit, encoding)
        elif method == "all":
            # file_str = "".join(file_line)
            file_str, truncated, read_lines = read_line_with_limit(file_line, 0, total_line_num - 1, byte_limit, encoding)
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        ctx.file_read_log(file_path)
        if not truncated:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: "
                          f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}, encoding: {encoding}")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: "
                                   f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                                   f"offset: {offset_line_num}, encoding: {encoding}", style="bright_black")
            return {"status": SUCCESS_LABEL,
                    "total_line": total_line_num,
                    "file_content": file_str}
        else:
            sys_log.warning(f"{func_name} {TRUNCATED_LABEL}: "
                          f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}, encoding: {encoding}, actual read-in line: {read_lines}. "
                          f"Target read-in part is larger than {ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB and truncated, "
                          f"please modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}")
            progress.console.print(f"{func_name} {TRUNCATED_LABEL}: "
                                   f"Path: {file_path}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                                   f"offset: {offset_line_num}, encoding: {encoding}, actual read-in line: {read_lines}. "
                                   f"Target read-in part is larger than {ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB "
                                   f"and truncated, please modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}", style="bold yellow")
            return {"status": TRUNCATED_LABEL,
                    "info": f"Target read-in part is larger than {ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB and truncated, "
                            f"user should modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}",
                    "total_line": read_lines,
                    "file_content": file_str}
    except UnicodeDecodeError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't read file with given encoding, error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't read file with given encoding, error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't read file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"{func_name} {DENIED_LABEL}: Can't read file, permission denied: {e}")
        progress.console.print(f"{func_name} {DENIED_LABEL}: Can't read file, permission denied: {e}", style="bold red")
        return {"status": DENIED_LABEL, "info": f"Can't read file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't read file, OS error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't read file, OS error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't read file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Read file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Read file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Read file failed with error: {e}"}


def tool_write_file_def() -> dict[str, Any]:
    """tool definition of writing the file (TOOL_NAME_WRITE_FILE)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_WRITE_FILE,
            "description": "Write a file or append content to a file to the local filesystem with given path, contents, writing "
                           "mode and encoding method. Supports creating parent directories automatically",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (must be absolute, not relative).",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file. Can be plain text, json, html, code, etc."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append"],
                        "description": "Optional write mode: `write` overwrites the file, `append` adds content to the end. "
                                       f"The default mode is `{WRITE_FILE_MODE_DEFAULT}`",
                        "default": WRITE_FILE_MODE_DEFAULT
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "Optional flag. If true (default), automatically create missing parent directories.",
                        "default": True
                    },
                    "encoding": {
                        "type": "string",
                        "description": f"Optional encoding type (e.g., `utf-8`, `gbk`, `ascii`). Default `{WRITE_FILE_ENCODING_DEFAULT}`.",
                        "default": WRITE_FILE_ENCODING_DEFAULT,
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
    func_name = TOOL_NAME_WRITE_FILE
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"path: {arguments["path"]}, "
                                         f"mode: {arguments.get("mode", WRITE_FILE_MODE_DEFAULT)}, "
                                         f"create_dirs: {arguments.get("create_dirs", True)}, "
                                         f"encoding: {arguments.get("encoding", WRITE_FILE_ENCODING_DEFAULT)}",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """check if read-only"""
        file_path = arguments["path"]
        if_readonly, check_info = check_read_only(file_path, ctx)
        if if_readonly:
            sys_log.error(f"{func_name} {FAIL_LABEL}: {check_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: {check_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"{check_info}"}
        """check the path"""
        create_dirs = arguments.get("create_dirs", True)
        if create_dirs:
            parent_dir = os.path.dirname(file_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                sys_log.debug(f"{func_name}: Parent directory: {parent_dir} created")
                progress.console.print(f"{func_name}: Parent directory: {parent_dir} created", style="bright_black")
        """write the file"""
        mode = arguments.get("mode", WRITE_FILE_MODE_DEFAULT)
        if mode == "write":
            w_mode = 'w'
        elif mode == "append":
            w_mode = 'a'
        else:
            w_mode = 'w'
            sys_log.warning(f"{func_name}: Unknown mode: {mode}, falling back to `write`")
            progress.console.print(f"{func_name}: Unknown mode: {mode}, falling back to `write`", style="bold yellow")
        encoding = arguments.get("encoding", WRITE_FILE_ENCODING_DEFAULT)
        content: str = arguments["content"]
        with open(file=file_path, mode=w_mode, encoding=encoding) as f:
            f.write(content)
        content_bytes = content.encode(encoding)
        byte_count = len(content_bytes)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: "
                      f"Path: {file_path}, mode: {mode}, create_dirs: {create_dirs}, encoding: {encoding}, bytes: {byte_count}")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: "
                               f"Path: {file_path}, mode: {mode}, create_dirs: {create_dirs}, encoding: {encoding}, bytes: {byte_count}", style="bright_black")
        return {"status": SUCCESS_LABEL,
                "bytes_written": byte_count,
                "info": f"Write content to {file_path} done successfully"}
    except UnicodeDecodeError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't write file with given encoding, error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't write file with given encoding, error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't write file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"{func_name} {DENIED_LABEL}: Can't write file, permission denied: {e}")
        progress.console.print(f"{func_name} {DENIED_LABEL}: Can't write file, permission denied: {e}", style="bold red")
        return {"status": DENIED_LABEL, "info": f"Can't write file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't write file, OS error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't write file, OS error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't write file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Write file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Write file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Write file failed with error: {e}"}


def tool_edit_file_def() -> dict[str, Any]:
    """tool definition of editing the file (TOOL_NAME_EDIT_FILE)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_EDIT_FILE,
            "description": "Edit the file with exact string replacement. Prefer editing files with this tool rather than "
                           f"using `{TOOL_NAME_BASH}` tool or other shell/script tools unless explicitly required. You must use "
                           f"`{TOOL_NAME_READ_FILE}` tool at least once before editing. This tool will error if you attempt "
                           f"an edit without reading the file.\n"
                           f"- When editing text from `{TOOL_NAME_READ_FILE}` tool output, ensure you preserve the exact indentation "
                           "(tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: "
                           "line number + tab (e.g., \"123\\t\"). Everything after that is the actual file content to match. "
                           "Never include any part of the line number prefix in the `old_string` or `new_string`\n"
                           "- For targeted edits (a specific line/block): ALWAYS include the exact leading whitespace to "
                           "match the precise scope. This is essential in languages like Python where indentation changes meaning\n"
                           "- For simple, scope-independent replacements (renaming a variable, fixing a typo in a comment, "
                           "changing a string literal everywhere): you may use the minimal unique string (e.g., just the identifier) "
                           "and set `replace_all` to true, without worrying about indentation. Be careful that the short string "
                           "does not accidentally match unrelated text\n"
                           "- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string "
                           "with more surrounding context to make it unique or use `replace_all` to change every instance "
                           "of `old_string`\n"
                           "- Prefer editing existing files and don't write new files unless explicitly required\n"
                           "- CRLF normalized automatically: `\\r` in both `old_string` and `new_string` is stripped "
                           "before matching/replacement, preventing CRLF-vs-LF and double-CR on Windows.\n"
                           f"- `{TOOL_NAME_READ_FILE}` output preserves file bytes as-is, no escaping: if the file has `\\n` "
                           "(backslash + \"n\") in it, the output literally shows `\\n`\n"
                           "- When match fails, error `info` includes `target(repr)`, `context(repr)` (bytes near "
                           "closest partial match), `content_len` and `target_len`. Use info to verify actual bytes\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file (must be absolute, not relative).",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The text to replace."
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The text to replace it with (must be different from `old_string`)."
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences of `old_string` (default false).",
                        "default": False
                    },
                    "encoding": {
                        "type": "string",
                        "description": f"Optional encoding type (e.g., `utf-8`, `gbk`, `ascii`). Default `{EDIT_FILE_ENCODING_DEFAULT}`.",
                        "default": EDIT_FILE_ENCODING_DEFAULT,
                    }
                },
                "required": ["path", "old_string", "new_string"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def edit_file(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of editing the file with arguments and AgentContext"""
    func_name = TOOL_NAME_EDIT_FILE
    try:
        """check if read-only"""
        file_path = arguments["path"]
        if_readonly, check_info = check_read_only(file_path, ctx)
        if if_readonly:
            sys_log.error(f"{func_name} {FAIL_LABEL}: {check_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: {check_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"{check_info}"}
        """check the path"""
        if not os.path.exists(file_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Path: {file_path} doesn't exist.")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Path: {file_path} doesn't exist", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Path: {file_path} doesn't exist"}
        """check the file"""
        if not os.path.isfile(file_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Path: {file_path} is not a file")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Path: {file_path} is not a file", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Path: {file_path} is not a file"}
        """check if the file is read"""
        if os.path.abspath(file_path) not in ctx.files_read:
            sys_log.error(f"{func_name} {FAIL_LABEL}: File: {file_path} is never read before editing")
            progress.console.print(f"{func_name} {FAIL_LABEL}: File: {file_path} is never read before editing", style="bold red")
            return {"status": FAIL_LABEL, "info": f"File: {file_path} is never read before editing"}
        """check the file size"""
        file_size = os.path.getsize(file_path)
        if file_size > ctx.agent_configs["READ_FILE_MB_LIMIT"] * 1024 * 1024:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"File: {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please modify "
                          f"the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"File {file_path} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please "
                                   f"modify the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}",
                                   style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"File is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, user should modify the `READ_FILE_MB_LIMIT` "
                            f"in {AGENT_CONFIGS_PATH}"}
        """read the file"""
        encoding = arguments.get("encoding", EDIT_FILE_ENCODING_DEFAULT)
        with open(file_path, 'r', encoding=encoding) as f:
            raw_line = f.readlines()
        raw_str = ''.join(raw_line)
        """find the string to replace"""
        old_string:str = arguments["old_string"]
        new_string:str = arguments["new_string"]
        replace_all:bool = arguments.get("replace_all", False)
        # normalize old_string & new_string: strip \r to prevent CRLF-vs-LF mismatch
        # (reading: text-mode universal newlines convert \r\n to \n in content)
        # (writing: text-mode on Windows converts \n to \r\n automatically,
        #  so if new_string kept \r, it would become \r\r\n - double CR)
        old_string_norm = old_string.replace('\r\n', '\n').replace('\r', '\n')
        new_string_norm = new_string.replace('\r\n', '\n').replace('\r', '\n')
        # try exact match first, then fall back to quote-normalized matching
        match_lines = match_line_ranges(raw_str, old_string_norm, True)
        count = len(match_lines)
        # use actual_old for replacement (may differ from old_string if quote normalization was needed)
        actual_old = old_string_norm
        if count == 0:
            sys_log.debug(f"{func_name}: try match via quote normalization")
            progress.console.print(f"{func_name}: try match via quote normalization", style="bright_black")
            actual_found = find_actual_string(raw_str, old_string_norm)
            if actual_found is not None:
                actual_old = actual_found
                match_lines = match_line_ranges(raw_str, actual_old, True)
                count = len(match_lines)
                sys_log.debug(f"{func_name}: matched via quote normalization: "
                              f"old_string={repr(old_string_norm)} actual={repr(actual_old)}")
                progress.console.print(f"{func_name}: matched via quote normalization", style="bright_black")
        if count == 0:
            debug_info = get_match_debug_info(raw_str, old_string_norm)
            sys_log.error(f"{func_name} {FAIL_LABEL}: No match of the string to replace. Details: {debug_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: No match of the string to replace", style="bold red")
            return {"status": FAIL_LABEL, "info": f"No match of the string to replace. Details: {debug_info}"}
        elif count > 1 and not replace_all:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Found {count} matches of the string to replace, but `replace_all` is false")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Found {count} matches of the string to replace, but `replace_all` is false", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"Found {count} matches of the string to replace, but `replace_all` is false. To replace all occurrences, "
                            f"set `replace_all` to true. To replace only one occurrence, please provide more context to uniquely "
                            f"identify the instance."}
        multi_match = True if (count > 1 and replace_all) else False
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_edit_tui(file_path, actual_old, new_string_norm, raw_line, match_lines, multi_match, ctx, progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """apply edit with replacement (use actual_old for consistency with matching, avoid double CR)"""
        if count > 1 and replace_all:  # multiple replace
            edit_str = raw_str.replace(actual_old, new_string_norm)
        else:
            edit_str = raw_str.replace(actual_old, new_string_norm, 1)
        """write the file"""
        encoding = arguments.get("encoding", EDIT_FILE_ENCODING_DEFAULT)
        with open(file=file_path, mode='w', encoding=encoding) as f:
            f.write(edit_str)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Path: {file_path}, replace_all: {replace_all}, encoding: {encoding},"
                      f" count: {count}")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: Path: {file_path}, replace_all: {replace_all}, encoding: {encoding},"
                               f" count: {count}", style="bright_black")
        return {"status": SUCCESS_LABEL,
                "info": f"File {file_path} updated successfully"}
    except UnicodeDecodeError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't edit file with given encoding, error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't edit file with given encoding, error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't edit file with given encoding, error: {e}"}
    except PermissionError as e:
        sys_log.error(f"{func_name} {DENIED_LABEL}: Can't edit file, permission denied: {e}")
        progress.console.print(f"{func_name} {DENIED_LABEL}: Can't edit file, permission denied: {e}", style="bold red")
        return {"status": DENIED_LABEL, "info": f"Can't edit file, permission denied: {e}"}
    except OSError as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Can't edit file, OS error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Can't edit file, OS error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Can't edit file, OS error: {e}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Edit file failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Edit file failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Edit file failed with error: {e}"}


def tool_skill_def() -> dict[str, Any]:
    """tool definition of launching skills (TOOL_NAME_SKILL)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_SKILL,
            "description": "Execute a skill within the main conversation. When users ask you to perform tasks, check if any "
                           "of the available skills match. Skills provide specialized capabilities and domain knowledge.\n"
                           "How to invoke:\n"
                           "- Use this tool with the skill `name` and optional `purpose`\n"
                           "- FORMAT EXAMPLE (not actual skills):\n"
                           "  - `name: \"ms-office-suite:pdf\"`, `purpose: invoke the pdf skill to read ...`\n"
                           "  - `name: \"svg-diagram\"`, `purpose: draw svg diagram on ... with the skill`\n"
                           "  - `name: \"<skill_name>\"`, `purpose: \"<purpose to invode skill>\"`\n"
                           "Important:\n"
                           "- All available skills and their description are listed in your system prompts\n"
                           f"- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the `{TOOL_NAME_SKILL}` "
                           f"tool with relevant skill's name BEFORE generating any other response about the task\n"
                           "- Do not invoke a skill that is already running or nonexists\n"
                           "- If the skill has ALREADY been loaded (by you or user), this tool will error, follow the "
                           "instructions directly instead of calling this tool again\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the skill to invoke.",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Optional purpose for invoking the skill.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def skill(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> tuple[dict[str, Any], dict[str, str] | None]:
    """tool realization of launching skill with AgentContext"""
    func_name = TOOL_NAME_SKILL
    try:
        """check if skills are disabled"""
        if ctx.args.noskills:
            return {"status": DISABLED_LABEL, "info": f"All skills are disabled by user in this launch of agent with "
                                                      f"`--noskills` argument"}, None
        name = str(arguments["name"])
        """permission request"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, f"{func_name}",
                                         f"skill name: {arguments["name"]}, "
                                         f"purpose: {arguments.get("purpose", "None")}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}, None
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}, None
        """load skill"""
        # check if loaded (skill can be loaded by previous conversation but is removed in this one)
        if any(item.get("name") == name for item in ctx.loaded_skills):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Skill {name} is already loaded")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Skill {name} is already loaded", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"Skill {name} is already loaded, follow the instructions directly instead of calling this tool again"}, None
        # if not loaded, check if the skill is available
        elif not any(item.get("name") == name for item in ctx.skills):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Skill {name} is not available")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Skill {name} is not available", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Skill {name} is not available"}, None
        else:
            # load the content
            content = load_skill_content(SKILLS_PATH, name, progress.console)
            if content is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Read content of skill {name} failed")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Read content of skill {name} failed", style="bold red")
                return {"status": FAIL_LABEL, "info": f"Read content of skill {name} failed"}, None
            else:
                ctx.loaded_skills.append({
                    "name": name,
                    "description": str(get_skill_description(name, ctx.skills)),
                })
                sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Skill {name} is loaded to context")
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: Skill {name} is loaded to context", style="bright_black")
                return {"status": SUCCESS_LABEL, "info": f"Skill {name} is loaded to context"}, content
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Load skill failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Load skill failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Load skill failed with error: {e}"}, None


def tool_web_fetch_def() -> dict[str, Any]:
    """tool definition of fetching contents of webpage (TOOL_NAME_WEB_FETCH)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_WEB_FETCH,
            "description": "Use this tool when you need to retrieve and analyze web content. `{TOOL_NAME_WEB_FETCH}` WILL FAIL for "
                           "authenticated or private URLs. Before using this tool, check if the URL points to an authenticated "
                           "service (e.g. Google Docs, Confluence, Jira, GitHub). If so, look for a specialized MCP tool "
                           "that provides authenticated access.\n"
                           "Usage:\n"
                           "- Takes a URL and a prompt (describe what information you want to extract) as input\n"
                           "- Fetches the URL content, converts HTML to markdown and processes it using another AI model with "
                           "given prompt\n"
                           "- Returns the model's response about the content\n"
                           "IMPORTANT: If an MCP-provided web fetch tool is available, prefer using that tool instead "
                           "of this one, as it may provide better web fetch quality.\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "url",
                        "description": "The URL to fetch content from.\n"
                                       "- The URL must be a fully-formed valid URL\n"
                                       "- HTTP URLs will be automatically upgraded to HTTPS\n",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The prompt for another AI model to process the fetched content."
                    }
                },
                "required": ["url", "prompt"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def web_fetch(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of fetching contents of webpage with AgentContext"""
    func_name = TOOL_NAME_WEB_FETCH
    try:
        url = arguments["url"]
        prompt = arguments["prompt"]
        """permission request"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"URL: {arguments["url"]}, "
                                         f"prompt: {arguments["prompt"]}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """check URL"""
        check_info, check_success = check_url(url, progress.console)
        if not check_success:
            sys_log.error(f"{func_name} {FAIL_LABEL}: URL {url} is not valid. Detail: {check_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: URL {url} is not valid. Detail: {check_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"URL {url} is not valid. Detail: {check_info}"}

        """fetch content"""
        content, content_info, if_redirect, final_url = ui_info.loading_spinner(
            web_single_fetch, url, ctx, progress.console,
            waiting_desc="Web fetching ...", done_desc="Web fetch time cost",
            intrp_desc="Web fetch interrupted", fail_desc="Web fetch failed",
            spinner="arrow3", out_except=WebFetchCancelled("Web fetch is cancelled by user"))
        # content, content_info, if_redirect, final_url = web_single_fetch(url, ctx, progress.console)
        if content is None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Failed to fetch content from URL: {url}. If redirect: {if_redirect}, final URL: "
                          f"{final_url}. Error detail: {content_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Failed to fetch content from URL: {url}. If redirect: {if_redirect}, final URL: "
                                   f"{final_url}. Error detail: {content_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Failed to fetch content from URL: {url}. If redirect: {if_redirect}, final URL: "
                                              f"{final_url}. Error detail: {content_info}"}

        """route to LLM to process the content"""
        process_content, if_success = web_fetch_process(prompt, content, ctx, progress.console)
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: URL {url} fetched and processed successfully. If redirect: {if_redirect}, "
                          f"final URL: {final_url}")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: URL {url} fetched and processed successfully. If redirect: "
                                   f"{if_redirect}, final URL: {final_url}", style="bright_black")
            if if_redirect:
                return {"status": SUCCESS_LABEL, "content": f"URL: {url} is redirected to {final_url}.\n\n" + f"{process_content}"}
            else:
                return {"status": SUCCESS_LABEL, "content": f"{process_content}"}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Failed to process content from URL: {url} with LLM. If redirect: {if_redirect}, "
                          f"final URL: {final_url}. Error detail: {process_content}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Failed to process content from URL: {url} with LLM. If redirect: "
                                   f"{if_redirect}, final URL: {final_url}. Error detail: {process_content}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Failed to process content from URL: {url} with LLM. If redirect: {if_redirect}, "
                                              f"final URL: {final_url}. Error detail: {process_content}"}
    except WebFetchCancelled:
        sys_log.warning(f"{func_name} {CANCELLED_LABEL}: Web fetch is cancelled by user")
        progress.console.print(f"{func_name} {CANCELLED_LABEL}: Web fetch is cancelled by user", style="bold yellow")
        return {"status": CANCELLED_LABEL, "info": f"Web fetch is cancelled by user"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Fetch content from URL failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Fetch content from URL failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Fetch content from URL failed with error: {e}"}


def tool_web_search_def() -> dict[str, Any]:
    """tool definition of searching query on web (TOOL_NAME_WEB_SEARCH)"""
    now = datetime.now()
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_WEB_SEARCH,
            "description": "Use this tool when you need to search the web or access information beyond your knowledge cutoff. "
                           "IMPORTANT: If an MCP-provided web search tool is available, prefer using that tool instead "
                           "of this one, as it may provide better web search quality.\n"
                           "Usage:\n"
                           "- Takes query (list of key words you want to search on the web) as input\n"
                           "- The search results will be processed by another AI model, and final results are formatted "
                           "as markdown with hyperlinks\n"
                           "CRITICAL REQUIREMENT. You MUST follow:\n  "
                           "- After answering the user's question, you MUST include a \"Sources:\" section at the end of "
                           "your response\n"
                           "- In the \"Sources:\" section, list all relevant URLs from the search results as markdown "
                           "hyperlinks: [Title](URL)\n"
                           "  - Example format:\n"
                           "    [Your answer here]\n"
                           "    Sources:\n"
                           "    - [Source Title 1](https://example.com/1)\n"
                           "    - [Source Title 2](https://example.com/2)\n"
                           " - This is MANDATORY: never skip including \"Sources:\" in your response\n"
                           "IMPORTANT - Use the correct year in search queries:\n"
                           f"- The current month is {now.strftime("%B-%Y")}. You MUST use this year when searching for "
                           f"recent information, documentation, or current events.\n"
                           "- Example: If the user asks for \"latest React docs\", "
                           "search for \"React documentation\" with the current year, NOT last year\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": WEB_SEARCH_QUERY_MIN,
                        "description": "key words you want to search on the web",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def web_search(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of searching query on web with AgentContext"""
    func_name = TOOL_NAME_WEB_SEARCH
    try:
        query = arguments["query"]
        """permission request"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"Web search with keywords {query}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """web search"""
        content, content_info = ui_info.loading_spinner(
            web_search_top, query, ctx, progress.console,
            waiting_desc="Web searching ...", done_desc="Web search time cost",
            intrp_desc="Web search interrupted", fail_desc="Web search failed",
            spinner="arrow3", out_except=WebSearchCancelled("Web search is cancelled by user"))
        # content, content_info = web_search_top(query, ctx, progress.console)
        if content is None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Failed to search on web with query: {query}. Error detail: {content_info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Failed to search on web with query: {query}. Error detail: "
                                   f"{content_info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Failed to search on web with query: {query}. Error detail: {content_info}"}

        """route to LLM to process the content"""
        process_content, if_success = web_search_process(query, content, ctx, progress.console)
        if if_success:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: {query} searched and processed successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: {query} searched and processed successfully", style="bright_black")
            return {"status": SUCCESS_LABEL, "content": f"{process_content}"}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Failed to search query with: {query} with LLM. Error detail: {process_content}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Failed to search query with: {query} with LLM. "
                                   f"Error detail: {process_content}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Failed to search query with: {query} with LLM. Error detail: {process_content}"}
    except WebSearchCancelled:
        sys_log.warning(f"{func_name} {CANCELLED_LABEL}: Web search is cancelled by user")
        progress.console.print(f"{func_name} {CANCELLED_LABEL}: Web search is cancelled by user", style="bold yellow")
        return {"status": CANCELLED_LABEL, "info": f"Web search is cancelled by user"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Web search failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Web search failed failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Web search failed failed with error: {e}"}


def call_mcp(tool_name: str, arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of call tools in MCP with AgentContext"""
    func_name = TOOL_NAME_CALL_MCP
    try:
        mcp_client = ctx.mcp_router.tool_registry.get(tool_name)
        if mcp_client is None:
            mcp_name = "Unknown"
        else:
            mcp_name = mcp_client.name
        """permission request"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, tool_name, f"Tool call from MCP: {mcp_name}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """call tool"""
        timeout = ctx.agent_configs["MCP_TIMEOUT_S"]
        results, info = ctx.mcp_router.call_tool_sync(tool_name, arguments, timeout, progress.console)
        if results is not None:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Tool call: {tool_name} from MCP: {mcp_name} called successfully")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Tool call: {tool_name} from MCP: {mcp_name} called "
                                   f"successfully", style="bright_black")
            return {"status": SUCCESS_LABEL, "results": results}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Failed to call: {tool_name} from MCP: {mcp_name}. Error detail: {info}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Failed to call: {tool_name} from MCP: {mcp_name}. "
                                   f"Error detail: {info}", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Failed to call: {tool_name} from MCP: {mcp_name}. Error detail: {info}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Call MCP tool {tool_name} failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Call MCP tool {tool_name} failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Call MCP tool {tool_name} failed with error: {e}"}


def tool_check_simulator_def() -> dict[str, Any]:
    """tool definition of checking the simulator (TOOL_NAME_CHECK_SIMULATOR)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_CHECK_SIMULATOR,
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
    func_name = TOOL_NAME_CHECK_SIMULATOR
    try:
        """check the path"""
        if not os.path.exists(ctx.agent_configs["SIMULATOR_PATH"]):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in "
                          f"`SIMULATOR_PATH` does not exist")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} "
                                   f"defined in `SIMULATOR_PATH` does not exist", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"Simulator's path {ctx.agent_configs["SIMULATOR_PATH"]} defined in `SIMULATOR_PATH` does not exist"}

        """check the executable"""
        results = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/TECoSim.exe'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results.returncode != 0 and results.stdout is not None:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Simulator is available")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Simulator is available", style="bright_black")
            return {"status": SUCCESS_LABEL, "info": "Simulator is available"}
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Simulator is unavailable")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Simulator is unavailable", style="bold red")
            return {"status": FAIL_LABEL, "info": "Simulator is unavailable"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Check simulator failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: check simulator failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Check simulator failed with error: {e}"}


def tool_init_design_def() -> dict[str, Any]:
    """tool definition of initializing the design (TOOL_NAME_INIT_DESIGN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_INIT_DESIGN,
            "description": f"Use this tool to create a brand-new `{SIM_DESIGN_NAME}` with default configuration from simulator's "
                           "path. Each design gets a unique auto-assigned ID (`design_id`, starting from 1), with its first "
                           "revision set to `design_rev` = 1\n"
                           f"Each `{SIM_DESIGN_NAME}` is an independent panel project identified by its `design_id`. Use "
                           f"this tool to start a new project from scratch.\n"
                           # f"TODO: For iterative changes on the same design, use the modify tool `{TOOL}` which creates a new revision under the same `design_id`.\n"
                           f"Each revision carries its own subject and description to document its purpose.\n"
                           f"Parameters:\n"
                           f" - `subject`: A short title describing this revision's purpose\n"
                           f" - `description`: Detailed notes about this revision's goals or specifications\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "A brief title for this design with first revision.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The detailed purpose or information for this design with first revision.",
                    },
                },
                "required": ["subject", "description"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def init_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of initializing a design with arguments and AgentContext"""
    func_name = TOOL_NAME_INIT_DESIGN
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,f"initialize a new design. Subject: {arguments["subject"]}\n"
                                                        f"Description: {arguments["description"]}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """initialize design"""
        if_success, label, info = init_design_impl(arguments, ctx.design_man, progress.console)
        return {"status": label, "info": info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Initialize design failed with error: {e}"}


def tool_query_design_def() -> dict[str, Any]:
    """tool definition of querying the list of created designs (TOOL_NAME_QUERY_DESIGN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_DESIGN,
            "description": f"Use this tool to retrieve detailed information about `{SIM_DESIGN_NAME}` or list them briefly.\n"
                           f"# Usage:\n"
                           f"- Get a specific `{SIM_DESIGN_NAME}` revision (requires both `design_id` and `design_rev`) and "
                           f"return:\n"
                           f"  1. The subject and description of the specified revision\n"
                           f"  2. The design ID and revision ID that this revision was copied from (if any)\n"
                           f"- Get all revisions under a specific design ID (requires only `design_id`) and return:\n"
                           f"  1. The subject of each revision belonging to this design\n"
                           f"  2. The design ID and revision ID that each revision was copied from (if any)\n"
                           f"- List all `{SIM_DESIGN_NAME}` designs (no parameters required):\n"
                           f"  1. The subject of the latest revision for each design\n"
                           f"  2. The design ID and revision ID that the latest revision was copied from (if any)\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "design_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The design ID to query. When provided without `design_rev`, lists all revisions "
                                       "of this design.",
                    },
                    "design_rev": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The revision ID to query. Must be used together with `design_id` if you want to "
                                       "get a specific revision.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_design(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the list of created designs with AgentContext"""
    func_name = TOOL_NAME_QUERY_DESIGN
    try:
        design_id = arguments.get("design_id")
        design_rev = arguments.get("design_rev")
        if design_id is None and design_rev is not None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Query design failed with error: only `design_rev` is given")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Query design failed with error: only `design_rev` is given",
                                   style="bold red")
            return {"status": FAIL_LABEL, "info": f"Query design failed with error: only `design_rev` is given"}
        if (design_id is not None) and (design_rev is not None):
            assert isinstance(design_id, int)
            assert isinstance(design_rev, int)
            if_success, design, get_info = ctx.design_man.get_design(design_id, design_rev)
            if not if_success or design is None:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Query design failed with error, detail: {get_info}")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Query design failed with error, detail: {get_info}",
                                       style="bold red")
                return {"status": FAIL_LABEL, "info": f"Query design failed with error, detail: {get_info}"}
            else:
                design_info = design_to_info(design)
                sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Query design succeed")
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: Query design succeed", style="bright_black")
                return {"status": SUCCESS_LABEL, "info": design_info}
        elif design_id is not None:
            assert isinstance(design_id, int)
            if_success, designs, get_info = ctx.design_man.list_design_revision(design_id)
            if not if_success:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Query design failed with error, detail: {get_info}")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Query design failed with error, detail: {get_info}",
                                       style="bold red")
                return {"status": FAIL_LABEL, "info": f"Query design failed with error, detail: {get_info}"}
            else:
                designs_info = designs_to_info(designs)
                sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Query design succeed")
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: Query design succeed", style="bright_black")
                return {"status": SUCCESS_LABEL, "info": designs_info}
        else:
            designs = ctx.design_man.list_latest_revisions()
            designs_info = designs_to_info(designs)
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Query design succeed")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Query design succeed", style="bright_black")
            return {"status": SUCCESS_LABEL, "info": designs_info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Query design failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Query design failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Query design failed with error: {e}"}


def tool_launch_sim_def() -> dict[str, Any]:
    """tool definition of launching the simulator (TOOL_NAME_LAUNCH_SIM)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_LAUNCH_SIM,
            "description": f"Run a thermo-electrical simulation through TECoSim on an existing display panel's `{SIM_DESIGN_NAME}`. "
                           f"A new `{SIM_RUN_NAME}` entry is created and the simulator executes with the design's configuration. "
                           f"After completion, simulation logs can BE read with `{TOOL_NAME_READ_LOG}`\n"
                           # f" (TODO: other results reading tools are not implemented).\n"
                           "This tool will fail if: the target design doesn't exist, the design path is invalid, simulator "
                           "times out, simulator encounters runtime error, or the simulation is cancelled by the user\n"
                           "Each run has its own `subject` and `description` to document its purpose.",
            "parameters": {
                "type": "object",
                "properties": {
                    "design_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": f"The ID of an existing `{SIM_DESIGN_NAME}` to simulate.",
                    },
                    "design_rev": {
                        "type": "integer",
                        "minimum": 1,
                        "description": f"The revision of the `{SIM_DESIGN_NAME}` to simulate. Use with `design_id` to "
                                       f"specify which version.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "A brief title for this run.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The detailed purpose or information for this run.",
                    },
                },
                "required": ["design_id", "design_rev", "subject", "description"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def launch_sim(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of launching the simulator with arguments and AgentContext"""
    func_name = TOOL_NAME_LAUNCH_SIM
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"launch simulation run under design: {arguments["design_id"]} (rev "
                                         f"{arguments["design_rev"]}). Subject: {arguments["subject"]}\n"
                                         f"Description : {arguments["description"]}",
                                         progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """launch sim"""
        if_success, label, info = launch_sim_impl(arguments, ctx.run_man, progress.console)
        return {"status": label, "info": info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Launch simulator failed with error: {e}"}


def tool_query_run_def() -> dict[str, Any]:
    """tool definition of querying launched run (TOOL_NAME_QUERY_RUN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_RUN,
            "description": f"Use this tool to retrieve a `{SIM_RUN_NAME}` by its run ID to get full details or list brief "
                           f"information of all `{SIM_RUN_NAME}` without params.\n\n"
                           f"# Usage:\n"
                           f"- Get a `{SIM_RUN_NAME}` by its run ID (`run_id`), this tool will return:\n"
                           f"  1. Its input design's ID and design's revision\n"
                           f"  2. Its subject AND description\n"
                           f"  3. Its status: `{RUN_CANCELLED_LABEL}`, `{RUN_TIMEOUT_LABEL}`, `{RUN_RUNTIME_ERROR_LABEL}`, "
                           f"`{RUN_DONE_LABEL}`\n"
                           f"- Get the full list without `run_id`, this tool will return:\n"
                           f"  1. Each run's input design ID and design revision\n"
                           f"  2. Each run's subject\n"
                           f"  3. Each run's status\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The ID of the run to get. If this parameter is not given, return the list of all runs",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_run(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying runs with AgentContext"""
    func_name = TOOL_NAME_QUERY_RUN
    try:
        """get task"""
        run_id = arguments.get("run_id")
        if run_id is not None:
            if not isinstance(run_id, int):
                sys_log.error(f"{func_name} {FAIL_LABEL}: Run ID to query is not an integer")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Run ID to query is not an integer", style="bold red")
                return {"status": FAIL_LABEL, "info": "Run ID to query is not an integer"}
            if_success, run, get_info = ctx.run_man.get_run(run_id)
            if if_success and run is not None:
                run_info = run_to_info(run)
                sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Get run success")
                progress.console.print(f"{func_name} {SUCCESS_LABEL}: Get run success", style="bright_black")
                return {"status": SUCCESS_LABEL, "info": run_info}
            elif not if_success:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Get run failed with error, details: {get_info}")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Get run failed with error, details: {get_info}",
                                       style="bold red")
                return {"status": FAIL_LABEL, "info": get_info}
            else:
                sys_log.error(f"{func_name} {FAIL_LABEL}: Get empty run with unknown error")
                progress.console.print(f"{func_name} {FAIL_LABEL}: Get empty run with unknown error", style="bold red")
                return {"status": FAIL_LABEL, "info": "Get empty run with unknown error"}
        else:
            runs = ctx.run_man.list_runs()
            runs_info = runs_to_info(runs)
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: List run success")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: List run success", style="bright_black")
            return {"status": SUCCESS_LABEL, "info": runs_info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Query run failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Query run failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Query run failed with error: {e}"}


def tool_read_log_def() -> dict[str, Any]:
    """tool definition of reading the log of the given run (TOOL_NAME_READ_LOG)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_READ_LOG,
            "description": f"Read the stdout or stderr log of a simulation `{SIM_RUN_NAME}`. Results are returned in cat -n "
                           f"format with line numbers starting from 1. The total line count of the log will always be returned. "
                           f"Use `from_bottom` (50-100 lines) to check for errors; use `offset` for targeted reads. Avoid "
                           f"reading the entire log (`all`) unless it's known to be short",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "integer",
                        "minimum": 1,
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
                        "description": "How to read the log:\n"
                                        "- `from_top`: Reads the first N lines\n"
                                        "- `from_bottom`: Reads the last N lines. The primary way to inspect logs; use this "
                                        "to find error messages, stack traces, or final output\n"
                                        "- `offset`: Reads N lines starting at a given line number (1-based). Precise for "
                                        "targeting known areas in the log\n"
                                        "- `all`: Reads the entire log. WARNING: Use only when you are certain the log "
                                        "is short or when you absolutely need every line. Otherwise, use the methods above "
                                        "to avoid filling the context",
                    },
                    "line_num": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": READ_LOG_MAX_LINE,
                        "description": f"Number of lines to read (for `from_top`, `from_bottom`, `offset`). Min 1, max {READ_LOG_MAX_LINE}. "
                                       "When scanning the end of a log for errors, 50-100 lines is usually sufficient",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "The starting line number (1-based) when method is `offset`. Only used with the "
                                       "`offset` method",
                    }
                },
                "required": ["run_id", "log_type", "method"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def read_log(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of reading the log with arguments and AgentContext"""
    func_name = TOOL_NAME_READ_LOG
    try:
        """request permission"""
        pause_for_permission(progress)
        token, info = ask_permission_tui(ctx, func_name,
                                         f"run id: {arguments["run_id"]}, "
                                         f"type: {arguments["log_type"]}, "
                                         f"method: {arguments["method"]}, "
                                         f"read-in line: {arguments.get("line_num", "None")}, "
                                         f"offset: {arguments.get("offset", "None")}", progress.console)
        resume_from_permission(progress)
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        if_success, label, info, lines, log = read_log_impl(arguments, ctx.run_man,
                                                            ctx.agent_configs["READ_FILE_MB_LIMIT"],
                                                            ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"],
                                                            progress.console)
        if if_success:
            if info.strip():
                return {"status": label, "info": info, "total_line": lines, "log_content": log}
            else:
                return {"status": label, "total_line": lines, "log_content": log}
        else:
            return {"status": label, "info": info}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Read log failed with error: {e}"}
