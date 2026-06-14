# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.12
Description: Agent status and progress types for TECoSim subagent coordination

Revision:
---------
2026.6.12      Yu Huang      1.0      First implementation
2026.6.13      Yu Huang      1.1      Add if_background and subject fields, replace simulate with scheduler agent type

Details:
---------
AgentStatus enum (pending/running/done/error/timeout) and SubAgentProgress dataclass with serialization. Also defines
subagent type configuration: SUPPORTED_TYPES (tool allowlists), PERMISSION_PRESETS (pre-granted permissions), and
SUPPORTED_TYPES_DESC (LLM-facing descriptions).
"""
from enum import Enum
from dataclasses import dataclass
from typing import Any
from src.constants import *


class AgentStatus(str, Enum):
    PENDING = AGENT_PENDING_LABEL
    RUNNING = AGENT_RUNNING_LABEL
    TIMEOUT = AGENT_TIMEOUT_LABEL
    ERROR = AGENT_ERROR_LABEL
    DONE = AGENT_DONE_LABEL


@dataclass
class SubAgentProgress:
    agent_id: str
    subagent_type: str
    subject: str
    status: AgentStatus
    if_background: bool = False
    if_archived: bool = False
    step: int = 0
    current_tool: str = ""
    tool_calls_done: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    last_activity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "subagent_type": self.subagent_type,
            "subject": self.subject,
            "status": self.status.value,
            "if_background": self.if_background,
            "if_archived": self.if_archived,
            "step": self.step,
            "current_tool": self.current_tool,
            "tool_calls_done": self.tool_calls_done,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "last_activity": self.last_activity,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SubAgentProgress":
        return cls(
            agent_id=d["agent_id"],
            subagent_type=d["subagent_type"],
            subject=d.get("subject", ""),
            status=AgentStatus(d["status"]),
            if_background=d.get("if_background", False),
            if_archived=d.get("if_archived", False),
            step=d.get("step", 0),
            current_tool=d.get("current_tool", ""),
            tool_calls_done=d.get("tool_calls_done", 0),
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            last_activity=d.get("last_activity", 0.0),
        )


SUPPORTED_TYPES: dict[str, tuple[str, ...]] = {
    EXPLORER_AGENT_LABEL: (
        TOOL_NAME_GLOB_FILE,
        TOOL_NAME_GREP_FILE,
        TOOL_NAME_READ_FILE,
        TOOL_NAME_WEB_FETCH,
        TOOL_NAME_WEB_SEARCH,
        TOOL_NAME_BASH,
        TOOL_NAME_READ_LOG,
        TOOL_NAME_CREATE_TASK,
        TOOL_NAME_UPDATE_TASK,
        TOOL_NAME_QUERY_TASK,
    ),
    WORKER_AGENT_LABEL: (),
    SCHEDULER_AGENT_LABEL: (
        TOOL_NAME_CREATE_TASK,
        TOOL_NAME_UPDATE_TASK,
        TOOL_NAME_QUERY_TASK,
        TOOL_NAME_GLOB_FILE,
        TOOL_NAME_GREP_FILE,
        TOOL_NAME_READ_FILE,
        TOOL_NAME_WEB_FETCH,
        TOOL_NAME_WEB_SEARCH,
        TOOL_NAME_BASH,
    ),
}

PERMISSION_PRESETS: dict[str, tuple[str, ...]] = {
    EXPLORER_AGENT_LABEL: (
        TOOL_NAME_GLOB_FILE,
        TOOL_NAME_GREP_FILE,
        TOOL_NAME_READ_FILE,
        TOOL_NAME_WEB_FETCH,
        TOOL_NAME_WEB_SEARCH,
        TOOL_NAME_READ_LOG,
        TOOL_NAME_CREATE_TASK,
        TOOL_NAME_UPDATE_TASK,
        TOOL_NAME_QUERY_TASK,
        BASH_SAFE_LABEL,
        BASH_NETWORK_LABEL,
    ),
    WORKER_AGENT_LABEL: (
        TOOL_NAME_GLOB_FILE,
        TOOL_NAME_GREP_FILE,
        TOOL_NAME_READ_FILE,
        TOOL_NAME_WRITE_FILE,
        TOOL_NAME_EDIT_FILE,
        TOOL_NAME_WEB_FETCH,
        TOOL_NAME_WEB_SEARCH,
        TOOL_NAME_READ_LOG,
        TOOL_NAME_CREATE_TASK,
        TOOL_NAME_UPDATE_TASK,
        TOOL_NAME_QUERY_TASK,
        BASH_SAFE_LABEL,
        BASH_NETWORK_LABEL,
        BASH_FILE_LABEL,
    ),
    SCHEDULER_AGENT_LABEL: (
        TOOL_NAME_CREATE_TASK,
        TOOL_NAME_UPDATE_TASK,
        TOOL_NAME_QUERY_TASK,
        TOOL_NAME_GLOB_FILE,
        TOOL_NAME_GREP_FILE,
        TOOL_NAME_READ_FILE,
        TOOL_NAME_WEB_FETCH,
        TOOL_NAME_WEB_SEARCH,
        BASH_SAFE_LABEL,
    ),
}

SUPPORTED_TYPES_DESC: dict[str, str] = {
    EXPLORER_AGENT_LABEL: (
        f"Read-only explorer. Can use {TOOL_NAME_GLOB_FILE}, `{TOOL_NAME_GREP_FILE}`, `{TOOL_NAME_READ_FILE}`, "
        f"`{TOOL_NAME_WEB_FETCH}`, `{TOOL_NAME_WEB_SEARCH}`, `{TOOL_NAME_BASH}`, `{TOOL_NAME_READ_LOG}`, plus task tools "
        f"(`{TOOL_NAME_CREATE_TASK}` / `{TOOL_NAME_UPDATE_TASK}` / `{TOOL_NAME_QUERY_TASK}`) for own workflow (independent "
        f"scoreboard)."
    ),
    WORKER_AGENT_LABEL: (
        "General-purpose worker agent for research, multi-step tasks, and implementation. Has all tools except spawning other "
        "agents and cron tasks management. Can use task tools for their own workflow (independent scoreboard)."
    ),
    SCHEDULER_AGENT_LABEL: (
        f"Task planning and dependency management agent with shared scoreboard access. Can use {TOOL_NAME_CREATE_TASK} / "
        f"{TOOL_NAME_UPDATE_TASK} / {TOOL_NAME_QUERY_TASK} to plan and organize work, set task dependencies, delete incorrect "
        f"tasks, and can access read-only tools. Tasks it creates are available for main-agent and subagent that have shared "
        f"scoreboard access."
    ),
}
