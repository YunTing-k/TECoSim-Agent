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
2026.6.10      Yu Huang      2.7      Revise the live TUI with the same console instance
2026.6.12      Yu Huang      2.8      Subagent spawn: classification, batch launch, poll, merge stats
2026.6.13      Yu Huang      2.9      Background subagent support + tool result truncation + batch agent permission TUI
2026.6.14      Yu Huang      3.0      Fix: foreground/background subagent timeout, tool call arg error handling
2026.6.21      Yu Huang      3.1      Fix: User addons cannot be inserted between tool results when LLM is deepseek
2026.6.29      Yu Huang      3.2      Subagent summary: summaries.json for foreground + background resume display
2026.6.30      Yu Huang      3.3      Add multi-round results truncate method with pydict keys preserved
2026.7.15      Yu Huang      3.4      Add merge subagent statistic method

Details:
---------
Tool execution orchestrator. `execute_tools()` classifies LLM tool-call requests into normal tools and agent
spawn calls, runs normal tools sequentially, then spawns agents concurrently in threads with progress polling.
Spinner wrappers integrate with Rich display. `call_tools` dispatch lives in `tool_dispatch.py`.
"""
import json
import os
import uuid
import time
import random
import logging
import threading

from typing import Callable, Any
from rich.console import Console
from rich.progress import Progress
from src.utility.ui_info import (
    loading_spinner, loading_spinner_with_board, pause_for_permission, resume_from_permission, render_subagent_line)
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.tool.tool_dispatch import ToolCallsCancelled, if_tool_mute, call_tools
from src.tool.ask_permission import ask_permission_tui
from src.utility.basic_utils import truncate_tool_result
from src.agent.subagent import SubAgent, merge_agent_stats
from src.agent.progress import AgentStatus, SubAgentProgress
from src.constants import *

sys_log = logging.getLogger('logger')


def tool_calls_spinner(func: Callable, *args, console: Console,
                       waiting_desc: str | None = None, done_desc: str | None = None,
                       intrp_desc: str | None = None, fail_desc: str | None = None,
                       spinner: str | None = None, if_random: bool, **kwargs) -> Any:
    """Tool calls with spinner through loading_spinner (for main agent)"""
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
                             console=console, with_progress=True,  # add progress to target function
                             **kwargs)
    return result


def tool_calls_spinner_board(func: Callable, *args,
                             board: Scoreboard, console: Console,
                             waiting_desc: str | None = None, done_desc: str | None = None,
                             intrp_desc: str | None = None, fail_desc: str | None = None,
                             spinner: str | None = None, if_random: bool,
                             agent_list: dict[str, SubAgentProgress] | None = None, **kwargs) -> Any:
    """Tool calls with spinner and scoreboard through loading_spinner_with_board (for main agent)"""
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
                                        board=board, agent_list=agent_list,
                                        waiting_desc=waiting_title, done_desc=done_title,
                                        intrp_desc=intrp_title, fail_desc=fail_title,
                                        spinner=spinner_choice,
                                        out_except=ToolCallsCancelled("Tool call is cancelled by user"),
                                        console=console, with_progress=True,
                                        **kwargs)
    return result


def execute_tools(tool_calls: list[dict[str, Any]], ctx: AgentContext, board: Scoreboard, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls with AgentContext (for main agent)

    Phase 1: execute all non-agent tool calls sequentially.
    Phase 2a: launch background agents concurrently in threads (non-blocking).
    Phase 2b: launch foreground agents concurrently, poll progress, merge results (blocking).
    """
    messages: list[dict[str, Any]] = []
    normal_calls: list[dict[str, Any]] = []
    bg_agent_calls: list[dict[str, Any]] = []
    fg_agent_calls: list[dict[str, Any]] = []

    for tc in tool_calls:
        if tc["function"]["name"] == TOOL_NAME_SPAWN_AGENT:
            try:
                args = json.loads(tc["function"]["arguments"])
                agent_type = args["subagent_type"]  # make sure there has subagent_type
                if args.get("if_background", False):
                    bg_agent_calls.append(tc)
                else:
                    fg_agent_calls.append(tc)
            except Exception as e:
                sys_log.error(f"Failed to parse {TOOL_NAME_SPAWN_AGENT} tool call's arguments: {tc} with error: {e}")
                progress.console.print(f"Failed to parse {TOOL_NAME_SPAWN_AGENT} tool call's arguments with error: {e}",
                                       style="bold red")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({
                        "status": FAIL_LABEL,
                        "info": f"Failed to parse {TOOL_NAME_SPAWN_AGENT} tool call's arguments with error: {e}. Please recheck."},
                        ensure_ascii=False),
                })
                continue
        else:
            normal_calls.append(tc)

    limit = ctx.agent_configs.get("MAIN_TOOL_RESULT_CHAR_LIMIT", MAIN_TOOL_RESULT_DEFAULT_CHAR_LIMIT)
    user_addons: list[dict[str, Any]] = []
    for tc in normal_calls:
        try:
            func_name = tc["function"]["name"]
            arguments = json.loads(tc["function"]["arguments"])
        except Exception as e:
            sys_log.error(f"Failed to parse normal tool call's arguments: {tc} with error: {e}")
            progress.console.print(f"Failed to parse normal tool call's arguments with error: {e}", style="bold red")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps({
                    "status": FAIL_LABEL,
                    "info": f"Failed to parse this tool call's arguments with error: {e}. Please recheck."}, ensure_ascii=False),
            })
            continue
        sys_log.debug(f"Using tool: {func_name}")
        if not if_tool_mute(func_name):
            progress.console.print(f"Using tool: [{MAJOR_COLOR1}]{func_name}[/{MAJOR_COLOR1}]", style="bright_black")
        results, user_addon = call_tools(func_name, arguments, ctx, board, progress)
        result_str = truncate_tool_result(results, limit, TOOL_RESULT_TRUNCATION_ROUNDS)
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result_str,
        })
        if ctx.api_configs["MAIN_MODEL_DEEPSEEK_SUPPORT"]:
            if user_addon is not None:
                user_addons.append(user_addon)
        else:
            if user_addon is not None:
                messages.append({
                    "role": "user",
                    "content": json.dumps(user_addon, ensure_ascii=False),
                })

    if bg_agent_calls or fg_agent_calls:
        all_agent_calls = bg_agent_calls + fg_agent_calls
        desc_parts = []
        for tc in all_agent_calls:
            args = json.loads(tc["function"]["arguments"])
            mode = "background" if args.get("if_background") else "foreground"
            desc_parts.append(f"  [{mode}] {args['subagent_type']}: {args.get('subject', '')}")
        desc = f"Spawn {len(all_agent_calls)} subagent(s):\n" + "\n".join(desc_parts)
        pause_for_permission(progress)
        token, comment = ask_permission_tui(ctx, TOOL_NAME_SPAWN_AGENT, desc, progress.console)
        resume_from_permission(progress)
        if not token:
            denied_info = f"All subagent spawns in this round of tool call are denied by user"
            if comment:
                denied_info += f" with comment: {comment}"
            for i, tc in enumerate(all_agent_calls):
                info = denied_info if i == 0 else f"Subagent spawn denied (see above)"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"status": DENIED_LABEL, "info": info}, ensure_ascii=False),
                })
            return messages

    if bg_agent_calls:
        bg_messages = execute_background_agents(bg_agent_calls, ctx, board, progress)
        messages.extend(bg_messages)

    if fg_agent_calls:
        fg_messages = execute_subagents(fg_agent_calls, ctx, board, progress)
        messages.extend(fg_messages)

    if ctx.api_configs["MAIN_MODEL_DEEPSEEK_SUPPORT"]:
        for addon in user_addons:
            messages.append({
                "role": "user",
                "content": json.dumps(addon, ensure_ascii=False),
            })

    return messages


