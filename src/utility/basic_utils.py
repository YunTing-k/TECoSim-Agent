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
