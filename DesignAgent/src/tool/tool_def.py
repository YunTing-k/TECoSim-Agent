# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.14\n
Description: Tools prompts for TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.14      Yu Huang     1.0               First implementation\n

Details:
Tools prompts of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import subprocess
import logging

from typing import Dict, Any
from rich.console import Console
from src.constants import *

sys_log = logging.getLogger('logger')


def create_tools_prompts(console: Console) -> list[dict[str, Any]]:
    """create prompts of all available tools"""
    prompts = tool_agent_version_def()  # test
    return prompts


def tool_agent_version_def() -> list[dict[str, Any]]:
    """tool definition of get current version of TECoSim Agent (get_agent_version)"""
    tool_def = [
        {
            "type": "function",
            "function": {
                "name": "get_agent_version",
                "description": "Get the current version of the TECoSim Agent",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            }
        }
    ]
    return tool_def


def get_agent_version() -> str:
    """get the dev version of TECoSim agent"""
    return f"{TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"
