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
2026.6.14      Yu Huang      1.9      Fix: grad_color zero div guard, bash version check, UUID validation log, file format offset
2026.6.30      Yu Huang      2.0      Add time formating function & Refactor the Markdown render style with custom theme &
                                      Add multi-round results truncate method with pydict keys preserved
2026.7.1       Yu Huang      2.1      Support of plain text of HTML tag rendering in LLM's response
2026.7.3       Yu Huang      2.2      Bugfix of buffered keyboard press before real TUI interaction
2026.7.17      Yu Huang      2.3      Fix: block quoted won't be suppressed by _escape_html_outside_code
2026.7.25      Yu Huang      2.4      Fix: prevent truncation in Markdown table with overflow="fold"
2026.8.2       Yu Huang      2.5      Remove get_webfetch_str from web_support.py to basic_utils.py
2026.8.15      Yu Huang      2.6      Add drain_after_kill: bounded pipe drain after kill (no infinite block)

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
import threading
import math
import rich.box

from typing import Any
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_input, Input
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Markdown, TableElement, HorizontalRule, ImageItem
from rich.segment import Segment
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from src.constants import *

sys_log = logging.getLogger('logger')


def create_clean_input() -> Input:
    """Create an Input with drained OS buffer and internal event queue.

    Call BEFORE raw_mode() to ensure no stale keystrokes leak into
    interactive dialogs (permission, question, edit, etc.).
    """
    input_device = create_input()
    input_device.flush_keys()
    while input_device.read_keys():
        pass
    return input_device


def flush_terminal_input() -> None:
    """Flush OS input buffer and drain event queue without creating a persistent Input.

    Call before any blocking input (e.g. PromptSession.prompt) to clear
    keystrokes pressed during non-interactive phases (LLM streaming).
    """
    d = create_input()
    try:
        d.flush_keys()
        while d.read_keys():
            pass
    finally:
        d.close()


class _RoundedTableElement(TableElement):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        table = Table(
            box=rich.box.ROUNDED,
            pad_edge=False,
            padding=(0, 0, 0, 0),
            border_style=MARKDOWN_TABLE_COLOR,
            style="markdown.table.border",
            show_edge=True,
            show_lines=True,
            collapse_padding=True,
        )

        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                table.add_column(heading, overflow="fold")

        if self.body is not None:
            for row in self.body.rows:
                row_content = [element.content for element in row.cells]
                table.add_row(*row_content)

        yield table


class _StyledHorizontalRule(HorizontalRule):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        style = console.get_style("markdown.hr", default="none")
        yield Rule(
            title=Text(f" {AGENT_CONSOLE_ICON} ", style=MARKDOWN_HR_COLOR),
            characters="─",
            style=style,
            align="center",
        )
        yield Text()


class _StyledImageItem(ImageItem):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        link_style = Style(link=self.link or self.destination or None)
        title = self.text or Text(self.destination.strip("/").rsplit("/", 1)[-1])
        if self.hyperlinks:
            title.stylize(link_style)
        text = Text.assemble("🖼️ ", title, " ")
        style = console.get_style("markdown.image", default="none")
        text.stylize(style)
        yield text


class _NoLeadingNewlinesMD(Markdown):
    """Markdown base: escapes < > outside code blocks so Rich does not strip them as HTML."""

    def __init__(self, markup: str, **kwargs):
        super().__init__(self._escape_html_outside_code(markup), **kwargs)

    @staticmethod
    def _escape_html_outside_code(markup: str) -> str:
        parts: list[str] = re.split(r"(```.*?```)", markup, flags=re.DOTALL)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                result.append(part)
            else:
                part = re.sub(
                    r"</?[a-zA-Z][^>]*>",
                    lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"),
                    part,
                )
                part = part.replace("<", "&lt;")
                result.append(part)
        return "".join(result)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        segments: list[Segment] = list(super().__rich_console__(console, options))
        start = 0
        for i, seg in enumerate(segments):
            if seg.text.strip():
                start = i
                break
        yield from segments[start:]


