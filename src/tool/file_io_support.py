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
2026.6.10      Yu Huang      2.2      Implement 7-stage edit_file fallback matching chain with per-mode TUI visibility &
                                      rewrite fill_str_line for long-line soft-wrap & fix merge_intervals for multi-preview blocks
2026.6.10      Yu Huang      2.3      Add syntax highlighting (pygments) to edit preview diff views
2026.6.11      Yu Huang      2.4      Refactor edit diff: separate gutter/line/content bg with per-area colors & 3-part
                                      continuation gutter split & fix pygments TextLexer extra \n & NBSP fill for full-width bg
2026.6.11      Yu Huang      2.5      Refactor render_preview_*: extract 4 shared helpers to eliminate ~194 lines of duplication
2026.6.11      Yu Huang      2.6      Fix CJK continuation via unicodedata display-width slicing & Rich multi-span boundary &
                                      enhance match chain with dash/space normalization, EOF-first rfind, pattern guards, hunk separator
2026.6.11      Yu Huang      2.7      Apply highlight-then-split to edit preview: _highlight_and_wrap_edit preserves token styles
                                      across wrap boundaries (replaces per-chunk _highlight_fragment in render_normal/diff_block)
2026.6.11      Yu Huang      2.8      Add get_write_render for write_file permission preview with syntax highlighting,
                                      line-number gutter, configurable truncation, and highlight-then-split wrapping
2026.6.11      Yu Huang      2.9      Move format_file_for_llm to basic_utils.py (circular import) & integrate pipe-format
                                      into read_file/read_log_impl XML-wrapped LLM output with truncation footer

