# -*- coding: utf-8 -*-
"""
Integration tests for read_file and read_log_impl — verify content correctness
across all methods (from_top/from_bottom/offset/all), truncation flags,
and format_file_for_llm edge cases.

Creates temp test files, mocks permission/progress, calls read_file directly.

Run:  python test/read_integration_test.py
"""
import sys, os, unittest, io, re, tempfile, shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.CRITICAL)

from unittest.mock import patch, MagicMock
from rich.console import Console
from src.context.agent_context import AgentContext
from src.tool.tool_def import read_file


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _extract_content(file_content: str) -> list[tuple[int, str]]:
    """parse <file> output, return [(line_no, content), ...]"""
    lines = file_content.split('\n')
    result = []
    in_content = False
    for line in lines:
        if '<content>' in line or line.startswith('<file '):
            in_content = True
            continue
        if '</file>' in line or '<system-reminder>' in line:
            break
        if in_content and '│' in line:
            parts = line.split('│', 1)
            if parts[0].strip().isdigit():
                result.append((int(parts[0].strip()), parts[1]))
    return result


def _make_ctx(byte_limit_kb: int = 500) -> AgentContext:
    ctx = AgentContext()
    ctx.agent_configs = {
        "READ_FILE_MB_LIMIT": 10,
        "READ_FILE_LLM_KB_LIMIT": byte_limit_kb,
    }
    return ctx


def _run_read_file(arguments: dict, ctx: AgentContext, term_width: int = 120):
    """run read_file with mocked permissions, return (result_dict, stripped_output)."""
    import os as _os
    f = io.StringIO()
    progress = MagicMock()
    progress.console = Console(file=f, force_terminal=True, width=term_width, height=40)
    progress._outer_live = None

    with patch('os.get_terminal_size', return_value=_os.terminal_size((term_width, 40))):
        with patch('src.tool.tool_def.pause_for_permission'):
            with patch('src.tool.tool_def.resume_from_permission'):
                with patch('src.tool.tool_def.ask_permission_tui', return_value=(True, None)):
                    result = read_file(arguments, ctx, progress)

    return result, _strip_ansi(f.getvalue())


class TestReadFileContentCorrectness(unittest.TestCase):
    """Verify that from_bottom/offset return CORRECT content (not just correct line numbers)."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='tesi_read_')
        # Create: 30 lines, each says "Content of line N"
        cls.file_30 = os.path.join(cls.tmpdir, 'test_30lines.txt')
        with open(cls.file_30, 'w', encoding='utf-8') as f:
            for i in range(1, 31):
                f.write(f"Content of line {i}\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_from_top_content(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_30, "method": "from_top", "line_num": 5}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        content = result["file_content"]
        parsed = _extract_content(content)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0], (1, "Content of line 1"))
        self.assertEqual(parsed[4], (5, "Content of line 5"))
        self.assertIn('truncated="true"', content)

    def test_from_bottom_content(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_30, "method": "from_bottom", "line_num": 5}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        content = result["file_content"]
        parsed = _extract_content(content)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0], (26, "Content of line 26"))
        self.assertEqual(parsed[4], (30, "Content of line 30"))
        self.assertIn('truncated="true"', content)

    def test_offset_content(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_30, "method": "offset", "line_num": 5, "offset": 12}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        content = result["file_content"]
        parsed = _extract_content(content)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0], (12, "Content of line 12"))
        self.assertEqual(parsed[4], (16, "Content of line 16"))

    def test_all_content(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_30, "method": "all"}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        content = result["file_content"]
        parsed = _extract_content(content)
        self.assertEqual(len(parsed), 30)
        self.assertEqual(parsed[0], (1, "Content of line 1"))
        self.assertEqual(parsed[29], (30, "Content of line 30"))
        self.assertIn('truncated="false"', content)
        self.assertIn("(End of file - total 30 lines)", content)

    def test_from_top_exceeds_file(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_30, "method": "from_top", "line_num": 100}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        parsed = _extract_content(result["file_content"])
        self.assertEqual(len(parsed), 30)
        self.assertIn('truncated="false"', result["file_content"])
        self.assertIn("(End of file - total 30 lines)", result["file_content"])


class TestReadFileTruncationFlags(unittest.TestCase):
    """Verify line-truncated returns SUCCESS, byte-truncated returns TRUNCATED."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='tesi_read_')
        cls.file_20 = os.path.join(cls.tmpdir, 'test_trunc.txt')
        with open(cls.file_20, 'w', encoding='utf-8') as f:
            for i in range(1, 21):
                f.write(f"Line {i:05d}\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_from_top_line_truncated_is_success(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_20, "method": "from_top", "line_num": 5}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn('truncated="true"', result["file_content"])
        # Should NOT have byte-limit warning
        self.assertNotIn("KB and truncated", result.get("info", ""))

    def test_byte_truncated_is_truncated_status(self):
        ctx = _make_ctx(byte_limit_kb=1)
        result, _ = _run_read_file({"path": self.file_20, "method": "all"}, ctx)
        if result["status"] == "truncated":
            self.assertIn("KB and truncated", result.get("info", ""))
            self.assertIn('truncated="true"', result["file_content"])

    def test_all_small_file_no_truncation(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_20, "method": "all"}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn('truncated="false"', result["file_content"])

    def test_from_bottom_line_truncated_is_success(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_20, "method": "from_bottom", "line_num": 5}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn('truncated="true"', result["file_content"])

    def test_from_bottom_full_file_no_truncation(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.file_20, "method": "from_bottom", "line_num": 20}, ctx)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn('truncated="false"', result["file_content"])