class ReasonMD(_NoLeadingNewlinesMD):
    """TECoSim agent Markdown render for agent reasoning"""

    elements = dict(Markdown.elements)
    elements["table_open"] = _RoundedTableElement
    elements["hr"] = _StyledHorizontalRule
    elements["image"] = _StyledImageItem

    def __init__(self, markup: str):
        super().__init__(markup)
        self.style = REASON_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


class ContentMD(_NoLeadingNewlinesMD):
    """TECoSim agent Markdown render for agent content"""

    elements = dict(Markdown.elements)
    elements["table_open"] = _RoundedTableElement
    elements["hr"] = _StyledHorizontalRule
    elements["image"] = _StyledImageItem

    def __init__(self, markup: str):
        super().__init__(markup)
        self.style = CONTENT_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


def get_console() -> Console:
    """Create a Console with Markdown theme styles applied."""
    return Console(theme=Theme({
        "markdown.h1": MARKDOWN_H1_STYLE,
        "markdown.h2": MARKDOWN_H2_STYLE,
        "markdown.h3": MARKDOWN_H3_STYLE,
        "markdown.h4": MARKDOWN_H4_STYLE,
        "markdown.h5": MARKDOWN_H5_STYLE,
        "markdown.h6": MARKDOWN_H6_STYLE,
        "markdown.code": MARKDOWN_INLINE_CODE_COLOR,
        "markdown.item.bullet": MARKDOWN_LIST_BULLET_COLOR,
        "markdown.item.number": MARKDOWN_LIST_NUMBER_COLOR,
        "markdown.table.header": MARKDOWN_TABLE_HEADER_STYLE,
        "markdown.block_quote": MARKDOWN_BLOCKQUOTE_STYLE,
        "markdown.link_url": MARKDOWN_LINK_COLOR,
        "markdown.hr": MARKDOWN_HR_COLOR,
        "markdown.image": MARKDOWN_IMAGE_STYLE,
    }))


def drain_after_kill(proc: subprocess.Popen, grace_s: float = 1.0) -> tuple[bytes, bytes]:
    """Bounded pipe drain after ``proc.kill()``.

    Runs ``proc.communicate()`` in a daemon thread and waits up to ``grace_s``
    seconds. If the pipe EOF never comes (a grandchild still holds the write
    end), give up and return empty bytes — the daemon thread keeps blocking,
    and its fds are reclaimed by the OS when the process exits.

    Notes:
    - Windows ``communicate(timeout=...)`` does not reliably time out
      (observed waiting for the full child lifetime), so the bound is enforced
      by a ``join`` with timeout instead of the timeout argument.
    - On give-up the pipe fds are intentionally NOT closed: closing a pipe
      read end on Windows blocks until the blocked reader thread unblocks
      (observed ~full child lifetime), which would defeat the bounded wait.
      The abandoned daemon thread + fds are reclaimed at process exit.

    Returns ``(stdout, stderr)`` bytes, possibly partial or empty.
    """
    result: dict[str, object] = {}

    def _read() -> None:
        try:
            result["out"], result["err"] = proc.communicate()
        except Exception as e:  # pragma: no cover - defensive
            result["exc"] = e

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(grace_s)
    if t.is_alive():
        return b"", b""
    if "exc" in result:
        raise result["exc"]  # type: ignore[misc]
    return result.get("out", b""), result.get("err", b"")  # type: ignore[return-value]