Details:
---------
File I/O support layer: (1) read truncation with byte-limit enforcement; (2) TOOL_NAME_EDIT_FILE — 7-stage cascade
fallback matching with per-mode track & enhanced Unicode normalization (quotes/dashes/spaces) and EOF-first rfind;
(3) preview renderers with pygments syntax highlighting, diff-style add/remove with soft-wrap, 3-part gutter bg,
CJK display-width continuity, inter-hunk separator, and highlight-then-split token-style preservation;
(4) write_file content preview (get_write_render) with lexer-based highlighting, line-number gutter, configurable
truncation, and highlight-then-split wrapping; (5) edit permission TUI with preview and match mode
visibility; (6) read-only path checking; (7) session saving utility.
"""
import os
import math
import time
import logging
import unicodedata

from pathlib import Path
from rich.console import Group, Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from pygments.styles import get_style_by_name
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.util import ClassNotFound
from pygments import lex
from src.context import prompt
from src.utility.basic_utils import get_user_input
from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.constants import *

sys_log = logging.getLogger('logger')

_lexer_cache: dict[str, object] = {}
_pygments_style_map: dict | None = None


def _get_lexer(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext not in _lexer_cache:
        try:
            _lexer_cache[ext] = get_lexer_for_filename(path)
        except ClassNotFound:
            _lexer_cache[ext] = TextLexer()
    return _lexer_cache[ext]


def _build_style_map():
    pygments_style = get_style_by_name(EDIT_SYNTAX_THEME)
    style_map = {}
    for token_type, style_str in pygments_style.styles.items():
        rich_style = Style()
        if not style_str:
            style_map[token_type] = rich_style
            continue
        parts = style_str.split()
        if "bold" in parts:
            rich_style = Style(bold=True)
        if "italic" in parts:
            rich_style += Style(italic=True)
        if "underline" in parts:
            rich_style += Style(underline=True)
        for part in parts:
            if part.startswith("#") and len(part) == 7:
                rich_style += Style(color=part)
            elif part.startswith("bg:#"):
                rich_style += Style(bgcolor=part[3:])
        if rich_style:
            style_map[token_type] = rich_style
    return style_map


def _get_style_map():  # type: ignore[return-type]
    global _pygments_style_map
    if _pygments_style_map is None:
        _pygments_style_map = _build_style_map()
    return _pygments_style_map


def _highlight_fragment(text: str, lexer, strip_bg: bool = False) -> Text:
    style_map = _get_style_map()
    assert style_map is not None
    result = Text()
    tokens = list(lex(text, lexer))
    # pygments TextLexer (and possibly others) append an extra trailing newline;
    # strip it when the input text did not originally end with a newline
    if tokens and not text.endswith('\n'):
        last_type, last_text = tokens[-1]
        if last_text.endswith('\n'):
            tokens[-1] = (last_type, last_text[:-1])
    for token_type, token_text in tokens:
        resolved = _resolve_token_style(style_map, token_type)
        if resolved is not None:
            if strip_bg and resolved.bgcolor:
                resolved = Style(color=resolved.color, bold=resolved.bold,
                                 italic=resolved.italic, underline=resolved.underline)
            result.append(token_text, style=resolved)
        else:
            result.append(token_text)
    return result


def _resolve_token_style(style_map: dict, token_type) -> Style | None:
    tt = token_type
    while tt is not None:
        s = style_map.get(tt)
        if s is not None and s != Style():
            return s
        tt = tt.parent
    return None


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


_PUNCTUATION_MAP: dict[str, str] = {
    '\u2018': "'", '\u2019': "'",  # curly single quotes
    '\u201c': '"', '\u201d': '"',  # curly double quotes
    '\u2013': '-', '\u2014': '-',  # en-dash, em-dash
    '\u00a0': ' ',                 # non-breaking space
    '\u3000': ' ',                 # full-width space (CJK)
}


def _normalize_quotes(s: str) -> str:
    """convert curly quotes to straight quotes for fuzzy matching (kept for backward compat)."""
    return _normalize_punctuation(s)


def _normalize_punctuation(s: str) -> str:
    """normalize Unicode typographic punctuation to ASCII equivalents.

    Handles copy-paste failures where browsers/chat clients silently
    substitute: smart quotes → straight quotes, em/en-dashes → hyphens,
    non-breaking space / full-width space → regular space.
    """
    for old, new in _PUNCTUATION_MAP.items():
        s = s.replace(old, new)
    return s


def _unescape_unicode(text: str) -> str:
    """decode Python-style \\uXXXX and \\UXXXXXXXX escape sequences to actual Unicode characters.
    
    Handles cases where the LLM outputs literal escape sequences (single or double-escaped)
    instead of the actual Unicode characters (e.g., '\\u201c' or '\\\\u201c' → '\u201c').
    Applies un-escaping repeatedly until no more escape sequences remain.
    """
    import re
    def _replace_hex(match):
        return chr(int(match.group(1), 16))
    prev = None
    while prev != text:
        prev = text
        text = text.replace('\\\\', '\\')
        text = re.sub(r'\\u([0-9a-fA-F]{4})', _replace_hex, text)
        text = re.sub(r'\\U([0-9a-fA-F]{8})', _replace_hex, text)
    return text


def _unescape_literals(text: str) -> str:
    """decode common escape sequences that LLMs may output as literal text.

    Handles cases where the LLM writes '\n' (backslash-n) instead of an actual
    newline character. Uses a character-by-character state machine to avoid
    double-processing already-escaped sequences.
    """
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == 'n':
                result.append('\n')
                i += 2
                continue
            elif nxt == 't':
                result.append('\t')
                i += 2
                continue
            elif nxt == 'r':
                result.append('\r')
                i += 2
                continue
            elif nxt == '\\':
                result.append('\\')
                i += 2
                continue
            elif nxt == '\'':
                result.append('\'')
                i += 2
                continue
            elif nxt == '"':
                result.append('"')
                i += 2
                continue
        result.append(text[i])
        i += 1
    return ''.join(result)


def match_escape_literal(raw_str: str, target: str) -> tuple[list[tuple[int, int]], str]:
    """try to match target in file by un-escaping literal escape sequences.

    Useful when the LLM outputs '\n' as literal text instead of actual newlines.
    target: LLM-provided old_string (already CRLF-normalized)
    raw_str: complete file content as a single string

    Returns (match_line_ranges, actual_old_string) or ([], "").
    """
    unescaped = _unescape_literals(target)
    if unescaped == target or len(unescaped) > len(raw_str):
        return [], ""

    idx = raw_str.find(unescaped)
    if idx == -1:
        return [], ""

    actual = raw_str[idx:idx + len(unescaped)]
    target_lines = actual.rstrip('\n').count('\n')
    prefix = raw_str[:idx]
    start_line = prefix.count('\n') + 1
    end_line = start_line + target_lines
    return [(start_line, end_line)], actual


def match_trimmed_boundary(raw_str: str, target: str) -> tuple[list[tuple[int, int]], str]:
    """try to match target after removing leading/trailing whitespace from old_string.

    Useful when the LLM accidentally includes extra whitespace around old_string.
    target: LLM-provided old_string (already CRLF-normalized)
    raw_str: complete file content as a single string

    Returns (match_line_ranges, actual_old_string) or ([], "").
    """
    trimmed = target.strip()
    if trimmed == target or not trimmed or len(trimmed) > len(raw_str):
        return [], ""

    idx = raw_str.find(trimmed)
    if idx == -1:
        return [], ""

    actual = raw_str[idx:idx + len(trimmed)]
    target_lines = actual.rstrip('\n').count('\n')
    prefix = raw_str[:idx]
    start_line = prefix.count('\n') + 1
    end_line = start_line + target_lines
    return [(start_line, end_line)], actual


def find_actual_string(file_content: str, search_string: str) -> str | None:
    """find the actual string in file_content that matches search_string.

    Tries exact match first, then punctuation-normalized forward search,
    then punctuation-normalized backward (EOF-first) search. Returns the
    actual string from the file (preserving original formatting), or None
    if not found.
    """
    # exact match
    idx = file_content.find(search_string)
    if idx != -1:
        return search_string

    # punctuation-normalized forward match (quotes, dashes, spaces)
    norm_file = _normalize_punctuation(file_content)
    norm_search = _normalize_punctuation(search_string)
    idx = norm_file.find(norm_search)
    if idx != -1:
        return file_content[idx:idx + len(search_string)]

    # punctuation-normalized backward (EOF-first) — useful when the
    # edit target is near the end of a long file and a similar string
    # appears earlier
    idx = norm_file.rfind(norm_search)
    if idx != -1:
        return file_content[idx:idx + len(search_string)]

    return None


def match_unicode_escape(raw_str: str, target: str) -> tuple[list[tuple[int, int]], str]:
    """try to match target in file by decoding \\uXXXX Unicode escape sequences.

    Useful when the LLM outputs literal Unicode escape sequences instead of
    the actual characters (e.g., '\\u00b2' → '²').
    raw_str: complete file content as a single string
    target: LLM-provided old_string (already CRLF-normalized)

    Returns (match_line_ranges, actual_old_string) or ([], "").
    """
    if '\\u' not in target and '\\U' not in target:
        return [], ""

    unescaped = _unescape_unicode(target)
    if unescaped == target or len(unescaped) > len(raw_str):
        return [], ""

    idx = raw_str.find(unescaped)
    if idx == -1:
        return [], ""

    actual = raw_str[idx:idx + len(unescaped)]
    target_lines = actual.rstrip('\n').count('\n')
    prefix = raw_str[:idx]
    start_line = prefix.count('\n') + 1
    end_line = start_line + target_lines
    return [(start_line, end_line)], actual


def match_line_ranges(content: str, target: str, match_all: bool) -> list[tuple[int, int]]:
    """match the content with target and return the line ranges of the matches"""
    if not target or len(target) > len(content):
        return []
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


def _strip_common_indent(text: str) -> str:
    """strip the minimum common indentation from all non-empty lines"""
    lines = text.splitlines()
    min_indent = None
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if min_indent is None or indent < min_indent:
                min_indent = indent
    if min_indent is None or min_indent == 0:
        return text
    return '\n'.join(line[min_indent:] if line.strip() else line for line in lines)


def match_line_trimmed(raw_line: list[str], target: str) -> tuple[list[tuple[int, int]], str]:
    """try to match target in file by trimming trailing whitespace from each line.

    Useful when LLM copies code but adds trailing whitespace differences.
    raw_line: list of original file lines (preserving native line endings)
    target: LLM-provided old_string (already CRLF-normalized to \\n)

    Returns (match_line_ranges, actual_old_string) or ([], "").
    """
    target_lines = target.rstrip('\n').splitlines()
    if not target_lines or len(target_lines) > len(raw_line):
        return [], ""

    content_stripped = [line.rstrip('\n').rstrip('\r').rstrip() for line in raw_line]
    target_stripped = [t.rstrip() for t in target_lines]
    t_len = len(target_stripped)
    c_len = len(content_stripped)

    start = 0
    while start <= c_len - t_len:
        if content_stripped[start:start + t_len] == target_stripped:
            actual = ''.join(raw_line[start:start + t_len])
            return [(start + 1, start + t_len)], actual
        start += 1

    return [], ""


def match_flexible_indent(raw_line: list[str], target: str) -> tuple[list[tuple[int, int]], str]:
    """try to match target in file by stripping common indentation from both sides.

    Useful when LLM copies indented code but gets the indentation level wrong.
    raw_line: list of original file lines (preserving native line endings)
    target: LLM-provided old_string (already CRLF-normalized to \\n)

    Returns (match_line_ranges, actual_old_string) or ([], "").
    """
    target_stripped = _strip_common_indent(target)
    target_lines_stripped = target_stripped.splitlines()
    t_len = len(target_lines_stripped)
    if not target_lines_stripped or t_len == 0 or t_len > len(raw_line):
        return [], ""

    c_len = len(raw_line)

    for start in range(c_len - t_len + 1):
        candidate_str = ''.join(raw_line[start:start + t_len])
        candidate_stripped = _strip_common_indent(candidate_str)
        # also rstrip lines to handle combined indent + trailing whitespace diff
        candidate_stripped_rstrip = '\n'.join(l.rstrip() for l in candidate_stripped.splitlines())
        target_stripped_rstrip = '\n'.join(l.rstrip() for l in target_lines_stripped)
        if candidate_stripped_rstrip == target_stripped_rstrip:
            actual = ''.join(raw_line[start:start + t_len])
            return [(start + 1, start + t_len)], actual

    return [], ""


def get_enhanced_debug_info(content: str, raw_line: list[str], target: str) -> str:
    """get enhanced debug info with per-line match status when exact match fails.

    Builds on the basic get_match_debug_info and adds line-by-line analysis
    to help the LLM identify which part of old_string needs correction.
    """
    parts = [get_match_debug_info(content, target)]

    target_lines = target.rstrip('\n').splitlines()
    if not target_lines:
        return " | ".join(parts)

    content_lines = [line.rstrip('\n').rstrip('\r') for line in raw_line]

    parts.append(f"target_line_count={len(target_lines)}")

    # for each target line, try to find it in content (trimmed comparison)
    # Cap per-line analysis at 30 lines to avoid excessive output for very large targets
    _MAX_LINE_ANALYSIS = 30
    line_status_parts = []
    if len(target_lines) <= _MAX_LINE_ANALYSIS:
        analyze_lines = list(enumerate(target_lines))
        truncated_lines = False
    else:
        half = _MAX_LINE_ANALYSIS // 2
        analyze_lines = list(enumerate(target_lines[:half])) + list(enumerate(target_lines[-half:], len(target_lines) - half))
        truncated_lines = True

    for i, t_line in analyze_lines:
        t_stripped = t_line.rstrip()
        found = False
        for j, c_line in enumerate(content_lines):
            if c_line.rstrip() == t_stripped:
                line_status_parts.append(f"tln_{i + 1}=found@cln_{j + 1}")
                found = True
                break
        if not found:
            line_status_parts.append(f"tln_{i + 1}=NOT_FOUND(repr={repr(t_line)})")

    if truncated_lines:
        half = _MAX_LINE_ANALYSIS // 2
        line_status_parts.insert(half, f"...({len(target_lines) - _MAX_LINE_ANALYSIS}_more_lines_omitted)...")

    parts.append("; ".join(line_status_parts))

    # try to find the first line match and show surrounding context
    if target_lines:
        first_stripped = target_lines[0].rstrip()
        for j, c_line in enumerate(content_lines):
            if c_line.rstrip() == first_stripped:
                ctx_start = max(0, j - 1)
                ctx_end = min(len(content_lines), j + len(target_lines) + 1)
                ctx_repr = [f"cln_{k + 1}(repr)={repr(content_lines[k])}" for k in range(ctx_start, ctx_end)]
                parts.append("context_around_first_match: " + "; ".join(ctx_repr))
                break
        else:
            parts.append("first_line_not_found_in_file")

    return " | ".join(parts)


def get_line_prefix(idx: int, budget: int, mode: str = "normal") -> tuple[str, str, str]:
    """get the prefix of line with space and line index
    Returns (prefix1_margin, prefix2_line_number, symbol).
    symbol is ' - ' for remove, ' + ' for add, '   ' for normal.
    """
    if idx <= 0:
        raise RuntimeError(f"Invalid line index {idx} <= 0")
    else:
        digits = math.floor(math.log10(idx)) + 1
    if budget < digits:
        raise RuntimeError(f"Invalid budget {budget} < digits {digits}")
    prefix1 = " " * EDIT_VIEW_LEFT_SPACE_MARGIN
    prefix2 = " " * (EDIT_VIEW_LINE_SPACE_MARGIN + budget - digits) + f"{idx}"
    if mode == "remove":
        symbol = " - "
    elif mode == "add":
        symbol = " + "
    elif mode == "normal":
        symbol = "   "
    else:
        sys_log.warning(f"Unknown line prefix mode: {mode}")
        symbol = "  "
    return prefix1, prefix2, symbol


def _display_width(s: str) -> int:
    """compute the terminal display width of a string (CJK characters count as 2)."""
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ('F', 'W') else 1
    return w


def _slice_by_width(s: str, max_width: int) -> tuple[str, str]:
    """split s at the display-width boundary: (head, tail) where display_width(head) <= max_width."""
    w = 0
    for i, ch in enumerate(s):
        cw = 2 if unicodedata.east_asian_width(ch) in ('F', 'W') else 1
        if w + cw > max_width:
            return s[:i], s[i:]
        w += cw
    return s, ''


def _highlight_and_wrap_edit(line: str, lexer, max_width: int, strip_bg: bool = True) -> tuple[Text, list[Text]]:
    """highlight full line then split by display width — preserves token styles across wrap boundaries.

    Returns (first_chunk, cont_chunks) where first_chunk is a Text object with the
    first display-width slice of content (no gutter, no padding, no newline), and
    cont_chunks is a list of Text objects for each subsequent wrapping slice
    (no gutter, no padding). The caller is responsible for adding gutter, NBSP padding,
    and newlines.

    max_width is the available display-width for content (terminal columns minus gutter offset minus 1).
    """
    if line.endswith('\r\n'):
        content = line[:-2]
    elif line.endswith('\n'):
        content = line[:-1]
    else:
        content = line

    hl = _highlight_fragment(content, lexer, strip_bg=strip_bg)
    plain = str(hl)

    char_styles: list[Style | None] = [None] * len(plain)
    for span in hl.spans:
        for i in range(span.start, span.end):
            if char_styles[i] is None:
                char_styles[i] = span.style

    chunks: list[Text] = []
    pos = 0
    total = len(plain)
    while pos < total:
        w = 0
        start = pos
        while pos < total:
            cw = 2 if unicodedata.east_asian_width(plain[pos]) in ('F', 'W') else 1
            if w + cw > max_width:
                break
            w += cw
            pos += 1
        chunk = Text()
        i = start
        while i < pos:
            j = i + 1
            sty = char_styles[i]
            while j < pos and char_styles[j] == sty:
                j += 1
            chunk.append(plain[i:j], style=sty)
            i = j
        chunks.append(chunk)

    return chunks[0] if chunks else Text(), chunks[1:]


def fill_str_line(input_line: str, offset: int) -> tuple[str, list[str]]:
    """split a content line into (first_physical_line, continuation_lines).

    The first element contains the content for the first physical line, padded to
    (terminal_width - offset) for background fill. Subsequent elements are continuation
    lines: indent(offset spaces) + content_chunk + padding, each terminal_width display cells.

    The caller must style continuation lines: the first len(prefix1) chars (margin) use
    EDIT_VIEW_NORMAL_BG, the next (len(prefix2)+3) chars (line/symbol gutter) use the
    block's line_bg, and the remainder (content) uses the block's content bg.

    Padding uses U+00A0 (non-breaking space) for invisible background fill.
    CJK full-width characters are accounted for (2 display cells each).
    """
    _fill = '\u00A0'
    width = os.get_terminal_size().columns - offset - 1
    if width < 1:
        width = 1

    if input_line.endswith('\r\n'):
        line_ending = '\r\n'
        content = input_line[:-2]
    elif input_line.endswith('\n'):
        line_ending = '\n'
        content = input_line[:-1]
    else:
        line_ending = '\n'
        content = input_line

    if _display_width(content) <= width:
        return content + _fill * (width - _display_width(content)) + line_ending, []

    indent = " " * offset
    chunk, remaining = _slice_by_width(content, width)
    chunk_padded = chunk + _fill * (width - _display_width(chunk))
    parts = [chunk_padded]
    while remaining:
        chunk, remaining = _slice_by_width(remaining, width)
        chunk_padded = chunk + _fill * (width - _display_width(chunk))
        parts.append(indent + chunk_padded)

    first = parts[0] + line_ending
    return first, parts[1:]


def _create_diff_styles() -> dict[str, Style]:
    """create all Style objects needed for diff preview rendering."""
    return {
        'rmv_style': Style(bgcolor=EDIT_VIEW_RMV_BG),
        'add_style': Style(bgcolor=EDIT_VIEW_ADD_BG),
        'normal_style': Style(bgcolor=EDIT_VIEW_NORMAL_BG),
        'normal_prefix_style': Style(color="bright_black", bgcolor=EDIT_VIEW_NORMAL_BG),
        'margin_style': Style(color="bright_black", bgcolor=EDIT_VIEW_NORMAL_BG),
        'rmv_line_style': Style(color="bright_black", bgcolor=EDIT_VIEW_RMV_LINE_BG),
        'add_line_style': Style(color="bright_black", bgcolor=EDIT_VIEW_ADD_LINE_BG),
    }


def _render_edit_header(body: Text, path: str, added_count: int, removed_count: int, match_mode: str):
    """append the edit header (path, line counts, match mode) to the body Text."""
    body.append("Edit file: ", style=f"bold {MAJOR_COLOR2}")
    body.append(f"{path}\n", style=f"bold white")
    body.append(f"Add ", style="bright_black")
    body.append(f"{added_count}", style=f"bold {MAJOR_COLOR2}")
    body.append(f" lines, remove ", style="bright_black")
    body.append(f"{removed_count}", style=f"bold {MAJOR_COLOR2}")
    body.append(f" lines", style="bright_black")
    if match_mode not in MATCH_MODE_EXACT_FAMILY:
        body.append(f"  [{MATCH_MODE_DESC[match_mode]}]", style=f"bold {EDIT_FUZZY_WARN_COLOR}")
    elif match_mode != MATCH_MODE_EXACT:
        body.append(f"  [{MATCH_MODE_DESC[match_mode]}]", style=f"{EDIT_SUBTLE_COLOR}")
    body.append(f"\n\n", style="bright_black")


def _render_normal_block(body: Text, lines: list[str], start_idx: int, budget: int, lexer, styles: dict[str, Style]):
    """render a block of normal (context) lines with gutter and optional syntax highlighting."""
    normal_style = styles['normal_style']
    normal_prefix_style = styles['normal_prefix_style']
    for idx, line in enumerate(lines):
        prefix1, prefix2, _ = get_line_prefix(start_idx + idx, budget)
        offset = len(prefix1) + len(prefix2) + 3
        body.append(prefix1 + prefix2 + "   ", style=f"bright_black on {EDIT_VIEW_NORMAL_BG}")
        if lexer:
            width = os.get_terminal_size().columns - offset - 1
            if width < 1:
                width = 1
            first_chunk, cont_chunks = _highlight_and_wrap_edit(line, lexer, width, strip_bg=False)
            first_chunk.stylize(normal_style)
            _pad = width - _display_width(str(first_chunk))
            if _pad > 0:
                first_chunk.append("\u00a0" * _pad, style=normal_style)
            first_chunk.append("\n")
            body.append(first_chunk)
            for chunk in cont_chunks:
                chunk.stylize(normal_style)
                cl = Text.assemble((" " * offset, normal_prefix_style), chunk)
                _pad = offset + width - _display_width(str(cl))
                if _pad > 0:
                    cl.append("\u00a0" * _pad, style=normal_style)
                body.append(cl)
                body.append("\n")
        else:
            first, cont_lines = fill_str_line(line, offset)
            body.append(first, style=f"bold white on {EDIT_VIEW_NORMAL_BG}")
            for cl in cont_lines:
                body.append(cl[:offset], style=f"bright_black on {EDIT_VIEW_NORMAL_BG}")
                body.append(cl[offset:] + "\n", style=f"bold white on {EDIT_VIEW_NORMAL_BG}")


def _render_diff_block(body: Text, lines: list[str], start_idx: int, budget: int,
                       mode: str, lexer, styles: dict[str, Style]):
    """render a block of remove/add lines with diff coloring and optional syntax highlighting."""
    if mode == "remove":
        content_style = styles['rmv_style']
        line_style = styles['rmv_line_style']
        content_bg = EDIT_VIEW_RMV_BG
        symbol_color = EDIT_VIEW_RMV_SYMBOL_COLOR
        line_bg = f"on {EDIT_VIEW_RMV_LINE_BG}"
    else:  # "add"
        content_style = styles['add_style']
        line_style = styles['add_line_style']
        content_bg = EDIT_VIEW_ADD_BG
        symbol_color = EDIT_VIEW_ADD_SYMBOL_COLOR
        line_bg = f"on {EDIT_VIEW_ADD_LINE_BG}"

    for idx, line in enumerate(lines):
        prefix1, prefix2, symbol = get_line_prefix(start_idx + idx, budget, mode=mode)
        offset = len(prefix1) + len(prefix2) + 3
        p1_len = len(prefix1)
        p2_len = len(prefix2) + 3
        body.append(prefix1, style=f"bright_black on {EDIT_VIEW_NORMAL_BG}")
        body.append(prefix2, style=f"bright_black {line_bg}")
        body.append(symbol, style=f"{symbol_color} {line_bg}")
        if lexer:
            width = os.get_terminal_size().columns - offset - 1
            if width < 1:
                width = 1
            first_chunk, cont_chunks = _highlight_and_wrap_edit(line, lexer, width, strip_bg=True)
            first_chunk.stylize(content_style)
            _pad = width - _display_width(str(first_chunk))
            if _pad > 0:
                first_chunk.append("\u00a0" * _pad, style=content_style)
            first_chunk.append("\n")
            body.append(first_chunk)
            margin_style = styles['margin_style']
            for chunk in cont_chunks:
                chunk.stylize(content_style)
                cl = Text.assemble(
                    (" " * p1_len, margin_style),
                    (" " * p2_len, line_style),
                    chunk,
                )
                _pad = offset + width - _display_width(str(cl))
                if _pad > 0:
                    cl.append("\u00a0" * _pad, style=content_style)
                body.append(cl)
                body.append("\n")
        else:
            first, cont_lines = fill_str_line(line, offset)
            body.append(first, style=f"bold white on {content_bg}")
            for cl in cont_lines:
                body.append(cl[:p1_len], style=f"bright_black on {EDIT_VIEW_NORMAL_BG}")
                body.append(cl[p1_len:p1_len + p2_len], style=f"bright_black {line_bg}")
                body.append(cl[p1_len + p2_len:] + "\n", style=f"bold white on {content_bg}")


def get_write_render(path: str, content: str) -> Text:
    """render file content preview for write_file permission.

    Syntax-highlighted (based on file extension), with line-number gutter,
    configurable truncation, highlight-then-split long-line wrapping,
    and visual padding above/below.
    """
    lexer = _get_lexer(path) if path else TextLexer()
    content_style = Style(bgcolor=WRITE_VIEW_CONTENT_BG)
    gutter_style = Style(color="bright_black", bgcolor=WRITE_VIEW_GUTTER_BG)

    truncated = False
    truncated_lines = 0
    if 0 < WRITE_VIEW_MAX_CHARS < len(content):
        content = content[:WRITE_VIEW_MAX_CHARS]
        truncated = True

    lines = content.split('\n')
    if 0 < WRITE_VIEW_MAX_LINES < len(lines):
        truncated_lines = len(lines) - WRITE_VIEW_MAX_LINES
        lines = lines[:WRITE_VIEW_MAX_LINES]
        truncated = True

    budget = math.floor(math.log10(max(len(lines), 1))) + 1
    gutter_width = EDIT_VIEW_LEFT_SPACE_MARGIN + budget + EDIT_VIEW_LINE_SPACE_MARGIN + 1
    max_width = os.get_terminal_size().columns - gutter_width - 1
    if max_width < 1:
        max_width = 1
    _pad_label = lambda txt: " " * (gutter_width - len(txt)) + txt
    gutter_nbsp = "\u00a0" * gutter_width

    body = Text()
    for i in range(WRITE_VIEW_PADDING_LINES):
        if i == 0:
            lbl = _pad_label("$write")
            body.append(lbl, style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
            first, _ = fill_str_line("", offset=len(lbl))
            body.append(first, style=content_style)
        else:
            first, _ = fill_str_line("", offset=gutter_width)
            body.append(gutter_nbsp, style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
            body.append(first, style=content_style)

    for idx, line in enumerate(lines):
        prefix1, prefix2, _ = get_line_prefix(idx + 1, budget)
        body.append(prefix1 + prefix2 + " ", style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
        first_chunk, cont_chunks = _highlight_and_wrap_edit(line, lexer, max_width, strip_bg=True)
        first_chunk.stylize(content_style)
        _pad = max_width - _display_width(str(first_chunk))
        if _pad > 0:
            first_chunk.append("\u00a0" * _pad, style=content_style)
        first_chunk.append("\n")
        body.append(first_chunk)
        for chunk in cont_chunks:
            chunk.stylize(content_style)
            cl = Text.assemble((" " * gutter_width, gutter_style), chunk)
            _pad = gutter_width + max_width - _display_width(str(cl))
            if _pad > 0:
                cl.append("\u00a0" * _pad, style=content_style)
            body.append(cl)
            body.append("\n")

    if truncated:
        info = "(%d lines not shown)" % truncated_lines if truncated_lines else "(output truncated)"
        prefix1, prefix2, _ = get_line_prefix(len(lines) + 1, budget)
        body.append(prefix1 + prefix2 + " ", style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
        info_first, info_cont = fill_str_line(info, offset=len(prefix1) + len(prefix2) + 1)
        body.append(info_first, style=Style(color="bright_black", bgcolor=WRITE_VIEW_CONTENT_BG))
        p = len(prefix1) + len(prefix2) + 1
        for cl in info_cont:
            body.append(cl[:p], style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
            body.append(cl[p:] + "\n", style=f"bright_black on {WRITE_VIEW_CONTENT_BG}")

    for _ in range(WRITE_VIEW_PADDING_LINES):
        first, _ = fill_str_line("", offset=gutter_width)
        body.append(gutter_nbsp, style=f"bright_black on {WRITE_VIEW_GUTTER_BG}")
        body.append(first, style=content_style)

    return body


def render_preview_single(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]],
                         match_mode: str = MATCH_MODE_EXACT, lexer = None):
    """render single-line file edit preview"""
    (start_line, end_line) = match_lines[0]
    old_lines = str_line[start_line - 1:end_line]
    old_str = "".join(old_lines)
    new_str = old_str.replace(old_string, new_string, 1)
    new_lines = new_str.splitlines()
    styles = _create_diff_styles()

    body = Text()
    _render_edit_header(body, path, len(new_lines), len(old_lines), match_mode)

    budget_lines = max(end_line, end_line + len(new_lines) - len(old_lines))
    if end_line != len(str_line):
        tail_lines = min(end_line + len(new_lines) - len(old_lines) + EDIT_VIEW_LINE_MARGIN_SINGLE,
                           len(str_line) + len(new_lines) - len(old_lines))
        budget_lines = max(budget_lines, tail_lines)
    budget = math.floor(math.log10(budget_lines)) + 1

    """before the modification region (normal)"""
    if start_line != 1:
        if start_line <= EDIT_VIEW_LINE_MARGIN_SINGLE:
            line_prefix1 = str_line[:start_line - 1]
            idx_prefix1 = 1
        else:
            line_prefix1 = str_line[start_line - EDIT_VIEW_LINE_MARGIN_SINGLE - 1:start_line - 1]
            idx_prefix1 = start_line - EDIT_VIEW_LINE_MARGIN_SINGLE
        _render_normal_block(body, line_prefix1, idx_prefix1, budget, lexer, styles)

    """in the modification region (remove)"""
    _render_diff_block(body, old_lines, start_line, budget, "remove", lexer, styles)

    """in the modification region (add)"""
    _render_diff_block(body, new_lines, start_line, budget, "add", lexer, styles)

    """after the modification region (normal)"""
    if end_line != len(str_line):
        if end_line >= len(str_line) - EDIT_VIEW_LINE_MARGIN_SINGLE + 1:
            line_prefix2 = str_line[end_line:]
        else:
            line_prefix2 = str_line[end_line:end_line + EDIT_VIEW_LINE_MARGIN_SINGLE]
        _render_normal_block(body, line_prefix2, end_line + 1 + len(new_lines) - len(old_lines), budget, lexer, styles)
    return body


def merge_intervals(match_lines: list[tuple[int, int]]):
    """merge overlap intervals with given matches list"""
    merged: list[tuple[int, int]] = []
    for ds, de in match_lines:
        if not merged:
            merged.append((ds, de))
        else:
            last_ds, last_de = merged[-1]
            if ds <= last_de + 1:
                merged[-1] = (last_ds, max(last_de, de))
            else:
                merged.append((ds, de))
    return merged


def render_preview_multi(path:str, old_string: str, new_string: str, str_line: list[str], match_lines: list[tuple[int, int]],
                         match_mode: str = MATCH_MODE_EXACT, lexer = None):
    """render multiple-line file edit preview"""
    merged_match_lines = merge_intervals(match_lines)
    styles = _create_diff_styles()

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
    budget_lines = max(all_end, all_end + total_added - total_removed)
    if all_end != len(str_line):
        tail_lines = min(all_end + total_added - total_removed + EDIT_VIEW_LINE_MARGIN_SINGLE,
                         len(str_line) + total_added - total_removed)
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
            _render_normal_block(body, line_prefix1, idx_prefix1, budget, lexer, styles)

        """in the modification region (remove)"""
        _render_diff_block(body, old_lines, start_line, budget, "remove", lexer, styles)

        """in the modification region (add)"""
        _render_diff_block(body, new_lines, start_line + added_lines - removed_lines, budget, "add", lexer, styles)

        """after the modification region (normal)"""
        this_tail = False
        next_head = False
        merged = False
        merged_lines = 0
        if block_idx < len(merged_match_lines) - 1:
            (nxt_start_line, nxt_end_line) = merged_match_lines[block_idx + 1]
            if nxt_start_line - end_line <= 1:
                pass
            elif nxt_start_line - end_line <= 2 * EDIT_VIEW_LINE_MARGIN_MULTI:
                merged = True
                merged_lines = nxt_start_line - end_line
            else:
                this_tail = True
                next_head = True
        else:
            this_tail = (end_line != len(str_line))

        if merged:
            _render_normal_block(body, str_line[end_line:end_line + merged_lines],
                                 end_line + 1 + added_lines - removed_lines, budget, lexer, styles)

        if this_tail:
            if end_line >= len(str_line) - EDIT_VIEW_LINE_MARGIN_MULTI + 1:
                line_prefix2 = str_line[end_line:]
            else:
                line_prefix2 = str_line[end_line:end_line + EDIT_VIEW_LINE_MARGIN_MULTI]
            _render_normal_block(body, line_prefix2, end_line + 1 + added_lines - removed_lines, budget, lexer, styles)
            if next_head:
                spacer = " " * (EDIT_VIEW_LEFT_SPACE_MARGIN + EDIT_VIEW_LINE_SPACE_MARGIN + budget) + "⋮"
                body.append(spacer + "\n", style="bright_black")

        if next_head:
            (nxt_start_line, nxt_end_line) = merged_match_lines[block_idx + 1]
            line_prefix1 = str_line[nxt_start_line - EDIT_VIEW_LINE_MARGIN_MULTI - 1:nxt_start_line - 1]
            _render_normal_block(body, line_prefix1, nxt_start_line - EDIT_VIEW_LINE_MARGIN_MULTI + added_lines - removed_lines,
                                 budget, lexer, styles)

        removed_lines += len(old_lines)
        added_lines += len(new_lines)

    head = Text()
    _render_edit_header(head, path, added_lines, removed_lines, match_mode)
    head.append(body)
    return head


def render_edit_permission(path:str, active_idx: int, user_cache: str, match_mode: str = MATCH_MODE_EXACT):
    """render file edit permission"""
    panels = []
    title = Text()
    title.append("Permission Request", style=f"bold {MAJOR_COLOR1}")
    if match_mode not in MATCH_MODE_EXACT_FAMILY:
        title.append(f"  [{MATCH_MODE_DESC[match_mode]}]", style=f"bold {EDIT_FUZZY_WARN_COLOR}")
    elif match_mode != MATCH_MODE_EXACT:
        title.append(f"  [{MATCH_MODE_DESC[match_mode]}]", style=f"{EDIT_SUBTLE_COLOR}")
    body = Text()
    body.append(f"TECoSim Agent want to request permission for ", style=f"white")
    body.append(f"{TOOL_NAME_EDIT_FILE}", style=f"bold {MAJOR_COLOR1}")
    body.append(f" to path: ", style=f"white")
    body.append(f"{path}\n", style=f"bold {MAJOR_COLOR1}")
    if match_mode not in MATCH_MODE_EXACT_FAMILY:
        body.append(f"  Match mode: {MATCH_MODE_DESC[match_mode]} — the file text differed slightly but was auto-corrected\n",
                    style=f"{EDIT_FUZZY_WARN_COLOR}")
    elif match_mode != MATCH_MODE_EXACT:
        body.append(f"  Match mode: {MATCH_MODE_DESC[match_mode]}\n", style=f"{EDIT_SUBTLE_COLOR}")
    body.append(f"\n")
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
                 multi_match: bool, match_mode: str, ctx: AgentContext, console: Console) -> tuple[bool, str | None]:
    """top realization of asking user for editing file TUI"""
    active_idx = 0  # default active option
    request_type = TOOL_NAME_EDIT_FILE
    user_cache = ""
    if ctx.args.dangerously_allow_all:
        return True, None
    if ctx.permissions[request_type]:
        return True, None
    if not multi_match:
        render_lexer = _get_lexer(path)
        console.print(render_preview_single(path, old_string, new_string, str_line, match_lines, match_mode, render_lexer))
    else:
        render_lexer = _get_lexer(path)
        console.print(render_preview_multi(path, old_string, new_string, str_line, match_lines, match_mode, render_lexer))
    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_edit_permission(path, active_idx, user_cache, match_mode),
                          console=console, auto_refresh=False, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                active_idx = (active_idx - 1) % 4
                                live.update(render_edit_permission(path, active_idx, user_cache, match_mode))
                                live.refresh()
                            elif key.key == Keys.Down:
                                active_idx = (active_idx + 1) % 4
                                live.update(render_edit_permission(path, active_idx, user_cache, match_mode))
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
