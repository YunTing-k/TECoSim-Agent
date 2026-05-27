# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.12\n
Description: File io support

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.12      Yu Huang     1.0               First implementation\n
2026.5.12      Yu Huang     1.1               TUI event trigger support\n
2026.5.15      Yu Huang     1.2               Move read lines/logs method to file_io_support.py\n
2026.5.27      Yu Huang     1.3               Move clean_stdout/stderr_log method to simulator_support.py\n

Details:
Support of file io with read truncation, user permission TUI and corresponding methods
------------------------------------------------------------------------------------------------------------------------
"""
import os
import math
import logging

from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.context import prompt
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def save_sessions(ctx: AgentContext, console: Console, mute: bool = False):
    """save all session's files"""
    try:
        prompt.save_messages(ctx, console, mute)
        ctx.save_context(console, mute)
    except Exception as e:
        sys_log.error(f"Save messages and context failed with error {e}")
        console.print(f"Save messages and context failed with error {e}", style="bold red")


def read_line_with_limit(lines: list[str], line_start: int, line_end: int, byte_limit: int, encoding: str) -> tuple[str, bool, int]:
    """read string lines with line range start from 0 and byte limits"""
    truncated = False
    accumulated_bytes = 0
    formatted_lines: list[str] = []
    lines_count = 0

    for i, line in enumerate(lines, start=0):
        if line_start <= i <= line_end:
            segment_bytes = len(line.encode(encoding))
            if accumulated_bytes + segment_bytes > byte_limit:
                truncated = True
                break
            formatted_lines.append(line)
            accumulated_bytes += segment_bytes
            lines_count += 1
    output = "".join(formatted_lines)
    return output, truncated, lines_count


def match_line_ranges(content: str, target: str, match_all: bool) -> list[tuple[int, int]]:
    """match the content with target and return the line ranges of the matches"""
    results = []
    target_lines = target.rstrip('\n').count('\n')
    start = 0
    while True:
        index = content.find(target, start)
        if index == -1:
            break
        prefix = content[:index]
        start_line = prefix.count('\n') + 1
        end_line = start_line + target_lines
        results.append((start_line, end_line))
        if not match_all:
            break
        start = index + 1
    return results


def get_line_prefix(idx: int, budget: int, mode: str = "normal") -> tuple[str, str]:
    """get the prefix of line with space and line index"""
    if idx <= 0:
        raise RuntimeError(f"Invalid line index {idx} <= 0")
    else:
        digits = math.floor(math.log10(idx)) + 1
    if budget < digits:
        raise RuntimeError(f"Invalid budget {budget} < digits {digits}")
    prefix1 = " " * EDIT_VIEW_LEFT_SPACE_MARGIN
    prefix2 = " " * (EDIT_VIEW_LINE_SPACE_MARGIN + budget - digits) + f"{idx}"
    if mode == "remove":
        prefix2 = prefix2 + " - "
    elif mode == "add":
        prefix2 = prefix2 + " + "
    elif mode == "normal":
        prefix2 = prefix2 + "   "
    else:
        sys_log.warning(f"Unknown line prefix mode: {mode}")
        prefix2 = prefix2 + "  "
    return prefix1, prefix2


def fill_str_line(input_line: str, offset: int) -> str:
    """fill the input string with spaces of command line"""
    width = os.get_terminal_size().columns - offset
    if width < 0:
        width = 0
    if input_line.endswith('\n'):
        output_line = input_line.rstrip('\n')
        output_line = output_line.ljust(width) + "\n"
    elif input_line.endswith('\r\n'):
        output_line = input_line.rstrip('\r\n')
        output_line = output_line.ljust(width) + "\r\n"
    else:
        output_line = input_line.ljust(width) + "\n"
    return output_line


