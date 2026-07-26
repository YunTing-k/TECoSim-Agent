# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.7
Description: Session management of the TECoSim agent

Revision:
---------
2026.4.7       Yu Huang      1.0      First implementation
2026.4.15      Yu Huang      1.1      Query prompts and message history
2026.4.16      Yu Huang      1.2      Agent context realization with logic merge
2026.4.28      Yu Huang      1.3      Permission request support
2026.4.29      Yu Huang      1.4      Builtin commands support
2026.5.13      Yu Huang      1.5      Bugfix of Mouse scrolling
2026.5.15      Yu Huang      1.6      Revise builtin command management with class
2026.5.15      Yu Huang      1.7      Agent skills support
2026.5.28      Yu Huang      1.8      Multi-line user prompt input support
2026.5.29      Yu Huang      1.9      Add unknown command's completer support
2026.5.31      Yu Huang      2.0      Add CLI session management support & Define used file/dir. paths in constants.py
2026.6.2       Yu Huang      2.1      Revise session list's layout and add usage info
2026.6.3       Yu Huang      2.2      Revise session list info & Add configurable title in yes or no request TUI
2026.6.13      Yu Huang      2.3      Bugfix: session list displays N/A instead of -0.0K when token data unavailable
2026.6.29      Yu Huang      2.4      Add session title info when removing sessions
2026.7.23      Yu Huang      2.5      Add launch support in arbitrary path

Details:
---------
Session lifecycle management: creates new sessions (UUID folder, prompt_tkit PromptSession with key bindings, command completer,
auto-suggest, multiline support), resumes existing sessions by UUID, and provides CLI operations (list/remove sessions with
confirmation TUI). `cmd_lexer` parses builtin commands (starting with "/") and dispatches to `BuiltinCommands`.
"""
import os
import uuid
import json
import shutil
import logging

from typing import Any
from argparse import Namespace
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit import PromptSession, cursor_shapes
from prompt_toolkit.history import FileHistory
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.text import Text
from rich.panel import Panel
from rich.console import Console
from src.utility import basic_utils, ui_info
from src.utility.command import BuiltinCommands, BUILTIN_UNKNOWN
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
            display = "/" + after_slash + " "
            meta = "Unknown command"
            yield Completion(
                display,
                start_position=-len(text),
                display_meta=meta,
            )


def cmd_lexer(cmd_in: str, cmd_object: BuiltinCommands) -> tuple[str, list[str]] | None:
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
    for cmd, (_, _, _) in cmd_object:
        if cmd == cmd_name:
            return cmd, cmd_args

    """unknown command"""
    return BUILTIN_UNKNOWN, cmd_args


def multiline_bindings() -> KeyBindings:
    """key bindings for multi-line input"""
    kb = KeyBindings()

    @kb.add(Keys.Enter)
    def _(event):
        """Enter submit"""
        buffer = event.current_buffer
        buffer.validate_and_handle()

    @kb.add(Keys.BackTab)
    def _(event):
        """Shift+Tab inset new line"""
        event.current_buffer.insert_text('\n')

    return kb


def get_prompt_session(path: str, cmd_object: BuiltinCommands) -> PromptSession:
    """get the prompt session"""
    cmd_completer = CmdCompleter(commands=[cmd for cmd, (_, _, _) in cmd_object],
                                 meta_dict={cmd: label for cmd, (_, label, _) in cmd_object})
    session = PromptSession(
        # history=FileHistory(path + "/user_history"),
        history=FileHistory(os.path.join(path, USER_HISTORY_NAME)),
        auto_suggest=AutoSuggestFromHistory(),
        mouse_support=False,
        key_bindings=multiline_bindings(),
        multiline=True,
        show_frame=True,
        cursor=cursor_shapes.CursorShape.BLINKING_UNDERLINE,
        validator=PromptValidator(),
        completer=cmd_completer
    )
    return session


def query_session(session_uuid: str | None, console: Console, cmd_object: BuiltinCommands) -> tuple[str, PromptSession]:
    """create a session or resume a session with given UUID"""
    if session_uuid is None:
        return create_session(console, cmd_object)
    else:
        return resume_session(session_uuid, console, cmd_object)


def create_session(console: Console, cmd_object: BuiltinCommands) -> tuple[str, PromptSession]:
    """create a session"""
    uuid_obj = uuid.uuid4()
    uuid_str = uuid_obj.__str__()
    # path = "./session/" + uuid_str
    path = str(AGENT_PATH / SESSION_PATH / uuid_str)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            sys_log.debug(f"Session of {uuid_str}'s folder created in {path}")
            session = get_prompt_session(path, cmd_object)
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


def resume_session(session_uuid: str, console: Console, cmd_object: BuiltinCommands) -> tuple[str, PromptSession]:
    """resume a session with given UUID"""
    try:
        uuid_obj = uuid.UUID(session_uuid)
        uuid_str = uuid_obj.__str__()
        # path = "./session/" + uuid_str
        path = str(AGENT_PATH / SESSION_PATH / uuid_str)
        if not os.path.exists(path):
            sys_log.error(f"Resuming session of {uuid_str}'s path not exist")
            console.print(f"Resuming session of {uuid_str}'s path not exist", style="bold red")
            raise RuntimeError(f"Resuming session of {uuid_str}'s path not exists")
        try:
            session = get_prompt_session(path, cmd_object)
            sys_log.debug(f"Session of {uuid_str} is resuming")
            console.print(f"Session of [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] is resuming")
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


def session_entry_cli(args: Namespace, console: Console):
    """session CLI operations support"""
    if args.command != "session":
        return

    """session operations"""
    if args.session_action == 'list':
        session_list_cli(console)
    elif args.session_action == 'remove':
        session_remove_cli(args, console)
    else:
        sys_log.warning(f"Unknown session action: {args.session_action}")
        console.print(f"Unknown session action: {args.session_action}", style="bold yellow")
        sys.exit(-1)

    """session action doesn't entry main program"""
    sys_log.info("Program end for session entry cli")
    sys.exit(0)


