# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.8
Description: Prompts management of the TECoSim agent

Revision:
---------
2026.4.8       Yu Huang      1.0      First implementation
2026.4.15      Yu Huang      1.1      Query prompts and message history
2026.4.16      Yu Huang      1.2      Agent context realization with logic merge
2026.4.22      Yu Huang      1.3      Bash support
2026.4.26      Yu Huang      1.4      Reasoning support
2026.4.29      Yu Huang      1.5      Builtin commands support
2026.5.15      Yu Huang      1.6      Agent skills support
2026.5.21      Yu Huang      1.7      Move get_platform_info, is_git_repo, is_bash_available to basic_utils.py
2026.5.23      Yu Huang      1.8      Stream response display update
2026.5.23      Yu Huang      1.9      Revise the stream response display when content overflow console length
2026.5.28      Yu Huang      2.0      Add read-only paths support
2026.5.29      Yu Huang      2.1      Revise displays of agent message & Fix incorrect empty message judgment
2026.5.31      Yu Huang      2.2      Define used file/dir. paths in constants.py
2026.6.2       Yu Huang      2.3      Add left padding with icon when printing LLM's messages & Revise the mark of skill content
2026.6.3       Yu Huang      2.4      Add flag of if display skills and crons when resuming session
2026.6.5       Yu Huang      2.5      Add --nosystem, --notools, --nocrons support & Bugfix of rendering msgs in non-Markdown format
2026.6.8       Yu Huang      2.6      Bash and ripgrep path configurable support
2026.6.9       Yu Huang      2.7      Revise the system prompts of task tools & Revise the highlight of the IO console print
2026.6.10      Yu Huang      2.8      Revise the system prompts of task tools & Main/Fast model can configure deepseek support dependently &
                                       Add reminder for LLM to manage workflow proactively & Define all inserted message labels in constans.py &
                                       Fix the bug of stream messages handling under direct connection API
2026.6.11      Yu Huang      2.9      Add resume-display preview switches for write_file/bash command/bash result in print_messages &
                                       integrate get_write_render/get_bash_render/get_bash_result_render into history replay

Details:
---------
Prompt assembly and LLM response management. Assembles system prompts (agent role, guidelines, environment, skills). Manages
message history (save/load JSON to session files with serialization). Handles both streaming and non-streaming LLM responses:
token usage tracking, reasoning/content extraction, tool call collection, context limit checking. Provides DeepSeek reasoning
format conversion. Also provides task usage tracking (`update_task_usage`) and task reminder generation (`get_task_reminder`)
for workflow management, with system reminder label display support.
"""
import os
import json
import logging
import rich.box

from typing import Any, Literal
from datetime import datetime
from openai import Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from rich.table import Table
from rich.console import Group, Console
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from src.tool.scoreboard import Scoreboard, Task, tasks_to_info
from src.tool.file_io_support import get_write_render
from src.tool.bash_support import get_bash_render, get_bash_result_render
from src.context.agent_context import AgentContext
from src.utility.basic_utils import (
    get_platform_info, is_git_available, is_git_repo, is_bash_available, is_ripgrep_available, ReasonMD, ContentMD)
from src.constants import *

sys_log = logging.getLogger('logger')


def create_system_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """create prompts of system (agent role, guideline, dynamic boundaries) with AgentContext"""
    """system: agent role"""
    prompts1 = get_agent_role_prompts()
    """system: agent guideline"""
    prompts2 = get_agent_guideline_prompts()
    """system: dynamic boundaries"""
    prompts3 = get_agent_environment_prompts(ctx)
    prompts4 = get_agent_skills_prompts(ctx)
    sys_log.debug("System prompts generated")
    if ctx.agent_configs["MERGE_SYSTEM_PROMPTS"]:
        prompts = prompts1
        prompts[0]["content"] += (prompts2[0]["content"])
        prompts[0]["content"] += (prompts3[0]["content"])
        prompts[0]["content"] += (prompts4[0]["content"])
        ctx.system_prompts = 1
    else:
        prompts = prompts1 + prompts2 + prompts3 + prompts4
        ctx.system_prompts = 4
    sys_log.debug("System prompts assembled")
    return prompts


def get_agent_role_prompts() -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's role"""
    prompts = [{"role": "system", "content":
                "You are TECoSim Agent, developed by Yu Huang (黄雨) from Shanghai Jiao Tong University.\n"}]
    return prompts