def render_preview_single(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]]):
    """render single-line file edit preview"""
    (start_line, end_line) = match_lines[0]
    old_lines = str_line[start_line - 1:end_line]
    old_str = "".join(old_lines)
    new_str = old_str.replace(old_string, new_string, 1)
    new_lines = new_str.splitlines()
    body = Text()
    body.append("Edit file: ", style=f"bold {MAJOR_COLOR2}")
    body.append(f"{path}\n", style=f"bold white")
    body.append(f"Add ", style="bright_black")
    body.append(f"{len(new_lines)}", style=f"bold {MAJOR_COLOR2}")
    body.append(f" lines, remove ", style="bright_black")
    body.append(f"{len(old_lines)}", style=f"bold {MAJOR_COLOR2}")
    body.append(f" lines\n\n", style="bright_black")

    # get the maximum digits of preview
    budget_lines = max(end_line, end_line + len(new_lines) - len(old_lines))  # remove (original), added (updated) line
    if end_line != len(str_line):
        tail_lines = min(end_line + len(new_lines) - len(old_lines) + EDIT_VIEW_LINE_MARGIN_SINGLE, # tail after modification (updated)
                           len(str_line) + len(new_lines) - len(old_lines))  # all lines after modification (updated)
        budget_lines = max(budget_lines, tail_lines)
    budget = math.floor(math.log10(budget_lines)) + 1
    """before the modification region (normal)"""
    if start_line != 1:  # if head
        if start_line <= EDIT_VIEW_LINE_MARGIN_SINGLE:
            line_prefix1 = str_line[:start_line - 1]
            idx_prefix1 = 1
        else:
            line_prefix1 = str_line[start_line - EDIT_VIEW_LINE_MARGIN_SINGLE - 1:start_line - 1]
            idx_prefix1 = start_line - EDIT_VIEW_LINE_MARGIN_SINGLE
        for idx, line in enumerate(line_prefix1):
            normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix1 + idx, budget)  # original index
            body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
            body.append(f"{line}", style=f"bold white")

    """in the modification region (remove)"""
    for idx, line in enumerate(old_lines):
        remove_prefix1, remove_prefix2 = get_line_prefix(start_line + idx, budget, mode="remove")  # original index
        body.append(remove_prefix1, style=f"bright_black")
        body.append(remove_prefix2, style=f"bright_black on {EDIT_VIEW_RMV_BG}")
        filled_line = fill_str_line(line, offset=len(remove_prefix1) + len(remove_prefix2))
        body.append(f"{filled_line}", style=f"bold white on {EDIT_VIEW_RMV_BG}")

    """in the modification region (add)"""
    for idx, line in enumerate(new_lines):
        add_prefix1, add_prefix2 = get_line_prefix(start_line + idx, budget, mode="add")  # updated index
        body.append(add_prefix1, style=f"bright_black")
        body.append(add_prefix2, style=f"bright_black on {EDIT_VIEW_ADD_BG}")
        filled_line = fill_str_line(line, offset=len(add_prefix1) + len(add_prefix2))
        body.append(f"{filled_line}", style=f"bold white on {EDIT_VIEW_ADD_BG}")

    """after the modification region (normal)"""
    if end_line != len(str_line):  # if tail
        if end_line >= len(str_line) - EDIT_VIEW_LINE_MARGIN_SINGLE + 1:
            line_prefix2 = str_line[end_line:]
            idx_prefix2 = end_line + 1
        else:
            line_prefix2 = str_line[end_line:end_line + EDIT_VIEW_LINE_MARGIN_SINGLE]
            idx_prefix2 = end_line + 1
        for idx, line in enumerate(line_prefix2):
            normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix2 + idx + len(new_lines) - len(old_lines), budget)  # updated index
            body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
            body.append(f"{line}", style=f"bold white")
    return body


def merge_intervals(match_lines: list[tuple[int, int]]):
    """merge overlap intervals with given matches list"""
    merged: list[tuple[int, int]] = []
    for ds, de in match_lines:
        if not merged:
            merged.append((ds, de))
        else:
            last_ds, last_de = merged[-1]
            if ds <= last_de:  # overlap or neighboring
                merged[-1] = (last_ds, max(last_de, de))
            else:
                merged.append((ds, de))
    return merged


