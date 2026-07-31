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
                                      integrate get_syntax_render/get_bash_render/get_bash_result_render into history replay
2026.6.11      Yu Huang      3.0      Add tools name display with color gradient in stream mode & Add switch if displaying the reasoning content
2026.6.12      Yu Huang      3.1      Upgrade workflow guidelines to CONSTRAINT-level mandate (3+ steps MUST create_task) with Good/Bad examples
2026.6.13      Yu Huang      3.2      Add subagent display in print_messages + migrate save/read_messages to file_io_support
2026.6.14      Yu Huang      3.3      Fix: skill description None guard, cached_tokens None guard
2026.6.29      Yu Huang      3.4      Fix: stream collectors None sentinel, reasoning-only content patch, falsy conversion removal
2026.6.29      Yu Huang      3.5      Resume display: ask_question answers + spawn_agent summaries (fg/bg)
2026.6.30      Yu Huang      3.6      Revise visuals of messages print (reminders, crons, skills, subagents) when resuming session
2026.7.3       Yu Huang      3.7      Revise visuals of messages print (create/query/remove crons, glob, query) when resuming session
2026.7.3       Yu Huang      3.8      Fix: overflow of printing LLM response when a line is too long
2026.7.15-16   Yu Huang      3.9      Add WeChat bot interaction support
2026.7.17      Yu Huang      4.0      Fix: last response of LLM won't be missed if bot keep sending WeChat msg
2026.7.18      Yu Huang      4.1      Revise WeChat Bot typing status & Support of fixing orphan and missing tool results in context
2026.7.23      Yu Huang      4.2      Add launch support in arbitrary path & Revise visibility of cron/web/WeChat tool calls
2026.7.26      Yu Huang      4.3      Fix: prevent orphan lines in stream messages display with final live.update
2026.7.28      Yu Huang      4.4      Support of customizable system prompts of main agent & replace --nosystem with --override_prompts
                                      & render user history messages as Markdown

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
from src.tool.file_io_support import read_messages, get_syntax_render
from src.tool.bash_support import get_bash_render, get_bash_result_render
from src.tool.ask_question import get_answers_render
from src.tool.web_support import get_webfetch_str
from src.tool.file_filter_support import get_grep_cmd
from src.tool.cron_support import get_cron_create_str
from src.agent.agent_types import SubAgentProgress, AgentStatus
from src.utility.ui_info import render_subagent_line
from src.context.agent_context import AgentContext
from src.utility.basic_utils import (
    get_platform_info, is_git_available, is_git_repo, is_bash_available, is_ripgrep_available, ReasonMD, ContentMD,
    grad_color_hex_list)
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
                f"Task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, `{TOOL_NAME_QUERY_TASK}`) are your PRIMARY "
                f"mechanism for planning, communicating with the user, and showing progress — keep them current at all times.\n\n"
                f"All tasks are created without an owner. Any agent — including you — can claim any unowned task via "
                f"`{TOOL_NAME_UPDATE_TASK}` with `if_claim`: true. Do NOT assume a task is off-limits just because a "
                f"subagent created it.\n\n"
                f"CONSTRAINT: For any request requiring 3+ distinct actions, you MUST call `{TOOL_NAME_CREATE_TASK}` FIRST "
                f"to break work into meaningful milestones BEFORE taking action. Each task = a logical phase, NOT a single "
                f"tool call. Do NOT create a single catch-all task, and do NOT begin work until tasks are created.\n"
                f"Then: query existing tasks → work ONE task `{TASK_IN_PROGRESS_LABEL}` "
                f"at a time, mark it `{TASK_COMPLETED_LABEL}` before starting the next. Never batch-complete.\n\n"
                f"Good: \"Set up design\" → \"Run simulation\" → \"Analyze results\" | Bad: \"Implement the feature\"\n"
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
                " - The user primarily requests display panel engineering tasks (panel design, IR drop validation, "
                "temperature distribution analysis). When given an unclear instruction, consider it in the context of "
                f"TECoSim capabilities and other available tools. Call `{TOOL_NAME_ASK_QUESTION}` to clarify if needed.\n"
                " - Avoid giving time estimates or predictions for how long tasks will take.\n"
                "# Tone and style\n"
                " - Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.\n"
                " - Your responses should be short and concise.\n"
                " - Do not use a colon before tool calls. Your tool calls may not be shown directly in the output, so text "
                "like \"Let me read the file:\" followed by a read tool call should just be \"Let me read the file.\" with a period.\n"
                "# Output efficiency\n"
                "Lead with the answer or action, not the reasoning. Skip preamble and filler. Focus text output on "
                "decisions the user needs to make, status updates at natural milestones, and errors or blockers. "
                "Prefer one short sentence over three.\n"
                "# Session-specific guidance\n"
                " - If a user denies your tool call, they may provide a comment explaining why. If you don't understand, "
                f"use `{TOOL_NAME_ASK_QUESTION}` to ask them\n"
                f" - IMPORTANT: Only use `{TOOL_NAME_SKILL}` for skills listed in user-invocable skills section, do not guess\n"
                " - User can manually load full prompt of skill to context with /<skill-name>\n"
                f"# Subagent Guidelines\n"
                f"Use `{TOOL_NAME_SPAWN_AGENT}` when tasks are complex and would consume too many turns in the main loop, "
                f"or independent of each other and can run in parallel. Prefer `{EXPLORER_AGENT_LABEL}` for read-only "
                f"investigation, `{WORKER_AGENT_LABEL}` for implementation, `{SCHEDULER_AGENT_LABEL}` for task planning "
                f"and dependency setup. Launch multiple agents per message when tasks are independent.\n"
                f"Foreground agents (default): blocks until complete, use when results are needed for your next step. "
                f"Background agents (`if_background`: true): runs independently, results delivered later, use for long "
                f"standalone work.\n"
                f"CRITICAL: Background agent results are injected into your message stream AUTOMATICALLY when "
                f"they finish — you do NOT need to query or poll for completion. After spawning a background agent, "
                f"move on to other work immediately. You will be notified when its results arrive.\n"
                f"Scoreboard: `{SCHEDULER_AGENT_LABEL}` agents share your scoreboard — tasks they create appear immediately. "
                f"Scheduler agents create UNOWNED tasks for you to claim and execute; they should not execute tasks themselves "
                f"but may delete tasks they created incorrectly. Other agent types have independent scoreboards.\n"
                f"IMPORTANT: `{SCHEDULER_AGENT_LABEL}` agents MUST run as foreground, not background — tasks appear "
                f"incrementally and you may mistake partial output for completion. "
                f"After spawning a scheduler, check `{TOOL_NAME_QUERY_TASK}` for new tasks to work on.\n"
                f"Do NOT duplicate work a subagent is already doing.\n"}]
    return prompts


