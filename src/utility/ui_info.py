# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.7
Description: Tools and methods for TECoSim agent UI

Revision:
---------
2026.4.7       Yu Huang      1.0      First implementation
2026.4.15      Yu Huang      1.1      Query prompts and message history
2026.4.26      Yu Huang      1.2      Quick interrupt support
2026.4.28      Yu Huang      1.3      Exit TUI support
2026.5.12      Yu Huang      1.4      Move ask permission to ask_permission.py
2026.5.12      Yu Huang      1.5      TUI event trigger support
2026.5.20      Yu Huang      1.6      Refactor llm_request_with_spinner and move to client.py
2026.5.22      Yu Huang      1.7      Add usage bar for main model & Summarize session title support
2026.5.30      Yu Huang      1.8      Optimize the hardware occupancy of TUI & Random spinner title support & Revise spinner
                                      logic with SIGINT pass through
2026.5.31      Yu Huang      1.9      Add standard yes or no request TUI
2026.5.31      Yu Huang      2.0      Fix the bug of nested progress wrapper function
2026.6.3       Yu Huang      2.1      Add gradient clor list generation with RGB and hex format & Add configurable title in
                                      yes or no request TUI
2026.6.7       Yu Huang      2.2      Support of task displays in scoreboard & Fix the bug of uncaught exception in spinner &
                                      Fix the bug of cut-off issued when resume from permission TUI
2026.6.8       Yu Huang      2.3      Fix the bug of duplicate tail if TUI pause for permission
2026.6.9       Yu Huang      2.4      Add design and run support for simulator
2026.6.10      Yu Huang      2.5      Revise the live TUI with the same console instance &  Revise the display cut off issue if
                                      there are multiple tool calls
2026.6.11      Yu Huang      2.6      Move rgb_to_hex, hex_to_rgb, grad_color_rgb_list and grad_color_hex_list to basic_utils.py
2026.6.12      Yu Huang      2.7      Add get_subagent_render for live agent progress display
2026.6.13      Yu Huang      2.8      get_subagent_render: ICON TYPE SUBJECT USAGE single-line, current_tool on separate line

Details:
---------
TUI components for the agent: gradient color utilities (RGB/hex conversion, vertical/horizontal text gradients), ASCII art
startup banner, context usage bar, loading spinner with rapid interrupt via SIGINT-to-thread injection, yes/no request TUI,
exit confirmation TUI, user prompt input, and normal/error exit handlers with session saving.
"""
import sys
import time
import signal
import random
import ctypes
import logging
import threading

from datetime import datetime
from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.live import Live
from rich.progress import Progress, ProgressColumn, SpinnerColumn, TimeElapsedColumn
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from prompt_toolkit.formatted_text import ANSI
from typing import Callable, Any
from src.tool.file_io_support import save_messages
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard, get_tasks_render
from src.utility.basic_utils import hex_to_rgb, grad_color_hex_list
from src.agent.progress import SubAgentProgress
from src.constants import *

sys_log = logging.getLogger('logger')


def set_terminal_title(title: str):
    """set the terminal's title"""
    if title != DEFAULT_SESSION_TITLE and title != ERROR_SESSION_TITLE:
        print(f"\033]0;{AGENT_CONSOLE_ICON} {title}\007", end="", flush=True)
    else:
        print(f"\033]0;{AGENT_CONSOLE_ICON} TECoSim Agent\007", end="", flush=True)


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


