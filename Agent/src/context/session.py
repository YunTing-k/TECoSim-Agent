# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.7\n
Description: Session management of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.7       Yu Huang     1.0               First implementation\n
2026.4.15      Yu Huang     1.1               Query prompts and message history\n
2026.4.16      Yu Huang     1.2               Agent context realization with logic merge\n
2026.4.28      Yu Huang     1.3               Permission request support\n

Details:
Session create, resume
------------------------------------------------------------------------------------------------------------------------
"""
import os
import uuid
import json
import logging

from argparse import Namespace
from prompt_toolkit import PromptSession, cursor_shapes
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from typing import Any
from rich.console import Console
from src.constants import *

sys_log = logging.getLogger('logger')


def query_session(session_uuid: str | None, console: Console) -> tuple[str, PromptSession[Any]]:
    """create a session or resume a session with given UUID"""
    if session_uuid is None:
        return create_session(console)
    else:
        return resume_session(session_uuid, console)


def create_session(console: Console) -> tuple[str, PromptSession[Any]]:
    """create a session"""
    uuid_obj = uuid.uuid4()
    uuid_str = uuid_obj.__str__()
    path = "./session/" + uuid_str
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            sys_log.debug(f"Session of {uuid_str}'s folder created in {path}")
            session = PromptSession(
                history=FileHistory(path + "/user_history"),
                auto_suggest=AutoSuggestFromHistory(),
                mouse_support=True,
                show_frame=True,
                cursor=cursor_shapes.CursorShape.BLINKING_UNDERLINE,
                enable_system_prompt=True
            )
            sys_log.debug(f"Session of {uuid_str} created")
            console.print(f"Session of [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] created")
            return uuid_str, session
        except Exception as e:
            sys_log.error(f"Failed to create session of {uuid_str} with error: {e}")
            console.print(f"Failed to create session of {uuid_str} with error: {e}", style="bold red")
            raise RuntimeError(e)
    else:
        sys_log.error(f"Path of session with UUID: {uuid_str} already exists")
        console.print(f"Path of session with UUID: {uuid_str} already exists", style="bold red")
        raise RuntimeError(f"Path of session with UUID: {uuid_str} already exists")


def resume_session(session_uuid: str, console: Console) -> tuple[str, PromptSession[Any]]:
    """resume a session with given UUID"""
    try:
        uuid_obj = uuid.UUID(session_uuid)
        uuid_str = uuid_obj.__str__()
        path = "./session/" + uuid_str
        if not os.path.exists(path):
            sys_log.error(f"Resuming session of {uuid_str}'s path not exist")
            console.print(f"Resuming session of {uuid_str}'s path not exist", style="bold red")
            raise RuntimeError(f"Resuming session of {uuid_str}'s path not exists")
        try:
            session = PromptSession(
                history=FileHistory(path + "/user_history"),
                auto_suggest=AutoSuggestFromHistory(),
                mouse_support=True,
                show_frame=True,
                cursor=cursor_shapes.CursorShape.BLINKING_UNDERLINE,
                enable_system_prompt=True
            )
            sys_log.debug(f"Session of {uuid_str} resumed")
            console.print(f"Session of [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] resumed")
            return uuid_str, session
        except Exception as e:
            sys_log.error(f"Failed to resume session of {uuid_str} with error: {e}")
            console.print(f"Failed to resume session of {uuid_str} with error: {e}", style="bold red")
            raise RuntimeError(e)
    except ValueError:
        sys_log.error(f"Invalid session UUID: {session_uuid}")
        console.print(f"Invalid session UUID: {session_uuid}", style="bold red")
        raise RuntimeError(f"Invalid session UUID: {session_uuid}")
    except Exception as e:
        sys_log.error(f"Failed to resume session of {session_uuid} with error: {e}")
        console.print(f"Failed to resume session of {session_uuid} with error: {e}", style="bold red")
        raise RuntimeError(e)


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
        # params
        self.session_uuid: str = ""  # (don't dump)
        self.agent_session: PromptSession | None = None  # (don't dump)
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_tokens: int = 0
        self.total_uncached_tokens: int = 0
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
            f"{BASH_RMRF_LABEL}": False,
            f"{BASH_RMR_LABEL}": False,
            f"{BASH_RMF_LABEL}": False,
            f"{BASH_RM_LABEL}": False,
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
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_uncached_tokens": self.total_uncached_tokens,
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
            self.total_input_tokens = in_dict["total_input_tokens"]
            self.total_output_tokens = in_dict["total_output_tokens"]
            self.total_tokens = in_dict["total_tokens"]
            self.total_uncached_tokens = in_dict["total_uncached_tokens"]
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