def get_agent_guideline_prompts() -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's guideline"""
    prompts = [{"role": "system", "content":
                "You are an interactive agent that embedded with TECoSim to helps user with display panel engineering tasks. "
                "Use the instructions below and the tools available to you to assist the user.\n"
                "# System\n"
                " - All text you output outside of tool calls is displayed to the user. Output text to communicate with "
                "the user. You can use Github-flavored markdown for formatting.\n"
                " - You are embedded with TECoSim (Thermo-Electric Coupling Cross-level Display Simulator), capable of display "
                "panel visual quality, IR drop, and temperature distribution analysis under thermo-electrical coupling effects\n"
                "# Workflow Guidelines\n"
                f"IMPORTANT: Task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, `{TOOL_NAME_QUERY_TASK}`) are "
                f"your primary mechanism for planning and communicating with the user. When receiving any user request, "
                f"follow this flow:\n"
                f"  1. Call `{TOOL_NAME_QUERY_TASK}` to check the progress of the current task. Call it with no arguments "
                f"to get the task list in brief, or with a known task ID to see that specific task's current state in detail\n"
                f"  2. If no relevant tasks exist, call `{TOOL_NAME_CREATE_TASK}` to break down the work into milestones "
                f"(e.g. \"Collect data\"), not single tool calls (e.g. \"Read file A\"). Then start executing them, using "
                f"`{TOOL_NAME_UPDATE_TASK}` to mark progress at each milestone\n"
                f"  3. If relevant tasks exist and not resolved, keep on executing and use `{TOOL_NAME_UPDATE_TASK}` to mark "
                f"progress at each milestone\n"
                f"Make sure to use `{TOOL_NAME_CREATE_TASK}` and `{TOOL_NAME_UPDATE_TASK}` to communicate your plan and "
                f"progress to the user - viewing the task list is always the best way for the user to understand what you're doing\n"
                # f"Task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, `{TOOL_NAME_QUERY_TASK}`) are your primary "
                # f"mechanism for planning and communicating with the user. When receiving any non-trivial user request, "
                # f"call `{TOOL_NAME_CREATE_TASK}` before taking action. Use task tools to manage your workflow:\n"
                # f"   - When the user's request involves 3+ distinct steps → `{TOOL_NAME_CREATE_TASK}` first to plan\n"
                # f"   - When the user's request is ambiguous or open-ended → `{TOOL_NAME_CREATE_TASK}` to clarify scope, "
                # f"then `{TOOL_NAME_ASK_QUESTION}` if needed\n"
                # f"   - A good rule of thumb: each task should represent a meaningful milestone (e.g. \"Set up design\", "
                # f"\"Run simulation\", \"Analyze results\"), not individual tool calls (e.g. \"Read file A\", \"Read file B\"). "
                # f"Create a new task only when entering a new logical phase of work.\n"
                # f"   - After completing a step → `{TOOL_NAME_UPDATE_TASK}` to mark progress and surface the next step\n"
                # f"Use `{TOOL_NAME_CREATE_TASK}` and `{TOOL_NAME_UPDATE_TASK}` to communicate your plan and progress to the "
                # f"user - viewing the task list is the best way for the user to understand what you're doing\n"
                "# Simulation Guidelines\n"
                " - Before the first simulation, you should check if the simulator is available. Only recheck when needed.\n"
                f" - A `{SIM_DESIGN_NAME}` is always needed before launching simulator for panel design or evaluation. "
                f"Each `{SIM_DESIGN_NAME}` is identified by a single integer id starts from 1, and you should managed the all "
                f"designs' ids and don't assume that user knows the ids. Each design can have multiple revisions, each revision "
                f"is a version of the design. New revisions are created when the design is modified. Each design is created "
                f"from scratch with default configuration. Designs cannot be deleted after creation.\n"
                # TODO: Support copy from existing designs and modify existing designs in future versions\n
                f" - After each simulation, the following contents are available with the unit of "
                f"`{SIM_RUN_NAME}`:\n"
                "    - 1) simulator's stdout log (read via `read_log`)\n"
                "    - 2) simulator's stderr log (read via `read_log`)\n"
                # "    - 3) TODO: other content\n"
                f"Each launch of simulator will create a `{SIM_RUN_NAME}` and each run is identified by a single integer "
                f"id starts from 1. Each run is read-only and its id is automatically managed.\n"
                "# User Requirements\n"
                " - The user will primarily request you to perform display panel engineering tasks. These may include "
                "designing a display panel from scratch with core target metrics, validating specific panel's IR drop severity "
                "or validating specific panel's temperature distribution under certain working scenarios, and more.\n"
                " - When given an unclear or generic instruction, consider it in the context of display panel engineering "
                f"tasks, capability of TECoSim and other available tools. Call `{TOOL_NAME_ASK_QUESTION}` to clarify the user's "
                f"idea if needed\n"
                " - You are highly capable and often allow users to complete ambitious tasks that would otherwise be too "
                "complex or take too long. You should defer to user judgement about whether a task is too large to attempt.\n"
                " - Avoid giving time estimates or predictions for how long tasks will take, whether for your own work or "
                "for users planning projects. Focus on what needs to be done, not how long it might take.\n"
                "# Tone and style\n"
                " - Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.\n"
                " - Your responses should be short and concise.\n"
                " - Do not use a colon before tool calls. Your tool calls may not be shown directly in the output, so text "
                "like \"Let me read the file:\" followed by a read tool call should just be \"Let me read the file.\" with a period.\n"
                "# Output efficiency\n"
                "Keep text output brief and direct. Lead with the answer or action, not the reasoning. Skip filler words, "
                "preamble, and unnecessary transitions. Do not restate what the user said - just do it. When explaining, "
                "include only what is necessary for the user to understand.\n"
                "Focus text output on:\n"
                " - Decisions that need the user's input\n"
                " - High-level task status updates at natural milestones\n"
                " - Errors or blockers that change the tasks or plans\n"
                "If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations. "
                "This does not apply to code or tool calls.\n"
                "# Session-specific guidance\n"
                " - If a user denies your tool call, they may provide a comment explaining why. If you don't understand, "
                f"use {TOOL_NAME_ASK_QUESTION} to ask them\n"
                f" - IMPORTANT: Only use `{TOOL_NAME_SKILL}` for skills listed in user-invocable skills section, do not guess\n"
                " - User can manually load full prompt of skill to context with /<skill-name>\n"}]
                # " TODO:- Use the Agent tool with specialized agents when the task at hand matches the agent's description. "
                # "Subagents are valuable for parallelizing independent queries or for protecting the main context window "
                # "from excessive results, but they should not be used excessively when not needed. Importantly, avoid duplicating "
                # "work that subagents are already doing - if you delegate research to a subagent, do not also perform the "
                # "same searches yourself.\n"
    return prompts