def get_subagent_render(agent_list: dict[str, SubAgentProgress], now_time: datetime, base_time: datetime,
                        color_list: list[str]) -> Text | None:
    """render subagent progress, same pattern as get_tasks_render"""
    if not agent_list:
        return None

    time_diff = (now_time - base_time).total_seconds()
    position_in_period = time_diff % SUBAGENT_COLOR_PERIOD
    index = int((position_in_period / SUBAGENT_COLOR_PERIOD) * len(color_list)) % len(color_list)
    color = color_list[index]

    _icon_map = {
        AGENT_PENDING_LABEL: SUBAGENT_PENDING_ICON,
        AGENT_RUNNING_LABEL: SUBAGENT_IN_PROGRESS_ICON,
        AGENT_DONE_LABEL: SUBAGENT_DONE_ICON,
        AGENT_TIMEOUT_LABEL: SUBAGENT_ERROR_ICON,
        AGENT_ERROR_LABEL: SUBAGENT_ERROR_ICON,
    }

    lines = []
    for aid, p in agent_list.items():
        if p.if_archived:
            continue
        sv = p.status.value
        icon = _icon_map.get(sv, SUBAGENT_PENDING_ICON)

        if sv == AGENT_RUNNING_LABEL:
            icon_style = f"bold {color}"
            name_style = f"bold {color}"
            usage_style = f"{color}"
        elif sv == AGENT_DONE_LABEL:
            icon_style = f"bold {TASK_COMPLETED_COLOR}"
            name_style = "bright_black"
            usage_style = f"bright_black"
        elif sv == AGENT_ERROR_LABEL:
            icon_style = f"bold red"
            name_style = "bold red"
            usage_style = f"bright_black"
        elif sv == AGENT_TIMEOUT_LABEL:
            icon_style = f"bold yellow"
            name_style = "bold yellow"
            usage_style = f"bright_black"
        else:
            icon_style = "bright_black"
            name_style = "bright_black"
            usage_style = f"bright_black"

        line = Text()
        line.append(f"\n {icon} ", style=icon_style)
        line.append(f"{p.subagent_type} ", style=name_style)
        subject_display = p.subject[:SUBAGENT_SUBJECT_CHAR_LIMIT] if len(p.subject) > SUBAGENT_SUBJECT_CHAR_LIMIT else p.subject
        line.append(f"{subject_display} ", style="bright_black")
        line.append("↑", style=f"bold {MAJOR_COLOR2}")
        line.append(f" {p.input_tokens / 1000:.1f} K", style=usage_style)
        line.append(" ↓", style=f"bold {MAJOR_COLOR1}")
        line.append(f" {p.output_tokens / 1000:.1f} K", style=usage_style)
        if p.current_tool:
            line.append(f"\n └─{p.current_tool}", style="bright_black")
        lines.append(line)

    return Text("").join(lines) if lines else None


