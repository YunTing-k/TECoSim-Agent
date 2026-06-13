# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.21
Description: Basic utilities for whole project

Revision:
---------
2026.5.21      Yu Huang      1.0      First implementation
2026.5.22      Yu Huang      1.1      Summarize session title support
2026.5.29      Yu Huang      1.2      Add agent's Markdown render style
2026.6.5       Yu Huang      1.3      Render bash command as Markdown support
2026.6.8       Yu Huang      1.4      Bash and ripgrep path configurable support
2026.6.9       Yu Huang      1.5      Remove read_line_with_limit to basic_utils.py
2026.6.11      Yu Huang      1.6      Add format_file_for_llm: XML-wrapped left-aligned pipe-separated line-number output for LLM consumption
2026.6.11      Yu Huang      1.7      Move rgb_to_hex, hex_to_rgb, grad_color_rgb_list and grad_color_hex_list to basic_utils.py &
                                       Remove the space noise in readout content line prefix
2026.6.13      Yu Huang      1.8      Add grad_type="sin" to grad_color_hex_list / grad_color_rgb_list for cosine-like smooth animation

Details:
---------
Shared utilities: JSON config load/save, platform detection, git repo check, bash availability check. Also provides custom
Rich Markdown renderers (ReasonMD, ContentMD) for agent output styling, UUID validation, and JSON field extraction (including
regex fallback) from LLM responses.
"""
import os
import re
import json
import uuid
import logging
import platform
import subprocess
import math

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown
from src.constants import *

sys_log = logging.getLogger('logger')


class ReasonMD(Markdown):
    """TECoSim agent Markdown render for agent reasoning"""
    def __init__(self, markup: str):
        super().__init__(markup)
        self.style = REASON_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


class ContentMD(Markdown):
    """TECoSim agent Markdown render for agent content"""
    def __init__(self, markup: str):
        super().__init__(markup)
        self.style = CONTENT_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


class BashMD(Markdown):
    """TECoSim agent Markdown render for bash command"""
    def __init__(self, markup: str):
        super().__init__(markup)
        self.style = BASH_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """convert rgb to hex color"""
    r, g, b = rgb
    for value, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
        if not isinstance(value, int):
            sys_log.error(f"Invalid RGB value: {name}={value} must be integer")
            raise TypeError(f"Invalid RGB value: {name}={value} must be integer")
        if value < 0 or value > 255:
            sys_log.error(f"Invalid RGB value: {name}={value} out of range [0, 255]")
            raise ValueError(f"Invalid RGB value: {name}={value} out of range [0, 255]")

    try:
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        return hex_color
    except Exception as e:
        sys_log.error(f"Failed to convert RGB {rgb} to hex with error: {e}")
        raise RuntimeError(f"Failed to convert RGB {rgb} to hex with error: {e}")


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
        sys_log.error(f"Failed to convert hex color: {hex_color} to RGB tuples with error: {e}")
        raise RuntimeError(f"Failed to convert hex color: {hex_color} to RGB tuples with error: {e}")


def grad_color_rgb_list(start_rgb: tuple, end_rgb: tuple, gradient: int, grad_type: str = "linear") -> tuple[list[int], list[int], list[int]]:
    """get gradient color RGB list; grad_type: "linear" (default) or "sin" (cosine-like, smooth acceleration/deceleration)"""
    r_list: list[int] = []
    g_list: list[int] = []
    b_list: list[int] = []
    for i in range(gradient):
        t = i / (gradient - 1)
        if grad_type == "sin":
            t = math.sin(t * math.pi / 2)
        r_list.append(int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t))
        g_list.append(int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t))
        b_list.append(int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t))
    return r_list, g_list, b_list


def grad_color_hex_list(start_hex: str, end_hex: str, gradient: int, grad_type: str = "linear") -> list[str]:
    """get gradient color hex list; grad_type: "linear" (default) or "sin" (cosine-like smooth ease-in/out)"""
    start_rgb = hex_to_rgb(start_hex)
    end_rgb = hex_to_rgb(end_hex)
    h_list: list[str] = []
    for i in range(gradient):
        t = i / (gradient - 1)
        if grad_type == "sin":
            t = math.sin(t * math.pi / 2)
        h_list.append(rgb_to_hex((
            int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t),
            int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t),
            int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t))))
    return h_list


def load_configs(configs_path: str, name: str, console: Console):
    """load JSON configs with given path"""
    try:
        with open(configs_path, 'r', encoding="utf-8") as file:
            api_configs = json.load(file)
            sys_log.debug(f"Load {name} configs from {configs_path} done")
            return api_configs
    except Exception as e:
        sys_log.error(f"Failed to load {name} configs from {configs_path} with error: {e}")
        console.print(f"Failed to load {name} configs from {configs_path} with error: {e}", style="bold red")
        raise RuntimeError(e)


def write_configs(configs_path: str, configs, name: str, console: Console):
    """write JSON configs with given path"""
    try:
        with open(configs_path, 'w', encoding="utf-8") as file:
            json.dump(configs, file, ensure_ascii=False, indent=2)
            sys_log.debug(f"Write {name} configs to {configs_path} done")
    except Exception as e:
        sys_log.error(f"Failed to write {name} configs to {configs_path} with error: {e}")
        console.print(f"Failed to write {name} configs to {configs_path} with error: {e}", style="bold red")
        raise RuntimeError(e)


def get_platform_info() -> list[str]:
    """get the information of the running platform"""
    system = platform.system()
    release = platform.release()
    version = platform.version()
    return [system, release, version]


def is_git_available() -> bool:
    """check if git is available"""
    try:
        result = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call git failed with error {e}. Check if git is available in you shell")
        return False


def is_git_repo(path: str = None) -> bool:
    """check if the given path is a git repository"""
    if path is None:
        path = os.getcwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call git failed with error {e}. Check if git is available in you shell")
        return False


def is_bash_available(path: str) -> bool:
    """check if bash is available"""
    try:
        result = subprocess.run(
            [path, "-c", "bash --version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call bash failed with error {e}. Check if bash is available in path: {path}")
        return False


def is_ripgrep_available(path: str) -> bool:
    """check if ripgrep is available"""
    try:
        result = subprocess.run(
            [path, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        sys_log.error(f"Call ripgrep failed with error {e}. Check if ripgrep is available in path: {path}")
        return False


def _extract_key_from_dict(d: dict, key: str) -> str | None:
    """traverse dict, find all possible key"""
    if key in d:
        return d[key]

    for value in d.values():
        if isinstance(value, dict):
            title = _extract_key_from_dict(value, key)
            if title is not None:
                return title
    return None


def _extract_json_candidates(text: str) -> list[str]:
    """find all possible JSON"""
    candidates = []
    brace_positions = [i for i, ch in enumerate(text) if ch == '{']

    for start in brace_positions:
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if depth == 0 and end > start:
            candidates.append(text[start:end + 1])
    return candidates


def get_field(str_in: str | None, key: str="title") -> str | None:
    """get key field from string, load as JSON, fallback with regx"""
    if not str_in:
        return None

    """load the whole string"""
    try:
        content = json.loads(str_in)
        if isinstance(content, dict):
            title = _extract_key_from_dict(content, key)
            if title:
                return str(title)
    except Exception:
        pass

    """find all possible json sub-string"""
    for candidate in _extract_json_candidates(str_in):
        try:
            content = json.loads(candidate)
            if isinstance(content, dict):
                title = _extract_key_from_dict(content, key)
                if isinstance(title, str) and title:
                    return str(title)
        except Exception:
            continue

    """extract key with regx"""
    match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', str_in)
    if match:
        title = match.group(1)
        title = title.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return str(title)
    return None


def is_valid_uuid(uuid_str: str) -> bool:
    """verify if UUID is valid"""
    try:
        uuid.UUID(uuid_str)
        return True
    except Exception:
        return False


def get_user_input(user_cache: str, agent_session: PromptSession, default_str: str) -> tuple[str, bool, bool]:
    """get the user's input with prompt and update the cache"""
    is_empty = True
    is_modify = False
    cache = user_cache
    user_input = agent_session.prompt(default_str, default=cache)
    if user_input.strip():
        is_empty = False
    if cache != user_input:
        is_modify = True
    return user_input, is_empty, is_modify


