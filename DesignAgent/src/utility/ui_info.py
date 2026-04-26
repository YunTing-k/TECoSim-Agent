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

Details:
UI information of agent dev version, ASCII art banner of start, error
------------------------------------------------------------------------------------------------------------------------
"""
import logging
import signal
import threading

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.progress import Progress, ProgressColumn, SpinnerColumn, TimeElapsedColumn
from contextlib import contextmanager
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
def loading_spinner(waiting_desc: str = "Brain (but not mine) using ...",
                    done_desc: str = "LLM response latency",
                    spinner: str = "dots2"):
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