def loading_spinner(func: Callable, *args,
                    waiting_desc: str, done_desc: str, intrp_desc: str, fail_desc: str, spinner: str, out_except: Exception,
                    console: Console, with_progress: bool = False,
                    **kwargs) -> Any:
    """Spinner for any time-consuming operation with `KeyboardInterrupt` signal for rapid interrupt

    NOTE: signal.signal() can only be called from the main thread. When called from a
    worker thread (e.g., nested inside another loading_spinner), the signal setup
    is skipped — the outer spinner's SIGINT handler already propagates KeyboardInterrupt
    to this thread via ctypes injection, so it can still be interrupted.
    """
    is_main_thread = threading.current_thread() is threading.main_thread()

    if not is_main_thread:
        # Running in a worker thread — signal.signal() would raise:
        #   "signal only works in main thread of the main interpreter"
        # The outer spinner's SIGINT handler already injects KeyboardInterrupt into
        # this thread via PyThreadState_SetAsyncExc, so Ctrl+C still works.
        # Just run the function synchronously with a Progress display (no signal ops).
        with Progress(
            GradientTextColumn(start_rgb=hex_to_rgb(MAJOR_COLOR1), end_rgb=hex_to_rgb(MAJOR_COLOR2)),
            SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
            TimeElapsedColumn(),
            console=console,
            transient=False, refresh_per_second=PROGRESS_DISPLAY_REFRESH_RATE
        ) as progress:
            task = progress.add_task(waiting_desc, total=None)
            try:
                if not with_progress:
                    ret = func(*args, **kwargs)
                else:
                    ret = func(*args, progress=progress, **kwargs)
                progress.update(task, description=done_desc)
                return ret
            except Exception as e:
                progress.update(task, description=fail_desc)
                raise e

    result = [None]
    exception: list[Exception | None] = [None]
    stop_event = threading.Event()
    worker_thread: list[threading.Thread | None] = [None]

    def sigint_handler(signum, frame):
        """SIGINT handler: signal sub-thread and let it handle cleanup if possible"""
        stop_event.set()
        # Inject KeyboardInterrupt into the sub-thread, so tools like
        # TOOL_NAME_LAUNCH_SIM can catch it and do cleanup (proc.terminate() etc.)
        th = worker_thread[0]
        if th is not None:
            ident = th.ident
            if ident is not None:
                tid = ctypes.c_long(ident)
                t_ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    tid, ctypes.py_object(KeyboardInterrupt))
                if t_ret != 1:
                    # Failed to inject / invalid thread, clear to avoid dangling exception
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)

    # set SIGINT (KeyboardInterrupt) handler with sigint_handler and restore the original handler
    original_handler = signal.signal(signal.SIGINT, sigint_handler)
    try:
        with Progress(
            GradientTextColumn(start_rgb=hex_to_rgb(MAJOR_COLOR1), end_rgb=hex_to_rgb(MAJOR_COLOR2)),
            SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
            TimeElapsedColumn(),
            console=console,
            transient=False, refresh_per_second=PROGRESS_DISPLAY_REFRESH_RATE
        ) as progress:
            task = progress.add_task(waiting_desc, total=None)
            if not with_progress:
                def target():
                    """target function without progress"""
                    try:
                        result[0] = func(*args, **kwargs)
                    except (Exception, KeyboardInterrupt) as err:
                        exception[0] = err
            else:
                def target():
                    """target function with progress"""
                    try:
                        result[0] = func(*args, progress=progress, **kwargs)
                    except (Exception, KeyboardInterrupt) as err:
                        exception[0] = err

            t = threading.Thread(target=target, daemon=True)
            worker_thread[0] = t
            t.start()
            while t.is_alive() and not stop_event.is_set():
                t.join(SPINNER_LIVE_CHECK_GAP_MS / 1000.0)
            if stop_event.is_set():
                # Give sub-thread a chance to handle KeyboardInterrupt and
                # do cleanup (e.g. proc.terminate()), then finish normally
                t.join(SPINNER_TERMINATE_WAIT_S)
                if t.is_alive():
                    # Thread didn't handle the interrupt, force cancel
                    progress.update(task, description=intrp_desc)
                    raise out_except
                # Thread handled the interrupt and finished.
                # Regardless of whether target() caught the KeyboardInterrupt,
                # the user pressed Ctrl+C so we must raise out_except.
                progress.update(task, description=intrp_desc)
                raise out_except
            progress.update(task, description=done_desc if exception[0] is None else fail_desc)
            if exception[0] is not None:
                raise exception[0]
            return result[0]
    finally:
        # set SIGINT handler with original_handler
        signal.signal(signal.SIGINT, original_handler)