def get_agent_environment_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's dynamic boundaries with AgentContext"""
    now = datetime.now()
    git_available = is_git_available()
    if git_available:
        git_prompts = " - Is git available: True\n"
    else:
        git_prompts = f" - Is git available: False\n"
    bash_available = is_bash_available(ctx.agent_configs["BASH_PATH"])
    ripgrep_available = is_ripgrep_available(ctx.agent_configs["RIPGREP_PATH"])
    if bash_available:
        bash_prompts = " - Is bash available: True\n"
    else:
        bash_prompts = (f" - Is bash available: False. User should check if bash is available in path: {ctx.agent_configs["BASH_PATH"]} "
                        f"defined in `BASH_PATH`\n")
    if ripgrep_available:
        grep_prompts = f" - Is `{TOOL_NAME_GREP_FILE}` available: True\n"
    else:
        grep_prompts = (f" - Is `{TOOL_NAME_GREP_FILE}` available: False. User should check if ripgrep is available in path: "
                        f"{ctx.agent_configs["RIPGREP_PATH"]} defined in `RIPGREP_PATH`")
    primary_dir_prompts = f" - Primary working directory: {os.getcwd()}"
    if git_available:
        primary_dir_prompts += f" (is git repository: {str(is_git_repo(os.getcwd()))})"
    primary_dir_prompts += "\n"
    prompts = [{"role": "system", "content":
                "# Environment\n"
                f"Today is: {now.strftime("%Y-%m-%d")}\n"
                "You have been invoked in the following environment: \n"
                f" - Platform: {get_platform_info()[0]} {get_platform_info()[1]} version: {get_platform_info()[2]}\n"
                f"{bash_prompts}"
                f"{git_prompts}"
                f"{grep_prompts}"
                f"{primary_dir_prompts}"
                f" - Path of simulator: {ctx.agent_configs["SIMULATOR_PATH"]}\n"
                f" - You are powered by the LLM: {ctx.api_configs["MAIN_MODEL_NAME"]}\n"}]
    return prompts


def get_agent_skills_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's skills with AgentContext"""
    limit = ctx.agent_configs["SKILL_DESC_CHAR_LIMIT"]
    skill_list_str = ""
    for skill in ctx.skills:
        if len(skill['description']) > limit:
            skill_list_str += f" - {skill["name"]}: {skill['description'][:limit]}...\n"
        else:
            skill_list_str += f" - {skill["name"]}: {skill['description']}\n"
    if len(ctx.skills) > 0:
        prompts = [{"role": "system", "content":
                    f"The following skills are user-invocable with the `{TOOL_NAME_SKILL}` tool:\n"
                    f"{skill_list_str}"}]
    else:
        prompts = [{"role": "system", "content":
                    f"The following skills are user-invocable with the `{TOOL_NAME_SKILL}` tool:\n"
                    f"(No available skill)\n)"}]
    return prompts


def update_task_usage(ctx: AgentContext, tool_calls: list[dict[str, Any]] | None, check_from: Literal["tool_call", "chat"]):
    """track whether LLM uses task tools for workflow management"""
    if check_from == "tool_call":
        if tool_calls is not None:
            if_use_task = False
            for tool_call in tool_calls:
                if tool_call["function"]["name"] in (TOOL_NAME_CREATE_TASK, TOOL_NAME_QUERY_TASK, TOOL_NAME_UPDATE_TASK):
                    if_use_task = True
                    break
            if if_use_task:
                ctx.task_tool_unuse = 0
            else:
                ctx.task_tool_unuse += 1
    elif check_from == "chat":
        ctx.task_tool_unuse += 1


