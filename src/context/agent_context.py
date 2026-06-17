# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.29
Description: Context management of the TECoSim agent

Revision:
---------
2026.4.29      Yu Huang      1.0      Separate from session module
2026.4.29      Yu Huang      1.1      Builtin commands support
2026.5.12      Yu Huang      1.2      Edit file support
2026.5.15      Yu Huang      1.3      Agent skills support
2026.5.19      Yu Huang      1.4      Webpage fetch support
2026.5.20      Yu Huang      1.5      Web search support
2026.5.22      Yu Huang      1.6      Agent MCPs support & Summarize session title support
2026.5.27      Yu Huang      1.7      Glob and grep file support
2026.5.28      Yu Huang      1.8      Add read-only paths support
2026.5.31      Yu Huang      1.9      Define used file/dir. paths in constants.py
2026.6.3       Yu Huang      2.0      Add cron tasks support
2026.6.5       Yu Huang      2.1      Add --nosystem, --notools, --nocrons support
2026.6.9       Yu Huang      2.2      Add design and run support for simulator & Revise the highlight of the IO console print
2026.6.10      Yu Huang      2.3      Add reminder for LLM to manage workflow proactively
2026.6.12      Yu Huang      2.4      Add subagent_mute flag and agent_list registry for subagent coordination
2026.6.13      Yu Huang      2.5      Add background_agents registry + stale agent cleanup on session resume
2026.6.14      Yu Huang      2.6      Fix: file_read_log path key, bg timeout tracking, if_summarized, cron file guard
2026.6.17      Yu Huang      2.7      Support inserting messages during tool calls

