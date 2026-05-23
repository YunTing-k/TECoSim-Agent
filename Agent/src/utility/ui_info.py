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
2026.5.12      Yu Huang     1.4               Move ask permission to ask_permission.py\n
2026.5.12      Yu Huang     1.5               TUI event trigger support\n
2026.5.20      Yu Huang     1.6               Refactor llm_request_with_spinner and move to client.py\n
2026.5.22      Yu Huang     1.7               Add usage bar for main model & Summarize session title support\n

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
from src.context import prompt
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def set_terminal_title(title: str):
    """set the terminal's title"""
    if title != DEFAULT_SESSION_TITLE and title != ERROR_SESSION_TITLE:
        print(f"\033]0;{AGENT_CONSOLE_ICON} {title}\007", end="", flush=True)
    else:
        print(f"\033]0;{AGENT_CONSOLE_ICON} TECoSim Agent\007", end="", flush=True)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """convert hex color to rgb"""
    hex_color = hex_color.lstrip('#').upper()

    if not all(c in '0123456789ABCDEF' for c in hex_color):
        sys_log.error(f"Invalid hex color: {hex_color}")
        raise ValueError(f"Invalid hex color: {hex_color}")

    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    elif len(hex_color) != 6:
        sys_log.error(f"Invalid hex color: {hex_color} not in 3 or 6 hex digits")
        raise ValueError(f"Invalid hex color: {hex_color} not in 3 or 6 hex digits")

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return r, g, b
    except Exception as e:
        sys_log.error(f"Failed to convert hex color: {hex_color} to RGB tuples")
        raise RuntimeError(f"Failed to convert hex color: {hex_color} to RGB tuples")


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
    colored_banner = vertical_color_grad_text(banner, hex_to_rgb(MAJOR_COLOR1), hex_to_rgb(MAJOR_COLOR2))

    dev_info = (
        "\n\nCopyright (c) 2026, Shanghai Jiao Tong University and Yu Huang. All Rights Reserved.\n"
        "Developed by Yu Huang at SMIL Lab, School of Integrated Circuits, Shanghai Jiao Tong University."
    )
    colored_dev_info = vertical_color_grad_text(dev_info, hex_to_rgb(MAJOR_COLOR2), hex_to_rgb(MAJOR_COLOR2))
    agent_info = colored_banner.append(colored_dev_info)

    title = "Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent"
    subtitle = f"Agent Version: {TECOSIM_AGENT_MAJOR_VERSION}.{TECOSIM_AGENT_MINOR_VERSION}.{TECOSIM_AGENT_UPDATE_VERSION}"
    console.print(Panel.fit(agent_info, title=title, title_align="left",
                            subtitle=subtitle, subtitle_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def usage_bar(ctx: AgentContext, console: Console, length: int = 20, prefix1: str = "[", prefix2: str = "]"):
    """print the usage bar from the agent context"""
    input_tokens = ctx.last_input_tokens
    total_input_tokens = ctx.total_input_tokens
    total_output_tokens = ctx.total_output_tokens
    total_context = ctx.api_configs["MAIN_MODEL_CONTEXT"]
    ratio = input_tokens / total_context
    start_color = hex_to_rgb(MAJOR_COLOR2)
    target_color = hex_to_rgb(MAJOR_COLOR1)
    stop_color = (int(start_color[0] + (target_color[0] - start_color[0]) * ratio),
                  int(start_color[1] + (target_color[1] - start_color[1]) * ratio),
                  int(start_color[2] + (target_color[2] - start_color[2]) * ratio),)
    len_full = int(length * ratio)
    progress_str = horizontal_color_grad_text(prefix1 + PROGRESS_BAR_FULL * len_full, start_color, stop_color)
    progress_str.append(PROGRESS_BAR_EMPTY * (length - len_full), style="bright_black")
    progress_str.append(prefix2, style=f"bold {MAJOR_COLOR1}")

    bar_str = Text()
    bar_str.append(f"Main: ", style="bright_black")
    bar_str.append(f"{ctx.api_configs["MAIN_MODEL_NAME"]}", style=f"bold {MAJOR_COLOR2}")
    bar_str.append(f" Usage: ", style="bright_black")
    bar_str.append(progress_str)
    bar_str.append(f" {100 * ratio:.1f} %", style="bright_black")
    bar_str.append(f" ({input_tokens / 1000.0:.1f} K / {total_context / 1000.0:.1f} K)", style="bright_black")
    bar_str.append(f" Total: ", style="bright_black")
    bar_str.append(f"↑", style=f"bold {MAJOR_COLOR2}")
    bar_str.append(f" {total_input_tokens / 1000.0:.1f} K, ", style="bright_black")
    bar_str.append(f"↓", style=f"bold {MAJOR_COLOR1}")
    bar_str.append(f" {total_output_tokens / 1000.0:.1f} K", style="bright_black")

    console.print(bar_str)


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
    """context manager for rich.Progress with any time-consuming operation (no rapid interrupt)"""
    with Progress(
        GradientTextColumn(start_rgb=(255, 159, 243), end_rgb=(84, 160, 255)),
        SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
        TimeElapsedColumn(),
        transient=False,
    ) as progress:
        task = progress.add_task(waiting_desc, total=None)
        yield progress
        progress.update(task, description=done_desc)


def loading_spinner_rap(func: Callable, *args, waiting_desc: str, done_desc: str, spinner: str, out_except: Exception, **kwargs) -> Any:
    """Spinner for any time-consuming operation with signal"""
    result = [None]
    exception: list[Exception | None] = [None]
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
            raise out_except
        progress.update(task, description=done_desc)

    # set SIGINT handler with original_handler
    signal.signal(signal.SIGINT, original_handler)
    if exception[0] is not None:
        raise exception[0]
    return result[0]


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
                          console=console, auto_refresh=False, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 2
                                live.update(render_exit(ctx, active_idx))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 2
                                live.update(render_exit(ctx, active_idx))
                                live.refresh()
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
