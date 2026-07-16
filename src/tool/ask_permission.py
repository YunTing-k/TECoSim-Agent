# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.12
Description: Ask user permission realization

Revision:
---------
2026.5.12      Yu Huang      1.0      Separate from ui_info.py
2026.5.12      Yu Huang      1.1      TUI event trigger support
2026.5.28      Yu Huang      1.2      Truncate permission request desc if it is too long
2026.5.30      Yu Huang      1.3      Optimize the hardware occupancy of TUI
2026.6.1       Yu Huang      1.4      Define TUI selection prefixes in constants.py
2026.6.4       Yu Huang      1.5      Add support of comment when user deny permission request
2026.6.6       Yu Huang      1.6      Bugfix of submit action in all ask permission TUIs
2026.6.7       Yu Huang      1.7      Revise the display style of all ask permission TUIs & Add newline and space padding
                                      for all ask permission TUIs
2026.6.12      Yu Huang      1.8      Add subagent_mute flag for subagent coordination
2026.7.3       Yu Huang      1.9      Bugfix of buffered keyboard press before real TUI interaction

Details:
---------
Permission request TUI with 4 options: "Yes" (one-time), "Yes, and agree all same request" (session-level), "No", "No, and
I have something to say" (with optional comment input). Skips if `dangerously_allow_all` is set or permission already granted.
Supports keyboard navigation and comment input via prompt_toolkit.
"""
import time
import logging

from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from prompt_toolkit.keys import Keys
from src.context.agent_context import AgentContext
from src.utility.basic_utils import get_user_input, create_clean_input
from src.constants import *

sys_log = logging.getLogger('logger')


def render_permission(active_idx: int, request_type: str, request_desc: str, user_cache: str):
    """render the permission panel according to the selection"""
    panels = []
    header_text = Text("Permission Request", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"\nTECoSim Agent want to request permission for ", style="white")
    body.append(f"{request_type}\n", style=f"bold {MAJOR_COLOR1}")
    body.append(f"Request detail: ", style="white")
    limit = PERMISSION_REQUEST_DSEC_CHAR_MAX
    if len(request_desc) > limit:
        body.append(f"{request_desc[:limit]} ... (truncated)\n\n", style="bright_black")
    else:
        body.append(f"{request_desc}\n\n", style="bright_black")
    str_list = ["Yes",
                "Yes, and agree all same request during this agent session",
                "No",
                "No, and I have something to say"]
    for i in range(4):
        is_selected = active_idx == i
        prefix1 = OPTIONS_TO_SELECT_PREFIX if is_selected else OPTIONS_UN_SELECT_PREFIX
        prefix2 = OPTIONS_SELECTED_PREFIX if is_selected else OPTIONS_UNSELECTED_PREFIX
        if is_selected:
            label_style = f"bold {MAJOR_COLOR2}"
        else:
            label_style = "white"
        if i != 3:
            body.append(f"{prefix1}{str_list[i]}{prefix2}\n\n", style=label_style)
        else:
            body.append(f"{prefix1}{str_list[i]}{prefix2}\n", style=label_style)
            body.append(f"    {user_cache}\n\n", style=TUI_USER_COMMENT_COLOR)
    if body.plain.endswith("\n"):
        body.rstrip()
    panels.append(Panel(body, title=header_text, title_align="left", border_style=MAJOR_COLOR2))
    if active_idx != 3:
        hint = Text(f"  ↑/↓ (select)    Enter (choose)\n", style="bright_black")
    else:
        hint = Text(f"  ↑/↓ (select)    Enter (modify)    Ctrl+Enter (confirm)\n", style="bright_black")
    return Group(*panels, hint)


def ask_permission_tui(ctx: AgentContext, request_type: str, request_desc: str, console: Console) -> tuple[bool, str | None]:
    """top realization of asking user for permission TUI"""
    limit = PERMISSION_REQUEST_DSEC_CHAR_MAX
    active_idx = 0  # default active option
    user_cache = ""
    if ctx.args.dangerously_allow_all:
        return True, None
    if ctx.tui_mute:
        if request_type in ctx.permissions and ctx.permissions[request_type]:
            return True, None
        return False, None
    if request_type in ctx.permissions:
        if ctx.permissions[request_type]:
            return True, None
    else:
        sys_log.warning(f"Unsupported request type: {request_type}")
        console.print(f"Unsupported request type: {request_type}", style="bold yellow")
        ctx.permissions[request_type] = False

    while True:
        input_device = create_clean_input()
        action = None
        try:
            with input_device.raw_mode():
                with Live(render_permission(active_idx, request_type, request_desc, user_cache),
                          console=console, auto_refresh=False, transient=True, vertical_overflow="visible") as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 4
                                live.update(render_permission(active_idx, request_type, request_desc, user_cache))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 4
                                live.update(render_permission(active_idx, request_type, request_desc, user_cache))
                                live.refresh()
                            elif key.key == Keys.Enter:
                                if active_idx != 3:
                                    action = "choose"
                                else:
                                    action = "input"
                                break
                            elif key.key == Keys.ControlJ:  # get answers
                                action = "submit"
                                break
                            elif key.key == Keys.Escape or key.key == Keys.ControlC:
                                action = "cancel"
                                break
                        if action is not None:  # no action no break
                            break
                        if not key_press:
                            time.sleep(KEY_LISTEN_SLEEP_TIME_MS / 1000.0)
        finally:
            input_device.close()

        if action == "choose":
            if active_idx == 0:
                return True, None
            elif active_idx == 1:
                ctx.permissions[request_type] = True
                return True, None
            elif active_idx == 2:
                return False, None
            elif active_idx == 3:
                active_idx = 2  # this should not happen
            else:
                return False, None
        if action == "input":  # choose I have sth to say label
            if ctx.agent_session is not None:
                console.print()
                user_cache, is_empty, is_modify = get_user_input(user_cache, ctx.agent_session,
                                                                 f"{AGENT_CONSOLE_ICON} Your comment for request: \n  ")
                if is_empty:  # if empty, unselect
                    active_idx = 2
                elif is_modify:  # if non-empty and modified, select
                    active_idx = 3
                else:  # if non-empty and not modified, select
                    active_idx = 3
            else:
                active_idx = 2
        if action == "submit":
            if active_idx == 3:
                if user_cache.strip():
                    return False, user_cache
                else:
                    return False, None
        if action == "cancel":
            if len(request_desc) > limit:
                sys_log.warning(f"Quest: {request_type} with desc. {request_desc[:limit]} ... (truncated) canceled, "
                                f"permission denied")
                console.print(f"Quest: {request_type} with desc. {request_desc[:limit]} ... (truncated) canceled, "
                              f"permission denied", style="bold yellow")
            else:
                sys_log.warning(f"Quest: {request_type} with desc. {request_desc} canceled, permission denied")
                console.print(f"Quest: {request_type} with desc. {request_desc} canceled, permission denied",
                              style="bold yellow")
            return False, None