class TestFormatFileForLlmEdgeCases(unittest.TestCase):
    """Additional edge cases for format_file_for_llm after offset fix."""

    def test_from_start_correct(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = [f"L{i}\n" for i in range(30)]
        result = format_file_for_llm(lines, "/t.txt", 5, 3, 30, True)
        self.assertIn("5│L4\n", result)
        self.assertIn("7│L6\n", result)
        self.assertNotIn("L0", result)
        self.assertNotIn("L7", result)

    def test_from_bottom_slice(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = [f"L{i}\n" for i in range(20)]
        result = format_file_for_llm(lines, "/t.txt", 17, 4, 20, True)
        self.assertIn("17│L16\n", result)
        self.assertIn("20│L19\n", result)
        self.assertNotIn("L15", result)

    def test_shown_count_zero(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = ["x\n"]
        result = format_file_for_llm(lines, "/t.txt", 1, 0, 1, False)
        self.assertIn('lines="0-0"', result)

    def test_total_line_count_in_footer(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = [f"L{i}\n" for i in range(3)]
        result = format_file_for_llm(lines, "/t.txt", 1, 3, 3, False)
        self.assertIn("(End of file - total 3 lines)", result)

    def test_remaining_lines_calc(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = [f"L{i}\n" for i in range(100)]
        result = format_file_for_llm(lines, "/t.txt", 50, 10, 100, True)
        self.assertIn("(41 lines not shown, use offset=60 to continue)", result)


class TestCJKAndEncoding(unittest.TestCase):
    """Tests for CJK content and encoding correctness."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='tesi_read_cjk_')
        cls.cjk_file = os.path.join(cls.tmpdir, 'cjk_test.txt')
        with open(cls.cjk_file, 'w', encoding='utf-8') as f:
            f.write("English line 1\n")
            f.write("中文第二行\n")
            f.write("\u4e2d\u6587\u7b2c\u4e09\u884c\n")
            f.write("Mixed 混合 line\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_cjk_content_preserved(self):
        ctx = _make_ctx()
        result, _ = _run_read_file({"path": self.cjk_file, "method": "all"}, ctx)
        content = result["file_content"]
        self.assertIn("English line 1", content)
        self.assertIn("中文第二行", content)
        self.assertIn("混合", content)

    def test_pipe_in_content_not_confused(self):
        """file content containing '│' should not break the parser."""
        from src.utility.basic_utils import format_file_for_llm
        lines = ["x = \"a│b\"\n"]
        result = format_file_for_llm(lines, "/t.txt", 1, 1, 1, False)
        self.assertIn("a│b", result)

    def test_colon_in_content_ok(self):
        from src.utility.basic_utils import format_file_for_llm
        lines = ['{"key": "value"}\n']
        result = format_file_for_llm(lines, "/t.txt", 1, 1, 1, False)
        self.assertIn('"value"', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
