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

Details:
System prompts, Reminder, Tools
------------------------------------------------------------------------------------------------------------------------
"""
import os
import platform
import subprocess
from typing import Dict, Any
import logging
from rich.console import Console

sys_log = logging.getLogger('logger')


def create_prompts(api_configs: Dict[str, Any], agent_configs: Dict[str, Any], console: Console):
    """create prompts of
      - system (agent role, guideline, dynamic boundaries)
      - tools"""
    """system: agent role"""
    prompts1 = get_agent_role_prompts()
    """system: agent guideline"""
    prompts2 = get_agent_guideline_prompts()
    """system: dynamic boundaries"""
    prompts3 = get_agent_dynamic_prompts(api_configs)
    sys_log.debug("System prompts generated")
    """tools"""

    sys_log.debug("Tools prompts generated")

    if agent_configs["MERGE_SYSTEM_PROMPTS"]:
        prompts = prompts1
        prompts[0]["content"] += (prompts2[0]["content"])
        prompts[0]["content"] += (prompts3[0]["content"])
    else:
        prompts = prompts1 + prompts2 + prompts3
    sys_log.debug("System & tools prompts assembled")
    return prompts


def get_agent_role_prompts():
    """get system prompts of TECoSim agent's role"""
    prompts = [{"role": "system", "content":
                "You are TECoSim Agent, developed by Yu Huang from Shanghai Jiao Tong University.\n"}]
    return prompts


def get_agent_guideline_prompts():
    """get system prompts of TECoSim agent's guideline"""
    prompts = [{"role": "system", "content":
                "You are an interactive agent that embedded with TECoSim to helps user with display panel engineering tasks. "
                "Use the instructions below and the tools available to you to assist the user.\n"
                "# System\n"
                " - All text you output outside of tool use is displayed to the user. "
                "Output text to communicate with the user. You can use Github-flavored markdown for formatting.\n"
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
                "This does not apply to code or tool calls.\n"}]
    return prompts


def get_agent_dynamic_prompts(api_configs: Dict[str, Any]):
    """get system prompts of TECoSim agent's dynamic boundaries"""
    prompts = [{"role": "system", "content":
                "# Environment\n"
                "You have been invoked in the following environment: \n"
                f" - Primary working directory: {os.getcwd()}\n"
                f" - Is a git repository: {str(is_git_repo(os.getcwd()))}\n"
                f" - Platform: {get_platform_info()[0]} {get_platform_info()[1]} version: {get_platform_info()[2]}\n"
                f" - You are powered by the LLM: {api_configs["MODEL_NAME"]}"}]
    return prompts


def get_platform_info() -> [str]:
    """get the information of the running platform"""
    system = platform.system()
    release = platform.release()
    version = platform.version()
    return [system, release, version]


def is_git_repo(path: str = None):
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
    except FileNotFoundError:
        return False