def loading_spinner_with_board(func: Callable, *args,
                               board: Scoreboard, agent_list: dict[str, SubAgentProgress] | None = None,
                               waiting_desc: str, done_desc: str, intrp_desc: str, fail_desc: str,
                               spinner: str, out_except: Exception,
                               console: Console, with_progress: bool = False,
                               **kwargs) -> Any:
    """Spinner with a live scoreboard text below, for any time-consuming operation.

    Progress bar (spinner + elapsed) on the first line, scoreboard tasks
    rendered as text underneath — updated live on each refresh cycle.

    NOTE: signal.signal() can only be called from the main thread.
    """
    is_main_thread = threading.current_thread() is threading.main_thread()

    subagent_color_list = grad_color_hex_list(SUBAGENT_COLOR_START, SUBAGENT_COLOR_END, SUBAGENT_COLOR_GRADIENT, "sin")
    subagent_color_list = subagent_color_list + subagent_color_list[::-1]
    task_color_list1 = grad_color_hex_list(TASK_PENDING_COLOR_START, TASK_PENDING_COLOR_END, TASK_COLOR_GRADIENT)
    task_color_list1 = task_color_list1 + task_color_list1[::-1]
    task_color_list2 = grad_color_hex_list(TASK_IN_PROGRESS_COLOR_START, TASK_IN_PROGRESS_COLOR_END, TASK_COLOR_GRADIENT)
    task_color_list2 = task_color_list2 + task_color_list2[::-1]
    base_time = datetime.now()

    columns = [
        GradientTextColumn(start_rgb=hex_to_rgb(MAJOR_COLOR1), end_rgb=hex_to_rgb(MAJOR_COLOR2)),
        SpinnerColumn(spinner_name=spinner, style=MAJOR_COLOR2),
        TimeElapsedColumn(),
    ]
    progress = Progress(*columns, console=console, transient=False,
                        refresh_per_second=PROGRESS_DISPLAY_REFRESH_RATE)

    # Store reference to the outer Live so worker thread can pause/resume it
    # during permission TUI (see pause_for_permission / resume_from_permission).
    progress._outer_live = None  # placeholder, set after Live is created

    def make_group() -> Group:
        agent_render = None
        if agent_list is not None:
            agent_render = get_subagent_render(agent_list, datetime.now(), base_time, subagent_color_list)
        task_str = get_tasks_render(board.list_tasks(), datetime.now(), base_time, task_color_list1, task_color_list2)

        final_str = Text("")

        parts = [progress]
        if agent_render is not None:
            final_str.append(agent_render)
            final_str.append(Text("\n"))
        if task_str.plain.strip():
            final_str.append(Text("\n"))
            final_str.append(task_str)
            final_str.append(Text("\n"))
        else:
            final_str.append(Text("\n"))
            final_str.append(Text(TASK_EMPTY_TITLE, style="bright_black"))
        parts.append(final_str)
        return Group(*parts)

    if not is_main_thread:
        with Live(make_group(), console=console, refresh_per_second=PROGRESS_DISPLAY_REFRESH_RATE, transient=False) as live:
            progress._outer_live = live
            task_id = progress.add_task(waiting_desc, total=None)
            try:
                if not with_progress:
                    ret = func(*args, **kwargs)
                else:
                    ret = func(*args, progress=progress, **kwargs)
                progress.update(task_id, description=done_desc)
                live.update(make_group())
                return ret
            except Exception as e:
                progress.update(task_id, description=fail_desc)
                live.update(make_group())
                raise e
            finally:
                board.archive_tasks()

    result = [None]
    exception: list[Exception | None] = [None]
    stop_event = threading.Event()
    worker_thread: list[threading.Thread | None] = [None]

    def sigint_handler(signum, frame):
        """SIGINT handler: signal sub-thread and let it handle cleanup"""
        stop_event.set()
        th = worker_thread[0]
        if th is not None:
            ident = th.ident
            if ident is not None:
                tid = ctypes.c_long(ident)
                t_ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    tid, ctypes.py_object(KeyboardInterrupt))
                if t_ret != 1:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)

    original_handler = signal.signal(signal.SIGINT, sigint_handler)
    try:
        def target():
            try:
                if not with_progress:
                    result[0] = func(*args, **kwargs)
                else:
                    result[0] = func(*args, progress=progress, **kwargs)
            except (Exception, KeyboardInterrupt) as err:
                exception[0] = err

        t = threading.Thread(target=target, daemon=True)
        worker_thread[0] = t

        with Live(make_group(), console=console, refresh_per_second=PROGRESS_DISPLAY_REFRESH_RATE, transient=False) as live:
            progress._outer_live = live
            task_id = progress.add_task(waiting_desc, total=None)
            t.start()
            while t.is_alive() and not stop_event.is_set():
                t.join(SPINNER_LIVE_CHECK_GAP_MS / 1000.0)
                live.update(make_group())
            if stop_event.is_set():
                t.join(SPINNER_TERMINATE_WAIT_S)
                if t.is_alive():
                    progress.update(task_id, description=intrp_desc)
                    live.update(make_group())
                    raise out_except
                progress.update(task_id, description=intrp_desc)
                live.update(make_group())
                raise out_except
            desc = done_desc if exception[0] is None else fail_desc
            progress.update(task_id, description=desc)
            live.update(make_group())
            if exception[0] is not None:
                raise exception[0]
            return result[0]
    finally:
        signal.signal(signal.SIGINT, original_handler)
        board.archive_tasks()


