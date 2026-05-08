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
2026.4.29      Yu Huang     1.4               Builtin commands support\n

Details:
Session management with create, resume
------------------------------------------------------------------------------------------------------------------------
"""
import os
import uuid
import logging

from typing import Any
from prompt_toolkit import PromptSession, cursor_shapes
from prompt_toolkit.history import FileHistory
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from src.utility.command import BUILTIN_COMMANDS, BUILTIN_UNKNOWN
from src.constants import *

sys_log = logging.getLogger('logger')

class PromptValidator(Validator):
    """validator for prompt"""
    def validate(self, document):
        text = document.text
        if not text.strip():
            raise ValidationError(
                message="Please enter some text",
                cursor_position=0,
            )


class CmdCompleter(Completer):
    """completer of builtin commands"""
    def __init__(self, commands: list[str], meta_dict: dict[str, str]):
        self.commands = commands
        self.meta_dict = meta_dict
        self.cmd_unknown: bool = True

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        clean_text = text.lstrip()
        """cmd start with '/' """
        if not clean_text.startswith("/"):
            return

        """get the str after '/' """
        after_slash = clean_text[1:]
        parts = after_slash.split()
        if not parts:  # empty
            prefix = ""
        else:
            prefix = parts[0]  # typing command (part)

        """traverse all commands and complete match one"""
        self.cmd_unknown = True
        for cmd in self.commands:
            if cmd.startswith(prefix):
                self.cmd_unknown = False
                display = "/" + cmd
                meta = self.meta_dict.get(cmd, "")
                yield Completion(
                    display,
                    start_position=-len(text),
                    display_meta=meta,
                )
        """unmatched command"""
        if self.cmd_unknown:
            display = "/" + after_slash
            meta = "Unknown command"
            yield Completion(
                display,
                start_position=-len(text),
                display_meta=meta,
            )


def cmd_lexer(cmd_in: str) -> tuple[str, list[str]] | None:
    """builtin commands lexer"""
    clean_cmd = cmd_in.strip()
    """empty"""
    if not clean_cmd:
        return None

    """invalid format"""
    if not clean_cmd.startswith("/"):
        return None

    """split into cmd name and args"""
    parts = clean_cmd[1:].split()
    cmd_name = parts[0]
    cmd_args = parts[1:]

    """check if the cmd is valid"""
    for cmd, (_, _, _) in BUILTIN_COMMANDS.items():
        if cmd == cmd_name:
            return cmd, cmd_args

    """unknown command"""
    return BUILTIN_UNKNOWN, cmd_args



def get_prompt_session(path: str) -> PromptSession:
    """get the prompt session"""
    cmd_completer = CmdCompleter(commands=[cmd for cmd, (_, _, _) in BUILTIN_COMMANDS.items()],
                                 meta_dict={cmd: label for cmd, (_, label, _) in BUILTIN_COMMANDS.items()})
    session = PromptSession(
        history=FileHistory(path + "/user_history"),
        auto_suggest=AutoSuggestFromHistory(),
        mouse_support=True,
        show_frame=True,
        cursor=cursor_shapes.CursorShape.BLINKING_UNDERLINE,
        validator=PromptValidator(),
        completer=cmd_completer
    )
    return session


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
            session = get_prompt_session(path)
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
            session = get_prompt_session(path)
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
