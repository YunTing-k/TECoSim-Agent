# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.22\n
Description: Tool def of ask_user_question

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.22      Yu Huang     1.0               First implementation\n
2026.4.23      Yu Huang     1.1               Multi-select support and render optimization\n

Details:
Ask user question TUI that TECoSim agent can call
------------------------------------------------------------------------------------------------------------------------
"""
import logging

from typing import Any
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from prompt_toolkit import PromptSession
from rich.console import Group, Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from src.constants import *

sys_log = logging.getLogger('logger')
OTHER_LABEL = "<Other>"
OTHER_DESCRIPTION = "Type other contents"
RECOMMEND_LABEL = "Recommended"


class AskUserCancelled(Exception):
    """Raised when user cancels interactive question answering."""


def norm_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """check if the option in questions has OTHER_LABEL, if not append one"""
    normalized: list[dict[str, Any]] = []
    for question in questions:
        options = list(question["options"])
        if not any(option.get("label") == OTHER_LABEL for option in options):
            options.append({"label": OTHER_LABEL, "description": OTHER_DESCRIPTION})
        normalized.append({
            "question": question["question"],
            "header": question["header"],
            "options": options,
            "multi_select": question.get("multi_select", False),
        })
    return normalized


def render_questions(questions: list[dict[str, Any]], active_idx: int, selected_indices: list[int],
                     options_choices: list[list[bool] | int], user_cache: list[str]):
    """render the questions panel according to the selections in single panel"""
    panels = []
    active_question = questions[active_idx]
    header_text = Text()
    for question_idx, question in enumerate(questions):
        if question_idx == active_idx:
            header_style = f"bold {MAJOR_COLOR1}"
        else:
            header_style = "bold bright_black"
        if question_idx != len(questions) - 1:
            header_text.append(question["header"] + "  ", style=header_style)
        else:
            header_text.append(question["header"], style=header_style)
    body = Text()
    for option_idx, option in enumerate(active_question["options"]):
        is_selected_option = selected_indices[active_idx] == option_idx
        prefix1 = "> " if is_selected_option else "  "
        if active_question.get("multi_select"):
            prefix2 = " ✓" if options_choices[active_idx][option_idx] else ""
        else:
            prefix2 = " ✓" if options_choices[active_idx] == option_idx else ""
        if is_selected_option:
            label_style = f"bold {MAJOR_COLOR2}"
            desc_style = "italic white"
        else:  # default
            label_style = "white"
            desc_style = "italic bright_black"
        body.append(f"{prefix1}{option['label']}{prefix2}\n", style=label_style)
        description = option.get("description", "(No desc.)")
        if option.get("label") == OTHER_LABEL:
            body.append(f"    {description}: {user_cache[active_idx]}\n", style=desc_style)
        else:
            body.append(f"    {description}\n", style=desc_style)
    if body.plain.endswith("\n"):
        body.rstrip()
    panels.append(Panel(body, title=header_text, title_align="left", border_style=MAJOR_COLOR2))
    hint = Text(f"←/→ (switch)    ↑/↓ (select)    Enter (choose)    Ctrl+Enter (confirm)    Esc/Ctrl+C (cancel)\n", style="bright_black")
    hint.append(f"This is a ", style="bright_black")
    if active_question.get("multi_select"):
        hint.append(f"multi-select ", style=MAJOR_COLOR2)
    else:
        hint.append(f"single-select ", style=MAJOR_COLOR2)
    hint.append(f"question", style="bright_black")
    return Group(*panels, hint)


def get_user_input(questions: list[dict[str, Any]], active_idx: int, selected_indices: list[int],
                   user_cache: list[str], agent_session: PromptSession) -> tuple[list[str], bool, bool]:
    """get the user's input with prompt and update the cache"""
    question = questions[active_idx]
    option = question["options"][selected_indices[active_idx]]
    if option.get("label") == OTHER_LABEL:
        is_empty = True
        is_modify = False
        cache = user_cache[active_idx]
        user_input = agent_session.prompt(f"[{question['header']}] Please input your text: > ", default=cache)
        user_cache[active_idx] = user_input
        if user_input.strip():
            is_empty = False
        if cache != user_input:
            is_modify = True
        return user_cache, is_empty, is_modify
    else:
        return user_cache, True, False


def get_answers(questions: list[dict[str, Any]], selected_indices: list[int],
                options_choices: list[list[bool] | int], user_cache: list[str]) -> list[dict[str, Any]]:
    """get the answers according to user selection or user's input"""
    answers: list[dict[str, Any]] = []
    for question_idx, question in enumerate(questions):
        if question.get("multi_select"):
            option_bools = options_choices[question_idx]
            option_indices = [i for i, flag in enumerate(option_bools) if flag]
            answer_str = ""
            if_other = False
            for option_idx, option in enumerate(question["options"]):
                if option_idx in option_indices:
                    answer_str = answer_str + option["label"] + " + "
                    if option["label"] == OTHER_LABEL:
                        if_other = True
            if answer_str.endswith(" + "):
                answer_str = answer_str[:-3]
            if if_other:
                answer = {
                    "question": question["question"],
                    "header": question["header"],
                    "answer": answer_str,
                }
                other_text = user_cache[question_idx]
                answer["other_text"] = other_text
            else:
                answer = {
                    "question": question["question"],
                    "header": question["header"],
                    "answer": answer_str,
                }
            answers.append(answer)
        else:
            option = question["options"][selected_indices[question_idx]]
            if option["label"] == OTHER_LABEL:
                answer = {
                    "question": question["question"],
                    "header": question["header"],
                    "answer": option["label"],
                }
                other_text = user_cache[question_idx]
                answer["other_text"] = other_text
            else:
                answer = {
                    "question": question["question"],
                    "header": question["header"],
                    "answer": option["label"],
                }
            answers.append(answer)
    return answers


