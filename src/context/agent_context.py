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
2026.7.15-16   Yu Huang      2.7      Add WeChat bot interaction support
2026.7.17      Yu Huang      2.8      Fix: last response of LLM won't be missed if bot keep sending WeChat msg
2026.7.23      Yu Huang      2.9      Add launch support in arbitrary path
2026.7.26      Yu Huang      3.0      Support of dumping webfetch caches to file & Revise TUI info for session file I/O

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
from croniter import croniter
from openai import OpenAI
from datetime import datetime, timedelta
from argparse import Namespace
from prompt_toolkit import PromptSession
from typing import Any, TypedDict, TYPE_CHECKING
from rich.console import Console
from src.tool.wechat_support import WeChatBridge, WeChatQueuedMsg
from src.tool.mcps_support import MCPToolRouter
from src.tool.simulator_support import DesignManager, RunManager
from src.agent.agent_types import SubAgentProgress, AgentStatus
if TYPE_CHECKING: from src.agent.subagent import SubAgent
from src.constants import *

sys_log = logging.getLogger('logger')


class RequestLLMCancelled(Exception):
    """Raised when user cancels requesting LLM"""

class WebFetchCancelled(Exception):
    """Raised when user cancels web fetch"""

class WebSearchCancelled(Exception):
    """Raised when user cancels web search"""

class URLCacheDump(TypedDict):
    """URL cache information to dump"""
    url: str
    time: float
    content: str

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


PERMISSION_LABEL_TO_NAME_MAP: dict[str, str] = {
    # basic tools
    "TOOL_NAME_SPAWN_AGENT": TOOL_NAME_SPAWN_AGENT,
    "TOOL_NAME_CREATE_CRON": TOOL_NAME_CREATE_CRON,
    "TOOL_NAME_REMOVE_CRON": TOOL_NAME_REMOVE_CRON,
    "BASH_HIGH_RISK_LABEL": BASH_HIGH_RISK_LABEL,
    "BASH_PACKAGE_LABEL": BASH_PACKAGE_LABEL,
    "BASH_NETWORK_LABEL": BASH_NETWORK_LABEL,
    "BASH_REMOVAL_RF_LABEL": BASH_REMOVAL_RF_LABEL,
    "BASH_REMOVAL_R_LABEL": BASH_REMOVAL_R_LABEL,
    "BASH_REMOVAL_F_LABEL": BASH_REMOVAL_F_LABEL,
    "BASH_REMOVAL_LABEL": BASH_REMOVAL_LABEL,
    "BASH_CHMOD_LABEL": BASH_CHMOD_LABEL,
    "BASH_CHOWN_LABEL": BASH_CHOWN_LABEL,
    "BASH_FILE_LABEL": BASH_FILE_LABEL,
    "BASH_INLINE_SCRIPT_LABEL": BASH_INLINE_SCRIPT_LABEL,
    "BASH_REPOSITORY_MODIFY_LABEL": BASH_REPOSITORY_MODIFY_LABEL,
    "BASH_STAGE_CHANGE_LABEL": BASH_STAGE_CHANGE_LABEL,
    "BASH_UNKNOWN_LABEL": BASH_UNKNOWN_LABEL,
    "BASH_SAFE_LABEL": BASH_SAFE_LABEL,
    "TOOL_NAME_GLOB_FILE": TOOL_NAME_GLOB_FILE,
    "TOOL_NAME_GREP_FILE": TOOL_NAME_GREP_FILE,
    "TOOL_NAME_READ_FILE": TOOL_NAME_READ_FILE,
    "TOOL_NAME_WRITE_FILE": TOOL_NAME_WRITE_FILE,
    "TOOL_NAME_EDIT_FILE": TOOL_NAME_EDIT_FILE,
    "TOOL_NAME_SKILL": TOOL_NAME_SKILL,
    "TOOL_NAME_WEB_FETCH": TOOL_NAME_WEB_FETCH,
    "TOOL_NAME_WEB_SEARCH": TOOL_NAME_WEB_SEARCH,
    # WeChat tools
    "TOOL_NAME_WECHAT_SEND_FILE": TOOL_NAME_WECHAT_SEND_FILE,
    # simulation tool"
    "TOOL_NAME_INIT_DESIGN": TOOL_NAME_INIT_DESIGN,
    "TOOL_NAME_LAUNCH_SIM": TOOL_NAME_LAUNCH_SIM,
    "TOOL_NAME_READ_LOG": TOOL_NAME_READ_LOG,
}