def generate_agent_id(ctx: AgentContext) -> str:
    """generate unique subagent ID (8-char hex), skipping MAIN_AGENT_ID and existing ids"""
    while True:
        aid = uuid.uuid4().hex[:AGENT_ID_LEN]
        if aid != MAIN_AGENT_ID and aid not in ctx.agent_list:
            return aid


def execute_background_agents(agent_calls: list[dict[str, Any]], main_ctx: AgentContext, board: Scoreboard,
                               progress: Progress) -> list[dict[str, Any]]:
    """launch background agents without blocking; store in ctx.background_agents for later collection (for main agent)"""
    messages = []
    for tc in agent_calls:
        args = json.loads(tc["function"]["arguments"])
        agent_id = generate_agent_id(main_ctx)
        sys_log.debug(f"Spawning background subagent: {agent_id}")
        progress.console.print(
            f"Spawning background subagent: [{MAJOR_COLOR1}]{agent_id}[/{MAJOR_COLOR1}]", style="bright_black")

        agent_type = args["subagent_type"]
        share_board = (agent_type == SCHEDULER_AGENT_LABEL)
        agent = SubAgent(
            parent_ctx=main_ctx,
            subagent_type=agent_type,
            subject=args["subject"],
            prompt=args["prompt"],
            agent_id=agent_id,
            share_parent_board=share_board,
            parent_board=board if share_board else None,
            model_type=args.get("model_type"),
            console=progress.console,
        )
        agent.build_tools()
        agent.build_messages()
        main_ctx.agent_list[agent_id] = agent.progress
        agent.progress.if_background = True

        t = threading.Thread(target=agent.run)
        t.start()
        main_ctx.background_agents.append((tc, agent, t, time.time()))

        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps({
                "status": DONE_LABEL,
                "info": f"background agent {agent_id} ({agent.subagent_type}) started. "
                        f"Results will be delivered when complete."
            }, ensure_ascii=False),
        })

    return messages


