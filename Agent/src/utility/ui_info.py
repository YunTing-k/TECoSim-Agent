# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.7\n
Description: UI information of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.7       Yu Huang     1.0               First implementation\n
2026.4.15      Yu Huang     1.1               Query prompts and message history\n
2026.4.26      Yu Huang     1.2               Quick interrupt support\n
2026.4.28      Yu Huang     1.3               Exit TUI support\n

Details:
UI information of agent dev version, ASCII art banner of start, error
------------------------------------------------------------------------------------------------------------------------
"""
import logging
import threading
import signal
import sys

from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.live import Live
from rich.progress import Progress, ProgressColumn, SpinnerColumn, TimeElapsedColumn
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from contextlib import contextmanager
from typing import Callable, Any
from src.utility.client import RequestLLMCancelled
from src.context import prompt
from src.context.session import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def vertical_color_grad_text(text: str, start_rgb: tuple, end_rgb: tuple) -> Text:
    """Transform multiline text into Text object with color gradient from top to down"""
    lines = text.splitlines()
    n = len(lines)
    result = Text()

    for i, line in enumerate(lines):
        ratio = i / (n - 1) if n > 1 else 0
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        result.append(line + ("\n" if i < n - 1 else ""), style=Style(color=hex_color))
    return result


def horizontal_color_grad_text(text: str, start_rgb: tuple, end_rgb: tuple) -> Text:
    """Transform multiline text into Text object with color gradient from left to right"""
    lines = text.splitlines()
    result = Text()

    for line_idx, line in enumerate(lines):
        if not line:
            result.append("\n" if line_idx < len(lines) - 1 else "")
            continue
        line_len = len(line)
        for char_idx, char in enumerate(line):
            ratio = char_idx / (line_len - 1) if line_len > 1 else 0
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            result.append(char, style=Style(color=hex_color))
        if line_idx < len(lines) - 1:
            result.append("\n")
    return result


def log_tecosim_agent_info():
    """print the agent's dev information into logger"""
    sys_log.info("Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent")
    sys_log.info("Agent Version: %d.%d.%d" %
                 (TECOSIM_AGENT_MAJOR_VERSION, TECOSIM_AGENT_MINOR_VERSION, TECOSIM_AGENT_UPDATE_VERSION))
    sys_log.info("Copyright (c) 2026, Shanghai Jiao Tong University and Yu Huang. All Rights Reserved.")
    sys_log.info("Developed by Yu Huang at SMIL Lab, School of Integrated Circuits, Shanghai Jiao Tong University.\n")