def get_agent_environment_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's dynamic boundaries with AgentContext"""
    now = datetime.now()

    bash_available = is_bash_available(ctx.agent_configs["BASH_PATH"])
    if bash_available:
        bash_prompts = " - Is bash available: True\n"
    else:
        bash_prompts = (
            f" - Is bash available: False. User should check if bash is available in path: {ctx.agent_configs["BASH_PATH"]} "
            f"defined in `BASH_PATH`\n")
    git_available = is_git_available()
    if git_available:
        git_prompts = " - Is git available: True\n"
    else:
        git_prompts = f" - Is git available: False\n"
    ripgrep_available = is_ripgrep_available(ctx.agent_configs["RIPGREP_PATH"])
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
        desc = skill.get('description')
        if desc is None:
            desc = ""
        if len(desc) > limit:
            skill_list_str += f" - {skill["name"]}: {desc[:limit]}...\n"
        else:
            skill_list_str += f" - {skill["name"]}: {desc}\n"
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
                     f"to manage your workflow during latest `{ctx.task_tool_unuse}` rounds of tool call or chat.\n")
            unresolved_tasks = board.list_unresolved_tasks(ctx.agent_id)
            unclaimed_tasks = board.list_unclaimed_tasks()
            if len(unresolved_tasks) == len(unclaimed_tasks) == 0:
                info += (f"Make sure using `{TOOL_NAME_CREATE_TASK}` to break down the work into milestones and communicate "
                         f"your plan and progress to the user with `{TOOL_NAME_UPDATE_TASK}`\n")
            if len(unresolved_tasks) > 0:
                info += (f"There are `{len(unresolved_tasks)}` tasks owned by you but not resolved (Task IDs: "
                         f"{[task["task_id"] for task in unresolved_tasks]})\n")
            if len(unclaimed_tasks) > 0:
                info += (f"There are `{len(unclaimed_tasks)}` tasks not claimed by any agent (Task IDs: "
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
            info += (f"There are still `{len(tasks)}` tasks needs your consideration:\n"
                     f"{tasks_info}\n"
                     f"Use task tools to manage your workflow\n")
        elif ctx.task_tool_unuse > ctx.agent_configs["REMIND_TASK_CHAT_GAP"]:
            if_remind = True
            info += (f"You haven't use any task tools to manage your workflow during latest `{ctx.task_tool_unuse}` rounds "
                     f"of chat or tool call. Make sure using task tools (`{TOOL_NAME_CREATE_TASK}`, `{TOOL_NAME_UPDATE_TASK}`, "
                     f"`{TOOL_NAME_QUERY_TASK}`) proactively.\n")

    return info.strip() if if_remind else None


def query_prompts(ctx: AgentContext, session_uuid: str | None, console: Console) -> list[dict[str, Any]]:
    """create new prompts or resume prompts from persistence file with AgentContext and given uuid"""
    if not ctx.args.override_prompts:
        messages = create_system_prompts(ctx)
    else:
        path = str(AGENT_PATH / OVERRIDE_PROMPTS_PATH)
        try:
            with open(path, "r", encoding='utf-8') as f:
                prompts = json.load(f)
            prompt = prompts["MAIN_AGENT_PROMPT"]
            if not isinstance(prompt, str):
                raise RuntimeError(f"Value of key: MAIN_AGENT_PROMPT in {path} is not a string")
            messages = [{"role": "system", "content": prompt}]
            sys_log.info("System prompts of main agent are overridden")
            console.print(f"[{MAJOR_COLOR2}]System prompts[/{MAJOR_COLOR2}] of main agent are overridden")
        except Exception as e:
            sys_log.warning(f"Override system prompts of main agent failed with error: {e}. Fallback to default system prompts")
            console.print(f"Override system prompts of main agent failed with error: {e}. Fallback to default system "
                          f"prompts", style=f"bold yellow")
            messages = create_system_prompts(ctx)

    if session_uuid is None:
        pass
    else:
        resumed_prompts = read_messages(session_uuid, console)
        msg_fix_toolcall(resumed_prompts, console)
        print_messages(resumed_prompts, ctx, console)
        messages = messages + resumed_prompts
    return messages


_SYSTEM_REMINDER_STR = Text(f"{SYS_REMINDER_ICON}", style=f"{MAJOR_COLOR1}")
_SYSTEM_REMINDER_STR = _SYSTEM_REMINDER_STR.append(" System reminder", style=f"{MAJOR_COLOR1}")
_SYSTEM_REMINDER_STR = _SYSTEM_REMINDER_STR.append(" is inserted, content is not displayed", style=f"bright_black")
_SKILL_STR = Text(f"{SKILL_ICON}", style=f"{MAJOR_COLOR1}")
_SKILL_STR = _SKILL_STR.append(" Agent skill", style=f"{MAJOR_COLOR1}")
_SKILL_STR = _SKILL_STR.append(" is invoked, content is not displayed", style=f"bright_black")
_CRON_STR = Text(f"{CRON_ICON}", style=f"{MAJOR_COLOR1}")
_CRON_STR = _CRON_STR.append(" Cron tasks", style=f"{MAJOR_COLOR1}")
_CRON_STR = _CRON_STR.append(" are invoked, content is not displayed", style=f"bright_black")
_SUBAGENT_STR = Text(f"{SUBAGENT_ICON}", style=f"{MAJOR_COLOR1}")
_SUBAGENT_STR = _SUBAGENT_STR.append(" Background subagent", style=f"{MAJOR_COLOR1}")
_SUBAGENT_STR = _SUBAGENT_STR.append(" is retrieved, content is not displayed", style=f"bright_black")


def get_user_history_render(msg: str, as_md: bool) -> Panel:
    """get user's history message render"""
    user_prefix = Text("History user input:\n", style=f"bright_black")
    t = Table(show_header=False, show_edge=False, padding=0, box=None, collapse_padding=True)
    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
    t.add_column(vertical="top", overflow="fold")
    if as_md:
        render_str = Text(f" {AGENT_CONSOLE_ICON} ", style=f"white")
        t.add_row(render_str, user_prefix)
        t.add_row(Text(), ContentMD(msg))
    else:
        render_str = Text(f" {AGENT_CONSOLE_ICON} ", style=f"white")
        t.add_row(render_str, user_prefix)
        t.add_row(Text(), Text(msg, style="white"))
    render = Panel(t, box=rich.box.SQUARE)
    return render


def get_msg_render(msg: str, icon: str, info: str, as_md: bool) -> Panel:
    """get message's render"""
    content = msg.strip()
    t = Table(show_header=False, show_edge=False, padding=0, box=None, collapse_padding=True)
    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
    t.add_column(vertical="top", overflow="fold")
    if as_md and content:
        render_str = Text(f" {icon} ", style=f"bold {MAJOR_COLOR1}")
        t.add_row(render_str, ContentMD(f"{info + content}"))
    else:
        render_str = Text(f" {icon} ", style=f"bold {MAJOR_COLOR1}")
        if content:
            t.add_row(render_str, Text(f"{info + content}", style="white"))
        else:
            t.add_row(render_str, Text(""))
    render = Panel(t, box=rich.box.SQUARE)
    return render


def get_msg_render_strip(msg: dict[str, Any], label_start: str, label_end: str, icon: str, info: str, as_md: bool) -> Panel:
    """get message's render after striping the label"""
    inner: str = msg["content"]
    start = inner.find(label_start) + len(label_start)
    end = inner.rfind(label_end)
    content = inner[start:end].strip()
    if not content:
        content = inner.strip()
    render = get_msg_render(content, icon, info, as_md)
    return render


def msg_fix_toolcall(messages: list[dict[str, Any]], console: Console, mute: bool = False):
    """Restore tool-call/tool-result pairing integrity in the conversation history.
    1. Orphan tool results — role: tool messages whose tool_call_id matches no assistant message's tool_calls[].id are removed.
    2. Missing tool results — assistant messages with tool_calls that lack corresponding role: tool messages get a synthetic
       error result appended right after the existing tool-result block.
    """
    # 1. Collect all valid tool_call_ids from assistant messages, keyed by index.
    assistant_ids: dict[int, set[str]] = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            assistant_ids[i] = {tc["id"] for tc in msg["tool_calls"] if tc.get("id")}

    all_valid_ids: set[str] = set()
    for ids in assistant_ids.values():
        all_valid_ids.update(ids)

    # 2. Build set of tool_call_ids that already have corresponding results.
    matched_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool":
            tc_id = msg.get("tool_call_id")
            if tc_id and tc_id in all_valid_ids:
                matched_ids.add(tc_id)

    # 3. Remove orphan tool results (iterate backward to keep indices stable).
    i = len(messages) - 1
    while i >= 0:
        msg = messages[i]
        if msg.get("role") == "tool" and msg.get("tool_call_id") not in all_valid_ids:
            messages.pop(i)
            sys_log.warning(f"Orphan tool results with tool call ID: {msg.get("tool_call_id")} is removed")
            if not mute:
                console.print(f"Orphan tool results with tool call ID: {msg.get("tool_call_id")} is removed",
                              style="bold yellow")
        i -= 1

    # 4. Insert synthetic error results for missing tool calls.
    #    Process assistants in reverse index order so insertions don't shift earlier indices.
    for assistant_idx in sorted(assistant_ids.keys(), reverse=True):
        missing_ids = assistant_ids[assistant_idx] - matched_ids
        if not missing_ids:
            continue

        # Find the end of the tool-result block belonging to this assistant.
        # (We removed orphans, so every tool message after this assistant belongs to it until the next non-tool message.)
        insert_idx = assistant_idx + 1
        while insert_idx < len(messages) and messages[insert_idx].get("role") == "tool":
            insert_idx += 1

        for tc in messages[assistant_idx]["tool_calls"]:
            call_id = tc.get("id")
            if call_id and call_id in missing_ids:
                messages.insert(insert_idx, {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps({
                        "status": UNKNOWN_LABEL,
                        "info": f"(Tool result was lost due to an unexpected error. Re-execute this tool call if necessary)"
                    }, ensure_ascii=False),
                })
                sys_log.warning(f"Missing tool results with tool call ID: {call_id} is inserted")
                if not mute:
                    console.print(f"Missing tool results with tool call ID: {call_id} is inserted", style="bold yellow")
                insert_idx += 1


def print_messages(messages: list[dict[str, Any]], ctx: AgentContext, console: Console):
    """print the given messages (exclude system) with AgentContext"""
    try:
        as_md: bool = ctx.agent_configs["RENDER_RESPONSE_AS_MD"]
        user_history_as_md: bool = ctx.agent_configs["RESUME_RENDER_USER_HISTORY_AS_MD"]
        display_subagent: bool = ctx.agent_configs["RESUME_DISPLAY_SUBAGENT"]
        display_sys_reminder: bool = ctx.agent_configs["RESUME_DISPLAY_SYS_REMINDER"]
        display_skill: bool = ctx.agent_configs["RESUME_DISPLAY_SKILLS"]
        display_cron: bool = ctx.agent_configs["RESUME_DISPLAY_CRONS"]
        display_write: bool = ctx.agent_configs["RESUME_DISPLAY_WRITE_PREVIEW"]
        display_bash: bool = ctx.agent_configs["RESUME_DISPLAY_BASH_PREVIEW"]
        display_bash_result: bool = ctx.agent_configs["RESUME_DISPLAY_BASH_RESULT"]
        display_glob: bool = ctx.agent_configs["RESUME_DISPLAY_GLOB_PREVIEW"]
        display_glob_result: bool = ctx.agent_configs["RESUME_DISPLAY_GLOB_RESULT"]
        display_grep: bool = ctx.agent_configs["RESUME_DISPLAY_GREP_PREVIEW"]
        display_grep_result: bool = ctx.agent_configs["RESUME_DISPLAY_GREP_RESULT"]
        display_web_fetch_result: bool = ctx.agent_configs["RESUME_DISPLAY_WEB_FETCH_RESULT"]
        display_web_search_result: bool = ctx.agent_configs["RESUME_DISPLAY_WEB_SEARCH_RESULT"]
        display_wechat_status_result: bool = ctx.agent_configs["RESUME_DISPLAY_WECHAT_STATUS_RESULT"]
        tool_id_map: dict[str, str] = {}
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                """WeChat Bot"""
                if (WECHAT_PROMPT_START_LABEL in msg["content"]) and (WECHAT_PROMPT_END_LABEL in msg["content"]):
                    console.print(get_msg_render_strip(
                        msg, WECHAT_PROMPT_START_LABEL, WECHAT_PROMPT_END_LABEL, WECHAT_PROMPT_ICON, "", as_md))
                    continue
                """system reminder"""
                if (SYS_REMINDER_START_LABEL in msg["content"]) and (SYS_REMINDER_END_LABEL in msg["content"]):
                    if not display_sys_reminder:
                        console.print(Panel(_SYSTEM_REMINDER_STR, box=rich.box.SQUARE))
                    else:
                        console.print(get_msg_render_strip(
                            msg, SYS_REMINDER_START_LABEL, SYS_REMINDER_END_LABEL, SYS_REMINDER_ICON,
                            "**(This is a system reminder)** \n\n", as_md))
                    continue
                """agent skill"""
                if ("skill_directory" in msg["content"]) and (SKILL_START_LABEL in msg["content"]) and (SKILL_END_LABEL in msg["content"]):
                    if not display_skill:
                        console.print(Panel(_SKILL_STR, box=rich.box.SQUARE))
                    else:
                        try:
                            skill_msg: dict[str, Any] = json.loads(msg["content"]) # msg["content"] = json str: {status, skill_directory, content}
                        except Exception as e:
                            sys_log.error(f"Can not convert skill content into pydict with error: {e}")
                            console.print(f"Can not convert skill content into pydict with error: {e}", style="bold red")
                            skill_msg = msg["content"]
                        console.print(get_msg_render_strip(
                            skill_msg, SKILL_START_LABEL, SKILL_END_LABEL, SKILL_ICON,
                            "**(This is an invoked agent skill)** \n\n", as_md))
                    continue
                """cron task"""
                if (CRON_START_LABEL in msg["content"]) and (CRON_END_LABEL in msg["content"]):
                    if not display_cron:
                        console.print(Panel(_CRON_STR, box=rich.box.SQUARE))
                    else:
                        console.print(get_msg_render_strip(
                            msg, CRON_START_LABEL, CRON_END_LABEL, CRON_ICON,
                            "**(This is the information of invoked cron tasks)** \n\n", as_md))
                    continue
                """background subagent"""
                # foreground subagent directly return in tool results. This branch is for background subagent with plain text handoff
                if (SUBAGENT_START_LABEL in msg["content"]) and (SUBAGENT_END_LABEL in msg["content"]):
                    if not display_subagent:
                        console.print(Panel(_SUBAGENT_STR, box=rich.box.SQUARE))
                    else:
                        console.print(get_msg_render_strip(
                            msg, SUBAGENT_START_LABEL, SUBAGENT_END_LABEL, SUBAGENT_ICON,
                            "**(This is the response of a retrieved background subagent)** \n\n", as_md))
                    continue
                """user input"""
                console.print(get_user_history_render(msg["content"], user_history_as_md))
            elif msg["role"] == "assistant":
                """display reasoning"""
                assistant_reasoning = get_reasoning(msg)
                if assistant_reasoning not in (None, ""):
                    console.print("\n")
                    t = Table(show_header=False, show_edge=False, padding=0,
                              box=None, collapse_padding=True)
                    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
                    t.add_column(vertical="top", overflow="fold")
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
                    t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
                    t.add_column(vertical="top", overflow="fold")
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
                        if display_cron and tool_name == TOOL_NAME_CREATE_CRON:
                            console.print(get_bash_render(get_cron_create_str(args, False)))
                            continue
                        if display_cron and tool_name == TOOL_NAME_REMOVE_CRON:
                            task_id = str(args.get("id", "(Empty cron task ID)"))
                            console.print(get_bash_render(f"{TOOL_NAME_REMOVE_CRON}: {task_id}"))
                            continue
                        if display_bash and tool_name == TOOL_NAME_BASH:
                            console.print(get_bash_render(args.get("command", "(Failed to get bash command)")))
                            continue
                        if display_glob and tool_name == TOOL_NAME_GLOB_FILE:
                            console.print(get_bash_render(f"{TOOL_NAME_GLOB_FILE}: {args.get("pattern", "(Failed to get glob pattern)")}"))
                            continue
                        if display_grep and tool_name == TOOL_NAME_GREP_FILE:
                            console.print(get_bash_render(get_grep_cmd(args, "rg")))
                            continue
                        if display_write and tool_name == TOOL_NAME_WRITE_FILE:
                            console.print(get_syntax_render(args.get("path", ""), args.get("content", "(Failed to get write content)")))
                            continue
                        if tool_name == TOOL_NAME_WEB_FETCH:
                            console.print(get_bash_render(get_webfetch_str(args)))
                            continue
                        if tool_name == TOOL_NAME_WEB_SEARCH:
                            console.print(get_bash_render(f"{TOOL_NAME_WEB_SEARCH}: {args.get("query", "(Failed to get query)")}"))
                            continue
                        if tool_name == TOOL_NAME_WECHAT_SEND_FILE:
                            file_path = args.get("path")
                            if file_path is not None:
                                path_str = str(Path(file_path).resolve())
                            else:
                                path_str = "(Failed to get file path)"
                            console.print(get_bash_render(f"{TOOL_NAME_WECHAT_SEND_FILE}: \"{path_str}\""))
                            continue
            elif msg["role"] == "tool":
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_SPAWN_AGENT:
                    stats: None | dict[str, Any] = None
                    try:
                        path = str(AGENT_PATH / SESSION_PATH / ctx.session_uuid / SUBAGENT_DUMP_DIR / SUBAGENT_SUMMARIES_NAME)
                        if os.path.exists(path):
                            with open(path, "r", encoding="utf-8") as f:
                                summaries = json.load(f)
                            stats = summaries.get(msg["tool_call_id"])
                    except Exception:
                        pass
                    if stats is not None:
                        p = SubAgentProgress(
                            agent_id=stats.get("agent_id", "(Unknown ID)"),
                            subagent_type=stats.get("subagent_type", "(Unknown Type)"),
                            subject=stats.get("subject", "(Unknown Subject)"),
                            status=AgentStatus(stats.get("status", AGENT_UNKNOWN_LABEL)),
                            tool_calls_done=stats.get("tool_calls_done", 0),
                            elapsed_s=stats.get("elapsed_s", 0.0),
                            input_tokens=stats.get("input_tokens", 0),
                            output_tokens=stats.get("output_tokens", 0),
                            if_archived=True,
                        )
                        console.print(render_subagent_line(p))
                    else:
                        console.print(f"  {SUBAGENT_PENDING_ICON} spawn_agent N/A", style="bright_black")
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_ASK_QUESTION:
                    try:
                        result = json.loads(msg["content"])
                    except (json.JSONDecodeError, TypeError):
                        result = {}
                    answers = result.get("answers", [])
                    if answers:
                        console.print(get_answers_render(answers))
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_CREATE_CRON:
                    if display_cron:
                        try:
                            result = json.loads(msg["content"])
                            cron_task_id: str = result.get("id")
                            if cron_task_id:
                                console.print(get_bash_result_render(f"Cron task: {cron_task_id} created"))
                            else:
                                console.print(get_bash_result_render("(Failed to get cron task)"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_bash_result_render("(Failed to get cron task)"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_QUERY_CRON:
                    if display_cron:
                        try:
                            result = json.loads(msg["content"])
                            cron_task_amount: int = result.get("total_tasks", -1)
                            cron_task_list = result.get("task_list", "(Failed to get cron tasks details)")
                            if cron_task_amount == -1:
                                console.print(get_syntax_render("cron.md", f"Total cron tasks: (Failed to cron tasks amount)"
                                                                           f"\n\n{cron_task_list}", "$cron"))
                            else:
                                console.print(get_syntax_render("cron.md", f"Total cron tasks: {cron_task_amount}\n\n"
                                                                           f"{cron_task_list}", "$cron"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_syntax_render("cron.md", "(Failed to get cron tasks)", "$cron"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_REMOVE_CRON:
                    if display_cron:
                        try:
                            result = json.loads(msg["content"])
                            info: str = result.get("info")
                            if info:
                                console.print(get_bash_result_render(info))
                            else:
                                console.print(get_bash_result_render("(Failed to get cron task removal info)"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_bash_result_render("(Failed to get cron task removal info)"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_BASH:
                    if display_bash_result:
                        try:
                            result = json.loads(msg["content"])
                        except (json.JSONDecodeError, TypeError):
                            result = {}
                        stdout = result.get("stdout", "")
                        stderr = result.get("stderr", "")
                        if stdout or stderr:
                            console.print(get_bash_result_render(stdout, stderr))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_GLOB_FILE:
                    if display_glob_result:
                        try:
                            result = json.loads(msg["content"])
                            glob_content: str = result.get("results", "(Failed to get glob result)")
                            console.print(get_bash_result_render(glob_content))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_bash_result_render("(Failed to get glob result)"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_GREP_FILE:
                    if display_grep_result:
                        try:
                            result = json.loads(msg["content"])
                            grep_content: str = result.get("results", "(Failed to get grep result)")
                            console.print(get_bash_result_render(grep_content))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_bash_result_render("(Failed to get grep result)"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_WEB_FETCH:
                    if display_web_fetch_result:
                        try:
                            result = json.loads(msg["content"])
                            web_fetch: str = result.get("content", "(Failed to get web fetch result)")
                            console.print(get_syntax_render("web_fetch.md", web_fetch, "$web"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_syntax_render("web_fetch.md", "(Failed to get web fetch result)", "$web"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_WEB_SEARCH:
                    if display_web_search_result:
                        try:
                            result = json.loads(msg["content"])
                            web_search: str = result.get("content", "(Failed to get web search result)")
                            console.print(get_syntax_render("web_search.md", web_search, "$web"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_syntax_render("web_search.md", "(Failed to get web search result)", "$web"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_WECHAT_STATUS:
                    if display_wechat_status_result:
                        try:
                            result = json.loads(msg["content"])
                            wechat_status: str = result.get("content", "(Failed to get WeChat status result)")
                            console.print(get_syntax_render("wechat.md", wechat_status, "$stats"))
                        except (json.JSONDecodeError, TypeError):
                            console.print(get_syntax_render("wechat.md", "(Failed to get WeChat status result)", "$stats"))
                    else:
                        pass
                    continue
                if msg.get("tool_call_id") and tool_id_map.get(msg["tool_call_id"]) == TOOL_NAME_WECHAT_SEND_FILE:
                    try:
                        result = json.loads(msg["content"])
                        send_info: str = result.get("info", "(Failed to get WeChat send info)")
                        console.print(get_bash_result_render(send_info))
                    except (json.JSONDecodeError, TypeError):
                        console.print(get_bash_result_render("(Failed to get WeChat send info)"))
                    continue
            else:
                sys_log.debug(f"Unknown role: {msg["role"]} in history massages")
                continue
    except Exception as e:
        sys_log.error(f"Failed to print the history messages with error: {e}")
        console.print(f"Failed to print the history messages with error: {e}", style="bold red")
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
            cached_tokens = usage.prompt_tokens_details.cached_tokens or 0
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
            sys_log.warning(f"LLM returned only reasoning content, setting content to empty string for API validity")
            console.print(f"LLM returned only reasoning content, content patched for API validity", style="bold yellow")
            dumped_msg["content"] = ""

    """print the final content"""
    console.print(get_block_render(assistant_reasoning, assistant_chat, ctx.agent_configs["RENDER_RESPONSE_AS_MD"],
                                   ctx.agent_configs["DISPLAY_RESPONSE_REASON"]))

    """send to WeChat"""
    # If there is tool call, and WECHAT_BOT_REPLY_DURING_TOOL_CALL is set:
    # 1). Only send messages if the budget is >= 1 (ensure that when task end, msg can be sent to user)
    # 2). Add hint for the last reply during tool call
    # 3). Typing status is set
    # (If tool call includes WeChat, they will fail if budget is < 1)
    if assistant_tool_calls is not None:
        if ctx.agent_configs["WECHAT_BOT_REPLY_DURING_TOOL_CALL"] and ctx.wechat_bot is not None and ctx.enable_wechat:
            if assistant_chat is not None:
                if (ctx.wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX: # out of budget
                    pass
                elif ctx.wechat_reply_count == WECHAT_REPLY_BUDGET_MAX - 2: # last hint
                    if_send = ctx.wechat_bot.reply_text_sync(
                        ctx.last_wechat_msg, f"{assistant_chat}\n\n{WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT}")
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                else:
                    if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_chat)
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                ctx.wechat_bot.send_typing_sync(ctx.last_wechat_msg)
            elif assistant_reasoning is not None:
                if (ctx.wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX:
                    pass
                elif ctx.wechat_reply_count == WECHAT_REPLY_BUDGET_MAX - 2:  # last hint
                    if_send = ctx.wechat_bot.reply_text_sync(
                        ctx.last_wechat_msg, f"{assistant_reasoning}\n\n{WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT}")
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                else:
                    if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_reasoning)
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                ctx.wechat_bot.send_typing_sync(ctx.last_wechat_msg)
            else:
                pass
    # If there is no tool call, task is end, WeChat msg should always be sent
    else:
        if ctx.wechat_bot is not None and ctx.enable_wechat:
            if assistant_chat is not None:
                if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_chat)
                if if_send:
                    ctx.wechat_reply_count += 1
                    ctx.wechat_reply_total_count += 1
            elif assistant_reasoning is not None:
                if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_reasoning)
                if if_send:
                    ctx.wechat_reply_count += 1
                    ctx.wechat_reply_total_count += 1
            else:
                pass

    """check context limits"""
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"]:
        sys_log.error(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens")
        console.print(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens", style="bold red")
        raise RuntimeError(f"LLM out of context: {ctx.api_configs["MAIN_MODEL_CONTEXT"]} tokens")
    if ctx.last_input_tokens >= ctx.api_configs["MAIN_MODEL_CONTEXT"] * ctx.agent_configs["CONTEXT_THRESHOLD"]:
        sys_log.warning(f"LLM's context >= {100 * ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context")
        console.print(f"LLM's context >= {100 * ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context",
                      style="bold yellow")

    return assistant_tool_calls


def get_block_render(collected_reasoning: str | None, collected_content: str | None, as_md: bool, show_reason: bool) -> Group:
    """get the render of the non-stream messages"""
    parts = []

    """display reasoning"""
    if collected_reasoning not in (None, ""):
        parts.append(Text("\n"))

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top", overflow="fold")
        if show_reason:
            if as_md:
                t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                          ReasonMD("{Think}: " + collected_reasoning))
            else:
                t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                          Text("{Think}: " + collected_reasoning, style=REASON_STYLE))
        else:
            t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
                      Text("Think done", style=REASON_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    """display chat"""
    if collected_content not in (None, ""):
        if collected_reasoning in (None, ""):
            parts.append(Text("\n"))

        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top", overflow="fold")
        if as_md:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), ContentMD(collected_content))
        else:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), Text(collected_content, style=CONTENT_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    return Group(*parts)


def get_stream_render(collected_reasoning: str | None, collected_content: str | None, as_md: bool, show_reason: bool,
                      collected_tool_names: list[str] | None, base_time: datetime, color_list: list[str]) -> Group:
    """get the render of the stream messages with smart truncation for long content"""
    now_time = datetime.now()
    time_diff = (now_time - base_time).total_seconds()
    position_in_period = time_diff % MESSAGE_COLOR_PERIOD
    index = int((position_in_period / MESSAGE_COLOR_PERIOD) * len(color_list)) % len(color_list)
    color = color_list[index]
    max_reasoning_lines = STREAM_DISPLAY_MAX_REASON_LINE
    max_content_lines = STREAM_DISPLAY_MAX_CONTENT_LINE
    parts = []

    """display reasoning with truncation for long output"""
    if collected_reasoning not in (None, ""):
        t = Table(show_header=False, show_edge=False, padding=0,
                  box=None, collapse_padding=True)
        t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t.add_column(vertical="top", overflow="fold")
        parts.append(Text("\n"))
        if show_reason:
            reason_lines = collected_reasoning.split('\n')
            if len(reason_lines) > max_reasoning_lines:
                # Show indicator and latest lines when reasoning is too long
                indicator = Text(f"[", style=f"bright_black")
                indicator.append(f"{AGENT_CONSOLE_ICON}", style=f"bold {color}")
                indicator.append(f" generating reasoning..., ", style=f"bright_black")
                indicator.append(f"{len(reason_lines)}", style=f"bold {color}")
                indicator.append(f" lines total, showing latest ", style=f"bright_black")
                indicator.append(f"{max_reasoning_lines}", style=f"bold {color}")
                indicator.append(f" lines]\n", style=f"bright_black")
                parts.append(indicator)
                reason_display = '\n'.join(reason_lines[-max_reasoning_lines:])
                reason_display = reason_display.lstrip()
                reason_display = reason_display.rstrip()
            else:
                reason_display = collected_reasoning

            if as_md:
                t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE), ReasonMD("{Think}: " + reason_display))
            else:
                t.add_row(Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE), Text("{Think}: " + reason_display, style=REASON_STYLE))
        else:
            t.add_row(Text(f" {REASON_ICON} ", style=f"bold {color}"), Text("Thinking ... ", style=f"bold {color}"))
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
            indicator.append(f"{AGENT_CONSOLE_ICON}", style=f"bold {color}")
            indicator.append(f" generating content..., ", style=f"bright_black")
            indicator.append(f"{len(content_lines)}", style=f"bold {color}")
            indicator.append(f" lines total, showing latest ", style=f"bright_black")
            indicator.append(f"{max_content_lines}", style=f"bold {color}")
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
        t.add_column(vertical="top", overflow="fold")
        if as_md:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), ContentMD(display_content))
        else:
            t.add_row(Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE), Text(display_content, style=CONTENT_STYLE))
        parts.append(t)
        parts.append(Text("\n"))

    """display tool calls being prepared"""
    if collected_tool_names:
        names = [n for n in collected_tool_names if n.strip()]
        if names:
            if collected_content in (None, "") and collected_reasoning in (None, ""):
                parts.append(Text("\n"))
            line = Text("Preparing tools: ", style=f"bright_black")
            for i, name in enumerate(names):
                if i > 0:
                    line.append(", ", style="bright_black")
                line.append(name, style=f"{color}")
            parts.append(line)
            parts.append(Text("\n"))

    return Group(*parts)


def llm_stream_manage(response: Stream[ChatCompletionChunk], ctx: AgentContext, console: Console) -> list[dict[str, Any]] | None:
    """realization of managing stream LLM responses in main agent-loop"""

    """initialize collectors for streaming response"""
    collected_reasoning = None
    collected_content = None
    collected_tool_calls: dict[int, dict[str, Any]] = {}  # index -> tool_call dict

    final_usage = None
    final_finish_reason = None
    as_md = ctx.agent_configs["RENDER_RESPONSE_AS_MD"]
    show_reason = ctx.agent_configs["DISPLAY_RESPONSE_REASON"]
    tool_names: list[str] = []
    base_time = datetime.now()
    msg_color_list = grad_color_hex_list(MAJOR_COLOR1, MAJOR_COLOR2, MESSAGE_COLOR_GRADIENT)
    msg_color_list = msg_color_list + msg_color_list[::-1]

    """process each chunk"""
    with Live(get_stream_render(collected_reasoning, collected_content, as_md, show_reason, tool_names, base_time, msg_color_list),
              refresh_per_second=STREAM_DISPLAY_REFRESH_RATE, console=console, transient=False) as live:
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
                if collected_content is None:
                    collected_content = ""
                collected_content += delta.content

            # Collect reasoning (for DeepSeek and similar models)
            reasoning_delta = get_reasoning_stream(delta)
            if reasoning_delta:
                if collected_reasoning is None:
                    collected_reasoning = ""
                collected_reasoning += reasoning_delta

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
            tool_names = [tc["function"]["name"] for tc in collected_tool_calls.values() if tc["function"]["name"].strip()]
            live.update(get_stream_render(collected_reasoning, collected_content, as_md, show_reason, tool_names if tool_names else None,
                                          base_time, msg_color_list))
        # print the final content without orphan lines
        live.update(get_block_render(collected_reasoning, collected_content, as_md, show_reason))

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
    if collected_reasoning is not None:
        ctx.reasoning_prompts += 1
    if collected_content is not None:
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
        "content": collected_content,
        "reasoning": collected_reasoning,
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
            sys_log.warning(f"LLM returned only reasoning content, setting content to empty string for API validity")
            console.print(f"LLM returned only reasoning content, content patched for API validity", style="bold yellow")
            dumped_msg["content"] = ""

    """send to WeChat"""
    # If there is tool call, and WECHAT_BOT_REPLY_DURING_TOOL_CALL is set:
    # 1). Only send messages if the budget is >= 1 (ensure that when task end, msg can be sent to user)
    # 2). Add hint for the last reply during tool call
    # 3). Typing status is set
    # (If tool call includes WeChat, they will fail if budget is < 1)
    if converted_tool_calls is not None:
        if ctx.agent_configs["WECHAT_BOT_REPLY_DURING_TOOL_CALL"] and ctx.wechat_bot is not None and ctx.enable_wechat:
            if assistant_chat is not None and assistant_chat != "":
                if (ctx.wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX:  # out of budget
                    pass
                elif ctx.wechat_reply_count == WECHAT_REPLY_BUDGET_MAX - 2:  # last hint
                    if_send = ctx.wechat_bot.reply_text_sync(
                        ctx.last_wechat_msg, f"{assistant_chat}\n\n{WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT}")
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                else:
                    if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_chat)
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                ctx.wechat_bot.send_typing_sync(ctx.last_wechat_msg)
            elif assistant_reasoning is not None and assistant_reasoning != "":
                if (ctx.wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX:
                    pass
                elif ctx.wechat_reply_count == WECHAT_REPLY_BUDGET_MAX - 2:  # last hint
                    if_send = ctx.wechat_bot.reply_text_sync(
                        ctx.last_wechat_msg, f"{assistant_reasoning}\n\n{WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT}")
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                else:
                    if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_reasoning)
                    if if_send:
                        ctx.wechat_reply_count += 1
                        ctx.wechat_reply_total_count += 1
                ctx.wechat_bot.send_typing_sync(ctx.last_wechat_msg)
            else:
                pass
    # If there is no tool call, task is end, WeChat msg should always be sent
    else:
        if ctx.wechat_bot is not None and ctx.enable_wechat:
            if assistant_chat is not None and assistant_chat != "":
                if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_chat)
                if if_send:
                    ctx.wechat_reply_count += 1
                    ctx.wechat_reply_total_count += 1
            elif assistant_reasoning is not None and assistant_reasoning != "":
                if_send = ctx.wechat_bot.reply_text_sync(ctx.last_wechat_msg, assistant_reasoning)
                if if_send:
                    ctx.wechat_reply_count += 1
                    ctx.wechat_reply_total_count += 1
            else:
                pass

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
