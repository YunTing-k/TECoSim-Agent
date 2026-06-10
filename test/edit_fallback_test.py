# -*- coding: utf-8 -*-
"""
Unit tests for the edit_file fallback matching chain.

Covers: _unescape_unicode, _unescape_literals, _strip_common_indent,
        find_actual_string, match_line_trimmed, match_flexible_indent,
        match_escape_literal, match_trimmed_boundary,
        get_enhanced_debug_info (with line cap).

Run:  python test/edit_fallback_test.py
"""
import sys, os, unittest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from tool.file_io_support import (
    match_line_trimmed, match_flexible_indent,
    match_escape_literal, match_trimmed_boundary, match_unicode_escape,
    find_actual_string, match_line_ranges,
    get_match_debug_info, get_enhanced_debug_info,
    _unescape_unicode, _unescape_literals, _strip_common_indent,
    _normalize_quotes,
)


class TestUnescapeUnicode(unittest.TestCase):
    def test_basic_4digit(self):
        self.assertEqual(_unescape_unicode(r'\u201c'), '\u201c')

    def test_basic_8digit(self):
        self.assertEqual(_unescape_unicode(r'\U0001F600'), '\U0001F600')

    def test_double_escaped(self):
        self.assertEqual(_unescape_unicode(r'\\u201c'), '\u201c')

    def test_mixed_text(self):
        result = _unescape_unicode(r'TECoSim\u2014Agent\u2122')
        self.assertIn('\u2014', result)
        self.assertIn('\u2122', result)

    def test_no_escape(self):
        self.assertEqual(_unescape_unicode('hello'), 'hello')

    def test_incomplete_escape(self):
        self.assertEqual(_unescape_unicode(r'\u12'), r'\u12')

    def test_empty(self):
        self.assertEqual(_unescape_unicode(''), '')


class TestUnescapeLiterals(unittest.TestCase):
    def test_newline(self):
        self.assertEqual(_unescape_literals(r'line1\nline2'), 'line1\nline2')

    def test_tab(self):
        self.assertEqual(_unescape_literals(r'col1\tcol2'), 'col1\tcol2')

    def test_backslash(self):
        self.assertEqual(_unescape_literals(r'C:\\path'), 'C:\\path')

    def test_single_quote(self):
        self.assertEqual(_unescape_literals(r"\'hello\'"), "'hello'")

    def test_double_quote(self):
        self.assertEqual(_unescape_literals(r'\"hello\"'), '"hello"')

    def test_carriage_return(self):
        self.assertEqual(_unescape_literals(r'line1\r\nline2'), 'line1\r\nline2')

    def test_no_escape(self):
        self.assertEqual(_unescape_literals('plain text'), 'plain text')

    def test_single_backslash(self):
        self.assertEqual(_unescape_literals(r'\x'), r'\x')

    def test_multiple_escapes(self):
        result = _unescape_literals(r'a\nb\tc\\d')
        self.assertEqual(result, 'a\nb\tc\\d')


class TestStripCommonIndent(unittest.TestCase):
    def test_uniform_indent(self):
        self.assertEqual(_strip_common_indent('    a\n    b'), 'a\nb')

    def test_no_indent(self):
        self.assertEqual(_strip_common_indent('a\nb'), 'a\nb')

    def test_empty_lines_skipped(self):
        self.assertEqual(_strip_common_indent('    a\n\n    b'), 'a\n\nb')

    def test_single_line(self):
        self.assertEqual(_strip_common_indent('    hello'), 'hello')

    def test_mixed_indent(self):
        text = '        a\n    b\n        c'
        result = _strip_common_indent(text)
        self.assertEqual(result, '    a\nb\n    c')  # min is 4 spaces

    def test_blank_only(self):
        self.assertEqual(_strip_common_indent('  \n  '), '  \n  ')


class TestFindActualString(unittest.TestCase):
    def test_exact(self):
        result = find_actual_string('hello world', 'hello')
        self.assertEqual(result, 'hello')

    def test_quote_norm_single(self):
        content = '\u2018hello\u2019'
        result = find_actual_string(content, "'hello'")
        self.assertEqual(result, content)

    def test_quote_norm_double(self):
        content = '\u201cworld\u201d'
        result = find_actual_string(content, '"world"')
        self.assertEqual(result, content)

    def test_not_found(self):
        result = find_actual_string('abcdef', 'xyz')
        self.assertIsNone(result)


