# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.8\n
Description: Prompts management of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.8       Yu Huang     1.0               First implementation\n
2026.4.15      Yu Huang     1.1               Query prompts and message history\n
2026.4.16      Yu Huang     1.2               Agent context realization with logic merge\n
2026.4.22      Yu Huang     1.3               Bash support\n
2026.4.26      Yu Huang     1.4               Reasoning support\n
2026.4.29      Yu Huang     1.5               Builtin commands support\n
2026.5.15      Yu Huang     1.6               Agent skills support\n

Details:
Prompts management with create, assemble, resume, save, load
------------------------------------------------------------------------------------------------------------------------
"""
import os
import platform
import subprocess
import logging
import json

from typing import Any

import rich.box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from src.context.agent_context import AgentContext
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
                " - Your are embedded with TECoSim (Thermo-Electric Coupling Cross-level Display Simulator), "
                "which is a high-performance display panel simulator based on C/C++ and NVIDIA CUDA. TECoSim adopts "
                "cross-level co-simulation methodology that combines bottom-up hierarchical abstraction with system-level "
                "end-to-end simulation.\n"
                " - TECoSim is efficient, system-level modeling oriented, and highly parameter-configurable, it "
                "can be used to validate arbitrary parameter-defined display panel's visual quality, voltage drop, temperature "
                "distribution under thermo-electrical coupling effect and IR drop effect with arbitrary parameter-defined "
                "working scenario and target video.\n"
                " - TECoSim carries out the system-level and panel-level simulation/analysis with multiple-hierarchy "
                "modeling. TECoSim is efficient in thermo-electric multiphysics coupled simulation and nonlinear power "
                "network quasi-static and dynamic analysis. With input target video, TECoSim is capable to give visualization "
                "of the panel's display effect and is capable to export other raw data such as whole panel's temperature, "
                "pixel current, PDN voltage drop and so on.\n"
                " - TECoSim models the whole display panel in multiple hierarchies: 1) Pixel circuit compact model with "
                "basic electrical characteristics, temperature sensitivity, hysteresis behavior and IR drop behavior. "
                "2) Based on 1), a nonlinear power distribution network (PDN) with full-panel pixels. 3) Based on 1), a "
                "thermo-electric coupling multiphysics model with full-panel pixels. 4) Based on 1), 2) and 3), a "
                "complete end-to-end piepline with Target Video → Driving Signal → Display Panel → Display Response"
                "Display Effect Visualization.\n"
                " - With user-exposed parameters, TECoSim is highly configurable in pixel circuit compact models, PDN "
                "layout/parasitic parameters, panel heat flux/contact parameters, panel specification (such as resolution, "
                "physical size and material parameters and so on), and simulation parameters (such as solving threads num, "
                "solving methods, data export configs, visualization configs and so on).\n"
                "# Guidelines\n"
                " - Before the first simulation, you should check if the simulator is available. Only recheck when needed.\n"
                " - A `design` is always needed before launching simulator for panel design or evaluation. Each design is "
                "identified by a single integer id starts from 1, and you should managed the all designs' ids and don't "
                "assume that user knows the ids. Design can be created with default value or copied from other existing "
                "designs. You can modify the design, but can't delete any design nor override it with another design by copy.\n"
                " - After each simulation, the following contents will be all outputted and managed with the unit of `run`: "
                "1) simulator's stdout log, 2) simulator's stderr log, 3) raw simulation results, 4) visualization video, "
                "5) copy of input design. Each launch of simulator will create a run and each run is identified by a single "
                "integer id starts from 1. Each run is read-only and its id is automatically managed by simulator.\n"
                " - Please use tool `read_log` to read the simulator's stdout/stderr logs in units of lines. When reading "
                "a stdout log, only read all lines of it when necessary, since the stdout log can be too long. For example, "
                "if you want to check for error information when a simulation fails, you can read a few lines of stdout "
                "log from the bottom (e.g., 50 lines) rather than reading all of the lines at once.\n"
                " - IMPORTANT: Never ever create/modify/delete any file or directory in the path of TECoSim simulator and "
                "the sub directory named `session` under primary working directory. They are read-only.\n"
                "# Tasks\n"
                " - The user will primarily request you to perform display panel engineering tasks. These may include "
                "designing a display panel from scratch with core target metis, validating specific panel's IR drop severity "
                "or validating specific panel's temperature distribution under certain working scenarios, and more. When "
                "given an unclear or generic instruction, consider it in the context of display panel engineering tasks, "
                "capability of TECoSim and other available tools.\n"
                " - You are highly capable and often allow users to complete ambitious tasks that would otherwise be too "
                "complex or take too long. You should defer to user judgement about whether a task is too large to attempt."
                " - Avoid giving time estimates or predictions for how long tasks will take, whether for your own work or "
                "for users planning projects. Focus on what needs to be done, not how long it might take.\n"
                "# Tone and style\n"
                " - Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.\n"
                " - Your responses should be short and concise.\n"
                " - Do not use a colon before tool calls. Your tool calls may not be shown directly in the output, so text "
                "like ""Let me read the file:"" followed by a read tool call should just be ""Let me read the file."" with a period.\n"
                "# Output efficiency\n"
                "IMPORTANT: Go straight to the point. Try the simplest approach first without going in circles. Do not "
                "overdo it. Be extra concise. Keep your text output brief and direct. Lead with the answer or action, "
                "not the reasoning. Skip filler words, preamble, and unnecessary transitions. Do not restate what the "
                "user said — just do it. When explaining, include only what is necessary for the user to understand.\n"
                "Focus text output on:\n"
                " - Decisions that need the user's input\n"
                " - High-level status updates at natural milestones\n"
                " - Errors or blockers that change the plan\n"
                "If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations. "
                "This does not apply to code or tool calls.\n"
                "# Session-specific guidance\n"
                " - If you do not understand why the user has denied a tool call, use the `ask_user_question` to ask them\n"
                " - IMPORTANT: Only use `skill` for skills listed in user-invocable skills section, do not guess\n"
                " - User can manually load full prompt of skill to context with /<skill-name> (e.g., /translate)\n"}]
                # " - Use the Agent tool with specialized agents when the task at hand matches the agent's description. "
                # "Subagents are valuable for parallelizing independent queries or for protecting the main context window "
                # "from excessive results, but they should not be used excessively when not needed. Importantly, avoid duplicating "
                # "work that subagents are already doing - if you delegate research to a subagent, do not also perform the "
                # "same searches yourself.\n"
    return prompts


def get_agent_environment_prompts(ctx: AgentContext) -> list[dict[str, Any]]:
    """get system prompts of TECoSim agent's dynamic boundaries with AgentContext"""
    prompts = [{"role": "system", "content":
                "# Environment\n"
                "You have been invoked in the following environment: \n"
                f" - Platform: {get_platform_info()[0]} {get_platform_info()[1]} version: {get_platform_info()[2]}\n"
                f" - Primary working directory: {os.getcwd()}\n"
                f"  - Is a git repository: {str(is_git_repo(os.getcwd()))}\n"
                f" - Is bash available: {is_bash_available()}\n"
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
                    "The following skills are user-invocable with the `skill` tool:\n"
                    f"{skill_list_str}"}]
    else:
        prompts = [{"role": "system", "content":
                    "The following skills are user-invocable with the `skill` tool:\n"
                    f"(No available skills)\n)"}]
    return prompts