Details:
---------
Central `AgentContext` class holding all agent state: configs (API, agent, MCP), messages/tools/skills, runtime objects
(LLM client, prompt session, MCP router, cron tasks), usage statistics (tokens, LLM requests), simulation tracking (designs,
runs), permissions, read-only paths, and file-read log. Provides serialization (to_dict/from_dict), context save/load to
session files, and cron task lifecycle (add/remove/save).
"""
import os
import uuid
import json
import logging
import threading
from pathlib import Path
from croniter import croniter
from openai import OpenAI
from datetime import datetime
from argparse import Namespace
from prompt_toolkit import PromptSession
from typing import Any, TypedDict, TYPE_CHECKING
from rich.console import Console
from src.tool.mcps_support import MCPToolRouter
from src.tool.simulator_support import DesignManager, RunManager
from src.agent.progress import SubAgentProgress, AgentStatus
if TYPE_CHECKING: from src.agent.subagent import SubAgent
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

class CronDump(TypedDict):
    """Cron task information to dump"""
    id: str
    prompt: str
    cron_str: str
    if_repeat: bool

class CronTask(TypedDict):
    """Cron task for runtime"""
    id: str
    prompt: str
    cron_str: str
    cron: croniter
    next_time: datetime
    durable: bool
    if_repeat: bool
    if_end: bool


class AgentContext:
    """context of TECoSim agent"""
    def __init__(self):
        # configs
        self.args: Namespace = Namespace()  # (don't dump, shared)
        self.api_configs: dict[str, Any] = {"None": None}  # (don't dump, shared)
        self.agent_configs: dict[str, Any] = {"None": None}  # (don't dump, shared)
        self.mcps_configs: list[dict[str, Any]] = []  # (don't dump, shared)
        # prompts
        self.messages: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        self.tools: list[dict[str, Any]] = [{"None": None}]  # (don't dump)
        self.skills: list[dict[str, str]] = []   # (don't dump)
        # objects
        self.agent_session: PromptSession | None = None  # (don't dump)
        self.llm_client: OpenAI | None = None  # (don't dump, shared)
        self.url_caches: list[URLCache] = []  # (don't dump)
        self.mcp_router: MCPToolRouter = MCPToolRouter([])  # (don't dump, shared)
        self.durable_crons: list[CronDump] = []  # (don't dump, read-only)
        self.session_crons: list[CronDump] = []  # (don't dump, read-only)
        self.cron_tasks: list[CronTask] = []
        self.cron_ids: list[str] = []  # (don't dump)
        self.active_cron: int = 0  # (don't dump)
        self.design_man: DesignManager = DesignManager() # (shared)
        self.run_man: RunManager = RunManager() # (shared)
        self.agent_list: dict[str, SubAgentProgress] = {}  # agent_id -> SubAgentProgress
        self.background_agents: list[tuple[dict[str, Any], "SubAgent", threading.Thread, float]] = []  # (don't dump) (tc, agent, thread, start_time)
        # params
        self.agent_id: str = MAIN_AGENT_ID  # (don't dump)
        self.session_uuid: str = ""  # (don't dump, shared)
        self.if_summarized: bool = False
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
        self.system_read_only_paths: list[Path] = []  # (don't dump)
        self.read_only_paths: list[Path] = []
        self.task_tool_unuse: int = 0
        self.files_read: dict[str, int] = {}
        self.loaded_skills: list[dict[str, str]] = []
        # signals
        self.task_end: bool = True  # (don't dump)
        self.subagent_mute: bool = False  # (don't dump) suppress console output and permission TUIs for subagents
        self.input_queue = None  # (don't dump) InputQueue | None, set by main loop after console is ready
        self.permissions: dict[str, bool] = {
            # basic tools
            AGENT_SPAWN_TOOL_NAME: False,
            TOOL_NAME_CREATE_CRON: False,
            TOOL_NAME_QUERY_CRON: False,
            TOOL_NAME_REMOVE_CRON: False,
            BASH_HIGH_RISK_LABEL: False,
            BASH_PACKAGE_LABEL: False,
            BASH_NETWORK_LABEL: False,
            BASH_REMOVAL_RF_LABEL: False,
            BASH_REMOVAL_R_LABEL: False,
            BASH_REMOVAL_F_LABEL: False,
            BASH_REMOVAL_LABEL: False,
            BASH_CHMOD_LABEL: False,
            BASH_CHOWN_LABEL: False,
            BASH_FILE_LABEL: False,
            BASH_INLINE_SCRIPT_LABEL: False,
            BASH_REPOSITORY_MODIFY_LABEL: False,
            BASH_STAGE_CHANGE_LABEL: False,
            BASH_UNKNOWN_LABEL: False,
            BASH_SAFE_LABEL: False,
            TOOL_NAME_GLOB_FILE: False,
            TOOL_NAME_GREP_FILE: False,
            TOOL_NAME_READ_FILE: False,
            TOOL_NAME_WRITE_FILE: False,
            TOOL_NAME_EDIT_FILE: False,
            TOOL_NAME_SKILL: False,
            TOOL_NAME_WEB_FETCH: False,
            TOOL_NAME_WEB_SEARCH: False,
            # simulation tools
            TOOL_NAME_INIT_DESIGN: False,
            TOOL_NAME_LAUNCH_SIM: False,
            TOOL_NAME_READ_LOG: False,
        }


    def file_read_log(self, path: str):
        """read-in file log, convert input path into absolute path"""
        file_path = os.path.abspath(path)
        if file_path not in self.files_read.keys():
            self.files_read[file_path] = 1
        else:
            self.files_read[file_path] += 1


    def add_cron_task(self, cron_task: CronTask):
        """add cron task to context"""
        self.cron_tasks.append(cron_task)  # add task in runtime
        self.cron_ids.append(cron_task["id"])   # add id
        assert self.active_cron >= 0
        self.active_cron += 1


    def remove_cron_task(self, task_id: str) -> tuple[bool, str]:
        """remove cron task from context with id"""
        if not task_id in self.cron_ids:
            return False, f"Cron task with id: {task_id} not found"

        try:
            for idx, cron_task in enumerate(self.cron_tasks):
                if cron_task["id"] == task_id:
                    if cron_task["if_repeat"]:
                        assert self.active_cron >= 1
                        self.active_cron -= 1
                    if not cron_task["if_repeat"] and not cron_task["if_end"]:
                        assert self.active_cron >= 1
                        self.active_cron -= 1
                    del self.cron_tasks[idx]
                    break
            for idx, cid in enumerate(self.cron_ids):
                if cid == task_id:
                    del self.cron_ids[idx]
            return True, SUCCESS_LABEL
        except Exception as e:
            return False, f"Remove cron task with id: {task_id} failed with error: {e}"


    def save_cron_task(self):
        """save cron tasks to files (overwrite files, duplicate task will be dropped, so make sure the id is unique)"""
        if self.args.nocrons:  # no cron tasks, no need to save anything
            return
        durable_crons: list[CronDump] = []
        session_crons: list[CronDump] = []
        for cron in self.cron_tasks:
            cron_dump = CronDump(
                id=cron["id"],
                prompt=cron["prompt"],
                cron_str=cron["cron_str"],
                if_repeat=cron["if_repeat"]
            )
            if cron["durable"]:
                if not cron["if_repeat"]:
                    if not cron["if_end"]:
                        durable_crons.append(cron_dump)
                else:
                    durable_crons.append(cron_dump)
            else:
                if not cron["if_repeat"]:
                    if not cron["if_end"]:
                        session_crons.append(cron_dump)
                else:
                    session_crons.append(cron_dump)

        uuid_obj = uuid.UUID(self.session_uuid)
        uuid_str = uuid_obj.__str__()
        path = os.path.join(SESSION_PATH, uuid_str, CRON_NAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_crons, f, indent=2, ensure_ascii=False)

        with open(CRON_CONFIGS_PATH, "w", encoding="utf-8") as f:
            json.dump(durable_crons, f, indent=2, ensure_ascii=False)


    def to_dict(self, console: Console, mute: bool = False) -> dict:
        """convert class to dict"""
        out_dict = {
            "if_summarized": self.if_summarized,
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
            "read_only_paths": [str(p) for p in self.read_only_paths]
                               if len(self.read_only_paths) > 0 else [],
            "task_tool_unuse": self.task_tool_unuse,
            "files_read": self.files_read,
            "loaded_skills": self.loaded_skills,
            "permissions": self.permissions,
            "agent_list": {aid: p.to_dict() for aid, p in self.agent_list.items()},
        }
        if not mute:
            sys_log.debug(f"Context of session {self.session_uuid} converted to dict")
            console.print(f"[{MAJOR_COLOR2}]Context[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}[/bright_black] "
                          f"converted to dict")
        return out_dict


    def from_dict(self, in_dict: dict[str, Any], console: Console, mute: bool = False):
        """convert dict to class"""
        try:
            self.if_summarized = in_dict["if_summarized"]
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
            self.read_only_paths = [Path(s) for s in in_dict["read_only_paths"]] \
                                   if len(in_dict["read_only_paths"]) > 0 else []
            self.task_tool_unuse = in_dict["task_tool_unuse"]
            self.files_read = in_dict["files_read"]
            self.loaded_skills = in_dict["loaded_skills"]
            self.permissions = in_dict["permissions"]
            if "agent_list" in in_dict:
                self.agent_list = {aid: SubAgentProgress.from_dict(d) for aid, d in in_dict["agent_list"].items()}
                for p in self.agent_list.values():
                    if not p.if_archived:
                        p.status = AgentStatus.ERROR
                        p.if_archived = True
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} converted from dict")
                console.print(f"[{MAJOR_COLOR2}]Context[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                              f"[/bright_black] converted from dict")
        except Exception as e:
            sys_log.error(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}")
            console.print(f"Failed to convert session {self.session_uuid}'s context from dict with error: {e}", style="bold red")
            raise RuntimeError(e)


    def save_context(self, console: Console, mute: bool = False):
        """save TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            """context save"""
            path = os.path.join(SESSION_PATH, uuid_str, CONTEXT_NAME)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(console, mute), f, indent=2, ensure_ascii=False)
            """durable and session cron tasks save"""
            self.save_cron_task()
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} saved")
                console.print(f"[{MAJOR_COLOR2}]Context[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}[/bright_black] saved")
        except Exception as e:
            sys_log.error(f"Failed to save session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to save session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)


    def load_context(self, console: Console, mute: bool = False):
        """load TECoSim agent's context"""
        try:
            uuid_obj = uuid.UUID(self.session_uuid)
            uuid_str = uuid_obj.__str__()
            """context load"""
            path = os.path.join(SESSION_PATH, uuid_str, CONTEXT_NAME)
            with open(path, 'r', encoding="utf-8") as f:
                in_dict = json.load(f)
            """session cron tasks load"""
            if not self.args.nocrons:
                path = os.path.join(SESSION_PATH, uuid_str, CRON_NAME)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        self.session_crons = json.load(f)
                else:
                    self.session_crons = []
            if not mute:
                sys_log.debug(f"Context of session {self.session_uuid} loaded")
                console.print(f"[{MAJOR_COLOR2}]Context[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}[/bright_black] loaded")
            self.from_dict(in_dict, console, mute)
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to load session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)