def is_list_of_int(obj) -> bool:
    """chek if the given object is a list of int"""
    if not isinstance(obj, list):
        return False
    return all(isinstance(item, int) for item in obj)


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


def format_file_for_llm(lines: list[str], file_path: str, start_line: int,
                        shown_count: int, total_lines: int, truncated: bool) -> str:
    """format file content for LLM consumption with pipe-separated line numbers and XML wrapper.

    Output format (following CodeWhale/OpenCode best practices):
      <file path="..." lines="X-Y" total="Z" truncated="true|false">
      X|content
      ...
      Y|content
      (footer)
      </file>
    """
    offset_idx = start_line - 1
    snippet = lines[offset_idx : offset_idx + shown_count]
    if shown_count > 0:
        shown_first = start_line
        shown_last = start_line + len(snippet) - 1
    else:
        shown_first = 0
        shown_last = 0
    output = f'<file path="{file_path}" lines="{shown_first}-{shown_last}" total="{total_lines}" truncated="{str(truncated).lower()}">\n'
    for i, line in enumerate(snippet):
        line_no = start_line + i
        if len(line) > READ_FILE_LINE_CHAR_LIMIT:
            line = line[:READ_FILE_LINE_CHAR_LIMIT] + f"... (line truncated to {READ_FILE_LINE_CHAR_LIMIT} chars)\n"
        output += f"{line_no}│{line}"

    if truncated:
        next_offset = start_line + len(snippet)
        remaining = total_lines - next_offset + 1
        output += f"\n({remaining} lines not shown, use offset={next_offset} to continue)\n"
    else:
        output += f"\n(End of file - total {total_lines} lines)\n"
    output += "</file>\n"
    return output
