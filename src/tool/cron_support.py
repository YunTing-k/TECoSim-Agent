# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.3
Description: Cron task management support

Revision:
---------
2026.6.3       Yu Huang      1.0      First implementation
2026.6.7       Yu Huang      1.1      Remove cron listen to agent_listen.py
2026.6.10      Yu Huang      1.2      Define all inserted message labels in constans.py
2026.6.13      Yu Huang      1.3      Bugfix: one-shot cron tasks now check next_time before firing
2026.6.13      Yu Huang      1.4      Add sys_log on cron fire (task id + type) and trigger summary
2026.7.3       Yu Huang      1.5      Revise visuals of messages print (create/query/remove crons, glob, query) when resuming session

Details:
---------
Cron task system: configures durable (cross-session) and session-only cron tasks from JSON configs using croniter. Supports
repetitive and one-shot tasks. Provides task checking/triggering (appends cron prompts to messages), listing, creation
(UUID-based ID), and a listening TUI (gradient color animation) that fires before user input. Also provides CLI operations
for durable cron management.
"""
import sys
import json
import uuid
import logging

from argparse import Namespace
from croniter import croniter
from datetime import datetime
from typing import Any
from rich.text import Text
from rich.panel import Panel
from rich.console import Console
from src.context.agent_context import AgentContext, CronDump, CronTask
from src.constants import *
from src.utility import ui_info, basic_utils

sys_log = logging.getLogger('logger')


def config_cron(durable_crons: list[CronDump], session_crons: list[CronDump], console: Console) -> tuple[list[CronTask], list[str]]:
    """configure durable cron tasks"""
    cron_list: list[CronTask] = []
    id_list: list[str] = []
    """configure durable cron tasks"""
    for cron in durable_crons:
        try:
            if not croniter.is_valid(cron["cron_str"]):
                sys_log.warning(f"Invalid durable cron id: {cron["id"]} with prompt: {cron['prompt']}")
                console.print(f"Invalid durable cron id: {cron["id"]} with prompt: {cron['prompt']}", style="bold yellow")
                continue
            if cron["id"] in id_list:
                sys_log.warning(f"Duplicate durable cron with id: {cron["id"]} and prompt: {cron['prompt']}")
                console.print(f"Duplicate durable cron with id: {cron["id"]} and prompt: {cron['prompt']}", style="bold yellow")
                continue
            cron_obj = croniter(cron["cron_str"], datetime.now())
            cron_list.append(CronTask(
                id=cron["id"],
                prompt=cron["prompt"],
                cron_str=cron["cron_str"],
                cron=cron_obj,
                next_time=cron_obj.get_next(datetime, update_current=True),
                durable=True,
                if_repeat=cron["if_repeat"],
                if_end=False
            ))
            id_list.append(cron["id"])
        except Exception as e:
            sys_log.warning(f"Configure durable cron task with config: {cron} failed with error: {e}")
            console.print(f"Configure durable cron task with config: {cron} failed with error: {e}", style="bold yellow")
            continue
    sys_log.debug(f"Configured {len(cron_list)} cron tasks from durable config file. "
                  f"{len(durable_crons) - len(cron_list)} out of {len(durable_crons)} tasks ignored")
    console.print(f"Configured [{MAJOR_COLOR2}]{len(cron_list)}[/{MAJOR_COLOR2}] cron tasks from durable config file. "
                  f"[{MAJOR_COLOR2}]{len(durable_crons) - len(cron_list)}[/{MAJOR_COLOR2}] out of "
                  f"[{MAJOR_COLOR2}]{len(durable_crons)}[/{MAJOR_COLOR2}] tasks ignored")

    """configure session cron tasks"""
    durable_num = len(cron_list)
    for cron in session_crons:
        try:
            if not croniter.is_valid(cron["cron_str"]):
                sys_log.warning(f"Invalid session cron id: {cron["id"]} with prompt: {cron['prompt']}")
                console.print(f"Invalid session cron id: {cron["id"]} with prompt: {cron['prompt']}", style="bold yellow")
                continue
            if cron["id"] in id_list:
                sys_log.warning(f"Duplicate session cron with id: {cron["id"]} and prompt: {cron['prompt']}")
                console.print(f"Duplicate session cron with id: {cron["id"]} and prompt: {cron['prompt']}", style="bold yellow")
                continue
            cron_obj = croniter(cron["cron_str"], datetime.now())
            cron_list.append(CronTask(
                id=cron["id"],
                prompt=cron["prompt"],
                cron_str=cron["cron_str"],
                cron=cron_obj,
                next_time=cron_obj.get_next(datetime, update_current=True),
                durable=False,
                if_repeat=cron["if_repeat"],
                if_end = False
            ))
            id_list.append(cron["id"])
        except Exception as e:
            sys_log.warning(f"Configure session cron task with config: {cron} failed with error: {e}")
            console.print(f"Configure session cron task with config: {cron} failed with error: {e}", style="bold yellow")
            continue
    session_num = len(cron_list) - durable_num
    sys_log.debug(f"Configured {session_num} cron tasks from session config file. "
                  f"{len(session_crons) - session_num} out of {len(session_crons)} tasks ignored")
    console.print(f"Configured [{MAJOR_COLOR2}]{session_num}[/{MAJOR_COLOR2}] cron tasks from session config file. "
                  f"[{MAJOR_COLOR2}]{len(session_crons) - session_num}[/{MAJOR_COLOR2}] out of "
                  f"[{MAJOR_COLOR2}]{len(session_crons)}[/{MAJOR_COLOR2}] tasks ignored")
    return cron_list, id_list


def check_cron_tasks(ctx: AgentContext) -> bool:
    """check if any cron task triggerd"""
    prompt_list: list[str] = []
    for cron_task in ctx.cron_tasks:
        now = datetime.now()
        if cron_task["if_repeat"]:
            if now >= cron_task["next_time"]:  # the cron task trigger or expire
                while now >= cron_task["next_time"]:
                    cron_task["next_time"] = cron_task["cron"].get_next(datetime, update_current=True)
                sys_log.debug(f"Cron task {cron_task['id']} fired (repeat): {cron_task['prompt'][:80]}")
                prompt_list.append(cron_task["prompt"])
        elif now >= cron_task["next_time"] and not cron_task["if_end"]:
            cron_task["if_end"] = True
            assert ctx.active_cron >= 1
            ctx.active_cron -= 1
            sys_log.debug(f"Cron task {cron_task['id']} fired (one-shot): {cron_task['prompt'][:80]}")
            prompt_list.append(cron_task["prompt"])

    if len(prompt_list) == 0:
        return False

    rules = (
        "\n"
        "## Task execution rules\n"
        "1. **Dependency first**: if a task's output or side effect is needed by another "
        "task, do the prerequisite one first.\n"
        "2. **Resource conflict**: if two tasks would conflict on the same resource "
        "(e.g. modifying the same design, launching simulator simultaneously), "
        "execute them sequentially one by one. Do not interleave them.\n"
        "3. **Errors don't block the rest**: if a task fails, report the failure and "
        "continue with remaining tasks -- do not abort the whole batch.\n"
        "4. **All tasks must be attempted**: do not skip any task unless it becomes "
        "impossible due to a prior failure.\n\n"
    )
    cron_prompts = (
        f"You have `{len(prompt_list)}` cron tasks triggered. Analyze these tasks and handle them accordingly.\n"
        f"{rules}"
        f"## Tasks\n"
    )
    for prompt in prompt_list:
        cron_prompts += f"- {prompt}\n"
    ctx.messages.append({"role": "user",
                         "content": f"{CRON_START_LABEL}\n"
                                    f"{cron_prompts}\n"
                                    f"{CRON_END_LABEL}"})
    sys_log.debug(f"check_cron_tasks: {len(prompt_list)} cron task(s) triggered, {ctx.active_cron} remaining active")
    return True


def get_cron_list(cron_tasks: list[CronTask]) -> str:
    """get the cron list as structured string"""
    cron_str: str = ""
    for cron_task in cron_tasks:
        cron_str += f"# id: {cron_task["id"]}\n"
        cron_str += f"- prompt: {cron_task["prompt"]}\n"
        cron_str += f"- cron pattern: {cron_task["cron_str"]}\n"
        cron_str += f"- is durable across sessions: {cron_task["durable"]}\n"
        cron_str += f"- is a repetitive task: {cron_task["if_repeat"]}\n"
        if not cron_task["if_repeat"]:
            cron_str += f"- is finished (one-shot): {cron_task["if_end"]}\n"
        cron_str += "\n"
    return cron_str if cron_str else "(Empty cron task list)"


def gen_cron_id(id_list: list[str]) -> str:
    """generate cron id with UUID"""
    uuid_obj = uuid.uuid4()
    uuid_str = uuid_obj.__str__().replace("-", "")
    cron_id = uuid_str[:CRON_TASK_ID_LEN]
    while cron_id in id_list:
        uuid_obj = uuid.uuid4()
        uuid_str = uuid_obj.__str__()
        cron_id = uuid_str[:CRON_TASK_ID_LEN]
    return cron_id


def get_cron_create_str(arguments: dict[str, Any], if_fail: bool) -> str:
    """get cron create string with arguments only for display"""
    cron_str: str = arguments.get("cron", "(Empty cron pattern)")
    prompt: str = arguments.get("prompt", "(Empty cron prompt)")
    if len(prompt) > CRON_PROMPT_DISPLAY_CHAR_MAX:
        prompt = prompt[:CRON_PROMPT_DISPLAY_CHAR_MAX] + "..."
    if_repeat: bool = arguments.get("if_repeat", True)
    durable: bool = arguments.get("durable", False)
    if not if_fail:
        return (f"{TOOL_NAME_CREATE_CRON}:\n"
                f"├─pattern: \"{cron_str}\", if repeat: {if_repeat}, if durable across sessions: {durable}\n"
                f"└─prompt: \"{prompt}\"")
    else:
        return (f"{TOOL_NAME_CREATE_CRON}: Fail\n"
                f"├─pattern: \"{cron_str}\", if repeat: {if_repeat}, if durable across sessions: {durable}\n"
                f"└─prompt: \"{prompt}\"")


def create_cron_impl(arguments: dict[str, Any], id_list: list[str]) -> tuple[CronTask | None, bool, str]:
    """implementation of creating cron tasks from arguments"""
    try:
        cron_str: str = arguments["cron"]
        prompt: str = arguments["prompt"]
        if_repeat: bool = arguments.get("if_repeat", True)
        durable: bool = arguments.get("durable", False)
        if not croniter.is_valid(cron_str):
            return None, False, f"Invalid cron pattern: {cron_str}"
        cron_id = gen_cron_id(id_list)
        cron_obj = croniter(cron_str, datetime.now())
        return CronTask(
            id=cron_id,
            prompt=prompt,
            cron_str=cron_str,
            cron=cron_obj,
            next_time=cron_obj.get_next(datetime, update_current=True),
            durable=durable,
            if_repeat=if_repeat,
            if_end=False), True, SUCCESS_LABEL
    except Exception as e:
        return None, False, f"Create cron task failed with error: {e}"


def cron_entry_cli(args: Namespace, console: Console):
    """durable cron task CLI operations support"""
    if args.command != "cron":
        return

    """cron operations"""
    if args.cron_action == 'list':
        cron_list_cli(console)
    elif args.cron_action == 'remove':
        cron_remove_cli(args, console)
    else:
        sys_log.warning(f"Unknown cron task action: {args.cron_action}")
        console.print(f"Unknown cron task action: {args.cron_action}", style="bold yellow")
        sys.exit(-1)

    """session action doesn't entry main program"""
    sys.exit(0)