def _save_subagent_summaries(session_uuid: str, entries: dict[str, dict]) -> None:
    """persist subagent summaries keyed by tool_call_id to summaries.json (read-merge-write)"""
    path = os.path.join(SESSION_PATH, session_uuid, SUBAGENT_DUMP_DIR, SUBAGENT_SUMMARIES_NAME)
    try:
        summaries: dict[str, dict] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                summaries = json.load(f)
        summaries.update(entries)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        sys_log.debug(f"Subagent summaries saved: {list(entries.keys())}")
    except Exception as e:
        sys_log.error(f"Failed to save subagent summaries: {e}")


def check_background_agents(main_ctx: AgentContext) -> bool:
    """check if any background agents have completed; collect results and inject into main_ctx.messages

    Returns True if at least one background agent completed, False otherwise.
    """
    completed = []
    now = time.time()
    for tc, agent, thread, start_time in main_ctx.background_agents:
        timeout_s = agent.timeout_s or SUBAGENT_DEFAULT_TIMEOUT_S
        if not thread.is_alive():
            thread.join()
        elif (agent.status == AgentStatus.RUNNING) and (now - start_time < timeout_s):
            continue
        else:
            if agent.status == AgentStatus.RUNNING:
                agent.status = AgentStatus.TIMEOUT
                agent.progress.status = AgentStatus.TIMEOUT

        merge_agent_stats(main_ctx, agent)
        agent_id_str = f"{agent.agent_id} ({agent.subagent_type})"
        if agent.status == AgentStatus.DONE:
            if agent.result:
                msg_content = (
                    f"{SUBAGENT_START_LABEL}\n"
                    f"Background agent {agent_id_str} completed.\n"
                    f"{agent.result}\n"
                    f"{SUBAGENT_END_LABEL}"
                )
                sys_log.debug(f"Background agent {agent.agent_id} done, "
                              f"result: {agent.result[:SUBAGENT_RESULT_LOG_CHAR_LIMIT]}...")
            else:
                msg_content = (
                    f"{SUBAGENT_START_LABEL}\n"
                    f"Background agent {agent_id_str} done, but there is no results from subagent.\n"
                    f"Error: {agent.error or '(There is no error info from subagent)'}.\n"
                    f"{SUBAGENT_END_LABEL}"
                )
                sys_log.warning(f"Background agent {agent.agent_id} done, there is no results from subagent")
        elif agent.status == AgentStatus.TIMEOUT:
            msg_content = (
                f"{SUBAGENT_START_LABEL}\n"
                f"Background agent {agent_id_str} timed out ({timeout_s:.0f}s). User should set `SUBAGENT_TIMEOUT_S` "
                f"in {AGENT_CONFIGS_PATH} to increase.\n"
                f"Result: {agent.result or '(There is no results from subagent)'}.\n"
                f"Error: {agent.error or '(There is no error info from subagent)'}.\n"
                f"{SUBAGENT_END_LABEL}"
            )
            sys_log.warning(f"Background agent {agent.agent_id} timed out ({timeout_s:.0f}s).. User should set "
                            f"`SUBAGENT_TIMEOUT_S` in {AGENT_CONFIGS_PATH} to increase.")
        elif agent.status == AgentStatus.RUNNING and agent.result is None:
            msg_content = (
                f"{SUBAGENT_START_LABEL}\n"
                f"Background agent {agent_id_str} exhausted all {agent.max_steps} steps without completing. User should "
                f"set `SUBAGENT_MAX_STEPS` in {AGENT_CONFIGS_PATH} to increase, or you should give a more specific "
                f"prompt.\n"
                f"Result: {agent.result or '(There is no results from subagent)'}.\n"
                f"Error: {agent.error or '(There is no error info from subagent)'}.\n"
                f"{SUBAGENT_END_LABEL}"
            )
            sys_log.warning(f"Background agent {agent.agent_id} exhausted {agent.max_steps} steps without completing. "
                            f"User should set `SUBAGENT_MAX_STEPS` in {AGENT_CONFIGS_PATH} to increase.")
        elif agent.status == AgentStatus.ERROR:
            msg_content = (
                f"{SUBAGENT_START_LABEL}\n"
                f"Background agent {agent_id_str} failed with error: {agent.error or '(There is no error info from subagent)'}.\n"
                f"Result: {agent.result or '(There is no results from subagent)'}.\n"
                f"{SUBAGENT_END_LABEL}"
            )
            sys_log.error(f"Background agent {agent.agent_id} failed: {agent.error or '(There is no error info from subagent)'}")
        else:
            msg_content = (
                f"{SUBAGENT_START_LABEL}\n"
                f"Background agent {agent_id_str} terminated with status {agent.status.value}.\n"
                f"Result: {agent.result or '(There is no results from subagent)'}.\n"
                f"Error: {agent.error or '(There is no error info from subagent)'}.\n"
                f"{SUBAGENT_END_LABEL}"
            )
            sys_log.warning(f"Background agent {agent.agent_id} terminated with status {agent.status.value}.")

        agent.progress.if_archived = True
        if agent.progress.elapsed_s == 0 and agent.start_time > 0:
            agent.progress.elapsed_s = time.time() - agent.start_time
        main_ctx.messages.append({
            "role": "user",
            "content": msg_content,
        })
        completed.append((tc, agent, thread, start_time))

    """persist background agent summaries for resume display"""
    if completed:
        _save_subagent_summaries(main_ctx.session_uuid, {
            tc["id"]: {
                "subagent_type": agent.progress.subagent_type,
                "subject": agent.progress.subject,
                "status": agent.progress.status.value,
                "tool_calls_done": agent.progress.tool_calls_done,
                "elapsed_s": agent.progress.elapsed_s,
                "input_tokens": agent.progress.input_tokens,
                "output_tokens": agent.progress.output_tokens,
                "agent_id": agent.agent_id,
            }
            for tc, agent, _, _ in completed
        })

    for item in completed:
        main_ctx.background_agents.remove(item)

    return len(completed) > 0