def render_preview_multi(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]]):
    """render multiple-line file edit preview"""
    merged_match_lines = merge_intervals(match_lines)  # sorted
    # get the maximum digits of preview of this block
    total_added = 0
    total_removed = 0
    (all_start, _) = merged_match_lines[0]
    (_, all_end) = merged_match_lines[-1]
    for block_idx, (start_line, end_line) in enumerate(merged_match_lines):
        old_lines = str_line[start_line - 1:end_line]
        old_str = "".join(old_lines)
        new_str = old_str.replace(old_string, new_string, 1)
        new_lines = new_str.splitlines()
        total_added += len(new_lines)
        total_removed += len(old_lines)
    budget_lines = max(all_end, all_end + total_added - total_removed)  # remove (original), added (updated) line
    if all_end != len(str_line):
        tail_lines = min(all_end + total_added - total_removed + EDIT_VIEW_LINE_MARGIN_SINGLE, # tail after modification (updated)
                         len(str_line) + total_added - total_removed)  # all lines after modification (updated)
        budget_lines = max(budget_lines, tail_lines)
    budget = math.floor(math.log10(budget_lines)) + 1

    body = Text()
    added_lines = 0
    removed_lines = 0
    for block_idx, (start_line, end_line) in enumerate(merged_match_lines):
        old_lines = str_line[start_line - 1:end_line]
        old_str = "".join(old_lines)
        new_str = old_str.replace(old_string, new_string, 1)
        new_lines = new_str.splitlines()
        """first block before the modification region (normal)"""
        if block_idx == 0 and start_line != 1:
            if start_line <= EDIT_VIEW_LINE_MARGIN_MULTI:
                line_prefix1 = str_line[:start_line - 1]
                idx_prefix1 = 1
            else:
                line_prefix1 = str_line[start_line - EDIT_VIEW_LINE_MARGIN_MULTI - 1:start_line - 1]
                idx_prefix1 = start_line - EDIT_VIEW_LINE_MARGIN_MULTI
            for idx, line in enumerate(line_prefix1):
                normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix1 + idx, budget)  # original index
                body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
                body.append(f"{line}", style=f"bold white")

        """in the modification region (remove)"""
        for idx, line in enumerate(old_lines):
            remove_prefix1, remove_prefix2 = get_line_prefix(start_line + idx, budget, mode="remove")  # original index
            body.append(remove_prefix1, style=f"bright_black")
            body.append(remove_prefix2, style=f"bright_black on {EDIT_VIEW_RMV_BG}")
            filled_line = fill_str_line(line, offset=len(remove_prefix1) + len(remove_prefix2))
            body.append(f"{filled_line}", style=f"bold white on {EDIT_VIEW_RMV_BG}")

        """in the modification region (add)"""
        for idx, line in enumerate(new_lines):
            add_prefix1, add_prefix2 = get_line_prefix(start_line + idx + added_lines - removed_lines, budget, mode="add")  # updated index
            body.append(add_prefix1, style=f"bright_black")
            body.append(add_prefix2, style=f"bright_black on {EDIT_VIEW_ADD_BG}")
            filled_line = fill_str_line(line, offset=len(add_prefix1) + len(add_prefix2))
            body.append(f"{filled_line}", style=f"bold white on {EDIT_VIEW_ADD_BG}")

        """after the modification region (normal)"""
        this_tail = False
        next_head = False
        merged = False
        merged_lines = 0
        if block_idx < len(merged_match_lines) - 1:  # not last block
            (nxt_start_line, nxt_end_line) = merged_match_lines[block_idx + 1]
            if nxt_start_line - end_line <= 1:  # gap is not big enough
                pass
            elif nxt_start_line - end_line <= 2 * EDIT_VIEW_LINE_MARGIN_MULTI:  # gap is big enough for merge
                merged = True
                merged_lines = nxt_start_line - end_line
            else:  # gap is big enough for this block's tail and next block's head
                this_tail = True
                next_head = True
        else:  # last block
            this_tail = (end_line != len(str_line))
        if merged:
            line_prefix2 = str_line[end_line:end_line + merged_lines]
            idx_prefix2 = end_line + 1
            for idx, line in enumerate(line_prefix2):
                normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix2 + idx + added_lines - removed_lines, budget)  # updated index
                body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
                body.append(f"{line}", style=f"bold white")
        if this_tail:
            if end_line >= len(str_line) - EDIT_VIEW_LINE_MARGIN_MULTI + 1:
                line_prefix2 = str_line[end_line:]
                idx_prefix2 = end_line + 1
            else:
                line_prefix2 = str_line[end_line:end_line + EDIT_VIEW_LINE_MARGIN_MULTI]
                idx_prefix2 = end_line + 1
            for idx, line in enumerate(line_prefix2):
                normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix2 + idx + added_lines - removed_lines, budget)  # updated index
                body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
                body.append(f"{line}", style=f"bold white")
            if next_head:
                body.append("\n", style=f"bold white")
        if next_head:
            (nxt_start_line, nxt_end_line) = merged_match_lines[block_idx + 1]
            line_prefix1 = str_line[nxt_start_line - EDIT_VIEW_LINE_MARGIN_MULTI - 1:nxt_start_line - 1]
            idx_prefix1 = nxt_start_line - EDIT_VIEW_LINE_MARGIN_MULTI
            for idx, line in enumerate(line_prefix1):
                normal_prefix1, normal_prefix2 = get_line_prefix(idx_prefix1 + idx + added_lines - removed_lines, budget)  # updated index
                body.append(normal_prefix1 + normal_prefix2, style=f"bright_black")
                body.append(f"{line}", style=f"bold white")
        removed_lines += len(old_lines)
        added_lines += len(new_lines)

    head = Text()
    head.append("Edit file: ", style=f"bold {MAJOR_COLOR2}")
    head.append(f"{path}\n", style=f"bold white")
    head.append(f"Add ", style="bright_black")
    head.append(f"{added_lines}", style=f"bold {MAJOR_COLOR2}")
    head.append(f" lines, remove ", style="bright_black")
    head.append(f"{removed_lines}", style=f"bold {MAJOR_COLOR2}")
    head.append(f" lines\n\n", style="bright_black")

    total = head.append(body)
    return total