def get_task_reminder(ctx: AgentContext, board: Scoreboard, remind_from: Literal["tool_call", "user_input"]) -> str | None:
    """generate task reminder based on current task state and remind source
    """
    info = ""
    if_remind = False
    if remind_from == "tool_call":
        """
        When after a round of tool call, remind LLM about task when:
        1). Never use task tool during recent `REMIND_TASK_TOOL_GAP` rounds of tool call
        """
        if ctx.task_tool_unuse > ctx.agent_configs["REMIND_TASK_TOOL_GAP"]:
            if_remind = True
            info += (f"You never use any task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, `{TOOL_NAME_QUERY_TASK}`) "
                     f"to manage your workflow during latest {ctx.task_tool_unuse} rounds of tool call or chat.\n")
            unresolved_tasks = board.list_unresolved_tasks(ctx.agent_id)
            unclaimed_tasks = board.list_unclaimed_tasks()
            if len(unresolved_tasks) == len(unclaimed_tasks) == 0:
                info += (f"Make sure using `{TOOL_NAME_CREATE_TASK}` to break down the work into milestones and communicate "
                         f"your plan and progress to the user with `{TOOL_NAME_UPDATE_TASK}`\n")
            if len(unresolved_tasks) > 0:
                info += (f"There are {len(unresolved_tasks)} tasks owned by you but not resolved (IDs: "
                         f"{[task["task_id"] for task in unresolved_tasks]})\n")
            if len(unclaimed_tasks) > 0:
                info += (f"There are {len(unresolved_tasks)} tasks not claimed by any agent (IDs: "
                         f"{[task["task_id"] for task in unclaimed_tasks]})\n")
    if remind_from == "user_input":
        """
        When user_input, remind LLM about task when:
        1). There are unresolved tasks owned by this agent
        2). There are unclaimed tasks
        3). Never use task tool during recent `REMIND_TASK_CHAT_GAP` rounds of chat
        """
        unresolved_tasks = board.list_unresolved_tasks(ctx.agent_id)
        unclaimed_tasks = board.list_unclaimed_tasks()
        tasks: list[Task] = unresolved_tasks + unclaimed_tasks
        if len(tasks) > 0:
            if_remind = True
            tasks_info = tasks_to_info(tasks, ctx.agent_id)
            info += (f"There are still {len(tasks)} tasks needs your consideration:\n"
                     f"{tasks_info}\n"
                     f"Use task tools to manage your workflow\n")
        elif ctx.task_tool_unuse > ctx.agent_configs["REMIND_TASK_CHAT_GAP"]:
            if_remind = True
            info += (f"You haven't use any task tools to manage your workflow during latest {ctx.task_tool_unuse} rounds "
                     f"of chat or tool call. Make sure using task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, "
                     f"`{TOOL_NAME_QUERY_TASK}`) proactively.\n")

    return info.strip() if if_remind else None


def query_prompts(ctx: AgentContext, session_uuid: str | None, console: Console) -> list[dict[str, Any]]:
    """create new prompts or resume prompts from persistence file with AgentContext and given uuid"""
    if not ctx.args.nosystem:
        messages = create_system_prompts(ctx)
    else:
        messages = []
        sys_log.debug("System prompts in main agent are disabled")
        console.print("System prompts in main agent are disabled", style=f"bold {MAJOR_COLOR1}")
    if session_uuid is None:
        pass
    else:
        resumed_prompts = read_messages(session_uuid, console)
        print_messages(resumed_prompts, ctx, console)
        messages = messages + resumed_prompts
    return messages