class TestMatchUnicodeEscape(unittest.TestCase):
    def test_basic(self):
        raw = 'TECoSim\u2014Agent\n'
        llm = r'TECoSim\u2014Agent'
        lines, actual = match_unicode_escape(raw, llm)
        self.assertEqual(lines, [(1, 1)])
        self.assertEqual(actual, 'TECoSim\u2014Agent')

    def test_double_escaped(self):
        raw = '\u201cSim\u201d\n'
        llm = r'\\u201cSim\\u201d'
        lines, actual = match_unicode_escape(raw, llm)
        self.assertEqual(lines, [(1, 1)])
        self.assertEqual(actual, '\u201cSim\u201d')

    def test_superscript(self):
        raw = '400 mJ/cm\u00b2.\n'
        llm = r'400 mJ/cm\u00b2.'
        lines, actual = match_unicode_escape(raw, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_no_escape_needed(self):
        raw = 'plain\n'
        llm = 'plain'
        lines, _ = match_unicode_escape(raw, llm)
        self.assertEqual(lines, [])

    def test_no_match(self):
        raw = 'hello\n'
        llm = r'\u0041'  # 'A' not in raw
        lines, _ = match_unicode_escape(raw, llm)
        self.assertEqual(lines, [])


class TestMatchLineTrimmed(unittest.TestCase):
    def setUp(self):
        self.raw = ['def foo():  \n', '    x = 1  \n', '    return x\n']

    def test_exact(self):
        llm = 'def foo():  \n    x = 1  \n    return x'
        lines, actual = match_line_trimmed(self.raw, llm)
        self.assertEqual(lines, [(1, 3)])
        self.assertIn('  ', actual)

    def test_trailing_ws_stripped(self):
        llm = 'def foo():\n    x = 1\n    return x'
        lines, actual = match_line_trimmed(self.raw, llm)
        self.assertEqual(lines, [(1, 3)])

    def test_no_match(self):
        llm = 'def bar():\n    y = 2\n    return y'
        lines, actual = match_line_trimmed(self.raw, llm)
        self.assertEqual(lines, [])

    def test_crlf_preserved(self):
        raw_crlf = ['def foo():\r\n', '    x = 1  \r\n', '    return x\r\n']
        llm = 'def foo():\n    x = 1\n    return x'
        lines, actual = match_line_trimmed(raw_crlf, llm)
        self.assertEqual(lines, [(1, 3)])
        self.assertIn('\r\n', actual)

    def test_not_found_at_file_start(self):
        raw = ['a\n', 'b\n']
        llm = 'x\ny'
        lines, _ = match_line_trimmed(raw, llm)
        self.assertEqual(lines, [])

    def test_too_short_content(self):
        llm = 'a\nb\nc'
        lines, _ = match_line_trimmed(['a\n'], llm)
        self.assertEqual(lines, [])


class TestMatchFlexibleIndent(unittest.TestCase):
    def test_less_indent(self):
        raw = ['        def foo():\n', '            x = 1\n']
        llm = '    def foo():\n        x = 1'
        lines, actual = match_flexible_indent(raw, llm)
        self.assertEqual(lines, [(1, 2)])
        self.assertIn('        def', actual)  # original indent preserved

    def test_more_indent(self):
        raw = ['    def foo():\n', '        x = 1\n']
        llm = '        def foo():\n            x = 1'
        lines, actual = match_flexible_indent(raw, llm)
        self.assertEqual(lines, [(1, 2)])

    def test_combined_trailing_ws(self):
        raw = ['        a = 1  \n', '        b = 2  \n']
        llm = '    a = 1\n    b = 2'
        lines, actual = match_flexible_indent(raw, llm)
        self.assertEqual(lines, [(1, 2)])

    def test_no_match(self):
        raw = ['    x\n', '    y\n']
        llm = 'z\nw'
        lines, _ = match_flexible_indent(raw, llm)
        self.assertEqual(lines, [])


class TestMatchEscapeLiteral(unittest.TestCase):
    def test_newline_escape(self):
        raw = 'electron_mobility: float = 80.0\nhole_mobility: float = 20.0\n'
        llm = r'electron_mobility: float = 80.0\nhole_mobility: float = 20.0'
        lines, actual = match_escape_literal(raw, llm)
        self.assertEqual(lines, [(1, 2)])

    def test_tab_escape(self):
        raw = 'col1\tcol2\n'
        llm = r'col1\tcol2'
        lines, _ = match_escape_literal(raw, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_double_backslash(self):
        raw = 'C:\\Users\\admin\n'
        llm = r'C:\\Users\\admin'
        lines, _ = match_escape_literal(raw, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_no_escape_needed(self):
        raw = 'plain text\n'
        llm = 'plain text'
        lines, _ = match_escape_literal(raw, llm)
        self.assertEqual(lines, [])  # no change, exact match would handle

    def test_no_match(self):
        raw = 'hello\nworld\n'
        llm = r'foo\nbar'
        lines, _ = match_escape_literal(raw, llm)
        self.assertEqual(lines, [])


class TestMatchTrimmedBoundary(unittest.TestCase):
    def test_leading_whitespace(self):
        raw = 'hello world'
        llm = '\n  hello world'
        lines, actual = match_trimmed_boundary(raw, llm)
        self.assertEqual(lines, [(1, 1)])
        self.assertEqual(actual, 'hello world')

    def test_trailing_whitespace(self):
        raw = 'hello world'
        llm = 'hello world  \n\n'
        lines, actual = match_trimmed_boundary(raw, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_both_sides(self):
        raw = 'hello world\n'
        llm = ' \n hello world \n '
        lines, actual = match_trimmed_boundary(raw, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_whitespace_only(self):
        raw = 'content'
        llm = '  \n \n  '
        lines, _ = match_trimmed_boundary(raw, llm)
        self.assertEqual(lines, [])

    def test_no_trim_needed(self):
        raw = 'hello'
        llm = 'hello'
        lines, _ = match_trimmed_boundary(raw, llm)
        self.assertEqual(lines, [])


class TestMatchLineRanges(unittest.TestCase):
    def test_single(self):
        r = match_line_ranges('a\nb\nc\n', 'b\n', True)
        self.assertEqual(r, [(2, 2)])

    def test_multiple(self):
        r = match_line_ranges('a\na\na\n', 'a\n', True)
        self.assertEqual(r, [(1, 1), (2, 2), (3, 3)])

    def test_multi_line_target(self):
        r = match_line_ranges('a\nb\nc\na\nb\n', 'a\nb', True)
        self.assertEqual(r, [(1, 2), (4, 5)])


class TestDebugInfo(unittest.TestCase):
    def test_basic(self):
        info = get_match_debug_info('hello world', 'xyz')
        self.assertIn('target(repr)=', info)
        self.assertIn('content_len=', info)

    def test_enhanced_basic(self):
        raw_line = ['line1\n', 'line2\n', 'line3\n']
        info = get_enhanced_debug_info('line1\nline2\nline3\n', raw_line, 'line1\nxxx\nline3')
        self.assertIn('target(repr)=', info)
        self.assertIn('tln_1=found', info)
        self.assertIn('NOT_FOUND', info)

    def test_enhanced_line_cap(self):
        lines = ['line%d\n' % i for i in range(1, 51)]
        raw_str = ''.join(lines)
        target = '\n'.join('line%d' % i for i in range(1, 51))
        info = get_enhanced_debug_info(raw_str, lines, target)
        self.assertIn('more_lines_omitted', info)  # truncation message present


class TestNormalizeQuotes(unittest.TestCase):
    def test_single_curly(self):
        self.assertEqual(_normalize_quotes('\u2018a\u2019'), "'a'")

    def test_double_curly(self):
        self.assertEqual(_normalize_quotes('\u201cx\u201d'), '"x"')

    def test_straight_unchanged(self):
        self.assertEqual(_normalize_quotes("'hello'"), "'hello'")


class TestIntegration(unittest.TestCase):
    """End-to-end fallback chain simulation with realistic data."""

    REALISTIC_CONTENT = (
        '\u201cSimulation Result\u201d  \n'
        '    electron_mobility: float = 80.0  \n'
        '    hole_mobility: float = 20.0  \n'
        '        # This comment is over-indented\n'
    )

    def setUp(self):
        self.raw = [
            '\u201cSimulation Result\u201d  \n',
            '    electron_mobility: float = 80.0  \n',
            '    hole_mobility: float = 20.0  \n',
            '        # This comment is over-indented\n',
        ]
        self.raw_str = ''.join(self.raw)

    def test_full_chain_stage1_exact(self):
        llm = '\u201cSimulation Result\u201d'
        found = find_actual_string(self.raw_str, llm)
        # exact match returns the search string itself (already identical to file content)
        self.assertEqual(found, llm)

    def test_full_chain_stage2_quote_norm(self):
        llm = '"Simulation Result"'
        found = find_actual_string(self.raw_str, llm)
        self.assertIsNotNone(found)

    def test_full_chain_stage2b_unicode_escape(self):
        llm = r'\\u201cSimulation Result\\u201d'
        lines, _ = match_unicode_escape(self.raw_str, llm)
        self.assertEqual(lines, [(1, 1)])

    def test_full_chain_stage3_line_trimmed(self):
        llm = '\u201cSimulation Result\u201d\n    electron_mobility: float = 80.0\n    hole_mobility: float = 20.0'
        lines, _ = match_line_trimmed(self.raw, llm)
        self.assertEqual(lines, [(1, 3)])

    def test_full_chain_stage4_flex_indent(self):
        llm = '    # This comment is over-indented'  # 4-space vs 8-space
        lines, _ = match_flexible_indent(self.raw, llm)
        self.assertEqual(lines, [(4, 4)])

    def test_full_chain_stage5_escape_literal(self):
        llm = r'    electron_mobility: float = 80.0  \n    hole_mobility: float = 20.0  '
        lines, _ = match_escape_literal(self.raw_str, llm)
        self.assertEqual(lines, [(2, 3)])

    def test_full_chain_stage6_trimmed_boundary(self):
        llm = ' \n' + '\u201cSimulation Result\u201d  \n  '
        lines, actual = match_trimmed_boundary(self.raw_str, llm)
        self.assertEqual(lines, [(1, 1)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
