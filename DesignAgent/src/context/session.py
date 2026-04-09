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

Details:
Session create, resume
------------------------------------------------------------------------------------------------------------------------
"""
import os
import uuid
import logging

from prompt_toolkit import PromptSession, cursor_shapes
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from src.constants import *

sys_log = logging.getLogger('logger')


def query_session(session_uuid: str, console: Console) -> [str, PromptSession]:
    """create a session or resume a session with UUID"""
    if session_uuid is None:
        return create_session(console)
    else:
        return resume_session(session_uuid, console)


def create_session(console: Console) -> [str, PromptSession]:
    """create a session"""
    uuid_obj = uuid.uuid4()
    uuid_str = uuid_obj.__str__()
    path = "./session/" + uuid_str
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            sys_log.debug(f"Session of {uuid_str}'s folder created in {path}")
            session = PromptSession(
                history=FileHistory(path + "/history"),
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
            sys_log.error(f"Failed to create session of {uuid_str} with unknown error: {e}")
            console.print(f"[bold red]Failed to create session of {uuid_str} with unknown error: {e}[/bold red]")
    else:
        sys_log.error(f"Session with UUID: {uuid_str} already exists")
        console.print(f"[bold red]Session with UUID: {uuid_str} already exists[/bold red]")


def resume_session(session_uuid: str, console: Console) -> [str, PromptSession]:
    """resume a session with UUID"""
    try:
        uuid_obj = uuid.UUID(session_uuid)
        uuid_str = uuid_obj.__str__()
        path = "../session/" + uuid_str
        if not os.path.exists(path):
            sys_log.error(f"Resuming session of {uuid_str} is empty")
            console.print(f"[bold red]Resuming session of {uuid_str} is empty[/bold red]")
        try:
            session = PromptSession(
                history=FileHistory(path + "/history"),
                auto_suggest=AutoSuggestFromHistory(),
                mouse_support=True
            )
            sys_log.debug(f"Session of {uuid_str} resumed")
            console.print(f"Session of [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] resumed")
            return uuid_str, session
        except Exception as e:
            sys_log.error(f"Failed to resume session of {uuid_str} with unknown error: {e}")
            console.print(f"[bold red]Failed to resume session of {uuid_str} with unknown error: {e}[/bold red]")
    except ValueError:
        sys_log.error(f"Invalid session UUID: {session_uuid}")
        console.print(f"[bold red]Invalid session UUID: {session_uuid}[/bold red]")
    except Exception as e:
        sys_log.error(f"Failed to resume session of {session_uuid} with unknown error: {e}")
        console.print(f"[bold red]Failed to resume session of {session_uuid} with unknown error: {e}[/bold red]")


def query_prompts(session_uuid: str, console: Console):
    """create new prompts or resume prompts with session UUID"""
    # if session_uuid is None:
    #     return prompt.create_prompts(console)
    # else:
    #     return prompt.resume_prompts(session_uuid, console)