def read_messages(session_uuid: str, console: Console) -> list[dict[str, Any]]:
    """read messages (exclude system) from persistence file with given uuid"""
    # path = "./session/" + session_uuid + "/messages.json"
    path = os.path.join(SESSION_PATH, session_uuid, MESSAGES_NAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        sys_log.debug(f"Messages of session {session_uuid} loaded")
        console.print(f"[{MAJOR_COLOR2}]Messages[/{MAJOR_COLOR2}] of session [bright_black]{session_uuid}[/bright_black] loaded")
        return messages
    except Exception as e:
        sys_log.error(f"Failed to load the messages of session {session_uuid} with error: {e}")
        console.print(f"Failed to load the messages of session {session_uuid} with error: {e}", style="bold red")
        raise RuntimeError(e)


def print_messages(messages: list[dict[str, Any]], ctx: AgentContext, console: Console):
    """print the given messages (exclude system) with AgentContext"""
    try:
        as_md: bool = ctx.agent_configs["RENDER_RESPONSE_AS_MD"]
        display_sys_reminder = ctx.agent_configs["RESUME_DISPLAY_SYS_REMINDER"]
        sys_reminder_str = Text("<A system reminder is inserted, content is not displayed>", style=f"bold {MAJOR_COLOR1}")
        skill_str = Text("<A skill is invoked, content is not displayed>", style=f"bold {MAJOR_COLOR1}")
        display_skill = ctx.agent_configs["RESUME_DISPLAY_SKILLS"]
        cron_str = Text("<Cron tasks are invoked, content is not displayed>", style=f"bold {MAJOR_COLOR1}")
        display_cron = ctx.agent_configs["RESUME_DISPLAY_CRONS"]
        display_write = ctx.agent_configs["RESUME_DISPLAY_WRITE_PREVIEW"]
        display_bash = ctx.agent_configs["RESUME_DISPLAY_BASH_PREVIEW"]
        display_bash_result = ctx.agent_configs["RESUME_DISPLAY_BASH_RESULT"]
        tool_id_map: dict[str, str] = {}
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                if (not display_sys_reminder) and (SYS_REMINDER_START_LABEL in msg["content"]) and (SYS_REMINDER_END_LABEL in msg["content"]):
                    console.print(Panel(sys_reminder_str, box=rich.box.SQUARE))
                    continue
                if (not display_skill and ("skill_directory" in msg["content"]) and (SKILL_START_LABEL in msg["content"])
                        and (SKILL_END_LABEL in msg["content"])):
                    console.print(Panel(skill_str, box=rich.box.SQUARE))
                    continue
                if not display_cron and (CRON_START_LABEL in msg["content"]) and (CRON_END_LABEL in msg["content"]):
                    console.print(Panel(cron_str, box=rich.box.SQUARE))
                    continue
                user_prefix_str = Text("History user input:\n", style=f"bright_black")
                user_prefix_str.append(f"{AGENT_CONSOLE_ICON} " + msg["content"], style="white")
                console.print(Panel(user_prefix_str, box=rich.box.SQUARE))
            elif msg["role"] == "assistant":
                """display reasoning"""
                assistant_reasoning = get_reasoning(msg)
                if assistant_reasoning not in (None, ""):
                    console.print("\n")
                    t = Table(show_header=False, show_edge=False, padding=0,
                              box=None, collapse_padding=True)
                    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True,
                                  vertical="top")
                    t.add_column(vertical="top")
                    if as_md:
                        t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                                  ReasonMD("{Think}: " + assistant_reasoning))
                    else:
                        t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                                  Text("{Think}: " + assistant_reasoning, style=REASON_STYLE))
                    console.print(t)
                    console.print("")

                """display chat"""
                if msg["content"] not in (None, ""):
                    if assistant_reasoning in (None, ""):
                        console.print("")
                    t = Table(show_header=False, show_edge=False, padding=0,
                              box=None, collapse_padding=True)
                    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True,
                                  vertical="top")
                    t.add_column(vertical="top")
                    if as_md:
                        t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), ContentMD(msg["content"]))
                    else:
                        t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), Text(msg["content"], style=CONTENT_STYLE))
                    console.print(t)
                    console.print("")
                if msg["tool_calls"] is not None:
                    for tool_calls in msg["tool_calls"]:
                        tool_name = tool_calls["function"]["name"]
                        console.print(f"Tool used: [{MAJOR_COLOR1}]{tool_name}[/{MAJOR_COLOR1}]", style="bright_black")
                        if tool_calls.get("id"):
                            tool_id_map[tool_calls["id"]] = tool_name
                        try:
                            args = json.loads(tool_calls["function"]["arguments"])
                        except (json.JSONDecodeError, TypeError, KeyError):
                            args = {}
                        if display_write and tool_name == TOOL_NAME_WRITE_FILE:
                            console.print(get_write_render(args.get("path", ""), args.get("content", "")))
                        if display_bash and tool_name == TOOL_NAME_BASH:
                            console.print(get_bash_render(args.get("command", "")))
            elif msg["role"] == "tool":
                if display_bash_result and msg.get("tool_call_id"):
                    matched_name = tool_id_map.get(msg["tool_call_id"], "")
                    if matched_name == TOOL_NAME_BASH:
                        try:
                            result = json.loads(msg["content"])
                        except (json.JSONDecodeError, TypeError):
                            result = {}
                        stdout = result.get("stdout", "")
                        stderr = result.get("stderr", "")
                        if stdout or stderr:
                            console.print(get_bash_result_render(stdout, stderr))
                continue
            else:
                sys_log.debug(f"Unknown role: {msg["role"]} in history massages")
                continue
    except Exception as e:
        sys_log.error(f"Failed to print the history messages with error: {e}")
        console.print(f"Failed to print the history messages with error: {e}", style="bold red")
        raise RuntimeError(e)


def save_messages(ctx: AgentContext, console: Console, mute: bool = False):
    """save messages (exclude system) to persistence file of AgentContext"""
    try:
        serializable_messages = []
        for msg in ctx.messages:
            if msg["role"] == "system":
                continue
            elif hasattr(msg, "model_dump"):
                serializable_messages.append(msg.model_dump(mode="json"))
            elif isinstance(msg, dict):
                serializable_messages.append(msg.copy())
            else:
                serializable_messages.append(dict(msg))
        if not mute:
            sys_log.debug(f"Messages of session {ctx.session_uuid} converted")
            console.print(f"[{MAJOR_COLOR2}]Messages[/{MAJOR_COLOR2}] of session [bright_black]{ctx.session_uuid}[/bright_black] converted")

        # path = "./session/" + ctx.session_uuid + "/messages.json"
        path = os.path.join(SESSION_PATH, ctx.session_uuid, MESSAGES_NAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable_messages, f, indent=2, ensure_ascii=False)
        if not mute:
            sys_log.debug(f"Messages of session {ctx.session_uuid} saved")
            console.print(f"[{MAJOR_COLOR2}]Messages[/{MAJOR_COLOR2}] of session [bright_black]{ctx.session_uuid}[/bright_black] saved")
    except Exception as e:
        sys_log.error(f"Failed to save the messages of session {ctx.session_uuid} with error: {e}")
        console.print(f"Failed to save the messages of session {ctx.session_uuid} with error: {e}", style="bold red")
        raise RuntimeError(e)


