"""
Edit preview visual debug tool.
Usage: python test/edit_preview_debug.py <path> <old_string> <new_string> [--no-lexer]

Renders an edit_file preview using the same code path as the agent,
dumps the plain text line-by-line, writes ANSI output to debug_ansi.txt,
and checks for consecutive blank lines / style resets.
"""
import os, sys, io, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TERMINAL_WIDTH = int(os.environ.get('COLUMNS', 90))

import argparse
p = argparse.ArgumentParser()
p.add_argument('path')
p.add_argument('old')
p.add_argument('new')
p.add_argument('--no-lexer', action='store_true')
args = p.parse_args()

from unittest.mock import patch
with patch('os.get_terminal_size', return_value=os.terminal_size((TERMINAL_WIDTH, 40))):
    from src.tool.file_io_support import (
        render_preview_single, render_preview_multi, _get_lexer, fill_str_line
    )
    from src.constants import *

    with open(args.path, 'r', encoding='utf-8') as f:
        raw = f.read()
    str_line = raw.splitlines(keepends=True)

    lexer = None if args.no_lexer else _get_lexer(args.path)

    from src.tool.file_io_support import match_line_ranges
    match_lines = match_line_ranges(raw, args.old, match_all=True)
    if not match_lines:
        print(f"ERROR: old_string not found in file")
        sys.exit(1)

    multi = len(match_lines) > 1
    body = render_preview_multi(args.path, args.old, args.new, str_line, match_lines, lexer=lexer) if multi \
      else render_preview_single(args.path, args.old, args.new, str_line, match_lines, lexer=lexer)

    # --- Dump plain text ---
    plain = body.plain
    plain_lines = plain.split('\n')
    print(f"=== PLAIN TEXT (terminal_w={TERMINAL_WIDTH}, lines={len(plain_lines)}, multi={multi}) ===")
    for i, l in enumerate(plain_lines):
        # Truncate for display, show repr of interesting parts
        r = repr(l)
        if len(r) > 130:
            r = r[:65] + "..." + r[-62:]
        print(f"  [{i:03d}] {r}")

    # Check consecutive blanks
    blanks = []
    for i in range(len(plain_lines) - 1):
        if plain_lines[i].strip() == '' and plain_lines[i+1].strip() == '':
            blanks.append(i)
    print(f"\n--- Blank line check: {len(blanks)} consecutive pairs ---")
    for b in blanks:
        print(f"  blank between line [{b:03d}] and [{b+1:03d}]")

    # --- Write ANSI ---
    from rich.console import Console
    buf = io.StringIO()
    c = Console(file=buf, width=TERMINAL_WIDTH, force_terminal=True, color_system='truecolor')
    c.print(body)
    ansi = buf.getvalue()

    out_path = os.path.join(os.path.dirname(__file__), 'debug_ansi.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(ansi)
    print(f"\n--- ANSI output written to: {out_path} ({len(ansi)} bytes) ---")

    # Count \x1b[0m resets near \n
    resets_before_nl = len(re.findall(r'\x1b\[0m\n', ansi))
    resets_after_nl = len(re.findall(r'\n\x1b\[0m', ansi))
    print(f"Style resets (\\x1b[0m) before \\n: {resets_before_nl}")
    print(f"Style resets (\\x1b[0m) after  \\n: {resets_after_nl}")

    # Check for double \n in ANSI (blank lines)
    double_nl = len(re.findall(r'\n\s*\n', ansi))
    print(f"Consecutive \\n (possible blank lines): {double_nl}")

    # Check _fill character presence
    fill_count = plain.count('\u2588')
    print(f"Fill chars (█ count in plain): {fill_count}")