def truncate_tool_result(results: dict, limit: int, max_rounds: int) -> str:
    """Iteratively truncate the longest string field until json.dumps fits.

    Each round, the longest string field is cut and appended with a
    ``<truncated>N chars omitted</truncated>`` marker visible to LLMs.
    Falls back to hard JSON cut if max_rounds exhausted or results is not a dict.

    Returns the serialized (possibly truncated) JSON string, always <= limit.
    """
    import json as _json
    result_str = _json.dumps(results, ensure_ascii=False)
    total = len(result_str)
    if total <= limit:
        return result_str

    sys_log.debug(f"Tool result ({total} chars) exceeds limit ({limit}), starting truncation")

    if not isinstance(results, dict) or max_rounds <= 0:
        sys_log.warning(f"Tool result truncation: non-dict type or zero rounds, falling back to hard cut")
        return _hard_cut(result_str, limit)

    for rnd in range(1, max_rounds + 1):
        str_fields = {k: v for k, v in results.items() if isinstance(v, str)}
        if not str_fields:
            break
        longest_key = max(str_fields, key=lambda k: len(str_fields[k]))
        overhead = len(result_str) - len(results[longest_key])
        budget = max(TOOL_RESULT_TRUNCATION_MIN_BUDGET, limit - overhead - TOOL_RESULT_TRUNCATION_MARKER_RESERVE)
        if len(results[longest_key]) <= budget:
            sys_log.debug(f"Truncation round {rnd}: field '{longest_key}' already fits ({len(results[longest_key])} <= {budget}), stopping")
            break
        omitted = len(results[longest_key]) - budget
        marker = f"...{TOOL_RESULT_TRUNCATION_START_LABEL}{omitted} chars omitted{TOOL_RESULT_TRUNCATION_END_LABEL}"
        results[longest_key] = results[longest_key][:budget] + marker
        result_str = _json.dumps(results, ensure_ascii=False)
        sys_log.debug(f"Truncation round {rnd}: field '{longest_key}' {len(results[longest_key])} -> {budget + len(marker)} "
                      f"chars, total {len(result_str)}/{limit}")
        if len(result_str) <= limit:
            sys_log.debug(f"Tool result truncation complete after {rnd} round(s), final size {len(result_str)}")
            break
    else:
        sys_log.warning(f"Tool result truncation: {max_rounds} round(s) exhausted, still {len(result_str)} chars (limit {limit})")

    if len(result_str) > limit:
        sys_log.warning(f"Tool result truncation: falling back to hard cut ({len(result_str)} -> {limit})")
        result_str = _hard_cut(result_str, limit)
    return result_str


def _hard_cut(result_str: str, limit: int) -> str:
    """Hard truncation: cut the JSON string, respecting limit."""
    marker = f"...{TOOL_RESULT_TRUNCATION_START_LABEL}{len(result_str) - limit} chars omitted{TOOL_RESULT_TRUNCATION_END_LABEL}"
    if limit > len(marker):
        return result_str[:limit - len(marker)] + marker
    return result_str[:limit]


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
    if gradient <= 1:
        return [start_rgb[0]], [start_rgb[1]], [start_rgb[2]]
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
    if gradient <= 1:
        return [start_hex]
    for i in range(gradient):
        t = i / (gradient - 1)
        if grad_type == "sin":
            t = math.sin(t * math.pi / 2)
        h_list.append(rgb_to_hex((
            int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t),
            int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t),
            int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t))))
    return h_list


def format_time_sec(seconds: float | int) -> str:
    """format seconds into string"""
    total_seconds = int(seconds)

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


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
            json.dump(configs, file, indent=2, ensure_ascii=False)
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
            [path, "--version"],
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
    except Exception as e:
        sys_log.error(f"UUID validation failed with error: {e}")
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


def get_webfetch_str(arguments: dict[str, Any]) -> str:
    """get webfetch string from arguments only for display"""
    url = arguments.get("url", "(Failed to get URL)")
    fetch_prompt = arguments.get("prompt", "(Failed to get prompt)")
    return (f"{TOOL_NAME_WEB_FETCH}:\n"
            f"├─URL: \"{url}\"\n"
            f"└─prompt: \"{fetch_prompt}\"")