def get_reasoning(message: dict[str, Any]) -> str | None:
    """get the reasoning contents of input message"""
    if "reasoning" in message:
        return message.get('reasoning')
    if "reasoning_details" in message:
        return message.get('reasoning_details')
    if "reasoning_content" in message:
        return message.get('reasoning_content')
    return None


def get_reasoning_stream(delta: ChoiceDelta) -> str:
    """get the reasoning contents in stream delta"""
    if hasattr(delta, 'reasoning'):
        if delta.reasoning is not None:
            return delta.reasoning
    if hasattr(delta, 'reasoning_details'):
        if delta.reasoning_details is not None:
            return delta.reasoning_details
    if hasattr(delta, 'reasoning_content'):
        if delta.reasoning_content is not None:
            return delta.reasoning_content
    return ""


def deepseek_support(message: dict[str, Any]) -> dict[str, Any]:
    """convert the input message with deepseek supported format"""
    if "reasoning_details" in message:
        del message["reasoning_details"]
        # print("reasoning_details")
    if "reasoning" in message:
        # print("reasoning")
        if "reasoning_content" in message:
            # print("reasoning_content")
            del message["reasoning"]
        else:
            message["reasoning_content"] = message["reasoning"]
            del message["reasoning"]
    if "reasoning_content" not in message:
        message["reasoning_content"] = None
    return message


def llm_response_manage(response, ctx: AgentContext, console: Console) -> list[dict[str, Any]] | None:
    """top method of managing LLM responses in main agent-loop"""
    if not ctx.api_configs["MAIN_MODEL_STREAM"]:
        too_calls = llm_nonstream_manage(response, ctx, console)
        return too_calls
    else:
        too_calls = llm_stream_manage(response, ctx, console)
        return too_calls


