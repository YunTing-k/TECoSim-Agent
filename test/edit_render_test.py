# -*- coding: utf-8 -*-
"""
Unit tests for edit preview rendering.

Covers: hunk separator (U+22EE), _highlight_and_wrap_edit token-style
        preservation, _render_normal_block / _render_diff_block with
        highlight-then-split wrapping and no-lexer fallback.

Run:  python test/edit_render_test.py
"""
import sys, os, unittest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from rich.text import Text
from rich.style import Style

from src.tool.file_io_support import (
    _highlight_and_wrap_edit, _render_normal_block, _render_diff_block,
    _create_diff_styles, _char_display_width, _sanitize_control,
    _display_width, _slice_by_width, fill_str_line,
)


class TestHunkSeparator(unittest.TestCase):
    """Test that the U+22EE separator appears between blocks."""

    def test_separator_rendered(self):
        from unittest.mock import patch
        from rich.console import Console
        import io, re, os
        from src.tool.file_io_support import render_preview_multi

        str_line = [
            'def foo():\n', '    return 1\n',
            'def bar():\n', '    return 2\n',
            'def baz():\n', '    return 3\n',
            'def qux():\n', '    return 4\n',
            'def xyz():\n', '    return 5\n',
            'def abc():\n', '    return 6\n',
        ]
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            body = render_preview_multi('t.py', 'return', 'yield', str_line, [(2, 2), (7, 7)])
        f = io.StringIO()
        console = Console(file=f, force_terminal=True, width=120, height=40)
        console.print(body)
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', f.getvalue())
        self.assertIn('\u22ee', stripped)


class TestHighlightAndWrapEdit(unittest.TestCase):
    """Tests for _highlight_and_wrap_edit -- preserve token styles across wrap boundaries."""

    def setUp(self):
        from pygments.lexers import PythonLexer
        self.lexer = PythonLexer()

    def test_short_line_no_wrap(self):
        line = "x = 1\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80, strip_bg=True)
        self.assertEqual(cont, [])
        self.assertGreater(len(first.spans), 0)

    def test_long_line_wrap(self):
        line = "x = 'hello world this is a very long string that should wrap around' + y + z\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=40, strip_bg=True)
        self.assertTrue(len(cont) > 0)
        self.assertGreater(len(first.spans), 0)
        for chunk in cont:
            self.assertGreater(len(chunk.spans), 0)

    def test_token_styles_on_continuation(self):
        line = "result = \"prefix_\" + str(value) + \"_suffix\"  # inline comment that makes this line very very long\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=30, strip_bg=True)
        self.assertTrue(len(cont) > 0)
        for chunk in cont:
            chunk_styles = set()
            for span in chunk.spans:
                if span.style is not None:
                    chunk_styles.add(span.style)
            self.assertGreater(len(chunk_styles), 0)

    def test_empty_line(self):
        first, cont = _highlight_and_wrap_edit('\n', self.lexer, max_width=80)
        self.assertEqual(str(first), '')
        self.assertEqual(cont, [])

    def test_strip_bg_respected(self):
        line = "pass\n"
        first_false, _ = _highlight_and_wrap_edit(line, self.lexer, max_width=80, strip_bg=False)
        first_true, _ = _highlight_and_wrap_edit(line, self.lexer, max_width=80, strip_bg=True)
        has_bg = any(isinstance(s.style, Style) and s.style.bgcolor is not None
                     for s in first_false.spans if s.style is not None)
        self.assertFalse(has_bg)

    def test_crlf_handled(self):
        line = "x = 1\r\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertEqual(str(first), 'x = 1')
        self.assertEqual(cont, [])

    def test_no_newline_preserved(self):
        line = "x = 1"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertEqual(str(first), 'x = 1')
        self.assertEqual(cont, [])

    def test_cjk_char_width(self):
        line = "\u4e2d\u6587\u5b57\u7b26\u4e32 plus_english_text_to_make_this_extremely_long\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=20, strip_bg=True)
        self.assertTrue(len(cont) > 0)

    def test_full_text_preserved(self):
        line = "abcdefghijklmnopqrstuvwxyz0123456789\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=10, strip_bg=True)
        combined = str(first) + ''.join(str(c) for c in cont)
        self.assertEqual(combined, 'abcdefghijklmnopqrstuvwxyz0123456789')

    def test_style_boundary_on_split(self):
        line = "a = 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=15, strip_bg=True)
        self.assertTrue(len(cont) > 0)
        for chunk in cont:
            self.assertIsInstance(chunk, Text)
            self.assertTrue(len(str(chunk)) > 0)

    def test_tab_expanded(self):
        line = "col1\tcol2\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertNotIn('\t', str(first))

    def test_carriage_return_replaced(self):
        line = "line1\rline2\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertNotIn('\r', str(first))
        self.assertIn('\u240d', str(first))

    def test_backspace_replaced(self):
        line = "abc\bdef\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertNotIn('\b', str(first))
        self.assertIn('\u2408', str(first))

    def test_combining_mark_preserved(self):
        line = "e\u0301\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertIn('\u0301', str(first))

    def test_zwsp_preserved(self):
        line = "a\u200bb\n"
        first, cont = _highlight_and_wrap_edit(line, self.lexer, max_width=80)
        self.assertIn('\u200b', str(first))


