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
2026.5.12      Yu Huang     1.2               Edit file support\n
2026.5.15      Yu Huang     1.3               Agent skills support\n
2026.5.19      Yu Huang     1.4               Webpage fetch support\n
2026.5.20      Yu Huang     1.5               Web search support\n
2026.5.22      Yu Huang     1.6               Agent MCPs support & Summarize session title support\n
2026.5.27      Yu Huang     1.7               Glob and grep file support\n
2026.5.28      Yu Huang     1.8               Add read-only paths support\n
2026.5.31      Yu Huang     1.9               Define used file/dir. paths in constants.py\n

Details:
Agent's context management with save/load
------------------------------------------------------------------------------------------------------------------------
"""
import os
import uuid
import json
import logging

from pathlib import Path
from openai import OpenAI
from datetime import datetime
from argparse import Namespace
from prompt_toolkit import PromptSession
from typing import Any, TypedDict
from rich.console import Console
from src.tool.mcps_support import MCPToolRouter
from src.constants import *

sys_log = logging.getLogger('logger')


class RequestLLMCancelled(Exception):
    """Raised when user cancels requesting LLM"""

class WebFetchCancelled(Exception):
    """Raised when user cancels web fetch"""

class WebSearchCancelled(Exception):
    """Raised when user cancels web search"""


class URLCache(TypedDict):
    """URL cache with time and content"""
    url: str
    time: datetime
    content: str


class AgentContext:
    """context of TECoSim agent"""
    def __init__(self):
        # configs
        self.args: Namespace = Namespace()  # (don't dump)
        self.api_configs: dict[str, Any] = {"None": None}  # (don't dump)
        self.agent_configs: dict[str, Any] = {"None": None}  # (don't dump)
        self.mcps_configs: list[dict[str, Any]] = []  # (don't dump)
        # prompts
        self.messages: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        self.tools: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        self.skills: list[dict[str, str]] = []   # (don't dump)
        # objects
        self.agent_session: PromptSession | None = None  # (don't dump)
        self.llm_client: OpenAI | None = None  # (don't dump)
        self.url_caches: list[URLCache] = []  # (don't dump)
        self.mcp_router: MCPToolRouter = MCPToolRouter([])  # (don't dump)
        # params
        self.session_uuid: str = ""  # (don't dump)
        self.session_title: str = DEFAULT_SESSION_TITLE
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
        self.system_read_only_paths: list[Path] = []  # (don't dump)
        self.read_only_paths: list[Path] = []
        self.files_read: dict[str, int] = {}
        self.loaded_skills: list[dict[str, str]] = []
        # signals
        self.task_end: bool = True  # (don't dump)
        self.permissions: dict[str, bool] = {
            # basic tools
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
            f"{BASH_SAFE_LABEL}": False,
            "glob_file": False,
            "grep_file": False,
            "read_file": False,
            "write_file": False,
            "edit_file": False,
            "skill": False,
            "web_fetch": False,
            "web_search": False,
            # expert tools
            "init_design": False,
            "copy_design": False,
            "launch_simulator": False,
            "read_log": False,
        }


    def file_read_log(self, path: str):
        """read-in file log"""
        file_path = os.path.abspath(path)
        if path not in self.files_read.keys():
            self.files_read[file_path] = 1
        else:
            self.files_read[file_path] += 1


    def to_dict(self, console: Console, mute: bool = False) -> dict:
        """convert class to dict"""
        out_dict = {
            "session_title": self.session_title,
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
            "read_only_paths": [str(p) for p in self.read_only_paths]
                               if len(self.read_only_paths) > 0 else [],
            "files_read": self.files_read,
            "loaded_skills": self.loaded_skills,
            "permissions": self.permissions
        }
        if not mute:
            sys_log.debug(f"Context of session {self.session_uuid} converted to dict")
            console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] converted to dict")
        return out_dict


    def from_dict(self, in_dict: dict[str, Any], console: Console, mute: bool = False):
        """convert dict to class"""
        try:
            self.session_title = in_dict["session_title"]
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
            self.read_only_paths = [Path(s) for s in in_dict["read_only_paths"]] \
                                   if len(in_dict["read_only_paths"]) > 0 else []
            self.files_read = in_dict["files_read"]
            self.loaded_skills = in_dict["loaded_skills"]
            self.permissions = in_dict["permissions"]
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} converted from dict")
                console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] converted from dict")
        except Exception as e:
            sys_log.error(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}")
            console.print(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}", style="bold red")
            raise RuntimeError(e)


    def save_context(self, console: Console, mute: bool = False):
        """save TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            # path = SESSION_PATH + uuid_str + "/context.json"
            path = os.path.join(SESSION_PATH, uuid_str, CONTEXT_NAME)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(console, mute), f, indent=2, ensure_ascii=False)
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} saved")
                console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] saved")
        except Exception as e:
            sys_log.error(f"Failed to save session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to save session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)


    def load_context(self, console: Console, mute: bool = False):
        """load TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            # path = SESSION_PATH + uuid_str + "/context.json"
            path = os.path.join(SESSION_PATH, uuid_str, CONTEXT_NAME)
            with open(path, 'r', encoding="utf-8") as f:
                in_dict = json.load(f)
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} loaded")
                console.print(f"Context of session [{MAJOR_COLOR2}]{self.session_uuid}[/{MAJOR_COLOR2}] loaded")
            self.from_dict(in_dict, console, mute)
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to load session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)