PERMISSION_NAME_TO_LABEL_MAP: dict[str, str] = {v: k for k, v in PERMISSION_LABEL_TO_NAME_MAP.items()}


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
        self.webfetch_caches: list[URLCache] = []
        self.wechat_bot: WeChatBridge | None = None  # (don't dump)
        self.last_wechat_msg: WeChatQueuedMsg | None = None  # (don't dump)
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
        self.enable_wechat: bool = False  # (don't dump)
        self.wechat_reply_count: int = 0  # (don't dump)
        self.wechat_reply_total_count: int = 0
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
        self.tui_mute: bool = False  # (don't dump) suppress console output and permission TUIs for all agents
        self.permissions: dict[str, bool] = {  # can be override if WeChat is enabled
            # basic tools
            TOOL_NAME_SPAWN_AGENT: False,
            TOOL_NAME_CREATE_CRON: False,
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
            # WeChat tools
            TOOL_NAME_WECHAT_SEND_FILE: False,
            # simulation tools
            TOOL_NAME_INIT_DESIGN: False,
            TOOL_NAME_LAUNCH_SIM: False,
            TOOL_NAME_READ_LOG: False,
        }


    def config_wechat_permission(self, config: dict[str, Any]):
        """configure the permission of Agent if WeChat is enabled (exclude MCPs)"""
        for k, v in PERMISSION_LABEL_TO_NAME_MAP.items():
            if isinstance(config.get(k), bool):
                self.permissions[v] = config.get(k)
            else:
                continue


    def file_read_log(self, path: str):
        """read-in file log, convert input path into absolute path"""
        file_path = os.path.abspath(path)
        if file_path not in self.files_read.keys():
            self.files_read[file_path] = 1
        else:
            self.files_read[file_path] += 1


    def config_webfetch_cache(self, url_dumps: list[URLCacheDump]):
        """config webfetch cache from list of URLCacheDump"""
        for dump in url_dumps:
            cache = URLCache(url=dump["url"],
                             time=datetime.fromtimestamp(dump["time"]),
                             content=dump["content"])
            self.webfetch_caches.append(cache)


    def get_webfetch_cache_dump(self) -> list[URLCacheDump]:
        """get Web fetch caches' dump checking expiration"""
        url_dumps: list[URLCacheDump] = []
        now = datetime.now()
        for cache in self.webfetch_caches:
            # check if URL is expired
            previous = cache["time"]
            if now - previous < timedelta(seconds=self.agent_configs.get("WEB_FETCH_CACHE_TIME_S", WEB_FETCH_CACHE_DEFAULT_TIME_S)):
                cache_dump = URLCacheDump(
                    url=cache["url"],
                    time=cache["time"].timestamp(),
                    content=cache["content"],
                )
                url_dumps.append(cache_dump)
            else:
                continue
        return url_dumps


    def save_webfetch_cache(self, console: Console, mute: bool = False):
        """save webfetch cache to file
        (prefer not to use this method when URL cache is large in save_context, which will be frequently called)"""
        uuid_obj = uuid.UUID(self.session_uuid)
        uuid_str = uuid_obj.__str__()
        path = str(AGENT_PATH / SESSION_PATH / uuid_str / WEBFETCH_CACHE_NAME)

        url_dumps = self.get_webfetch_cache_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(url_dumps, f, indent=2, ensure_ascii=False)

        sys_log.debug(f"Webfetch caches with {len(url_dumps)} entries of session {self.session_uuid} saved")
        if not mute:
            console.print(
                f"[{MAJOR_COLOR2}]Webfetch caches[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(url_dumps)}[/{MAJOR_COLOR2}] "
                f"entries of session [bright_black]{self.session_uuid}[/bright_black] saved")


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


    def save_cron_task(self, console: Console, mute: bool = False):
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
        path = str(AGENT_PATH / SESSION_PATH / uuid_str / CRON_NAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_crons, f, indent=2, ensure_ascii=False)
        sys_log.debug(f"{len(session_crons)} cron tasks of session {self.session_uuid} saved")
        if not mute:
            console.print(
                f"[{MAJOR_COLOR2}]{len(session_crons)} cron tasks[/{MAJOR_COLOR2}] of session "
                f"[bright_black]{self.session_uuid}[/bright_black] saved")

        with open(str(AGENT_PATH / CRON_CONFIGS_PATH), "w", encoding="utf-8") as f:
            json.dump(durable_crons, f, indent=2, ensure_ascii=False)
        sys_log.debug(f"{len(durable_crons)} cron tasks across sessions saved")
        if not mute:
            console.print(f"[{MAJOR_COLOR2}]{len(durable_crons)} cron tasks[/{MAJOR_COLOR2}] across sessions saved")


    def to_dict(self, console: Console, mute: bool = False) -> dict:
        """convert class to dict"""
        out_dict = {
            "wechat_reply_total_count": self.wechat_reply_total_count,
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
        sys_log.debug(f"Context of session {self.session_uuid} converted to dict")
        if not mute:
            console.print(f"[{MAJOR_COLOR2}]Context[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}[/bright_black] "
                          f"converted to dict")
        return out_dict


    def from_dict(self, in_dict: dict[str, Any], console: Console, mute: bool = False):
        """convert dict to class"""
        try:
            self.wechat_reply_total_count = in_dict["wechat_reply_total_count"]
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
                    if not p.if_archived: # non-archived agent in file config when resuming means error (run killed etc.)
                        p.status = AgentStatus.ERROR
                        p.if_archived = True
            sys_log.debug(f"Context of session {self.session_uuid} converted from dict")
            if not mute:
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
            path = str(AGENT_PATH / SESSION_PATH / uuid_str / CONTEXT_NAME)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(console, mute), f, indent=2, ensure_ascii=False)
            """webfetch cache save"""
            self.save_webfetch_cache(console, mute)
            """durable and session cron tasks save"""
            self.save_cron_task(console, mute)
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
            path = str(AGENT_PATH / SESSION_PATH / uuid_str / CONTEXT_NAME)
            with open(path, 'r', encoding="utf-8") as f:
                in_dict = json.load(f)
            self.from_dict(in_dict, console, mute)
            """webfetch cache load"""
            path = str(AGENT_PATH / SESSION_PATH / uuid_str / WEBFETCH_CACHE_NAME)
            with open(path, 'r', encoding="utf-8") as f:
                url_dumps = json.load(f)
            self.config_webfetch_cache(url_dumps)
            sys_log.debug(f"Webfetch caches with {len(url_dumps)} entries of session {self.session_uuid} loaded")
            if not mute:
                console.print(
                    f"[{MAJOR_COLOR2}]Webfetch caches[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(url_dumps)}[/{MAJOR_COLOR2}] "
                    f"entries of session [bright_black]{self.session_uuid}[/bright_black] loaded")
            """session cron tasks load"""
            if not self.args.nocrons:
                path = str(AGENT_PATH / SESSION_PATH / uuid_str / CRON_NAME)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        self.session_crons = json.load(f)
                else:
                    self.session_crons = []
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s context with error: {e}")
            console.print(f"Failed to load session {self.session_uuid}'s context with error: {e}", style="bold red")
            raise RuntimeError(e)
