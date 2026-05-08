# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.29\n
Description: Session management of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.29      Yu Huang     1.0               Separate from session module\n
2026.4.29      Yu Huang     1.1               Builtin commands support\n

Details:
Agent's context management with save/load
------------------------------------------------------------------------------------------------------------------------
"""
import uuid
import json
import logging

from argparse import Namespace
from prompt_toolkit import PromptSession
from typing import Any
from rich.console import Console
from src.constants import *

sys_log = logging.getLogger('logger')

class AgentContext:
    """context of TECoSim agent"""
    def __init__(self):
        # configs
        self.args: Namespace = Namespace()  # (don't dump)
        self.api_configs: dict[str, Any] = {"None": None}  # (don't dump)
        self.agent_configs: dict[str, Any] = {"None": None}  # (don't dump)
        # prompts
        self.messages: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        self.tools: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        # objects
        self.agent_session: PromptSession | None = None  # (don't dump)
        self.console: Console | None = None  # (don't dump)
        # params
        self.session_uuid: str = ""  # (don't dump)
        self.system_prompts: int = 0  # (don't dump)
        self.tools_prompts: int = 0  # (don't dump)
        self.user_prompts: int = 0
        self.content_prompts: int = 0
        self.reasoning_prompts: int = 0
        self.tool_calls_prompts: int = 0
        self.tool_results_prompts: int = 0
        self.total_llm_requests: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_tokens: int = 0
        self.total_uncached_tokens: int = 0
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_tokens: int = 0
        self.simulation_launched: int = 0
        self.design_created: list[int] = []
        # signals
        self.task_end: bool = True  # (don't dump)
        self.permissions: dict[str, bool] = {
            "init_design": False,
            "copy_design": False,
            "launch_simulator": False,
            "read_log": False,
            "read_file": False,
            "write_file": False,
            f"{BASH_HIGH_RISK_LABEL}": False,
            f"{BASH_PACKAGE_LABEL}": False,
            f"{BASH_NETWORK_LABEL}": False,
            f"{BASH_REMOVAL_RF_LABEL}": False,
            f"{BASH_REMOVAL_R_LABEL}": False,
            f"{BASH_REMOVAL_F_LABEL}": False,
            f"{BASH_REMOVAL_LABEL}": False,
            f"{BASH_CHMOD_LABEL}": False,
            f"{BASH_CHOWN_LABEL}": False,
            f"{BASH_FILE_LABEL}": False,
            f"{BASH_REPOSITORY_MODIFY_LABEL}": False,
            f"{BASH_STAGE_CHANGE_LABEL}": False,
            f"{BASH_UNKNOWN_LABEL}": False,
            f"{BASH_SAFE_LABEL}": False
        }

    def to_dict(self, console: Console) -> dict:
        """convert class to dict"""
        out_dict = {
            "user_prompts": self.user_prompts,
            "content_prompts": self.content_prompts,
            "reasoning_prompts": self.reasoning_prompts,
            "tool_calls_prompts": self.tool_calls_prompts,
            "tool_results_prompts": self.tool_results_prompts,
            "total_llm_requests": self.total_llm_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_uncached_tokens": self.total_uncached_tokens,
            "last_input_tokens": self.last_input_tokens,
            "last_output_tokens": self.last_output_tokens,
            "last_tokens": self.last_tokens,
            "simulation_launched": self.simulation_launched,
            "design_created": self.design_created,
            "permissions": self.permissions
        }

        sys_log.debug(f"Context of session {self.session_uuid} converted to dict")
        console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] converted to dict")
        return out_dict

    def from_dict(self, in_dict: dict[str, Any], console: Console):
        """convert dict to class"""
        try:
            self.user_prompts = in_dict["user_prompts"]
            self.content_prompts = in_dict["content_prompts"]
            self.reasoning_prompts = in_dict["reasoning_prompts"]
            self.tool_calls_prompts = in_dict["tool_calls_prompts"]
            self.tool_results_prompts = in_dict["tool_results_prompts"]
            self.total_llm_requests = in_dict["total_llm_requests"]
            self.total_input_tokens = in_dict["total_input_tokens"]
            self.total_output_tokens = in_dict["total_output_tokens"]
            self.total_tokens = in_dict["total_tokens"]
            self.total_uncached_tokens = in_dict["total_uncached_tokens"]
            self.last_input_tokens = in_dict["last_input_tokens"]
            self.last_output_tokens = in_dict["last_output_tokens"]
            self.last_tokens = in_dict["last_tokens"]
            self.simulation_launched = in_dict["simulation_launched"]
            self.design_created = in_dict["design_created"]
            self.permissions = in_dict["permissions"]

            sys_log.debug(f"Context of session {self.session_uuid} converted from dict")
            console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] converted from dict")
        except Exception as e:
            sys_log.error(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}")
            console.print(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}", style="bold red")
            raise RuntimeError(e)

    def save_context(self, console: Console):
        """save TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            path = "./session/" + uuid_str + "/context.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(console), f, indent=2, ensure_ascii=False)
            sys_log.debug(f"Context of session {self.session_uuid} saved")
            console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] saved")
        except Exception as e:
            sys_log.error(f"Failed to save session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to save session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)

    def load_context(self, console: Console):
        """load TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            path = "./session/" + uuid_str + "/context.json"
            with open(path, 'r', encoding="utf-8") as f:
                in_dict = json.load(f)
            sys_log.debug(f"Context of session {self.session_uuid} loaded")
            console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] loaded")
            self.from_dict(in_dict, console)
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to load session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)
