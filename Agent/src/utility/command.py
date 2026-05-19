# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.29\n
Description: Builtin command

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.29      Yu Huang     1.0               First implementation\n
2026.5.12      Yu Huang     1.1               Add builtin command of querying read file\n
2026.5.15      Yu Huang     1.2               Revise builtin command management\n
2026.5.15      Yu Huang     1.3               Agent skills support\n
2026.5.19      Yu Huang     1.4               Webpage fetch support\n

Details:
Realization of builtin commands
------------------------------------------------------------------------------------------------------------------------
"""
import json
import logging

from functools import partial
from typing import Callable, Any
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from src.context.agent_context import AgentContext
from src.tool.skills_support import load_skill_content, get_skill_description
from src.constants import *

sys_log = logging.getLogger('logger')
BUILTIN_UNKNOWN = "UNKNOWN"


def cmd_unknown(console: Console):
    """unknown builtin commands"""
    cmd_str = Text()
    cmd_str.append("Unknown command ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("called, nothing happen", style=f"white")
    console.print(cmd_str)


def cmd_query_design(args: Any, ctx: AgentContext, console: Console):
    """query the list of current designs"""
    cmd_str = Text()
    cmd_str.append("query_design", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f":\n    total design num: ", style=f"white")
    cmd_str.append(f"{len(ctx.design_created)}", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f", list of design id: ", style=f"white")
    cmd_str.append(f"{ctx.design_created}", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_query_run(args: Any, ctx: AgentContext, console: Console):
    """query the amount of launched simulation"""
    cmd_str = Text()
    cmd_str.append("query_run", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f":\n    total launched run: ", style=f"white")
    cmd_str.append(f"{ctx.simulation_launched}", style=f"bold {MAJOR_COLOR2}")
    console.print(cmd_str)


def cmd_context(args: Any, ctx: AgentContext, console: Console):
    """query the token usage, message and API requests statistics"""
    title = "TECoSim Agent Context Usage"
    if ctx.total_input_tokens <= 0:
        uncached_rate = 100
    else:
        uncached_rate = 100 * ctx.total_uncached_tokens / ctx.total_input_tokens
    if ctx.api_configs["MAIN_MODEL_CONTEXT"] <= 0:
        ctx_usage = 100
    else:
        ctx_usage = 100 * ctx.last_input_tokens / ctx.api_configs["MAIN_MODEL_CONTEXT"]
    cmd_str = Text()
    cmd_str.append("Session UUID: ", style=f"white")
    cmd_str.append(f"{ctx.session_uuid}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total input tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_input_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total output tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_output_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total uncached tokens of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_uncached_tokens / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", uncached: ", style=f"white")
    cmd_str.append(f"{uncached_rate} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", cached: ", style=f"white")
    cmd_str.append(f"{100 - uncached_rate} %\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total tokens consumption of this session: ", style=f"white")
    cmd_str.append(f"{ctx.total_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue input tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue output tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_output_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue total tokens of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx.last_tokens / 1000} K\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Last dialogue's context usage of this session (main model): ", style=f"white")
    cmd_str.append(f"{ctx_usage} %", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(", ", style=f"white")
    cmd_str.append(f"{ctx.last_input_tokens / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" out of ", style=f"white")
    cmd_str.append(f"{ctx.api_configs["MAIN_MODEL_CONTEXT"] / 1000} K", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(" were used\n", style=f"white")

    cmd_str.append("\nTotal LLM API request num: ", style=f"white")
    cmd_str.append(f"{ctx.total_llm_requests}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Total messages num (main model): ", style=f"white")
    cmd_str.append(f"{len(ctx.messages)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("System prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.system_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tools prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tools_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("User prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.user_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant content prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.content_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant reasoning content prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.reasoning_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Assistant tool calls prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tool_calls_prompts}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Tool results prompts num (main model): ", style=f"white")
    cmd_str.append(f"{ctx.tool_results_prompts}\n", style=f"bold {MAJOR_COLOR2}")

    cmd_str.append("\nAvailable skills amount: ", style=f"white")
    cmd_str.append(f"{len(ctx.skills)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Available skills: ", style=f"white")
    for skill in ctx.skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f" ,", style=f"white")
    if cmd_str.plain.endswith(" ,"):
        cmd_str.right_crop(2)
    cmd_str.append("\nLoaded skills amount: ", style=f"white")
    cmd_str.append(f"{len(ctx.loaded_skills)}\n", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append("Loaded skills: ", style=f"white")
    for skill in ctx.loaded_skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f" ,", style=f"white")
    if cmd_str.plain.endswith(" ,"):
        cmd_str.right_crop(2)

    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_query_fread(args: Any, ctx: AgentContext, console: Console):
    """query the absolute paths of all read files"""
    title = "TECoSim Agent Files Read"
    cmd_str = Text()
    cmd_str.append(f"{len(ctx.files_read)} ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" files read by TECoSim Agent\n\n", style=f"white")

    cmd_str.append("File list: \n", style=f"bold {MAJOR_COLOR2}")
    for path, amount in ctx.files_read.items():
        cmd_str.append(f"{path}: ", style=f"white")
        cmd_str.append(f"{amount}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(" times\n", style=f"white")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_permission_list(args: Any, ctx: AgentContext, console: Console):
    """query the configs of always-allowed-configurable tool calls permission token"""
    title = "TECoSim Agent Tool Call Permission"
    cmd_str = Text()
    cmd_str.append(f"{len(ctx.permissions)} ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f"types of ", style=f"white")
    cmd_str.append(f"always-allowed-configurable", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f" tool calls permission: \n\n", style=f"white")

    cmd_str.append("Dangerously allow all: ", style=f"bold {MAJOR_COLOR2}")
    if ctx.args.dangerously_allow_all:
        cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
    else:
        cmd_str.append("False\n", style="bright_black")
    for name, token in ctx.permissions.items():
        cmd_str.append(f"{name}: ", style=f"white")
        if ctx.args.dangerously_allow_all:
            cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
        else:
            if token:
                cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
            else:
                cmd_str.append("False\n", style="bright_black")
    cmd_str.append(f"\nYou can also toggle the permission config with following command: \n", style=f"white")
    cmd_str.append(f"    /permission_toggle ", style=f"bold {MAJOR_COLOR2}")
    cmd_str.append(f"[NAME OF PERMISSION]", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f" (Swap ", style=f"white")
    cmd_str.append(f"True", style=f"bold {MAJOR_COLOR1}")
    cmd_str.append(f" and ", style=f"white")
    cmd_str.append(f"False", style=f"bright_black")
    cmd_str.append(f")\n", style=f"white")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_permission_toggle(args: Any, ctx: AgentContext, console: Console):
    """toggle the permission token of the tool calls permission with given name"""
    cmd_str = Text()
    if ctx.args.dangerously_allow_all:
        cmd_str.append("You can't toggle any permission token, since ", style=f"white")
        cmd_str.append("dangerously_allow_all", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(" is ", style=f"white")
        cmd_str.append("enabled", style=f"bold {MAJOR_COLOR1}")
        console.print(cmd_str)
        return

    try:
        arg_name = str(args[0])
    except Exception as e:
        sys_log.warning(f"Unable to toggle the permission, target name is invalid with error {e}")
        console.print(f"Unable to toggle the permission, target name is invalid with error {e}", style=f"bold yellow")
        return

    for name, token in ctx.permissions.items():
        if arg_name == name:
            ctx.permissions[name] = not token
            cmd_str.append(f"Permission ", style=f"white")
            cmd_str.append(f"{name}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f" toggled from ", style=f"white")
            cmd_str.append(f"{"True" if token else "False"}", style=f"bold {MAJOR_COLOR1}" if token else f"bright_black")
            cmd_str.append(f" to ", style=f"white")
            cmd_str.append(f"{"False" if token else "True"}", style=f"bright_black" if token else f"bold {MAJOR_COLOR1}")
            cmd_str.append(f" successfully", style=f"white")
            console.print(cmd_str)
            return
    sys_log.warning(f"Unknown permission name {arg_name}, toggle failed")
    console.print(f"Unknown permission name {arg_name}, toggle failed", style=f"bold yellow")


def cmd_query_skills(args: Any, ctx: AgentContext, console: Console):
    """query all available skills (truncate)"""
    title = f"Available Skills ({len(ctx.skills)})"
    limit = ctx.agent_configs["SKILL_DESC_CHAR_LIMIT"]
    cmd_str = Text()
    for skill in ctx.skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        if len(skill["description"]) > limit:
            cmd_str.append(f" {skill["description"][:limit]}...\n\n", style=f"white")
        else:
            cmd_str.append(f" {skill["description"]}\n\n", style=f"white")
    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def cmd_query_loaded_skills(args: Any, ctx: AgentContext, console: Console):
    """query all loaded skills (no truncate)"""
    title = f"Loaded Skills ({len(ctx.loaded_skills)})"
    cmd_str = Text()
    for skill in ctx.loaded_skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        cmd_str.append(f" {skill["description"]}\n\n", style=f"white")
    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


def skill_bound_command(name: str, func: Callable, *args, **kwargs):
    """crete a partial function for loading skills"""
    bound_func = partial(func, *args, **kwargs)
    bound_func.__name__ = name
    return bound_func


def cmd_load_skills(skill_name: str, args: Any, ctx: AgentContext, console: Console):
    """manually load the full prompts of skill to context immediately"""
    try:
        content = load_skill_content("./skills", skill_name, console, True)
        if content is None:
            sys_log.warning(f"Load skill {skill_name} manually failed")
            console.print(f"Load skill {skill_name} manually failed", style=f"bold yellow")
            ctx.messages.append(
                {"role": "user", "content": f"<Load skill {skill_name} manually by user failed>"})
        else:
            ctx.messages.append({"role": "user", "content": json.dumps(content)})
        if not any(item.get("name") == skill_name for item in ctx.loaded_skills):  # registered skills must be available
            ctx.loaded_skills.append({
                "name": skill_name,
                "description": str(get_skill_description(skill_name, ctx.skills)),
            })
    except Exception as e:
        sys_log.warning(f"Load skill {skill_name} manually failed with error {e}")
        console.print(f"Load skill {skill_name} manually failed with error {e}", style=f"bold yellow")
        ctx.messages.append(
            {"role": "user", "content": f"<Load skill {skill_name} manually by user failed with error {e}>"})


def cmd_query_url_caches(args: Any, ctx: AgentContext, console: Console):
    """query all cached URLs"""
    title = f"Cached URLs ({len(ctx.url_caches)})"
    cmd_str = Text()
    view_limit = URL_CACHE_VIEW_MAX
    char_limit = URL_CACHE_CONTENT_CHAR_MAX
    view_left = len(ctx.url_caches) - view_limit if len(ctx.url_caches) >= view_limit else  0
    for idx, url_cache in enumerate(ctx.url_caches):
        cmd_str.append(f"URL: ", style=f"white")
        cmd_str.append(f"{url_cache["url"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", timestamp: ", style=f"white")
        cmd_str.append(f"{url_cache["time"].strftime("%Y-%m-%d %H:%M:%S")}\n", style=f"bold {MAJOR_COLOR2}")
        content = url_cache["content"]
        if len(content) > char_limit:
            content = content[:char_limit] + "..."
        cmd_str.append(f"Cached content: ", style=f"white")
        cmd_str.append(f"{content}\n\n", style=f"bright_black")
        if idx + 1 >= view_limit:
            break
    cmd_str.append(f"Remaining cached URLs not-displayed: ", style=f"white")
    cmd_str.append(f"{view_left}", style=f"bold {MAJOR_COLOR2}")
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
    console.print("\n")


class BuiltinCommands:
    """builtin command class"""
    def __init__(self, console: Console):
        self._commands: dict[str, tuple[Callable[..., Any], str, str]] = {
            "help": (self.cmd_help, "help info", "print all available builtin commands"),
            "query_design": (cmd_query_design, "list designs", "query the list of current designs"),
            "query_run": (cmd_query_run, "list runs", "query the amount of launched simulation"),
            "context": (cmd_context, "query context info", "query the token usage, message and API requests statistics"),
            "query_fread": (cmd_query_fread, "query all read files", "query the absolute paths of all read files"),
            "permission_list": (cmd_permission_list, "query permission info",
                                "query the configs of always-allowed-configurable tool calls permission token"),
            "permission_toggle": (cmd_permission_toggle, "toggle the permission with given name",
                                "toggle the permission token of the tool calls permission with given name"),
            "query_skills": (cmd_query_skills, "query all available skills",
                                               "query all the available skills with name and truncated description"),
            "query_loaded_skills": (cmd_query_loaded_skills, "query all loaded skills",
                                               "query all the loaded skills with name and full description"),
            "query_url_caches": (cmd_query_url_caches, "query all cached URLs",
                                               "query all the cached URLs with timestamp and truncated content"),
        }
        self._request_commands: list[str] = []
        sys_log.debug(f"{len(self._commands)} builtin commands initialized")
        console.print(f"[{MAJOR_COLOR2}]{len(self._commands)}[/{MAJOR_COLOR2}] builtin commands initialized")


    def get_all_commands(self) -> dict[str, tuple[Callable, str, str]]:
        """get copy of all available commands"""
        return self._commands.copy()


    def register(self, name: str, func: Callable, short_desc: str, long_desc: str, request_llm: bool):
        """register a new command, raise error if function already exists"""
        if name in self._commands:
            raise ValueError(f"Command '{name}' already registered")

        for cmd_name, (existing_func, _, _) in self._commands.items():
            if existing_func.__name__ == func.__name__:
                raise ValueError(f"Function '{func.__name__}' already registered as command '{cmd_name}'")
        self._commands[name] = (func, short_desc, long_desc)
        if request_llm:
            self._request_commands.append(name)


    def unregister(self, name: str):
        """unregister a command"""
        self._commands.pop(name, None)
        if name in self._request_commands:
            self._request_commands.remove(name)


    def register_skills(self, skills: list[dict[str, str]], console: Console):
        """register skills as builtin commands"""
        registered_skills = 0
        for skill in skills:
            if skill["name"] in self._commands:
                sys_log.warning(f"Skill with '{skill['name']}' is already registered")
                console.print(f"Skill with '{skill['name']}' is already registered", style="bold yellow")
            else:
                self.register(skill["name"], skill_bound_command(skill["name"], cmd_load_skills, skill["name"]),
                              "load this skill immediately",
                              f"load the skill {skill['name']} immediately to context", True)
                registered_skills += 1
        sys_log.debug(f"{registered_skills} skills registered as builtin commands, "
                      f"{len(self._commands)} builtin commands available")
        console.print(f"[{MAJOR_COLOR2}]{registered_skills}[/{MAJOR_COLOR2}] skills registered as builtin commands, "
                      f"[{MAJOR_COLOR2}]{len(self._commands)}[/{MAJOR_COLOR2}] builtin commands available")


    def cmd_help(self, args: Any, ctx: AgentContext, console: Console):
        """print all available commands"""
        title = "Available Commands"
        cmd_str = Text()
        for cmd, (func, label, desc) in self._commands.items():
            cmd_str.append(f"/{cmd}", style=f"bold {MAJOR_COLOR1}")
            cmd_str.append(f": ", style=f"white")
            cmd_str.append(f"{label}", style=f"bold {MAJOR_COLOR2}")
            cmd_str.append(f", {desc}\n", style=f"white")
        if cmd_str.plain.endswith("\n"):
            cmd_str.rstrip()
        console.print(Panel.fit(cmd_str, title=title, title_align="left",
                                padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
        console.print("\n")


    def execute_cmd(self, cmd: str, args: list[str], ctx: AgentContext, console: Console) -> bool:
        """execute builtin command, return if goto the LLM request"""
        if cmd == BUILTIN_UNKNOWN:
            sys_log.debug("Unknown command called, nothing happen")
            cmd_unknown(console)
            return False
        else:
            sys_log.debug(f"Command call: {cmd} with args {args} start")
            self._commands[cmd][0](args, ctx, console)
            sys_log.debug(f"Command call: {cmd} done")
            if cmd in self._request_commands:
                return True
            else:
                return False


    def __contains__(self, name: str) -> bool:
        """in operations"""
        return name in self._commands


    def __iter__(self):
        """iterator"""
        return iter(self._commands.items())
