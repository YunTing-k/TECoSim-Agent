# -*- coding: utf-8 -*-
"""
Unit tests for ask_question.py: get_answers, get_answers_render.
Run: python -m unittest test.ask_question_test
"""
import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tool.ask_question import get_answers, get_answers_render, norm_questions, init_options_choice
from src.constants import QUESTION_NO_CHOICE_LABEL, QUESTION_OTHER_LABEL
from rich.console import Console


class TestGetAnswersSingleSelect(unittest.TestCase):
    def setUp(self):
        self.question_single = [{
            "question": "What color?",
            "header": "Color",
            "options": [
                {"label": "Red", "description": "Red color"},
                {"label": "Blue", "description": "Blue color"},
            ],
            "multi_select": False,
        }]

    def test_single_select_returns_chosen_option(self):
        questions = norm_questions(self.question_single)
        selected_indices = [0]
        options_choices = [0]  # first option
        user_cache = [""]
        answers = get_answers(questions, selected_indices, options_choices, user_cache)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["header"], "Color")
        self.assertEqual(answers[0]["answer"], "Red")

    def test_single_select_other_with_text(self):
        questions = norm_questions(self.question_single)
        # <Other> is appended by norm_questions, so it's index 2
        selected_indices = [2]
        options_choices = [2]
        user_cache = ["my custom color"]
        answers = get_answers(questions, selected_indices, options_choices, user_cache)
        self.assertEqual(answers[0]["answer"], QUESTION_OTHER_LABEL)
        self.assertEqual(answers[0]["other_text"], "my custom color")


class TestGetAnswersMultiSelect(unittest.TestCase):
    def setUp(self):
        self.question_multi = [{
            "question": "Which features?",
            "header": "Features",
            "options": [
                {"label": "Feature A", "description": "First feature"},
                {"label": "Feature B", "description": "Second feature"},
            ],
            "multi_select": True,
        }]

    def test_multi_select_one_option(self):
        questions = norm_questions(self.question_multi)
        options_choices = init_options_choice(questions)
        # default: first option selected
        answers = get_answers(questions, [0 for _ in questions], options_choices, ["" for _ in questions])
        self.assertEqual(answers[0]["answer"], "Feature A")

    def test_multi_select_two_options(self):
        questions = norm_questions(self.question_multi)
        options_choices = [[True, True, False]]  # Feature A + Feature B (not <Other>)
        answers = get_answers(questions, [0], options_choices, [""])
        self.assertEqual(answers[0]["answer"], "Feature A + Feature B")

    def test_multi_select_with_other(self):
        questions = norm_questions(self.question_multi)
        # <Other> is at index 2 after norm_questions
        options_choices = [[True, False, True]]  # Feature A + <Other>
        user_cache = ["custom stuff"]
        answers = get_answers(questions, [0], options_choices, user_cache)
        self.assertIn("Feature A", answers[0]["answer"])
        self.assertIn(QUESTION_OTHER_LABEL, answers[0]["answer"])
        self.assertEqual(answers[0]["other_text"], "custom stuff")

    def test_multi_select_no_choice_returns_explicit_label(self):
        questions = norm_questions(self.question_multi)
        options_choices = [[False, False, False]]  # nothing selected
        answers = get_answers(questions, [0], options_choices, [""])
        self.assertEqual(answers[0]["answer"], QUESTION_NO_CHOICE_LABEL)
        self.assertNotIn("other_text", answers[0])

    def test_multi_select_no_choice_with_existing_other_cache(self):
        """Even if user_cache had prior text, no-choice should still show the label."""
        questions = norm_questions(self.question_multi)
        options_choices = [[False, False, False]]
        user_cache = ["some old text in cache"]
        answers = get_answers(questions, [0], options_choices, user_cache)
        self.assertEqual(answers[0]["answer"], QUESTION_NO_CHOICE_LABEL)


class TestGetAnswersRender(unittest.TestCase):
    def setUp(self):
        self.console = Console(force_terminal=True, color_system=None)

    def test_render_single_answer(self):
        answers = [{
            "question": "What color?",
            "header": "Color",
            "answer": "Red",
        }]
        with patch.object(self.console, 'print') as mock_print:
            get_answers_render(answers, self.console)
            mock_print.assert_called_once()
            render = mock_print.call_args[0][0]
            self.assertIn("Color", render.plain)
            self.assertIn("Red", render.plain)

    def test_render_multi_answer(self):
        answers = [
            {"question": "Color?", "header": "Color", "answer": "Red + Blue"},
            {"question": "Size?", "header": "Size", "answer": "Large"},
        ]
        with patch.object(self.console, 'print') as mock_print:
            get_answers_render(answers, self.console)
            render = mock_print.call_args[0][0]
            self.assertIn("Red + Blue", render.plain)
            self.assertIn("Large", render.plain)

    def test_render_no_choice_label(self):
        answers = [{
            "question": "Features?",
            "header": "Features",
            "answer": QUESTION_NO_CHOICE_LABEL,
        }]
        with patch.object(self.console, 'print') as mock_print:
            get_answers_render(answers, self.console)
            render = mock_print.call_args[0][0]
            self.assertIn(QUESTION_NO_CHOICE_LABEL, render.plain)

    def test_render_with_other_text(self):
        answers = [{
            "question": "Ideas?",
            "header": "Ideas",
            "answer": QUESTION_OTHER_LABEL,
            "other_text": "my custom input",
        }]
        with patch.object(self.console, 'print') as mock_print:
            get_answers_render(answers, self.console)
            render = mock_print.call_args[0][0]
            self.assertIn("my custom input", render.plain)

    def test_render_empty_answers(self):
        with patch.object(self.console, 'print') as mock_print:
            get_answers_render([], self.console)
            mock_print.assert_called_once()
            render = mock_print.call_args[0][0]
            self.assertIn("User's choices", render.plain)