def execute_subagents(agent_calls: list[dict[str, Any]], main_ctx: AgentContext, board: Scoreboard, progress: Progress) \
        -> list[dict[str, Any]]:
    """spawn foreground subagents concurrently, poll progress, merge results and token stats (blocking)"""
    subagents: list[tuple[dict[str, Any], SubAgent]] = []
    for tc in agent_calls:
        args = json.loads(tc["function"]["arguments"])
        agent_id = generate_agent_id(main_ctx)
        sys_log.debug(f"Spawning subagent: {agent_id}")
        progress.console.print(
            f"Spawning subagent: [{MAJOR_COLOR1}]{agent_id}[/{MAJOR_COLOR1}]", style="bright_black")

        agent_type = args["subagent_type"]
        share_board = (agent_type == SCHEDULER_AGENT_LABEL)
        agent = SubAgent(
            parent_ctx=main_ctx,
            subagent_type=agent_type,
            subject=args["subject"],
            prompt=args["prompt"],
            agent_id=agent_id,
            share_parent_board=share_board,
            parent_board=board if share_board else None,
            model_type=args.get("model_type"),
            console=progress.console,
        )
        agent.build_tools()
        agent.build_messages()
        main_ctx.agent_list[agent_id] = agent.progress
        subagents.append((tc, agent))

    threads = []
    for _, agent in subagents:
        t = threading.Thread(target=agent.run)
        t.start()
        threads.append(t)
    """wait for all threads to finish (inner subagent has timeout, but we also need to handle it when timeout)"""
    timeout = main_ctx.agent_configs.get("SUBAGENT_TIMEOUT_S", SUBAGENT_DEFAULT_TIMEOUT_S)
    deadline = time.time() + timeout
    for t in threads:
        remaining = max(0, deadline - time.time())
        t.join(timeout=remaining)
    for _, agent in subagents:
        if agent.status == AgentStatus.RUNNING:
            agent.status = AgentStatus.TIMEOUT
            agent.progress.status = AgentStatus.TIMEOUT
    """update stats"""
    for _, agent in subagents:
        merge_agent_stats(main_ctx, agent)
    """gather subagent results"""
    messages = []
    for tc, agent in subagents:
        if agent.status == AgentStatus.DONE:
            if agent.result:
                result = {"status": DONE_LABEL, "result": f"{SUBAGENT_START_LABEL}\n"
                                                          f"{agent.result}\n"
                                                          f"{SUBAGENT_END_LABEL}"}
                sys_log.debug(f"Subagent {agent.agent_id} done, result: {agent.result[:SUBAGENT_RESULT_LOG_CHAR_LIMIT]}...")
            else:
                result = {"status": DONE_LABEL, "info": f"(There is no results from subagent)"}
                sys_log.warning(f"Subagent {agent.agent_id} done, there is no results from subagent")
        elif agent.status == AgentStatus.TIMEOUT:
            result = {"status": TIMEOUT_LABEL, "info": f"Subagent exceeded configured time limit ({agent.timeout_s:.0f}s). "
                                                       f"User should set `SUBAGENT_TIMEOUT_S` in {AGENT_CONFIGS_PATH} to increase."}
            sys_log.warning(f"Subagent {agent.agent_id} exceeded configured time limit ({agent.timeout_s:.0f}s). User should "
                            f"set `SUBAGENT_TIMEOUT_S` in {AGENT_CONFIGS_PATH} to increase.")
        elif agent.status == AgentStatus.RUNNING and agent.result is None:
            result = {"status": FAIL_LABEL,
                      "info": f"Subagent used all {agent.max_steps} steps without completing. User should set `SUBAGENT_MAX_STEPS` "
                              f"in {AGENT_CONFIGS_PATH} to increase, or you should give a more specific prompt."}
            sys_log.warning(f"Subagent {agent.agent_id} used all {agent.max_steps} steps without completing. User should "
                            f"set `SUBAGENT_MAX_STEPS` in {AGENT_CONFIGS_PATH} to increase")
        elif agent.status == AgentStatus.PENDING:
            result = {"status": UNKNOWN_LABEL,
                      "info": f"Subagent terminated with {AgentStatus.PENDING.value} status with unknown reason.",
                      "result": f"{agent.result or '(There is no results from subagent)'}",
                      "error": f"{agent.error or '(There is no error info from subagent)'}"}
            sys_log.warning(f"Subagent {agent.agent_id} terminated with {AgentStatus.PENDING.value} status with unknown reason.")
        elif agent.status == AgentStatus.ERROR:
            result = {"status": FAIL_LABEL,
                      "info": f"Subagent failed with error. Details: {agent.error or '(There is no error info from subagent)'}"}
            sys_log.error(f"Subagent {agent.agent_id} failed with error. Details: {agent.error or '(There is no error info from subagent)'}")
            progress.console.print(f"Subagent {agent.agent_id} failed with error. "
                                   f"Details: {agent.error or '(There is no error info from subagent)'}", style="bold red")
        else:
            result = {"status": UNKNOWN_LABEL,
                      "info": f"Subagent terminated with {agent.status.value} status with unknown reason.",
                      "result": f"{agent.result or '(There is no results from subagent)'}",
                      "error": f"{agent.error or '(There is no error info from subagent)'}"}
            sys_log.warning(f"Subagent {agent.agent_id} terminated with {agent.status.value} status with unknown reason.")
            progress.console.print(f"Subagent {agent.agent_id} terminated with {agent.status.value} status with "
                                   f"unknown reason.", style="bold yellow")
        agent.progress.if_archived = True
        """print per-agent summary (match live display)"""
        progress.console.print(render_subagent_line(agent.progress))
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps(result, ensure_ascii=False),
        })
    """persist subagent summaries for resume display"""
    _save_subagent_summaries(main_ctx.session_uuid, {
        tc["id"]: {
            "subagent_type": agent.progress.subagent_type,
            "subject": agent.progress.subject,
            "status": agent.progress.status.value,
            "tool_calls_done": agent.progress.tool_calls_done,
            "elapsed_s": agent.progress.elapsed_s,
            "input_tokens": agent.progress.input_tokens,
            "output_tokens": agent.progress.output_tokens,
            "agent_id": agent.agent_id,
        }
        for tc, agent in subagents
    })

    return messages
