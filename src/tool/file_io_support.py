# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.12
Description: File io support

Revision:
---------
2026.5.12      Yu Huang      1.0      First implementation
2026.5.12      Yu Huang      1.1      TUI event trigger support
2026.5.15      Yu Huang      1.2      Move read lines/logs method to file_io_support.py
2026.5.27      Yu Huang      1.3      Move clean_stdout/stderr_log method to simulator_support.py
2026.5.28      Yu Huang      1.4      Add read-only paths support & Bugfix preview of multi-line file edit
2026.5.29      Yu Huang      1.5      Bugfix of check readonly paths when path is nonexists
2026.5.30      Yu Huang      1.6      Optimize the hardware occupancy of TUI
2026.6.1       Yu Huang      1.7      Normalize old/new strings for CRLF and quote marks handling & add debug info on edit_file match failure
2026.6.4       Yu Huang      1.8      Add support of comment when user deny permission request
2026.6.6       Yu Huang      1.9      Bugfix of submit action in all ask permission TUIs
2026.6.7       Yu Huang      2.0      Revise the display style of edit permission TUI & Add newline and space padding for
                                      all ask permission TUIs
2026.6.9       Yu Huang      2.1      Remove read_line_with_limit to basic_utils.py & Add design and run support for simulator

Details:
---------
File I/O support layer: (1) read truncation with byte-limit enforcement; (2) TOOL_NAME_EDIT_FILE helper - quote-normalized fuzzy
matching, CRLF normalization, match debug info with repr context; (3) preview renderers (single/multi-match) showing diff-style
add/remove lines; (4) edit permission TUI with preview; (5) read-only path checking against system and user-defined paths.
Also provides session saving utility.
"""
import os
import math
import time
import logging

from pathlib import Path
from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.context import prompt
from src.utility.basic_utils import get_user_input
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.constants import *

sys_log = logging.getLogger('logger')


def save_sessions(ctx: AgentContext, board: Scoreboard, console: Console, mute: bool = False):
    """save all session's files"""
    try:
        prompt.save_messages(ctx, console, mute)
        ctx.save_context(console, mute)
        ctx.design_man.save_to_file(console, mute)
        ctx.run_man.save_to_file(console, mute)
        board.save_to_file(console, mute)
    except Exception as e:
        sys_log.error(f"Save messages and context failed with error {e}")
        console.print(f"Save messages and context failed with error {e}", style="bold red")


def get_match_debug_info(content: str, target: str) -> str:
    """get debug info when `TOOL_NAME_EDIT_FILE` cannot match target string in content"""
    _TARGET_REPR_MAX = 500
    _PROBE_LEN = 40
    _PROBE_MIN = 5
    _CTX_MARGIN = 40
    _CTX_TAIL = 80

    parts = []
    # show repr of target to reveal hidden chars (e.g. \r, literal \n vs real newline)
    target_repr = repr(target[:_TARGET_REPR_MAX])
    parts.append(f"target(repr)={target_repr}")
    # try partial match with first meaningful chunk of target
    probe = target[:_PROBE_LEN].strip()
    if len(probe) >= _PROBE_MIN:
        idx = content.find(probe)
        if idx >= 0:
            ctx_start = max(0, idx - _CTX_MARGIN)
            ctx_end = min(len(content), idx + len(probe) + _CTX_TAIL)
            context = content[ctx_start:ctx_end]
            parts.append(f"closest_partial_offset={idx}")
            parts.append(f"context(repr)={repr(context)}")
        else:
            parts.append(f"no_partial_match_for_first_{_CTX_MARGIN}_chars")
    # check common issues
    if '\r' in target:
        parts.append("WARNING: target contains CR(\\r) chars, but file was read with universal newlines")
    # total length hint
    parts.append(f"content_len={len(content)} target_len={len(target)}")
    return " | ".join(parts)


# Curly/smart quotes that may appear in files but LLM cannot output
_LEFT_SINGLE_CURLY = '\u2018'
_RIGHT_SINGLE_CURLY = '\u2019'
_LEFT_DOUBLE_CURLY = '\u201c'
_RIGHT_DOUBLE_CURLY = '\u201d'