def cron_list_cli(console: Console):
    """query all durable cron tasks"""
    try:
        durable_crons: list[CronDump] = basic_utils.load_configs(configs_path=CRON_CONFIGS_PATH, name="Durable Crons", console=console)
    except Exception as e:
        sys_log.error(f"Failed to load durable cron tasks from: {CRON_CONFIGS_PATH} with error {e}")
        console.print(f"Failed to load durable cron tasks from: {CRON_CONFIGS_PATH} with error {e}", style="bold red")
        return

    title = f"Durable Cron Tasks ({len(durable_crons)})"
    cmd_str = Text()
    for cron in durable_crons:
        cmd_str.append(f"ID: ", style=f"white")
        cmd_str.append(f"{cron["id"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Pattern: ", style=f"white")
        cmd_str.append(f"{cron["cron_str"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"  Repetitive: ", style=f"white")
        if not cron["if_repeat"]:
            cmd_str.append(f"False", style=f"bright_black")
        else:
            cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f"\nPrompt: ", style=f"white")
        cmd_str.append(f"{cron["prompt"]}\n\n", style=f"bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()

    hint = Text()
    hint.append(f"  Tips: You can remove any durable cron task with following command in shell: ", style=f"bright_black")
    hint.append(f"python -m src.main cron remove ", style=f"bold {MAJOR_COLOR2}")
    hint.append(f"[Cron ID]\n", style=f"bold {MAJOR_COLOR1}")
    hint.append(f"        You can only remove session-specific cron task with builtin command: ", style=f"bright_black")
    hint.append(f"/cron_remove", style=f"bold {MAJOR_COLOR2}")

    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print(hint)


def cron_remove_cli(args: Namespace, console: Console):
    """remove a durable cron task"""
    try:
        """load cron tasks"""
        id_str: str = args.id
        try:
            durable_crons: list[CronDump] = basic_utils.load_configs(configs_path=CRON_CONFIGS_PATH, name="Durable Crons", console=console)
        except Exception as e:
            sys_log.error(f"Failed to load durable cron tasks from: {CRON_CONFIGS_PATH} with error {e}")
            console.print(f"Failed to load durable cron tasks from: {CRON_CONFIGS_PATH} with error {e}", style="bold red")
            return
        """find cron task with ID"""
        del_idx = -1
        for idx, cron in enumerate(durable_crons):
            if cron["id"] == id_str:
                del_idx = idx
                break
        if del_idx == -1:
            sys_log.error(f"Durable cron task with id: {id_str} not found")
            console.print(f"Durable cron task with id: {id_str} not found", style="bold red")
            return
        """request"""
        token = ui_info.request_tui(console=console, title="Remove Durable Cron Task", request_desc=f"remove the cron: {id_str}",
                                    request_detail=f"This cron task will be deleted forever",
                                    cancel_str=f"Cron task remove cancelled")
        if not token:
            sys_log.debug(f"Durable cron with ID: {id_str} remove cancelled")
            console.print(f"Durable cron with ID: [{MAJOR_COLOR2}]{id_str}[/{MAJOR_COLOR2}] remove cancelled")
            return
        """remove and save"""
        del durable_crons[del_idx]
        with open(CRON_CONFIGS_PATH, "w", encoding="utf-8") as f:
            json.dump(durable_crons, f, indent=2, ensure_ascii=False)
        sys_log.debug(f"Remove durable cron task with id: {id_str} successfully")
        console.print(f"Remove durable cron task with id: [{MAJOR_COLOR2}]{id_str}[/{MAJOR_COLOR2}] successfully", style="bright_black")
    except Exception as e:
        sys_log.error(f"Remove durable cron task with args: {args} failed with error: {e}")
        console.print(f"Remove durable cron task with args: {args} failed with error: {e}", style="bold red")