class TestPrintMessagesAskQuestion(unittest.TestCase):
    """Test that print_messages correctly displays ask_user_question tool results."""

    def test_tool_msg_ask_question_renders_answers(self):
        from src.context.prompt import print_messages
        console = Console(force_terminal=True, color_system=None)

        mock_ctx = MagicMock()
        mock_ctx.agent_configs = {
            "RENDER_RESPONSE_AS_MD": False,
            "RESUME_DISPLAY_SYS_REMINDER": False,
            "RESUME_DISPLAY_SKILLS": False,
            "RESUME_DISPLAY_CRONS": False,
            "RESUME_DISPLAY_WRITE_PREVIEW": False,
            "RESUME_DISPLAY_BASH_PREVIEW": False,
            "RESUME_DISPLAY_BASH_RESULT": False,
            "RESUME_DISPLAY_SUBAGENT": False,
        }

        answers = [{
            "question": "What color?",
            "header": "Color",
            "answer": "Red",
        }]
        content = json.dumps({"status": "SUCCESS", "answers": answers, "info": "Collected 1 answers from user"})

        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "function": {"name": "ask_user_question", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": content},
        ]

        with patch.object(console, 'print') as mock_print:
            print_messages(messages, mock_ctx, console)

            # Find the call that contains the answer
            found = False
            for call_args in mock_print.call_args_list:
                arg = call_args[0][0]
                plain = getattr(arg, 'plain', str(arg))
                if 'Red' in plain and 'Color' in plain:
                    found = True
                    break
            self.assertTrue(found, "Expected answer 'Red' for header 'Color' not found in console output")

    def test_tool_msg_ask_question_empty_answers(self):
        from src.context.prompt import print_messages
        console = Console(force_terminal=True, color_system=None)

        mock_ctx = MagicMock()
        mock_ctx.agent_configs = {
            "RENDER_RESPONSE_AS_MD": False,
            "RESUME_DISPLAY_SYS_REMINDER": False,
            "RESUME_DISPLAY_SKILLS": False,
            "RESUME_DISPLAY_CRONS": False,
            "RESUME_DISPLAY_WRITE_PREVIEW": False,
            "RESUME_DISPLAY_BASH_PREVIEW": False,
            "RESUME_DISPLAY_BASH_RESULT": False,
            "RESUME_DISPLAY_SUBAGENT": False,
        }

        content = json.dumps({"status": "SUCCESS", "answers": [], "info": "Collected 0 answers from user"})

        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_2", "function": {"name": "ask_user_question", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_2", "content": content},
        ]

        with patch.object(console, 'print') as mock_print:
            print_messages(messages, mock_ctx, console)
            # Should not crash; empty answers skipped
            found_choices = False
            for call_args in mock_print.call_args_list:
                arg = call_args[0][0]
                plain = getattr(arg, 'plain', str(arg))
                if "User's choices" in plain:
                    found_choices = True
            self.assertFalse(found_choices)

    def test_tool_msg_bash_not_affected(self):
        """Other tool messages (e.g. bash) should still pass through normally."""
        from src.context.prompt import print_messages
        console = Console(force_terminal=True, color_system=None)

        mock_ctx = MagicMock()
        mock_ctx.agent_configs = {
            "RENDER_RESPONSE_AS_MD": False,
            "RESUME_DISPLAY_SYS_REMINDER": False,
            "RESUME_DISPLAY_SKILLS": False,
            "RESUME_DISPLAY_CRONS": False,
            "RESUME_DISPLAY_WRITE_PREVIEW": False,
            "RESUME_DISPLAY_BASH_PREVIEW": False,
            "RESUME_DISPLAY_BASH_RESULT": False,
            "RESUME_DISPLAY_SUBAGENT": False,
        }

        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_3", "function": {"name": "bash", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_3", "content": json.dumps({"stdout": "ok", "stderr": ""})},
        ]

        with patch.object(console, 'print') as mock_print:
            print_messages(messages, mock_ctx, console)
            found_choices = False
            for call_args in mock_print.call_args_list:
                arg = call_args[0][0]
                plain = getattr(arg, 'plain', str(arg))
                if "User's choices" in plain:
                    found_choices = True
            self.assertFalse(found_choices)


class TestNormQuestions(unittest.TestCase):
    def test_other_option_appended(self):
        questions = [{
            "question": "Test?",
            "header": "Test",
            "options": [{"label": "A", "description": "Option A"}],
            "multi_select": False,
        }]
        normalized = norm_questions(questions)
        self.assertEqual(len(normalized[0]["options"]), 2)
        self.assertEqual(normalized[0]["options"][1]["label"], QUESTION_OTHER_LABEL)

    def test_other_option_not_duplicated(self):
        questions = [{
            "question": "Test?",
            "header": "Test",
            "options": [
                {"label": "A", "description": "A"},
                {"label": QUESTION_OTHER_LABEL, "description": "custom"},
            ],
            "multi_select": False,
        }]
        normalized = norm_questions(questions)
        self.assertEqual(len(normalized[0]["options"]), 2)


if __name__ == '__main__':
    unittest.main()
