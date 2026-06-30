# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.7
Description: Agent listening TUI before user input

Revision:
---------
2026.6.7       Yu Huang      1.0      First implementation
2026.6.13      Yu Huang      1.1      Add background agent monitoring: entry condition + check_background_agents in listen loop
2026.6.13      Yu Huang      1.2      Add subagent progress render in listen TUI (between cron and task)
2026.6.30      Yu Huang      1.3      Add time info string in listen TUI

Details:
---------
Listening TUI displayed when active cron tasks or non-resolved Scoreboard tasks exist. Shows animated gradient-color indicators
for listening status, active cron count, and task progress. Periodically checks cron tasks while listening. Exits on any key
press (returns to user input mode) or when a cron task is triggered (returns to main loop).
"""
import time
import rich.box
import logging

from datetime import datetime
from rich.text import Text
from rich.panel import Panel
from rich.console import Group, Console
from rich.live import Live
from prompt_toolkit.input import create_input
from src.context.agent_context import AgentContext
from src.tool.cron_support import check_cron_tasks
from src.tool.scoreboard import Scoreboard, TaskStatus, Task, get_tasks_render
from src.tool.tool_execute import check_background_agents
from src.utility.ui_info import get_subagent_render
from src.agent.progress import SubAgentProgress
from src.constants import *
from src.utility.basic_utils import grad_color_hex_list, format_time_sec

sys_log = logging.getLogger('logger')


def render_listen(active_cron: int, agent_list: dict[str, SubAgentProgress], board: Scoreboard,
                  base_time: datetime, tui_color_list: list[str], cron_color_list: list[str],
                  subagent_color_list: list[str], task_color_list1: list[str], task_color_list2: list[str]) -> Group:
    """render the agent listening panel before user input"""
    panels = []
    now_time = datetime.now()
    title_str = get_listen_title(now_time, base_time, tui_color_list)
    cron_str = get_listen_cron(active_cron, now_time, base_time, cron_color_list)
    subagent_str = get_subagent_render(agent_list, now_time, base_time, subagent_color_list)
    task_str = get_listen_task(board.list_tasks(), now_time, base_time, tui_color_list, task_color_list1, task_color_list2)
    tail_str = get_listen_tail()
    render_str = title_str
    if cron_str is not None:
        render_str.append(cron_str)
    if subagent_str is not None:
        render_str.append(subagent_str)
        render_str.append("\n")
    if task_str is not None:
        render_str.append(task_str)
    # strip
    if render_str.plain.endswith("\n"):
        render_str.rstrip()
    render_str.append(tail_str)
    panels.append(Panel(render_str, box=rich.box.SQUARE))
    return Group(*panels)


def get_listen_title(now_time: datetime, base_time: datetime, color_list: list[str]) -> Text:
    """get title of listen TUI"""
    time_diff = (now_time - base_time).total_seconds()
    position_in_period = time_diff % LISTEN_TUI_COLOR_PERIOD
    index = int((position_in_period / LISTEN_TUI_COLOR_PERIOD) * len(color_list)) % len(color_list)
    color = color_list[index]
    title_str = Text(f"{AGENT_CONSOLE_ICON}", style=f"bold {color}")
    title_str = title_str.append(f" TECoSim agent is in ", style=f"bright_black")
    title_str = title_str.append(f"listening mode", style=f"bold {color}")
    title_str = title_str.append(f" ({now_time.strftime("%H:%M:%S")}) · ", style=f"bright_black")
    title_str = title_str.append(f"{format_time_sec(time_diff)}\n", style=f"bold {color}")
    return title_str


def get_listen_cron(active_cron: int, now_time: datetime, base_time: datetime, color_list: list[str]) -> Text | None:
    """get the cron tasks rendering"""
    if active_cron == 0:
        return None
    time_diff = (now_time - base_time).total_seconds()
    position_in_period = time_diff % CRON_LISTEN_COLOR_PERIOD
    index = int((position_in_period / CRON_LISTEN_COLOR_PERIOD) * len(color_list)) % len(color_list)
    color = color_list[index]
    cron_str = Text(f"  {active_cron}", style=f"bold {color}")
    cron_str = cron_str.append(f" cron tasks are active ... \n\n", style=f"bright_black")
    return cron_str


def get_listen_task(tasks: list[Task], now_time: datetime, base_time: datetime, tui_color_list: list[str],
                    task_color_list1: list[str], task_color_list2: list[str]) -> Text | None:
    """get the tasks rendering"""
    if len(tasks) == 0:
        return None
    nonresolved_tasks = 0
    for task in tasks:
        if task["status"] in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            nonresolved_tasks += 1
    time_diff = (now_time - base_time).total_seconds()
    position_in_period = time_diff % LISTEN_TUI_COLOR_PERIOD
    index = int((position_in_period / LISTEN_TUI_COLOR_PERIOD) * len(tui_color_list)) % len(tui_color_list)
    color = tui_color_list[index]
    task_str = Text(f"  {nonresolved_tasks}", style=f"bold {color}")
    task_str = task_str.append(f" tasks non-resolved out of ", style=f"bright_black")
    task_str = task_str.append(f"{len(tasks)}", style=f"bold {color}")
    task_str = task_str.append(f" tasks\n", style=f"bright_black")
    task_render = get_tasks_render(tasks, now_time, base_time, task_color_list1, task_color_list2)
    task_str.append(task_render)
    task_str.append("\n\n")
    return task_str


def get_listen_tail():
    """get tail of listen TUI"""
    tail_str = Text(f"\n\n  Press any key", style=f"{MAJOR_COLOR2}")
    tail_str = tail_str.append(f" to quit listening mode and type your words", style=f"bright_black")
    return tail_str


def listen_tui(ctx: AgentContext, board: Scoreboard, console: Console) -> bool:
    """realization of agent listening TUI before user input"""
    """
    display this TUI when:
    1). There is active cron task
    2). There is non-resolved task
    3). There is running background agent
    """
    has_active_cron = (ctx.active_cron != 0)
    has_pending_task = False
    for task in board.list_tasks():
        if task["status"] in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            has_pending_task = True
            break
    has_background_agent = len(ctx.background_agents) > 0

    if not has_active_cron and not has_pending_task and not has_background_agent:
        return False

    """get gradient color"""
    base_time = datetime.now()
    tui_color_list = grad_color_hex_list(LISTEN_TUI_COLOR_START, LISTEN_TUI_COLOR_END, LISTEN_TUI_COLOR_GRADIENT)
    tui_color_list = tui_color_list + tui_color_list[::-1]
    cron_color_list = grad_color_hex_list(CRON_LISTEN_COLOR_START, CRON_LISTEN_COLOR_END, CRON_LISTEN_COLOR_GRADIENT)
    cron_color_list = cron_color_list + cron_color_list[::-1]
    task_color_list1 = grad_color_hex_list(TASK_PENDING_COLOR_START, TASK_PENDING_COLOR_END, TASK_COLOR_GRADIENT)
    task_color_list1 = task_color_list1 + task_color_list1[::-1]
    task_color_list2 = grad_color_hex_list(TASK_IN_PROGRESS_COLOR_START, TASK_IN_PROGRESS_COLOR_END, TASK_COLOR_GRADIENT)
    task_color_list2 = task_color_list2 + task_color_list2[::-1]
    subagent_color_list = grad_color_hex_list(SUBAGENT_COLOR_START, SUBAGENT_COLOR_END, SUBAGENT_COLOR_GRADIENT, "sin")
    subagent_color_list = subagent_color_list + subagent_color_list[::-1]
    """TUI"""
    input_device = create_input()
    try:
        with input_device.raw_mode():
            input_device.flush_keys()
            with Live(render_listen(ctx.active_cron, ctx.agent_list, board, base_time, tui_color_list,
                                    cron_color_list, subagent_color_list, task_color_list1, task_color_list2),
                      console=console, auto_refresh=False, transient=True, vertical_overflow="visible") as live:
                while True:
                    key_press = input_device.read_keys()
                    cron_triggerd = check_cron_tasks(ctx)  # listen cron tasks
                    agent_triggerd = check_background_agents(ctx)  # listen background agents
                    if cron_triggerd or agent_triggerd:
                        return True
                    if key_press:
                        return False
                    live.update(render_listen(ctx.active_cron, ctx.agent_list, board, base_time, tui_color_list,
                                cron_color_list, subagent_color_list, task_color_list1, task_color_list2))
                    live.refresh()
                    time.sleep(KEY_LISTEN_SLEEP_TIME_MS / 1000.0)
    finally:
        input_device.close()