def pause_for_permission(progress):
    """Pause the outer Live before showing a permission TUI from the worker thread.

    Stops the outer Live (restore cursor, pop render hook, stop auto-refresh)
    so the permission TUI's Live can take over the console cleanly without
    interference from prompt_toolkit or overlapping renders.

    CRITICAL: Does NOT touch `progress.live` (Progress's internal Live).
    `progress.live` is never started by `Progress.start()` when Progress
    is used inside an outer `Live` (as in `loading_spinner_with_board`).
    Instead, operates on the outer Live stored at `progress._outer_live`.
    """
    outer_live = getattr(progress, '_outer_live', None)
    if outer_live is not None:
        # Save original transient value. Only temporarily switch to True
        # (clear on stop) if it's currently False (static text on stop),
        # preventing stale frame remnants after resume_from_permission.
        original_transient = outer_live.transient
        if not original_transient:
            outer_live.transient = True
        outer_live.stop()
        outer_live.transient = original_transient


def resume_from_permission(progress):
    """Resume the outer Live after a permission TUI has finished.

    Restarts the outer Live (hide cursor, register render hook, start
    auto-refresh) so normal spinner + scoreboard display resumes.

    Prints enough newlines (last_render_height + 1) before restarting
    so that the Live's `position_cursor()` on next auto-refresh only
    erases empty lines and does not overwrite content printed in a
    previous tool cycle (e.g. bash previews, SUCCESS messages).
    """
    outer_live = getattr(progress, '_outer_live', None)
    if outer_live is not None:
        last_height = getattr(outer_live._live_render, 'last_render_height', 0)
        for _ in range(last_height):
            progress.console.print()
        outer_live.start()


def get_user_prompt(ctx: AgentContext) -> str:
    """get the user prompt text"""
    if ctx.agent_session:
        if ctx.agent_configs["RANDOM_PROGRESS_TITLE"]:
            prefix = random.choice(USER_PROMPT_PREFIX_LIST)
        else:
            prefix = USER_PROMPT_PREFIX_LIST[0]
        user_input = ctx.agent_session.prompt(ANSI(f"\033[90m{prefix} {USER_PROMPT_FIXED_PREFIX}\033[0m\n"
                                               f"{AGENT_CONSOLE_ICON} "))
        return user_input
    return ""


def render_request(title: str, request_desc: str, request_detail: str | None, active_idx: int):
    """render the yes or no request panel according to the selection"""
    panels = []
    header_text = Text(title, style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"\nAre you sure to ", style="white")
    body.append(f"{request_desc}", style=f"bold {MAJOR_COLOR2}")
    body.append(f"?\n", style="white")
    body.append(f"Request detail: ", style="white")
    body.append(f"{request_detail}\n\n", style="bright_black")
    str_list = ["Yes", "No"]
    for i in range(2):
        is_selected = active_idx == i
        prefix1 = OPTIONS_TO_SELECT_PREFIX if is_selected else OPTIONS_UN_SELECT_PREFIX
        prefix2 = OPTIONS_SELECTED_PREFIX if is_selected else OPTIONS_UNSELECTED_PREFIX
        if is_selected:
            label_style = f"bold {MAJOR_COLOR2}"
        else:
            label_style = "white"
        body.append(f"{prefix1}{str_list[i]}{prefix2}\n\n", style=label_style)
    if body.plain.endswith("\n"):
        body.rstrip()
    panels.append(Panel(body, title=header_text, title_align="left", border_style=MAJOR_COLOR2))
    hint = Text(f"  ↑/↓ (select)    Enter (choose)    Ctrl+C (exit)    Esc (cancel)\n", style="bright_black")
    return Group(*panels, hint)