def init_options_choice(questions: list[dict[str, Any]]) -> list[list[bool] | int]:
    """initialize the option's choices"""
    options_choices = []
    for question_idx, question in enumerate(questions):
        if question.get("multi_select"):
            bool_list = [False for _ in question["options"]]
            bool_list[0] = True
            options_choices.append(bool_list)
        else:
            options_choices.append(0)
    return options_choices


def toggle_options_choice(questions: list[dict[str, Any]], active_idx: int, selected_indices: list[int],
                          options_choices: list[list[bool] | int]) -> list[list[bool] | int]:
    """toggle the option's choices"""
    active_question = questions[active_idx]
    if active_question.get("multi_select"):
        if_select = options_choices[active_idx][selected_indices[active_idx]]
        options_choices[active_idx][selected_indices[active_idx]] = not if_select
    else:
        options_choices[active_idx] = selected_indices[active_idx]
    return options_choices


def set_options_choice(questions: list[dict[str, Any]], active_idx: int, selected_indices: list[int],
                       options_choices: list[list[bool] | int], key: bool) -> list[list[bool] | int]:
    """set the option's choices according to given key"""
    active_question = questions[active_idx]
    if active_question.get("multi_select"):
        options_choices[active_idx][selected_indices[active_idx]] = key
    else:
        if key:
            options_choices[active_idx] = selected_indices[active_idx]
        else:
            pass
    return options_choices


def ask_user_question_tui(questions: list[dict[str, Any]], console: Console, agent_session: PromptSession) -> list[dict[str, Any]]:
    """top realization of asking user question TUI"""
    questions_normalized = norm_questions(questions)
    active_idx = 0  # default active question
    selected_indices = [0 for _ in questions_normalized]  # default option display selection
    options_choices = init_options_choice(questions_normalized)  # default option choice selection
    user_cache = ["" for _ in questions_normalized]  # empty user cache

    while True:
        input_device = create_input()
        action = None
        try:
            with input_device.raw_mode():
                input_device.flush_keys()
                with Live(render_questions(questions_normalized, active_idx, selected_indices, options_choices, user_cache),
                          console=console, refresh_per_second=TUI_REFRESH_RATE, transient=True) as live:
                    while True:
                        key_press = input_device.read_keys()
                        for key in key_press:
                            if key.key == Keys.Up:
                                selected_indices[active_idx] = (selected_indices[active_idx] - 1) % len(questions_normalized[active_idx]["options"])
                            elif key.key == Keys.Down:
                                selected_indices[active_idx] = (selected_indices[active_idx] + 1) % len(questions_normalized[active_idx]["options"])
                            elif key.key == Keys.Left:
                                active_idx = (active_idx - 1) % len(questions_normalized)
                            elif key.key == Keys.Right:
                                active_idx = (active_idx + 1) % len(questions_normalized)
                            elif key.key == Keys.Enter:
                                option = questions_normalized[active_idx]["options"][selected_indices[active_idx]]
                                if option.get("label") == OTHER_LABEL:
                                    action = "input"
                                else:
                                    action = "choose"
                                break
                            elif key.key == Keys.ControlJ:  # get answers
                                action = "submit"
                                break
                            elif key.key == Keys.Escape or key.key == Keys.ControlC:
                                raise AskUserCancelled("ask question cancelled by user")
                        if action is not None:  # no action no break
                            break
                        live.update(render_questions(questions_normalized, active_idx, selected_indices, options_choices, user_cache))
        finally:
            input_device.close()

        if action == "input":  # choose an Other label
            console.print()
            user_cache, is_empty, is_modify = get_user_input(questions_normalized, active_idx, selected_indices, user_cache, agent_session)
            if is_empty:  # if empty, unselect
                options_choices = set_options_choice(questions_normalized, active_idx, selected_indices, options_choices, False)
            elif is_modify:  # if non-empty and modified, always select
                options_choices = set_options_choice(questions_normalized, active_idx, selected_indices, options_choices, True)
            else:  # if non-empty and not modified, toggle it
                options_choices = toggle_options_choice(questions_normalized, active_idx, selected_indices, options_choices)
        if action == "choose":  # choose a none Other label
            options_choices = toggle_options_choice(questions_normalized, active_idx, selected_indices, options_choices)
        if action == "submit":
            return get_answers(questions_normalized, selected_indices, options_choices, user_cache)
