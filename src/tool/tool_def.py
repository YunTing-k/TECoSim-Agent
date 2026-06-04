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

Details:
---------
Tool definitions (OpenAI function-calling schema) and their realizations for all 20+ agent tools. Organized as: (1) basic
tools - ask user question, cron, bash (with permission/per-subprocess/risk-eval), glob/grep, read/write/edit file, skill,
web fetch/search; (2) simulation tools - check simulator, init/copy/query design, launch sim, query run, read log;
(3) MCP tool dispatch via TOOL_NAME_CALL_MCP. Each tool handles permission TUI, logging, and error reporting.
"""
import os
import subprocess
import logging
import shutil

from typing import Any
from datetime import datetime
from rich.progress import Progress
from src.utility import ui_info
from src.context.agent_context import WebFetchCancelled, WebSearchCancelled, AgentContext
from src.tool.cron_support import get_cron_list, create_cron_impl
from src.tool.file_filter_support import glob_impl, grep_impl
from src.tool.file_io_support import read_line_with_limit, match_line_ranges, get_match_debug_info, find_actual_string, ask_edit_tui, check_read_only
from src.tool.simulator_support import clean_stdout_log, clean_stderr_log
from src.tool.skills_support import load_skill_content, get_skill_description
from src.tool.web_support import check_url, web_single_fetch, web_fetch_process
from src.tool.web_support import web_search_top, web_search_process
from src.tool.ask_permission import ask_permission_tui
from src.tool.bash_support import evaluate_bash_risk
from src.tool.ask_question import ask_user_question_tui, AskUserCancelled
from src.constants import *

sys_log = logging.getLogger('logger')


def create_tools_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """create prompts of all available tools"""
    # Agent tools
    prompts: list[dict[str, Any]] = [
        # basic tools
        tool_ask_user_question_def(),
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
        tool_copy_design_def(),
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        try:
            answers = ask_user_question_tui(questions, progress.console, ctx.agent_session)
        finally:
            progress.live.transient = if_tran
            progress.start()
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
        """request permission"""
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"cron pattern: {arguments.get("cron")}, "
                                         f"prompt: {arguments.get("prompt")}, "
                                         f"if_repeat: {arguments.get("if_repeat", True)}, "
                                         f"durable: {arguments.get("durable", False)},",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """creat cron tasks"""
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"task id: {arguments.get("id")}",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """remove cron tasks"""
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, risk, f"bash description: {arguments["description"]}, "
                                         f"risk level: {level} with reason: {reason}. Full command: {arguments["command"]}",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """execute command"""
        command = arguments["command"]
        limit = BASH_COMMAND_VIEW_CHAR_MAX
        if len(command) > limit:
            command_str = command[:limit] + " ... (truncated)"
        else:
            command_str = command
        description = arguments.get("description", "")
        timeout = arguments.get("timeout", BASH_TIMEOUT_MS_DEFAULT)
        sys_log.debug(f"{func_name}: {description} start")
        progress.console.print(f"{func_name}: {description} start", style="bright_black")
        proc = subprocess.Popen(["bash", "-c", command],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            stdout, stderr = proc.communicate(timeout=timeout / 1000)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            sys_log.error(f"{func_name} {CANCELLED_LABEL}: {description} with command: {command_str} is cancelled by user. "
                          f"Command interrupted")
            progress.console.print(f"{func_name} {CANCELLED_LABEL}: {description} with command: {command_str} is "
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
                          f"{description} with command: {command_str} timeout > {timeout / 1000} s. Command interrupted")
            progress.console.print(f"{func_name} {TIMEOUT_LABEL}: "
                                   f"{description} with command: {command_str} timeout > {timeout / 1000} s. Command "
                                   f"interrupted", style="bold red")
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
        sys_log.debug(f"{func_name}: {description} with command {command_str} done")
        progress.console.print(f"{func_name}: {description} with command {command_str} done", style="bright_black")
        return {"status": "DONE",
                "return code": proc.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')}
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name, f"pattern: {arguments.get("pattern")}, "
                                         f"path: {arguments.get("path", os.getcwd())}", progress.console)
        progress.live.transient = if_tran
        progress.start()
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
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
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """grep file"""
        results, if_success, grep_info = grep_impl(arguments, ctx.agent_configs["GREP_FILE_TIMEOUT_S"])
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"path: {arguments["path"]}, "
                                         f"method: {arguments["method"]}, "
                                         f"read-in line: {arguments.get("line_num", "None")}, "
                                         f"offset: {arguments.get("offset", "None")}, "
                                         f"encoding: {arguments.get("encoding", READ_FILE_ENCODING_DEFAULT)}",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"path: {arguments["path"]}, "
                                         f"mode: {arguments.get("mode", WRITE_FILE_MODE_DEFAULT)}, "
                                         f"create_dirs: {arguments.get("create_dirs", True)}, "
                                         f"encoding: {arguments.get("encoding", WRITE_FILE_ENCODING_DEFAULT)}",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token = ask_edit_tui(file_path, actual_old, new_string_norm, raw_line, match_lines, multi_match, ctx, progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
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
                           "- Use this tool with the skill name and optional arguments\n"
                           "- Examples:\n"
                           "  - `skill: \"pdf\"` - invoke the pdf skill\n"
                           "  - `skill: \"review-pr\", args: \"123\"` - invoke with arguments\n"
                           "  - `skill: \"ms-office-suite:pdf\"` - invoke using fully qualified name\n"
                           "Important:\n"
                           "- Available skills and their description are listed in system messages\n"
                           "- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant "
                           f"`{TOOL_NAME_SKILL}` tool BEFORE generating any other response about the task\n"
                           "- NEVER mention a skill without actually calling this tool\n"
                           "- Do not invoke a skill that is already running\n"
                           "- If the skill has ALREADY been loaded (by you or user), this tool will error, follow the "
                           "instructions directly instead of calling this tool again\n",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "string",
                        "description": "Optional arguments for the skill.",
                    },
                    "skill": {
                        "type": "string",
                        "description": "The skill name. E.g., \"translate\", \"review-pr\", or \"pdf\"."
                    }
                },
                "required": ["skill"],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def skill(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> tuple[dict[str, Any], dict[str, str] | None]:
    """tool realization of launching skill with AgentContext"""
    func_name = TOOL_NAME_SKILL
    try:
        name = str(arguments["skill"])
        """permission request"""
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, "{func_name}",
                                         f"skill name: {arguments["skill"]}, "
                                         f"args: {arguments.get("args", "None")}", progress.console)
        progress.live.transient = if_tran
        progress.start()
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"URL: {arguments["url"]}, "
                                         f"prompt: {arguments["prompt"]}", progress.console)
        progress.live.transient = if_tran
        progress.start()
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
        content, content_info, if_redirect, final_url = ui_info.loading_spinner_rap(
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"Web search with keywords {query}", progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}

        """web search"""
        content, content_info = ui_info.loading_spinner_rap(
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, tool_name, f"Tool call from MCP: {mcp_name}", progress.console)
        progress.live.transient = if_tran
        progress.start()
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
            "description": "Create and initialize a design in default value with given id. This tool will fail if the id "
                           "of the design to be created already exists",
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
    func_name = TOOL_NAME_INIT_DESIGN
    try:
        """request permission"""
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"initialize a new design with id {arguments["id"]}", progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """initialize design"""
        design_id = arguments["id"]
        # path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_DESIGN_NAME}{design_id}")
        if os.path.exists(path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Design with id: {design_id} already exists")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Design with id: {design_id} already exists", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Design with id: {design_id} already exists"}
        os.makedirs(path)
        source_path = ctx.agent_configs["SIMULATOR_PATH"] + "/config"
        shutil.copytree(src=source_path, dst=path, dirs_exist_ok=True)
        ctx.design_created.append(design_id)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Design with id: {design_id} initialized")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: Design with id: {design_id} initialized", style="bright_black")
        return {"status": SUCCESS_LABEL, "info": f"Design with id: {design_id} initialized"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Initialize design failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Initialize design failed with error: {e}"}


def tool_copy_design_def() -> dict[str, Any]:
    """tool definition of copying a design (TOOL_NAME_COPY_DESIGN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_COPY_DESIGN,
            "description": "Create a new design by copying an existing design with given id. This tool will fail if the target "
                           "design already exists or source design nonexists",
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
    func_name = TOOL_NAME_COPY_DESIGN
    try:
        """request permission"""
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"copy design with id {arguments["source_id"]} to create a new design with "
                                         f"id {arguments["target_id"]}", progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """copy design"""
        source_id = arguments["source_id"]
        target_id = arguments["target_id"]
        # source_path = "./session/" + ctx.session_uuid + f"/design{source_id}"
        source_path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_DESIGN_NAME}{source_id}")
        # target_path = "./session/" + ctx.session_uuid + f"/design{target_id}"
        target_path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_DESIGN_NAME}{target_id}")
        if not os.path.exists(source_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Source design with id: {source_id} doesn't exist")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Source design with id: {source_id} doesn't exist", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Source design with id: {source_id} doesn't exist"}
        if os.path.exists(target_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Target design with id: {target_id} already exists")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Target design with id: {target_id} already exists", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Target design with id: {target_id} already exists"}
        os.makedirs(target_path)
        shutil.copytree(src=source_path, dst=target_path, dirs_exist_ok=True)
        ctx.design_created.append(target_id)
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Design with id: {target_id} created by design with id: {source_id}")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: Design with id: {target_id} created by design with id: {source_id}", style="bright_black")
        return {"status": SUCCESS_LABEL, "info": f"Design with id: {target_id} created by design with id: {source_id}"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Create design by copying failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Create design by copying failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Create design by copying failed with error: {e}"}


def tool_query_design_def() -> dict[str, Any]:
    """tool definition of querying the list of created designs (TOOL_NAME_QUERY_DESIGN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_DESIGN,
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


def query_design(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the list of created designs with AgentContext"""
    func_name = TOOL_NAME_QUERY_DESIGN
    sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Total num: {len(ctx.design_created)}, list: {ctx.design_created}")
    progress.console.print(f"{func_name} {SUCCESS_LABEL}: Total num: {len(ctx.design_created)}, "
                           f"list: {ctx.design_created}", style="bright_black")
    return {"status": SUCCESS_LABEL,
            "total_num": f"{len(ctx.design_created)}",
            "list": f"{ctx.design_created}"}


def tool_launch_sim_def() -> dict[str, Any]:
    """tool definition of launching the simulator (TOOL_NAME_LAUNCH_SIM)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_LAUNCH_SIM,
            "description": "Launch the simulator with given id of existing design. This tool will fail if:\n"
                           "- target design doesn't exist"
                           "- target design is invalid"
                           "- clean up before the simulation fails"
                           "- simulator terminate with runtime error"
                           "- simulator timeout"
                           "- simulation cancelled by user",
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


def launch_sim(arguments: dict[str, Any], ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of launching the simulator with arguments and AgentContext"""
    func_name = TOOL_NAME_LAUNCH_SIM
    try:
        """request permission"""
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"launch simulation run under design with id: {arguments["id"]}",
                                         progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """check the design"""
        design_id = arguments["id"]
        # design_path = "./session/" + ctx.session_uuid + f"/design{design_id}"
        design_path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_DESIGN_NAME}{design_id}")
        if not os.path.exists(design_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"Design with id: {design_id} doesn't exist. Run is not created. Launch is not performed"}
        """clean up"""
        results1 = subprocess.run([ctx.agent_configs["SIMULATOR_PATH"] + '/clean.bat', "1"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if results1.returncode != 0 or results1.stdout is None:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          "Clean up script exits with error. Run is not created. Launch is not performed")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   "Clean up script exits with error. Run is not created. Launch is not performed", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Clean up script exits with error. Run is not created. Launch is not performed"}
        sys_log.debug(f"{func_name}: clean up done")
        progress.console.print(f"{func_name}: clean up done", style="bright_black")
        """create run"""
        ctx.simulation_launched += 1
        # run_path = "./session/" + ctx.session_uuid + f"/run{ctx.simulation_launched}"
        run_path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_RUN_NAME}{ctx.simulation_launched}")
        if os.path.exists(run_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed", style="bold red")
            return {"status": FAIL_LABEL,
                    "run_id": ctx.simulation_launched,
                    "info": f"Simulation run with id: {ctx.simulation_launched} already exists. Launch is not performed"}
        os.makedirs(run_path)
        sys_log.debug(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} created")
        progress.console.print(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} created", style="bright_black")
        """launch simulation"""
        sys_log.debug(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} start")
        progress.console.print(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} start", style="bright_black")
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
            sys_log.error(f"{func_name} {CANCELLED_LABEL}: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} is cancelled by user. Simulator interrupted")
            progress.console.print(f"{func_name} {CANCELLED_LABEL}: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} is cancelled by user. Simulator interrupted", style="bold red")
            return {"status": CANCELLED_LABEL,
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
            sys_log.debug(f"{func_name}: logs write/copy done")
            sys_log.error(f"{func_name} {TIMEOUT_LABEL}: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                          f"Check logs for details if needed")
            progress.console.print(f"{func_name} {TIMEOUT_LABEL}: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                                   f"Check logs for details if needed", style="bold red")
            return {"status": TIMEOUT_LABEL,
                    "run_id": ctx.simulation_launched,
                    "design_id": design_id,
                    "return code": proc.returncode,
                    "info": f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                            f"{design_id} timeout > {ctx.agent_configs["SIMULATOR_TIMEOUT_S"]} s. Simulator interrupted. "
                            f"Check logs for details if needed"}
        except Exception as e:
            proc.terminate()
            try:
                proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            raise RuntimeError(e)
        sys_log.debug(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} stop")
        progress.console.print(f"{func_name}: simulation run with id: {ctx.simulation_launched} under design with id: {design_id} stop", style="bright_black")
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
        sys_log.debug(f"{func_name}: logs write/copy done")
        progress.console.print(f"{func_name}: logs write/copy done", style="bright_black")
        """check status"""
        if results2.returncode != 0:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                          f"{design_id} failed with error. Check logs for details if needed")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"Launch is performed. Simulation run with id: {ctx.simulation_launched} under design with id: "
                                   f"{design_id} failed with error. Check logs for details if needed", style="bold red")
            return {"status": FAIL_LABEL,
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
        sys_log.debug(f"{func_name} {SUCCESS_LABEL}: "
                      f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without error. Results are ready")
        progress.console.print(f"{func_name} {SUCCESS_LABEL}: "
                               f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without error. Results are ready", style="bright_black")
        return {"status": SUCCESS_LABEL,
                "run_id": ctx.simulation_launched,
                "design_id": design_id,
                "info": f"Simulation run with id: {ctx.simulation_launched} under design with id: {design_id} exits without "
                        f"error. Results are ready"}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Launch simulator failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Launch simulator failed with error: {e}"}


def tool_query_run_def() -> dict[str, Any]:
    """tool definition of querying the amount of launched run (TOOL_NAME_QUERY_RUN)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_QUERY_RUN,
            "description": "Get the amount of launched run. Each run is always start with index of 1 and increase by 1",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        }
    }
    return tool_def


def query_run(ctx: AgentContext, progress: Progress) -> dict[str, Any]:
    """tool realization of querying the amount of launched run with AgentContext"""
    func_name = TOOL_NAME_QUERY_RUN
    sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Total num: {ctx.simulation_launched}")
    progress.console.print(f"{func_name} {SUCCESS_LABEL}: Total num: {ctx.simulation_launched}", style="bright_black")
    return {"status": SUCCESS_LABEL,
            "total_num": f"{ctx.simulation_launched}"}


def tool_read_log_def() -> dict[str, Any]:
    """tool definition of reading the log of the given run (TOOL_NAME_READ_LOG)"""
    tool_def = {
        "type": "function",
        "function": {
            "name": TOOL_NAME_READ_LOG,
            "description": "Read the stdout or stderr log of the simulation run with given id, reading method and line num. "
                           "Results are returned using cat -n format, with line numbers starting from 1. This tool will also "
                           "return the total line count of the log (regardless of read method).\n"
                           "- IMPORTANT: Never start by reading the entire log (`all`) unless the log is known to be very "
                           "short or instructed to do so\n"
                           "- For any unread log, first use `from_bottom` with a moderate number of lines (e.g., 50-100) "
                           "to see the log's end and possible errors\n"
                           "- Once you know the total line count, you can use `from_top` or `from_bottom` to read additional "
                           "chunks, or `offset` to jump to a specific area as needed",
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
                        "description": "How to read the log:\n"
                                        "- `from_top`: Reads the first N lines. Best for seeing the beginning of the log, "
                                       "such as initialization messages or early output\n"
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
                "required": ["id", "log_type", "method"],
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
        if_tran = progress.live.transient
        progress.live.transient = True
        progress.stop()
        token, info = ask_permission_tui(ctx, func_name,
                                         f"run id: {arguments["id"]}, "
                                         f"type: {arguments["log_type"]}, "
                                         f"method: {arguments["method"]}, "
                                         f"read-in line: {arguments.get("line_num", "None")}, "
                                         f"offset: {arguments.get("offset", "None")}", progress.console)
        progress.live.transient = if_tran
        progress.start()
        if not token:
            if info is None:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user"}
            else:
                return {"status": DENIED_LABEL, "info": f"Permission request denied by user with comment: {info}"}
        """check the run"""
        run_id = arguments["id"]
        # run_path = "./session/" + ctx.session_uuid + f"/run{run_id}"
        run_path = os.path.join(SESSION_PATH, ctx.session_uuid, f"{SIM_RUN_NAME}{run_id}")
        if not os.path.exists(run_path):
            sys_log.error(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} doesn't exist")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Run with id: {run_id} doesn't exist", style="bold red")
            return {"status": FAIL_LABEL, "info": f"Run with id: {run_id} doesn't exist"}
        """check the file size"""
        log_type = str(arguments["log_type"]).lower()
        log_path = run_path + "/" + log_type + ".log"
        file_size = os.path.getsize(log_path)
        if file_size > ctx.agent_configs["READ_FILE_MB_LIMIT"] * 1024 * 1024:
            sys_log.error(f"{func_name} {FAIL_LABEL}: "
                          f"Log with type: {log_type} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please modify "
                          f"the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: "
                                   f"Log with type: {log_type} is larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, please "
                                   f"modify the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}", style="bold red")
            return {"status": FAIL_LABEL,
                    "info": f"Log with type: {log_type} IS larger than {ctx.agent_configs["READ_FILE_MB_LIMIT"]} MB, user "
                            f"should modify the `READ_FILE_MB_LIMIT` in {AGENT_CONFIGS_PATH}"}
        """read the log"""
        with open(log_path, 'r', encoding=READ_LOG_ENCODING_DEFAULT) as f:
            log_content = f.read()
        if log_type == "stdout":
            clean_line = clean_stdout_log(log_content)
        elif log_type == "stderr":
            clean_line = clean_stderr_log(log_content)
        else:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid log type: {log_type}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid log type: {log_type}", style="bold red")
            raise RuntimeError(f"Invalid log type: {log_type}")
        log_line: list[str] = []
        for i, line in enumerate(clean_line, start=1):
            log_line.append(f"{i}\t{line}")
        total_line_num = len(log_line)
        """prepare the content"""
        read_line_num: int | None = arguments.get("line_num")
        if read_line_num is not None and read_line_num > READ_LOG_MAX_LINE:
            sys_log.error(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}")
            progress.console.print(f"{func_name} {FAIL_LABEL}: Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}", style="bold red")
            raise RuntimeError(f"Invalid line num: {read_line_num} > {READ_LOG_MAX_LINE}")
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
                # log_str = "\n".join(log_line)
                log_str, truncated, read_lines = read_line_with_limit(log_line, 0, total_line_num - 1, byte_limit, 'utf-8')
            else:
                # log_str = "\n".join(log_line[0:read_line_num])
                log_str, truncated, read_lines = read_line_with_limit(log_line, 0, read_line_num - 1, byte_limit, 'utf-8')
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
                # log_str = "\n".join(log_line)
                log_str, truncated, read_lines = read_line_with_limit(log_line, 0, total_line_num - 1, byte_limit, 'utf-8')
            else:
                # log_str = "\n".join(log_line[-read_line_num:])
                log_str, truncated, read_lines = read_line_with_limit(log_line, total_line_num - read_line_num, total_line_num - 1, byte_limit, 'utf-8')
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
                # log_str = "\n".join(log_line[offset_line_num - 1:offset_line_num - 1 + read_line_num])
                log_str, truncated, read_lines = read_line_with_limit(log_line, offset_line_num - 1, offset_line_num - 2 + read_line_num, byte_limit, 'utf-8')
            else:
                # log_str = "\n".join(log_line[offset_line_num - 1:])
                log_str, truncated, read_lines = read_line_with_limit(log_line, offset_line_num - 1, total_line_num - 1, byte_limit, 'utf-8')
        elif method == "all":
            # log_str = "\n".join(log_line)
            log_str, truncated, read_lines = read_line_with_limit(log_line, 0, total_line_num - 1, byte_limit, 'utf-8')
        else:
            raise RuntimeError(f"Invalid method type: {method}")
        if not truncated:
            sys_log.debug(f"{func_name} {SUCCESS_LABEL}: Run id: {run_id} "
                          f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}")
            progress.console.print(f"{func_name} {SUCCESS_LABEL}: Run id: {run_id} "
                                   f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                                   f"offset: {offset_line_num}", style="bright_black")
            return {"status": SUCCESS_LABEL,
                    "total_line": total_line_num,
                    "log_content": log_str}
        else:
            sys_log.warning(f"{func_name} {TRUNCATED_LABEL}: Run id: {run_id} "
                          f"type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                          f"offset: {offset_line_num}, actual read-in line: {read_lines}. Target read-in part is larger than "
                          f"{ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB and truncated, please modify the `READ_FILE_LLM_KB_LIMIT` "
                          f"in {AGENT_CONFIGS_PATH}")
            progress.console.print(f"{func_name} {TRUNCATED_LABEL}: Run id: {run_id} "
                                   f"Type: {log_type}, method: {method}, total line: {total_line_num}, read-in line: {read_line_num}, "
                                   f"offset: {offset_line_num}, actual read-in line: {read_lines}. Target read-in part is "
                                   f"larger than {ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB and truncated, please "
                                   f"modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}", style="bold yellow")
            return {"status": TRUNCATED_LABEL,
                    "info": f"Target read-in part is larger than {ctx.agent_configs["READ_FILE_LLM_KB_LIMIT"]} KB and truncated, "
                            f"user should modify the `READ_FILE_LLM_KB_LIMIT` in {AGENT_CONFIGS_PATH}",
                    "total_line": read_lines,
                    "log_content": log_str}
    except Exception as e:
        sys_log.error(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}")
        progress.console.print(f"{func_name} {FAIL_LABEL}: Read log failed with error: {e}", style="bold red")
        return {"status": FAIL_LABEL, "info": f"Read log failed with error: {e}"}