def request_tui(console: Console, title: str, request_desc: str, request_detail: str | None, cancel_str: str="Request canceled") -> bool:
    """top realization of request yes or no TUI"""
    active_idx = 0  # default active option

    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_request(title, request_desc, request_detail, active_idx),
                          console=console, auto_refresh=False, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 2
                                live.update(render_request(title, request_desc, request_detail, active_idx))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 2
                                live.update(render_request(title, request_desc, request_detail, active_idx))
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
                        if not key_press:
                            time.sleep(KEY_LISTEN_SLEEP_TIME_MS / 1000.0)
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
            sys_log.debug(cancel_str)
            console.print(cancel_str, style="bright_black")
            return False


def render_exit(ctx: AgentContext, active_idx: int):
    """render the exit panel according to the selection"""
    panels = []
    header_text = Text("Exit", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"\nAre you sure to exit TECoSim Agent?\n", style="white")
    body.append(f"Tip: You can always resume this session with ", style="white")
    body.append(f"python -m src.main -r ", style=f"bold {MAJOR_COLOR2}")
    body.append(f"{ctx.session_uuid}\n\n", style=f"bold {MAJOR_COLOR1}")
    str_list = ["Yes", "No"]
    for i in range(2):
        is_selected = active_idx == i
        prefix1 = OPTIONS_TO_SELECT_PREFIX if is_selected else OPTIONS_UN_SELECT_PREFIX
        prefix2 = OPTIONS_SELECTED_PREFIX if is_selected else OPTIONS_UNSELECTED_PREFIX
        if is_selected:
            label_style = f"bold {MAJOR_COLOR2}"
        else:
            label_style = "white"
        body.append(f"{prefix1}{str_list[i]}{prefix2}\n\n", style=label_style)
    if body.plain.endswith("\n"):
        body.rstrip()
    panels.append(Panel(body, title=header_text, title_align="left", border_style=MAJOR_COLOR2))
    hint = Text(f"  ↑/↓ (select)    Enter (choose)    Ctrl+C (exit)    Esc (cancel)\n", style="bright_black")
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
                        if not key_press:
                            time.sleep(KEY_LISTEN_SLEEP_TIME_MS / 1000.0)
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


def normal_exit(ctx: AgentContext, board: Scoreboard, console: Console, exit_str: str):
    """normal exit of agent"""
    token = exit_tui(ctx, console)
    if token:
        try:
            save_messages(ctx, console)
            ctx.save_context(console)
            ctx.design_man.save_to_file(console)
            ctx.run_man.save_to_file(console)
            board.save_to_file(console)
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


def error_exit(ctx: AgentContext, board: Scoreboard, console: Console, error: Exception):
    """error exit of agent"""
    try:
        save_messages(ctx, console)
        ctx.save_context(console)
        ctx.design_man.save_to_file(console)
        ctx.run_man.save_to_file(console)
        board.save_to_file(console)
    except Exception as e:
        sys_log.error(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally")
        console.print(f"Save messages and context failed with error {e}, TECoSim Agent exits abnormally", style="bold red")
        sys.exit(-1)
    sys_log.error(f"TECoSim Agent exits with error: {error}")
    console.print(f"TECoSim Agent exits with error: {error}", style="bold red")
    sys.exit(-1)
