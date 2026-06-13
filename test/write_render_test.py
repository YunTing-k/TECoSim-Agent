# -*- coding: utf-8 -*-
"""
Unit tests for write_file content preview rendering.

Covers: get_write_render with syntax highlighting, line-number gutter,
        long-line wrap, configurable truncation, and visual padding.

Run:  python test/write_render_test.py
"""
import sys, os, unittest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from src.tool.file_io_support import get_write_render


class TestWriteRender(unittest.TestCase):
    """Tests for get_write_render -- file content preview with syntax highlighting."""

    def test_basic_render(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("test.py", "x = 1\ny = 2\n")
        output = str(body)
        self.assertIn("x = 1", output)
        self.assertIn("y = 2", output)
        self.assertIn("1", output)
        self.assertIn("2", output)

    def test_syntax_highlighting_applied(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("test.py", "def foo():\n    return 42\n")
        self.assertGreater(len(body.spans), 0)
        styles_used = set()
        for span in body.spans:
            if span.style is not None:
                styles_used.add(span.style)
        self.assertGreater(len(styles_used), 1)

    def test_line_number_gutter(self):
        from unittest.mock import patch
        import os as _os
        from rich.console import Console
        import io, re
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("test.py", "a = 1\nb = 2\nc = 3\n")
        f = io.StringIO()
        console = Console(file=f, force_terminal=True, width=120, height=40)
        console.print(body)
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', f.getvalue())
        self.assertIn('1', stripped)
        self.assertIn('2', stripped)
        self.assertIn('3', stripped)

    def test_long_line_wrap(self):
        from unittest.mock import patch
        import os as _os
        line = "x = 'this is a very long string that " + "should " * 10 + "wrap around'\n"
        with patch('os.get_terminal_size', return_value=_os.terminal_size((60, 40))):
            body = get_write_render("test.py", line)
        output = str(body)
        self.assertIn("wrap", output)
        self.assertIn("around", output)

    def test_truncation_by_lines(self):
        from unittest.mock import patch
        import os as _os
        lines = "\n".join(f"line{i}" for i in range(100))
        with patch('src.tool.file_io_support.WRITE_VIEW_MAX_LINES', 5):
            with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
                body = get_write_render("test.txt", lines)
        output = str(body)
        self.assertIn("line0", output)
        self.assertIn("line4", output)
        self.assertNotIn("line5", output)
        self.assertIn("lines not shown", output)

    def test_truncation_by_chars(self):
        from unittest.mock import patch
        import os as _os
        content = "x" * 5000
        with patch('src.tool.file_io_support.WRITE_VIEW_MAX_CHARS', 100):
            with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
                body = get_write_render("test.txt", content)
        output = str(body)
        self.assertIn("truncated", output.lower())

    def test_empty_content(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("empty.py", "")
        output = str(body)
        self.assertIn("$write", output)

    def test_no_path_works(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("", "hello world\n")
        self.assertIsNotNone(body)
        self.assertIn("hello world", str(body))

    def test_padding_lines_present(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("test.py", "x = 1\n")
        output = str(body)
        self.assertIn("$write", output)

    def test_cjk_content(self):
        from unittest.mock import patch
        import os as _os
        with patch('os.get_terminal_size', return_value=_os.terminal_size((120, 40))):
            body = get_write_render("test.py", 'x = "\u4e2d\u6587\u5b57\u7b26\u4e32"\n')
        output = str(body)
        self.assertIn("\u4e2d", output)
        self.assertIn("\u6587", output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