def llm_nonstream_manage(response: ChatCompletion, ctx: AgentContext, console: Console) -> list[dict[str, Any]] | None:
    """realization of managing stream LLM responses in main agent-loop"""

    """check the type"""
    if type(response) is not ChatCompletion:
        raise RuntimeError(f"Invalid response type, need ChatCompletion but got {type(response)}")

    """check finish reason"""
    finish_reason = response.choices[0].finish_reason
    sys_log.debug(f"Finish reason: {finish_reason}")
    if finish_reason is None:
        sys_log.warning(f"LLM's response is not finished")
        console.print(f"LLM's response is not finished", style="bold yellow")
    if finish_reason == "length":
        sys_log.error(f"LLM out of input/output context")
        console.print(f"LLM out of input/output context", style="bold red")
    if finish_reason == "content_filter":
        sys_log.warning(f"LLM's response has been filtered")
        console.print(f"LLM's response has been filtered", style="bold yellow")

    """check the usage"""
    usage = response.usage
    if usage is not None:
        ctx.total_input_tokens += usage.prompt_tokens
        ctx.last_input_tokens = usage.prompt_tokens
        ctx.total_output_tokens += usage.completion_tokens
        ctx.last_output_tokens = usage.completion_tokens
        ctx.total_tokens += usage.total_tokens
        ctx.last_tokens = usage.total_tokens
        if usage.prompt_tokens_details is not None:
            cached_tokens = usage.prompt_tokens_details.cached_tokens
            uncached_tokens = usage.prompt_tokens - cached_tokens  # uncached input tokens
            ctx.total_uncached_tokens += uncached_tokens
        else:
            cached_tokens = None
            uncached_tokens = None
        sys_log.debug(f"Token usage: input= +{usage.prompt_tokens} ({ctx.total_input_tokens}), "
                      f"output= +{usage.completion_tokens} ({ctx.total_output_tokens}), "
                      f"total= +{usage.total_tokens} ({ctx.total_tokens}), "
                      f"cached= {cached_tokens}, "
                      f"uncached= +{uncached_tokens} ({ctx.total_uncached_tokens})")
    else:
        sys_log.warning("Response usage is None")
        console.print("Response usage is None", style="bold yellow")

    """message dump and conversion"""
    dumped_msg = response.choices[0].message.model_dump(mode="json")
    if ctx.api_configs["MAIN_MODEL_DEEPSEEK_SUPPORT"]:
        dumped_msg = deepseek_support(dumped_msg)
    ctx.messages.append(dumped_msg)
    assistant_reasoning = get_reasoning(dumped_msg)
    assistant_chat: str | None = dumped_msg.get("content", None)
    # (string, will be loaded to json when called)
    assistant_tool_calls: list[dict[str, Any]] | None = dumped_msg.get("tool_calls", None)

    """count update"""
    if assistant_reasoning is not None:
        ctx.reasoning_prompts += 1
    if assistant_chat is not None:
        ctx.content_prompts += 1

    """validate response"""
    if (assistant_chat is None) and (assistant_tool_calls is None):
        if assistant_reasoning is None:
            raise RuntimeError("Output and Tool calls in LLM's message are both empty")
        else:
            sys_log.warning(f"There is only reasoning content in LLM's message")
            console.print(f"There is only reasoning content in LLM's message", style="bold yellow")

    """check context limits"""
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"]:
        sys_log.error(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens")
        console.print(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens", style="bold red")
        raise RuntimeError(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens")
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"] * ctx.agent_configs["CONTEXT_THRESHOLD"]:
        sys_log.warning(f"LLM's context >= {100 * ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context")
        console.print(f"LLM's context >= {100 * ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context",
                      style="bold yellow")

    """print the final content"""
    console.print(get_block_render(assistant_reasoning, assistant_chat, ctx.agent_configs["RENDER_RESPONSE_AS_MD"]))

    return assistant_tool_calls


def get_block_render(collected_reasoning: str | None, collected_content: str | None, as_md: bool) -> Group:
    """get the render of the non-stream messages"""
    parts = []

    """display reasoning"""
    if collected_reasoning not in (None, ""):
        parts.append(Text("\n"))

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top")
        if as_md:
            t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                      ReasonMD("{Think}: " + collected_reasoning))
        else:
            t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                      Text("{Think}: " + collected_reasoning, style=REASON_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    """display chat"""
    if collected_content not in (None, ""):
        if collected_reasoning in (None, ""):
            parts.append(Text("\n"))

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top")
        if as_md:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), ContentMD(collected_content))
        else:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), Text(collected_content, style=CONTENT_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    return Group(*parts)


def get_stream_render(collected_reasoning: str | None, collected_content: str | None, as_md: bool) -> Group:
    """get the render of the stream messages with smart truncation for long content"""
    max_reasoning_lines = STREAM_DISPLAY_MAX_REASON_LINE
    max_content_lines = STREAM_DISPLAY_MAX_CONTENT_LINE
    parts = []

    """display reasoning with truncation for long output"""
    if collected_reasoning not in (None, ""):
        reason_lines = collected_reasoning.split('\n')
        parts.append(Text("\n"))
        if len(reason_lines) > max_reasoning_lines:
            # Show indicator and latest lines when reasoning is too long
            indicator = Text(f"[", style=f"bright_black")
            indicator.append(f"{AGENT_CONSOLE_ICON}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" generating reasoning..., ", style=f"bright_black")
            indicator.append(f"{len(reason_lines)}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" lines total, showing latest ", style=f"bright_black")
            indicator.append(f"{max_reasoning_lines}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" lines]\n", style=f"bright_black")
            parts.append(indicator)
            reason_display = '\n'.join(reason_lines[-max_reasoning_lines:])
            reason_display = reason_display.lstrip()
            reason_display = reason_display.rstrip()
        else:
            reason_display = collected_reasoning

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top")
        if as_md:
            t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE), ReasonMD("{Think}: " + reason_display))
        else:
            t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE), Text("{Think}: " + reason_display, style=REASON_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    """display chat with truncation for long output"""
    if collected_content not in (None, ""):
        if collected_reasoning in (None, ""):
            parts.append(Text("\n"))
        content_lines = collected_content.split('\n')
        if len(content_lines) > max_content_lines:
            # Show indicator and latest lines when content is too long
            indicator = Text(f"[", style=f"bright_black")
            indicator.append(f"{AGENT_CONSOLE_ICON}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" generating content..., ", style=f"bright_black")
            indicator.append(f"{len(content_lines)}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" lines total, showing latest ", style=f"bright_black")
            indicator.append(f"{max_content_lines}", style=f"bold {MAJOR_COLOR1}")
            indicator.append(f" lines]\n", style=f"bright_black")
            parts.append(indicator)
            display_content = '\n'.join(content_lines[-max_content_lines:])
            display_content = display_content.lstrip()
            display_content = display_content.rstrip()
        else:
            display_content = collected_content

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top")
        if as_md:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), ContentMD(display_content))
        else:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), Text(display_content, style=CONTENT_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    return Group(*parts)


def llm_stream_manage(response: Stream[ChatCompletionChunk], ctx: AgentContext, console: Console) -> list[dict[str, Any]] | None:
    """realization of managing stream LLM responses in main agent-loop"""

    """initialize collectors for streaming response"""
    collected_reasoning = ""
    collected_content = ""
    collected_tool_calls: dict[int, dict[str, Any]] = {}  # index -> tool_call dict

    final_usage = None
    final_finish_reason = None
    as_md = ctx.agent_configs["RENDER_RESPONSE_AS_MD"]

    """process each chunk"""
    with Live(get_stream_render(collected_reasoning, collected_content, as_md),
              refresh_per_second=STREAM_DISPLAY_REFRESH_RATE, console=console, transient=True) as live:
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Collect usage if available (some providers send it in the last chunk)
            if chunk.usage:
                final_usage = chunk.usage

            # Collect finish reason
            if finish_reason:
                final_finish_reason = finish_reason

            # Collect content
            if delta.content:
                collected_content += delta.content

            # Collect reasoning (for DeepSeek and similar models)
            collected_reasoning += get_reasoning_stream(delta)

            """collect tool calls"""
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    index = tool_call_delta.index

                    # Initialize tool call entry if new index
                    if index not in collected_tool_calls:
                        collected_tool_calls[index] = {
                            "id": None,
                            "type": "function",
                            "function": {
                                "name": "",
                                "arguments": ""
                            },
                            "index": index
                        }
                    tc = collected_tool_calls[index]

                    # Accumulate tool call ID
                    if tool_call_delta.id:
                        tc["id"] = tool_call_delta.id  # ID is complete

                    # Accumulate function name
                    if tool_call_delta.function and tool_call_delta.function.name:
                        tc["function"]["name"] += tool_call_delta.function.name

                    # Accumulate function arguments (string, will be loaded to json when called)
                    if tool_call_delta.function and tool_call_delta.function.arguments:
                        tc["function"]["arguments"] += tool_call_delta.function.arguments
            """update display"""
            live.update(get_stream_render(collected_reasoning, collected_content, as_md))

    """print the final content"""
    console.print(get_block_render(collected_reasoning, collected_content, as_md))

    """check finish reason"""
    sys_log.debug(f"Finish reason: {final_finish_reason}")
    if final_finish_reason is None:
        sys_log.warning(f"LLM's response is not finished")
        console.print(f"LLM's response is not finished", style="bold yellow")
    if final_finish_reason == "length":
        sys_log.error(f"LLM out of input/output context")
        console.print(f"LLM out of input/output context", style="bold red")
    if final_finish_reason == "content_filter":
        sys_log.warning(f"LLM's response has been filtered")
        console.print(f"LLM's response has been filtered", style="bold yellow")

    """count update"""
    if collected_reasoning not in (None, ""):  # "" is ignored since default is ""
        ctx.reasoning_prompts += 1
    if collected_content not in (None, ""):  # "" is ignored since default is ""
        ctx.content_prompts += 1

    """check the usage"""
    if final_usage is not None:
        ctx.total_input_tokens += final_usage.prompt_tokens
        ctx.last_input_tokens = final_usage.prompt_tokens
        ctx.total_output_tokens += final_usage.completion_tokens
        ctx.last_output_tokens = final_usage.completion_tokens
        ctx.total_tokens += final_usage.total_tokens
        ctx.last_tokens = final_usage.total_tokens
        if final_usage.prompt_tokens_details is not None:
            cached_tokens = final_usage.prompt_tokens_details.cached_tokens
            uncached_tokens = final_usage.prompt_tokens - cached_tokens  # uncached input tokens
            ctx.total_uncached_tokens += uncached_tokens
        else:
            cached_tokens = None
            uncached_tokens = None
        sys_log.debug(f"Token usage: input= +{final_usage.prompt_tokens} ({ctx.total_input_tokens}), "
                      f"output= +{final_usage.completion_tokens} ({ctx.total_output_tokens}), "
                      f"total= +{final_usage.total_tokens} ({ctx.total_tokens}), "
                      f"cached= {cached_tokens}, "
                      f"uncached= +{uncached_tokens} ({ctx.total_uncached_tokens})")
    else:
        sys_log.warning("Response usage is None")
        console.print("Response usage is None", style="bold yellow")

    """build the complete message from collected parts"""
    if collected_tool_calls:
        converted_tool_calls: list[dict[str, Any]] = [
            collected_tool_calls[i] for i in sorted(collected_tool_calls.keys())
        ]
    else:
        converted_tool_calls = None

    # Build the message dict (matching non-streaming format)
    dumped_msg = {
        "role": "assistant",
        "content": collected_content if collected_content else None,
        "reasoning": collected_reasoning if collected_reasoning else None,
        "tool_calls": converted_tool_calls if converted_tool_calls else None,
    }

    """apply deepseek support if needed"""
    if ctx.api_configs["MAIN_MODEL_DEEPSEEK_SUPPORT"]:
        dumped_msg = deepseek_support(dumped_msg)

    """append to conversation history"""
    ctx.messages.append(dumped_msg)

    """extract parts for display"""
    assistant_reasoning = get_reasoning(dumped_msg)
    assistant_chat = dumped_msg.get("content")

    """validate response"""
    if (assistant_chat is None or assistant_chat == "") and (converted_tool_calls is None):
        if assistant_reasoning is None or assistant_reasoning == "":
            raise RuntimeError("Output and Tool calls in LLM's message are both empty")
        else:
            sys_log.warning(f"There is only reasoning content in LLM's message")
            console.print(f"There is only reasoning content in LLM's message", style="bold yellow")

    """check context limits"""
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"]:
        sys_log.error(f"LLM out of context: {ctx.api_configs['MAIN_MODEL_CONTEXT']} tokens")
        console.print(f"LLM out of context: {ctx.api_configs['MAIN_MODEL_CONTEXT']} tokens", style="bold red")
        raise RuntimeError(f"LLM out of context: {ctx.api_configs['MAIN_MODEL_CONTEXT']} tokens")
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"] * ctx.agent_configs["CONTEXT_THRESHOLD"]:
        sys_log.warning(f"LLM's context >= {100 * ctx.agent_configs['CONTEXT_THRESHOLD']}% maximum context")
        console.print(f"LLM's context >= {100 * ctx.agent_configs['CONTEXT_THRESHOLD']}% maximum context",
                      style="bold yellow")

    return converted_tool_calls
