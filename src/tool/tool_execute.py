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

Details:
---------
Tool execution orchestrator. `execute_tools()` classifies LLM tool-call requests into normal tools and agent
spawn calls, runs normal tools sequentially, then spawns agents concurrently in threads with progress polling.
Spinner wrappers integrate with Rich display. `call_tools` dispatch lives in `tool_dispatch.py`.
"""
import json
import uuid
import time
import random
import logging
import threading

from typing import Callable, Any
from rich.console import Console
from rich.progress import Progress
from src.utility.ui_info import loading_spinner, loading_spinner_with_board
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.tool.tool_dispatch import ToolCallsCancelled, if_tool_mute, call_tools
from src.agent.subagent import SubAgent
from src.agent.progress import AgentStatus, SubAgentProgress
from src.constants import *

sys_log = logging.getLogger('logger')


def tool_calls_spinner(func: Callable, *args, console: Console,
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
                             console=console, with_progress=True,  # add progress to target function
                             **kwargs)
    return result


def tool_calls_spinner_board(func: Callable, *args,
                             board: Scoreboard, console: Console,
                             waiting_desc: str | None = None, done_desc: str | None = None,
                             intrp_desc: str | None = None, fail_desc: str | None = None,
                             spinner: str | None = None, if_random: bool,
                             agent_list: dict[str, SubAgentProgress] | None = None, **kwargs) -> Any:
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
                                        board=board, agent_list=agent_list,
                                        waiting_desc=waiting_title, done_desc=done_title,
                                        intrp_desc=intrp_title, fail_desc=fail_title,
                                        spinner=spinner_choice,
                                        out_except=ToolCallsCancelled("Tool call is cancelled by user"),
                                        console=console, with_progress=True,
                                        **kwargs)
    return result


def execute_tools(tool_calls: list[dict[str, Any]], ctx: AgentContext, board: Scoreboard, progress: Progress) -> list[dict[str, Any]]:
    """execute the tools in the LLM tool calls with AgentContext

    Phase 1: execute all non-agent tool calls sequentially (original path).
    Phase 2: spawn all agent tool calls concurrently in threads, poll progress, merge results.
    """
    messages = []
    normal_calls = []
    agent_calls = []

    for tc in tool_calls:
        if tc["function"]["name"] == AGENT_SPAWN_TOOL_NAME:
            agent_calls.append(tc)
        else:
            normal_calls.append(tc)

    for tc in normal_calls:
        func_name = tc["function"]["name"]
        arguments = json.loads(tc["function"]["arguments"])
        sys_log.debug(f"Using tool: {func_name}")
        if not if_tool_mute(func_name):
            progress.console.print(f"Using tool: [{MAJOR_COLOR1}]{func_name}[/{MAJOR_COLOR1}]", style="bright_black")
        results, user_addons = call_tools(func_name, arguments, ctx, board, progress)
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps(results, ensure_ascii=False),
        })
        if user_addons is not None:
            messages.append({
                "role": "user",
                "content": json.dumps(user_addons, ensure_ascii=False),
            })

    if agent_calls:
        agent_messages = execute_subagents(agent_calls, ctx, board, progress)
        messages.extend(agent_messages)

    return messages


def generate_agent_id(ctx: AgentContext) -> str:
    """generate unique subagent ID (8-char hex), skipping MAIN_AGENT_ID and existing ids"""
    while True:
        aid = uuid.uuid4().hex[:AGENT_ID_LEN]
        if aid != MAIN_AGENT_ID and aid not in ctx.agent_list:
            return aid


def execute_subagents(agent_calls: list[dict[str, Any]], main_ctx: AgentContext, board: Scoreboard, progress: Progress) -> list[dict[str, Any]]:
    """spawn subagents concurrently, poll progress, merge results and token stats"""
    subagents: list[tuple[dict[str, Any], SubAgent]] = []
    for tc in agent_calls:
        args = json.loads(tc["function"]["arguments"])
        agent_id = generate_agent_id(main_ctx)
        sys_log.debug(f"Spawning subagent: {agent_id}")
        progress.console.print(
            f"Spawning subagent: [{MAJOR_COLOR1}]{agent_id}[/{MAJOR_COLOR1}]", style="bright_black")

        agent = SubAgent(
            parent_ctx=main_ctx,
            subagent_type=args["subagent_type"],
            prompt=args["prompt"],
            agent_id=agent_id,
            share_parent_board= False,  # TODO some agent can use read board
            parent_board= None,
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
    """wait for all threads to finish"""
    while any(t.is_alive() for t in threads):
        time.sleep(SUBAGENT_POLL_INTERVAL_S)
    for t in threads:
        t.join()
    """update stats"""
    for _, agent in subagents:
        main_ctx.total_llm_requests += agent.stats["total_llm_requests"]
        main_ctx.user_prompts += agent.stats["user_prompts"]
        main_ctx.content_prompts += agent.stats["content_prompts"]
        main_ctx.reasoning_prompts += agent.stats["reasoning_prompts"]
        main_ctx.total_input_tokens += agent.stats["total_input_tokens"]
        main_ctx.total_output_tokens += agent.stats["total_output_tokens"]
        main_ctx.total_tokens += agent.stats["total_tokens"]
        main_ctx.total_uncached_tokens += agent.stats["total_uncached_tokens"]
        main_ctx.tool_calls_prompts += agent.stats["tool_calls_prompts"]
        main_ctx.tool_results_prompts += agent.stats["tool_results_prompts"]
    """gather subagent results"""
    messages = []
    for tc, agent in subagents:
        if agent.status == AgentStatus.DONE:
            result_text = agent.result or "[done] no output"
        elif agent.status == AgentStatus.TIMEOUT:
            result_text = (
                f"[timeout] Subagent exceeded configured time limit ({agent.timeout_s:.0f}s). "
                f"Set SUBAGENT_TIMEOUT_S in {AGENT_CONFIGS_PATH} to increase."
            )
        elif agent.status == AgentStatus.RUNNING and agent.result is None:
            result_text = (
                f"[steps exhausted] Subagent used all {agent.max_steps} steps without completing. "
                f"Set SUBAGENT_DEFAULT_MAX_STEPS in {AGENT_CONFIGS_PATH} to increase, "
                f"or give a more specific prompt."
            )
        else:
            result_text = agent.result or f"[{agent.status.value}] {agent.error or 'no output'}"
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result_text,
        })
        sys_log.debug(f"Subagent {agent.agent_id} result: {result_text[:SUBAGENT_RESULT_LOG_CHAR_LIMIT]}...")

    for _, agent in subagents:
        agent.progress.if_archived = True

    return messages