def _normalize_quotes(s: str) -> str:
    """convert curly quotes to straight quotes for fuzzy matching"""
    return s.replace(_LEFT_SINGLE_CURLY, "'").replace(_RIGHT_SINGLE_CURLY, "'")\
            .replace(_LEFT_DOUBLE_CURLY, '"').replace(_RIGHT_DOUBLE_CURLY, '"')


def find_actual_string(file_content: str, search_string: str) -> str | None:
    """find the actual string in file_content that matches search_string.

    Tries exact match first, then falls back to quote-normalized matching.
    Returns the actual string from the file (preserving original formatting),
    or None if not found.
    """
    # exact match
    idx = file_content.find(search_string)
    if idx != -1:
        return search_string

    # quote-normalized match
    norm_file = _normalize_quotes(file_content)
    norm_search = _normalize_quotes(search_string)
    idx = norm_file.find(norm_search)
    if idx != -1:
        return file_content[idx:idx + len(search_string)]

    return None


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
        new_str = old_str.replace(old_string, new_string, -1)
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
        new_str = old_str.replace(old_string, new_string, -1)
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


def render_edit_permission(path:str, active_idx: int, user_cache: str):
    """render file edit permission"""
    panels = []
    title = Text()
    title.append("Permission Request", style=f"bold {MAJOR_COLOR1}")
    body = Text()
    body.append(f"TECoSim Agent want to request permission for ", style=f"white")
    body.append(f"{TOOL_NAME_EDIT_FILE}", style=f"bold {MAJOR_COLOR1}")
    body.append(f" to path: ", style=f"white")
    body.append(f"{path}\n\n", style=f"bold {MAJOR_COLOR1}")
    str_list = ["Yes",
                "Yes, and agree all file edit during this agent session",
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
    if active_idx != 3:
        hint = Text(f"  ↑/↓ (select)    Enter (choose)\n", style="bright_black")
    else:
        hint = Text(f"  ↑/↓ (select)    Enter (modify)    Ctrl+Enter (confirm)\n", style="bright_black")
    panels.append(Panel(body, title=title, title_align="left", border_style=MAJOR_COLOR2))
    return Group(*panels, hint)


def ask_edit_tui(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]],
                 multi_match: bool, ctx: AgentContext, console: Console) -> tuple[bool, str | None]:
    """top realization of asking user for editing file TUI"""
    active_idx = 0  # default active option
    request_type = TOOL_NAME_EDIT_FILE
    user_cache = ""
    if ctx.args.dangerously_allow_all:
        return True, None
    if ctx.permissions[request_type]:
        return True, None
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
                with Live(render_edit_permission(path, active_idx, user_cache),
                          console=console, auto_refresh=False, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 4
                                live.update(render_edit_permission(path, active_idx, user_cache))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 4
                                live.update(render_edit_permission(path, active_idx, user_cache))
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
                                                                 f"{AGENT_CONSOLE_ICON} Your comment for edit: \n  ")
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
            sys_log.warning(f"Quest: {request_type} canceled, permission denied")
            console.print(f"Quest: {request_type} canceled, permission denied", style="bold yellow")
            return False, None


def check_read_only(in_path: str, ctx: AgentContext) -> tuple[bool, str]:
    """check the input str path is in read-only list in AgentContext"""
    try:
        fpath = Path(in_path)
        resolved_fpath = fpath.resolve()

        for base_path in ctx.system_read_only_paths:
            resolved_base_path = base_path.resolve()
            if resolved_fpath == resolved_base_path:
                return True, "You can't edit this path. This path is system read-only"
            if resolved_base_path.is_dir():
                if resolved_fpath.is_relative_to(resolved_base_path):
                    return True, f"You can't edit this path. The parent path {resolved_base_path} is system read-only"

        for base_path in ctx.read_only_paths:
            resolved_base_path = base_path.resolve()
            if resolved_fpath == resolved_base_path:
                return True, "You can't edit this path. This path is set to read-only by user"
            if resolved_base_path.is_dir():
                if resolved_fpath.is_relative_to(resolved_base_path):
                    return True, f"You can't edit this path. The parent path {resolved_base_path} is set to read-only by user"

        return False, ""
    except Exception as e:
        return False, f"Check read-only list failed with error {e}"
