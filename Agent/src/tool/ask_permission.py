# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.12\n
Description: Ask user permission

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.12      Yu Huang     1.0               Separate from ui_info.py\n
2026.5.12      Yu Huang     1.1               TUI event trigger support\n
2026.5.28      Yu Huang     1.2               Truncate permission request desc if it is too long\n
2026.5.30      Yu Huang     1.3               Optimize the hardware occupancy of TUI\n

Details:
Ask user permission with TUI
------------------------------------------------------------------------------------------------------------------------
"""
import time
import logging

from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def render_permission(active_idx: int, request_type: str, request_desc: str):
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
                "No"]
    for i in range(3):
        is_selected = active_idx == i
        prefix1 = "> " if is_selected else "  "
        prefix2 = " ✓" if is_selected else ""
        if is_selected:
            label_style = f"bold {MAJOR_COLOR2}"
        else:
            label_style = "white"
        body.append(f"{prefix1}{str_list[i]}{prefix2}\n\n", style=label_style)
    if body.plain.endswith("\n"):
        body.rstrip()
    panels.append(Panel(body, title=header_text, title_align="left", border_style=MAJOR_COLOR2))
    hint = Text(f"  ↑/↓ (select)    Enter (choose)\n", style="bright_black")
    return Group(*panels, hint)


def ask_permission_tui(ctx: AgentContext, request_type: str, request_desc: str, console: Console) -> bool:
    """top realization of asking user for permission TUI"""
    limit = PERMISSION_REQUEST_DSEC_CHAR_MAX
    active_idx = 0  # default active option
    if ctx.args.dangerously_allow_all:
        return True
    if request_type in ctx.permissions:
        if ctx.permissions[request_type]:
            return True
    else:
        sys_log.warning(f"Unsupported request type: {request_type}")
        console.print(f"Unsupported request type: {request_type}", style="bold yellow")
        ctx.permissions[request_type] = False

    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_permission(active_idx, request_type, request_desc),
                          console=console, auto_refresh=False, transient=True, vertical_overflow="visible") as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 3
                                live.update(render_permission(active_idx, request_type, request_desc))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 3
                                live.update(render_permission(active_idx, request_type, request_desc))
                                live.refresh()
                            elif key.key == Keys.Enter:
                                action = "choose"
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
                token = True
            elif active_idx == 1:
                ctx.permissions[request_type] = True
                token = True
            else:
                token = False
            return token
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
            return False