def render_edit_permission(path:str, active_idx: int):
    """render file edit permission"""
    panels = []
    title = Text()
    title.append("Permission Request", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"TECoSim Agent want to request permission for ", style=f"white")
    body.append(f"file_edit", style=f"bold {MAJOR_COLOR1}")
    body.append(f" to path: ", style=f"white")
    body.append(f"{path}\n\n", style=f"bold {MAJOR_COLOR1}")
    str_list = ["Yes",
                "Yes, and agree all file edit during this agent session",
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
    hint = Text(f"↑/↓ (select)    Enter (choose)\n", style="bright_black")
    panels.append(Panel(body, title=title, title_align="left", border_style=MAJOR_COLOR2))
    return Group(*panels, hint)


def ask_edit_tui(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]],
                 multi_match: bool, ctx: AgentContext, console: Console) -> bool:
    """top realization of asking user for editing file TUI"""
    active_idx = 0  # default active option
    request_type = "edit_file"
    if ctx.args.dangerously_allow_all:
        return True
    if ctx.permissions[request_type]:
        return True
    if not multi_match:
        console.print(render_preview_single(path, old_string, new_string, str_line, match_lines))
    else:
        console.print(render_preview_multi(path, old_string, new_string, str_line, match_lines))
    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_edit_permission(path, active_idx),
                          console=console, auto_refresh=False, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 3
                                live.update(render_edit_permission(path, active_idx))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 3
                                live.update(render_edit_permission(path, active_idx))
                                live.refresh()
                            elif key.key == Keys.Enter:
                                action = "choose"
                                break
                            elif key.key == Keys.Escape or key.key == Keys.ControlC:
                                action = "cancel"
                                break
                        if action is not None:  # no action no break
                            break
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
            sys_log.warning(f"Quest: {request_type} canceled, permission denied")
            console.print(f"Quest: {request_type} canceled, permission denied", style="bold yellow")
            return False