def get_platform_info() -> list[str]:
    """get the information of the running platform"""
    system = platform.system()
    release = platform.release()
    version = platform.version()
    return [system, release, version]


def is_git_repo(path: str = None) -> bool:
    """check if the given path is a git repository"""
    if path is None:
        path = os.getcwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call git failed with error {e}")
        return False


def is_bash_available() -> bool:
    """check if bash is available"""
    try:
        result = subprocess.run(
            ["bash", "-c", "bash --version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call bash failed with error {e}")
        return False


def query_prompts(ctx: AgentContext, session_uuid: str | None, console: Console) -> list[dict[str, Any]]:
    """create new prompts or resume prompts from persistence file with AgentContext and given uuid"""
    messages = create_system_prompts(ctx)
    if session_uuid is None:
        pass
    else:
        resumed_prompts = read_messages(session_uuid, console)
        print_messages(resumed_prompts, ctx, console)
        messages = messages + resumed_prompts
    return messages


def read_messages(session_uuid: str, console: Console) -> list[dict[str, Any]]:
    """read messages (exclude system) from persistence file with given uuid"""
    path = "./session/" + session_uuid + "/messages.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        sys_log.debug(f"Messages of session {session_uuid} loaded")
        console.print(f"Messages of session [{MAJOR_COLOR2}]{session_uuid}[/{MAJOR_COLOR2}] loaded")
        return messages
    except Exception as e:
        sys_log.error(f"Failed to load the messages of session {session_uuid} with error: {e}")
        console.print(f"Failed to load the messages of session {session_uuid} with error: {e}", style="bold red")
        raise RuntimeError(e)


def print_messages(messages: list[dict[str, Any]], ctx: AgentContext, console: Console):
    """print the given messages (exclude system) with AgentContext"""
    try:
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                if "skill_directory" in msg["content"] and "skill_content" in msg["content"]:
                    console.print(Panel("<A skill is invoked, content is not displayed>", box=rich.box.SQUARE))
                    continue
                console.print(Panel("> " + msg["content"], box=rich.box.SQUARE))
            elif msg["role"] == "assistant":
                assistant_reasoning = get_reasoning(msg)
                if assistant_reasoning is not None and not "":
                    console.print("\n")
                    if ctx.agent_configs["RENDER_RESPONSE_AS_MD"]:
                        console.print(Markdown("{Think}: " + assistant_reasoning), style=f"italic {REASONING_COLOR}")
                    else:
                        console.print("{Think}: " + assistant_reasoning, style=f"italic {REASONING_COLOR}")
                    if msg["content"] is None:
                        console.print("\n")
                if msg["content"] is not None and not "":
                    if assistant_reasoning is None:
                        console.print("\n")
                    if ctx.agent_configs["RENDER_RESPONSE_AS_MD"]:
                        console.print(Markdown(msg["content"]), style="bold")
                    else:
                        console.print(msg["content"], style="bold")
                    console.print("\n")
                if msg["tool_calls"] is not None:
                    for tool_calls in msg["tool_calls"]:
                        tool_name = tool_calls["function"]["name"]
                        console.print(f"Tool used: [{MAJOR_COLOR1}]{tool_name}[/{MAJOR_COLOR1}]", style="bright_black")
            elif msg["role"] == "tool":
                continue
            else:
                sys_log.debug(f"Unknown role: {msg["role"]} in history massages")
                continue
    except Exception as e:
        sys_log.error(f"Failed to print the history messages with error: {e}")
        console.print(f"Failed to print the history messages with error: {e}", style="bold red")
        raise RuntimeError(e)


def save_messages(ctx: AgentContext, console: Console):
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
        sys_log.debug(f"Messages of session {ctx.session_uuid} converted")
        console.print(f"Messages of session [{MAJOR_COLOR2}]{ctx.session_uuid}[/{MAJOR_COLOR2}] converted")

        path = "./session/" + ctx.session_uuid + "/messages.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable_messages, f, indent=2, ensure_ascii=False)
        sys_log.debug(f"Messages of session {ctx.session_uuid} saved")
        console.print(f"Messages of session [{MAJOR_COLOR2}]{ctx.session_uuid}[/{MAJOR_COLOR2}] saved")
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