def session_list_cli(console: Console):
    """query all sessions"""
    session_dir = str(AGENT_PATH / SESSION_PATH)
    if not os.path.exists(session_dir):
        sys_log.error(f"Session directory {session_dir} does not exist")
        console.print(f"Session directory {session_dir} does not exist", style="bold red")
        return

    sessions_list:list[dict[str, Any]] = []
    for item in os.listdir(session_dir):
        item_path = os.path.join(session_dir, item)
        if not os.path.isdir(item_path):
            continue
        if not basic_utils.is_valid_uuid(item):
            continue

        context_file = os.path.join(item_path, CONTEXT_NAME)
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)
            sessions_list.append({"uuid": item,
                                  "title": context.get("session_title", UNKNOWN_SESSION_TITLE),
                                  "input_tokens": context.get("last_input_tokens", -1)})
        except Exception as e:
            sys_log.error(f"Failed to load session {item}'s context with error {e}")
            console.print(f"Failed to load session {item}'s context with error {e}", style="bold red")

    sys_log.info(f"Loaded {len(sessions_list)} sessions")
    title = f"Available Sessions ({len(sessions_list)})"
    cmd_str = Text()
    for session in sessions_list:
        token_str = "N/A" if session["input_tokens"] == -1 else f"{session["input_tokens"] / 1000.0:.1f} K tokens"
        cmd_str.append(f"UUID: ", style=f"white")
        cmd_str.append(f"{session["uuid"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Title: ", style=f"white")
        cmd_str.append(f"{session["title"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f" ({token_str})\n", style=f"bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))


def session_remove_cli(args: Namespace, console: Console):
    """remove a session"""
    session_dir = str(AGENT_PATH / SESSION_PATH)
    if not os.path.exists(session_dir):
        sys_log.error(f"Session directory {session_dir} does not exist")
        console.print(f"Session directory {session_dir} does not exist", style="bold red")
        return

    try:
        """validate UUID"""
        uuid_str: str = str(args.uuid)
        if not basic_utils.is_valid_uuid(uuid_str):
            sys_log.error(f"Session UUID: {uuid_str} is not valid")
            console.print(f"Session UUID: {uuid_str} is not valid", style="bold red")
            return

        """check the path"""
        if not os.path.exists(os.path.join(session_dir, uuid_str)):
            sys_log.error(f"Session with UUID: {uuid_str} not exists")
            console.print(f"Session with UUID: {uuid_str} not exists", style="bold red")
            return
        if os.path.isfile(os.path.join(session_dir, uuid_str)):
            sys_log.error(f"Session with UUID: {uuid_str} is a file, not a directory")
            console.print(f"Session with UUID: {uuid_str} is a file, not a directory", style="bold red")
            return

        """read session title"""
        context_file = os.path.join(session_dir, uuid_str, CONTEXT_NAME)
        session_title = UNKNOWN_SESSION_TITLE
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)
            session_title = context.get("session_title", UNKNOWN_SESSION_TITLE)
        except Exception as e:
            sys_log.error(f"Failed to load session {uuid_str}'s context with error {e}")

        """delete the session folder"""
        token = ui_info.request_tui(console=console, title="Remove Session", request_desc=f"remove the session: {uuid_str} (Title: {session_title})",
                                    request_detail=f"This session will be deleted forever",
                                    cancel_str=f"Session remove cancelled")
        if token:
            shutil.rmtree(os.path.join(session_dir, uuid_str))
            sys_log.debug(f"Session with UUID: {uuid_str} (Title: {session_title}) has been removed")
            console.print(f"Session with UUID: [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] (Title: [{MAJOR_COLOR2}]{session_title}[/{MAJOR_COLOR2}]) has been removed")
        else:
            sys_log.debug(f"Session with UUID: {uuid_str} (Title: {session_title}) remove cancelled")
            console.print(f"Session with UUID: [{MAJOR_COLOR2}]{uuid_str}[/{MAJOR_COLOR2}] (Title: [{MAJOR_COLOR2}]{session_title}[/{MAJOR_COLOR2}]) remove cancelled")
            return

    except Exception as e:
        sys_log.error(f"Remove session with args: {args} failed with error: {e}")
        console.print(f"Remove session with args: {args} failed with error: {e}", style="bold red")