def console_tecosim_agent_info(console: Console):
    """print the agent's dev information into console"""
    banner = (
        "████████╗███████╗ ██████╗ ██████╗ ███████╗██╗███╗   ███╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗\n"
        "╚══██╔══╝██╔════╝██╔════╝██╔═══██╗██╔════╝██║████╗ ████║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝\n"
        "   ██║   █████╗  ██║     ██║   ██║███████╗██║██╔████╔██║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║\n"
        "   ██║   ██╔══╝  ██║     ██║   ██║╚════██║██║██║╚██╔╝██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║\n"
        "   ██║   ███████╗╚██████╗╚██████╔╝███████║██║██║ ╚═╝ ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║\n"
        "   ╚═╝   ╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝╚═╝     ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝"
    )
    colored_banner = vertical_color_grad_text(banner, (255, 159, 243), (84, 160, 255))

    dev_info = (
        "\n\nCopyright (c) 2026, Shanghai Jiao Tong University and Yu Huang. All Rights Reserved.\n"
        "Developed by Yu Huang at SMIL Lab, School of Integrated Circuits, Shanghai Jiao Tong University."
    )
    colored_dev_info = vertical_color_grad_text(dev_info, (84, 160, 255), (84, 160, 255))
    agent_info = colored_banner.append(colored_dev_info)

    title = "Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent"
    subtitle = f"Agent Version: {TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"
    console.print(Panel.fit(agent_info, title=title, title_align="left",
                            subtitle=subtitle, subtitle_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


class GradientTextColumn(ProgressColumn):
    """Customized progress column with Text"""
    def __init__(self, start_rgb=(100, 100, 100), end_rgb=(255, 255, 255)):
        super().__init__()
        self.start_rgb = start_rgb
        self.end_rgb = end_rgb

    def render(self, task):
        return horizontal_color_grad_text(
            task.description,
            self.start_rgb,
            self.end_rgb
        )


@contextmanager
def loading_spinner(waiting_desc: str, done_desc: str, spinner: str = "dots2"):
    """context manager for rich.Progress with any time-consuming operation"""
    with Progress(
        GradientTextColumn(start_rgb=(255, 159, 243), end_rgb=(84, 160, 255)),
        SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
        TimeElapsedColumn(),
        transient=False,
    ) as progress:
        task = progress.add_task(waiting_desc, total=None)
        yield progress
        progress.update(task, description=done_desc)


def llm_request_with_spinner(func: Callable, *args,
                             waiting_desc: str = "Brain (but not mine) using ...",
                             done_desc: str = "LLM response latency",
                             spinner: str = "dots2",
                             **kwargs) -> Any:
    """LLM request with spinner and signal"""
    result = [None]
    exception = [None]
    interrupted = False

    def sigint_handler(signum, frame):
        nonlocal interrupted
        interrupted = True
    # set SIGINT handler with sigint_handler and restore the original handler
    original_handler = signal.signal(signal.SIGINT, sigint_handler)

    with Progress(
            GradientTextColumn(start_rgb=(255, 159, 243), end_rgb=(84, 160, 255)),
            SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
            TimeElapsedColumn(),
            transient=False,
    ) as progress:
        task = progress.add_task(waiting_desc, total=None)

        def target():
            """target function"""
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e

        t = threading.Thread(target=target, daemon=True)
        t.start()
        while t.is_alive():
            t.join(0.2)
            if interrupted:
                progress.stop()
                break
        if interrupted:
            # set SIGINT handler with original_handler
            signal.signal(signal.SIGINT, original_handler)
            raise RequestLLMCancelled("cancelled by user")
        progress.update(task, description=done_desc)

    # set SIGINT handler with original_handler
    signal.signal(signal.SIGINT, original_handler)
    if exception[0] is not None:
        raise exception[0]
    return result[0]


def render_permission(active_idx: int, request_type: str, request_desc: str):
    """render the permission panel according to the selection"""
    panels = []
    header_text = Text("Permission Request", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"\nTECoSim Agent want to request permission for ", style="white")
    body.append(f"{request_type}\n", style=f"bold {MAJOR_COLOR1}")
    body.append(f"Request detail: ", style="white")
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
    hint = Text(f"↑/↓ (select)    Enter (choose)\n", style="bright_black")
    return Group(*panels, hint)


def ask_permission_tui(ctx: AgentContext, request_type: str, request_desc: str, console: Console) -> bool:
    """top realization of asking user for permission TUI"""
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
                          console=console, refresh_per_second=TUI_REFRESH_RATE, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 3
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 3
                            elif key.key == Keys.Enter:
                                action = "choose"
                                break
                            elif key.key == Keys.Escape or key.key == Keys.ControlC:
                                action = "cancel"
                                break
                        if action is not None:  # no action no break
                            break
                        live.update(render_permission(active_idx, request_type, request_desc))
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
            sys_log.warning(f"Quest: {request_type} with desc. {request_desc} canceled, permission denied")
            console.print(f"Quest: {request_type} with desc. {request_desc} canceled, permission denied", style="bold yellow")
            return False


def render_exit(ctx: AgentContext, active_idx: int):
    """render the exit panel according to the selection"""
    panels = []
    header_text = Text("Exit", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"\nAre you sure to exit TECoSim Agent?\n", style="white")
    body.append(f"Tip: You can always resume this session with ", style="white")
    body.append(f"python src.main -r ", style=f"bold {MAJOR_COLOR2}")
    body.append(f"{ctx.session_uuid}\n\n", style=f"bold {MAJOR_COLOR1}")
    str_list = ["Yes", "No"]
    for i in range(2):
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
    hint = Text(f"↑/↓ (select)    Enter (choose)    Ctrl+C (exit)    Esc (cancel)\n", style="bright_black")
    return Group(*panels, hint)


def exit_tui(ctx: AgentContext, console: Console) -> bool:
    """top realization of exiting TUI"""
    active_idx = 0  # default active option

    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_exit(ctx, active_idx),
                          console=console, refresh_per_second=TUI_REFRESH_RATE, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 2
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 2
                            elif key.key == Keys.Enter:
                                action = "choose"
                                break
                            elif key.key == Keys.ControlC:
                                action = "exit"
                                break
                            elif key.key == Keys.Escape:
                                action = "cancel"
                                break
                        if action is not None:  # no action no break
                            break
                        live.update(render_exit(ctx, active_idx))
        finally:
            input_device.close()

        if action == "choose":
            if active_idx == 0:
                token = True
            else:
                token = False
            return token
        if action == "exit":
            return True
        if action == "cancel":
            sys_log.debug(f"Exit canceled")
            console.print(f"Exit canceled", style="bright_black")
            return False


def normal_exit(ctx: AgentContext, console: Console, exit_str: str):
    """normal exit of agent"""
    token = exit_tui(ctx, console)
    if token:
        try:
            prompt.save_messages(ctx, console)
            ctx.save_context(console)
        except Exception as e:
            sys_log.error(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally")
            console.print(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally", style="bold red")
            sys.exit(-1)
        sys_log.debug(exit_str)
        console.print(exit_str, style=MAJOR_COLOR2)
        sys.exit(-1)
    else:
        sys_log.debug("Exit canceled")
        console.print("Exit canceled", style="bright_black")


def error_exit(ctx: AgentContext, console: Console, error: Exception):
    """error exit of agent"""
    try:
        prompt.save_messages(ctx, console)
        ctx.save_context(console)
    except Exception as e:
        sys_log.error(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally")
        console.print(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally", style="bold red")
        sys.exit(-1)
    sys_log.error(f"TECoSim Agent exits with error: {error}")
    console.print(f"TECoSim Agent exits with error: {error}", style="bold red")
    sys.exit(-1)