class TestRenderBlockHighlightWrapping(unittest.TestCase):
    """Integration tests for _render_normal_block / _render_diff_block using highlight-then-split."""

    def setUp(self):
        from pygments.lexers import PythonLexer
        self.lexer = PythonLexer()

    def test_render_normal_block_with_wrap(self):
        from unittest.mock import patch
        import os as _os
        styles = _create_diff_styles()
        body = Text()
        lines = ["x = 'this string is long enough to exceed 40 columns easily'\n"]
        with patch('os.get_terminal_size', return_value=_os.terminal_size((60, 40))):
            _render_normal_block(body, lines, 1, 1, self.lexer, styles)
        self.assertTrue(len(str(body)) > 0)
        output = str(body)
        self.assertIn('\n', output)

    def test_render_diff_block_with_wrap(self):
        from unittest.mock import patch
        import os as _os
        styles = _create_diff_styles()
        body = Text()
        lines = ["x = 'this string is long enough to exceed 40 columns easily'\n"]
        with patch('os.get_terminal_size', return_value=_os.terminal_size((60, 40))):
            _render_diff_block(body, lines, 1, 1, "remove", self.lexer, styles)
        self.assertTrue(len(str(body)) > 0)
        output = str(body)
        self.assertIn('\n', output)

    def test_render_normal_block_no_lexer_fallback(self):
        from unittest.mock import patch
        import os as _os
        styles = _create_diff_styles()
        body = Text()
        lines = ["plain text that is quite long and should wrap nicely here\n"]
        with patch('os.get_terminal_size', return_value=_os.terminal_size((60, 40))):
            _render_normal_block(body, lines, 1, 1, None, styles)
        self.assertTrue(len(str(body)) > 0)
        self.assertIn('\n', str(body))

    def test_render_diff_block_no_lexer_fallback(self):
        from unittest.mock import patch
        import os as _os
        styles = _create_diff_styles()
        body = Text()
        lines = ["plain text that is quite long and should wrap nicely here\n"]
        with patch('os.get_terminal_size', return_value=_os.terminal_size((60, 40))):
            _render_diff_block(body, lines, 1, 1, "add", None, styles)
        self.assertTrue(len(str(body)) > 0)
        self.assertIn('\n', str(body))


class TestCharDisplayWidth(unittest.TestCase):
    """Tests for _char_display_width — single-character terminal display width."""

    def test_normal_ascii(self):
        self.assertEqual(_char_display_width('a'), 1)
        self.assertEqual(_char_display_width('Z'), 1)
        self.assertEqual(_char_display_width(' '), 1)

    def test_cjk_fullwidth(self):
        self.assertEqual(_char_display_width('\u4e2d'), 2)
        self.assertEqual(_char_display_width('\u6587'), 2)

    def test_combining_mark_zero(self):
        self.assertEqual(_char_display_width('\u0301'), 0)

    def test_zero_width_space(self):
        self.assertEqual(_char_display_width('\u200b'), 0)
        self.assertEqual(_char_display_width('\u200c'), 0)
        self.assertEqual(_char_display_width('\u200d'), 0)

    def test_control_chars_zero(self):
        self.assertEqual(_char_display_width('\b'), 0)
        self.assertEqual(_char_display_width('\r'), 0)
        self.assertEqual(_char_display_width('\0'), 0)


class TestSanitizeControl(unittest.TestCase):
    """Tests for _sanitize_control — replace terminal-affecting control chars."""

    def test_carriage_return(self):
        self.assertEqual(_sanitize_control('line1\rline2'), 'line1\u240dline2')

    def test_backspace(self):
        self.assertEqual(_sanitize_control('abc\bdef'), 'abc\u2408def')

    def test_null(self):
        self.assertEqual(_sanitize_control('a\0b'), 'a\u2400b')

    def test_no_control_no_change(self):
        self.assertEqual(_sanitize_control('hello world'), 'hello world')

    def test_multiple_controls(self):
        self.assertEqual(_sanitize_control('\r\b\0'), '\u240d\u2408\u2400')


class TestDisplayWidth(unittest.TestCase):
    """Tests for _display_width — zero-width character handling."""

    def test_zero_width_chars_inside_text(self):
        self.assertEqual(_display_width('e\u0301'), 1)
        self.assertEqual(_display_width('a\u200bb'), 2)

    def test_standalone_zero_width(self):
        self.assertEqual(_display_width('\u200b'), 0)
        self.assertEqual(_display_width('\u0301'), 0)

    def test_cjk_still_works(self):
        self.assertEqual(_display_width('\u4e2d\u6587'), 4)

    def test_mixed_text(self):
        self.assertEqual(_display_width('a\u4e2d\u0301b'), 4)


class TestFillStrLine(unittest.TestCase):
    """Tests for fill_str_line — tab expansion, control sanitization, zero-width."""

    def test_tab_expanded(self):
        from unittest.mock import patch
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            first, cont = fill_str_line("col1\tcol2\n", offset=10)
        self.assertNotIn('\t', first)

    def test_carriage_return_replaced(self):
        from unittest.mock import patch
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            first, cont = fill_str_line("line1\rline2\n", offset=10)
        self.assertNotIn('\r', first)
        self.assertIn('\u240d', first)

    def test_backspace_replaced(self):
        from unittest.mock import patch
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            first, cont = fill_str_line("abc\bdef\n", offset=10)
        self.assertNotIn('\b', first)
        self.assertIn('\u2408', first)

    def test_combining_mark_preserved(self):
        from unittest.mock import patch
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            first, cont = fill_str_line("e\u0301\n", offset=10)
        self.assertIn('e\u0301', first)

    def test_zwsp_preserved(self):
        from unittest.mock import patch
        with patch('os.get_terminal_size', return_value=os.terminal_size((120, 40))):
            first, cont = fill_str_line("a\u200bb\n", offset=10)
        self.assertIn('a\u200bb', first)


if __name__ == '__main__':
    unittest.main(verbosity=2)
