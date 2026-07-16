# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.12
Description: Subagent module for TECoSim agent

Revision:
---------
2026.6.12      Yu Huang      1.0      First implementation
2026.6.13      Yu Huang      1.1      Add subject parameter for concise task title display
2026.6.13      Yu Huang      1.2      Create _dummy_progress once per agent & API retry on transient failures support
2026.6.13      Yu Huang      1.3      Truncate oversized tool results & Scheduler agent support of shared scoreboard
2026.6.13      Yu Huang      1.4      Support medium model tier (main/medium/fast) via api_configs MEDIUM_MODEL_*
2026.6.14      Yu Huang      1.5      Add warning to subagent when they are about to run out of step budget
2026.6.14      Yu Huang      1.6      Fix: remove unused lock/threading, parse_response propagate, cached_tokens None guard
2026.6.21      Yu Huang      1.7      Fix: User addons cannot be inserted between tool results when LLM is deepseek
2026.6.29      Yu Huang      1.8      Expose start_time for per-agent summary display in execute_subagents & Add GNU bash
                                      hint to subagent system prompt (avoid PowerShell on Windows)
2026.6.30      Yu Huang      1.9      Add multi-round results truncate method with pydict keys preserved
2026.7.3       Yu Huang      2.0      Add more current tools info when subagent is running
2026.7.15      Yu Huang      2.1      Add merge subagent statistic method

Details:
---------
SubAgent wraps a cloned AgentContext + own Scoreboard to run a mini-agent loop. The loop mimics main.py: LLM request
(non-streaming) → tool dispatch → append results. On completion or failure, raw data (messages, tokens, tool stats) is auto-dumped.
SubAgentProgress provides lightweight monitoring for TUI display.
"""
import os
import json
import time
import logging

from typing import Any
from openai import OpenAI
from openai.types.chat import ChatCompletion
from rich.console import Console
from rich.progress import Progress
from src.context.agent_context import AgentContext
from src.context.prompt import get_reasoning, deepseek_support
from src.tool.scoreboard import Scoreboard
from src.tool import tool_def
from src.tool.tool_dispatch import call_tools
from src.utility.basic_utils import truncate_tool_result
from src.agent.progress import AgentStatus, SubAgentProgress, SUPPORTED_TYPES, PERMISSION_PRESETS, SUPPORTED_TYPES_DESC
from src.constants import *

sys_log = logging.getLogger('logger')

# subagent config keys read from ctx.agent_configs at init time
_CONFIG_KEY_MAX_STEPS = "SUBAGENT_MAX_STEPS"
_CONFIG_KEY_WARN_STEPS = "SUBAGENT_EARLY_WARN_STEPS"
_CONFIG_KEY_MODEL_TYPE = "SUBAGENT_MODEL_TYPE"
_CONFIG_KEY_TIMEOUT_S = "SUBAGENT_TIMEOUT_S"
_CONFIG_KEY_API_RETRY = "SUBAGENT_API_RETRY_COUNT"
_CONFIG_KEY_TOOL_RESULT_LIMIT = "SUBAGENT_TOOL_RESULT_CHAR_LIMIT"

_TOOL_DISPLAY_KEYS: dict[str, str] = {
    # basic tools
    TOOL_NAME_CREATE_TASK: "subject",
    TOOL_NAME_UPDATE_TASK: "task_id",
    TOOL_NAME_QUERY_TASK: "task_id",
    TOOL_NAME_BASH: "description",
    TOOL_NAME_GLOB_FILE: "pattern",
    TOOL_NAME_GREP_FILE: "pattern",
    TOOL_NAME_READ_FILE: "path",
    TOOL_NAME_WRITE_FILE: "path",
    TOOL_NAME_EDIT_FILE: "path",
    TOOL_NAME_SKILL: "name",
    TOOL_NAME_WEB_FETCH: "url",
    TOOL_NAME_WEB_SEARCH: "query",
    # simulation tools
    TOOL_NAME_INIT_DESIGN: "subject",
    TOOL_NAME_QUERY_DESIGN: "design_id",
    TOOL_NAME_LAUNCH_SIM: "subject",
    TOOL_NAME_QUERY_RUN: "run_id",
    TOOL_NAME_READ_LOG: "run_id",
}


def format_tool_display(func_name: str, arguments: dict[str, Any]) -> str:
    """format tool call display with key argument, e.g. read_file(path), bash(description)"""
    key = _TOOL_DISPLAY_KEYS.get(func_name)
    if key is not None and key in arguments:
        val = str(arguments[key])
        if len(val) > SUBAGENT_TOOL_DISPLAY_MAX_LEN:
            val = val[:SUBAGENT_TOOL_DISPLAY_MAX_LEN] + "..."
        return f"{func_name} ({val})"
    return func_name


def clone_context(parent_ctx: AgentContext, agent_id: str, subagent_type: str) -> AgentContext:
    """clone parent AgentContext for subagent: share configs/LLM/MCP, own messages/tools/stats"""
    ctx = AgentContext()
    # configs
    ctx.args = parent_ctx.args
    ctx.api_configs = parent_ctx.api_configs
    ctx.agent_configs = parent_ctx.agent_configs
    ctx.mcps_configs = parent_ctx.mcps_configs
    # prompts
    ctx.messages = []
    ctx.tools = []
    ctx.skills = list(parent_ctx.skills)
    # objects
    ctx.agent_session = None
    ctx.llm_client = parent_ctx.llm_client
    ctx.url_caches = []
    ctx.wechat_bot = None
    ctx.last_wechat_msg = None
    ctx.mcp_router = parent_ctx.mcp_router
    ctx.durable_crons = []
    ctx.session_crons = []
    ctx.cron_tasks = []
    ctx.cron_ids = []
    ctx.active_cron = 0
    ctx.design_man = parent_ctx.design_man
    ctx.run_man = parent_ctx.run_man
    ctx.agent_list = {}
    ctx.background_agents = []
    # params
    ctx.agent_id = agent_id
    ctx.session_uuid = agent_id
    ctx.enable_wechat = False
    ctx.if_summarized = False
    ctx.session_title = f"subagent-{agent_id}"
    ctx.system_prompts = 0
    ctx.tools_prompts = 0
    ctx.user_prompts = 0
    ctx.content_prompts = 0
    ctx.reasoning_prompts = 0
    ctx.tool_calls_prompts = 0
    ctx.tool_results_prompts = 0
    ctx.total_llm_requests = 0
    ctx.total_input_tokens = 0
    ctx.total_output_tokens = 0
    ctx.total_tokens = 0
    ctx.total_uncached_tokens = 0
    ctx.last_input_tokens = 0
    ctx.last_output_tokens = 0
    ctx.last_tokens = 0
    ctx.system_read_only_paths = parent_ctx.system_read_only_paths
    ctx.read_only_paths = list(parent_ctx.read_only_paths)
    ctx.task_tool_unuse = 0
    ctx.files_read = {}
    ctx.loaded_skills = list(parent_ctx.loaded_skills)
    # signals
    ctx.task_end = True
    ctx.tui_mute = True
    ctx.permissions = dict(parent_ctx.permissions)

    if subagent_type in PERMISSION_PRESETS:
        for perm in PERMISSION_PRESETS[subagent_type]:
            ctx.permissions[perm] = True

    return ctx


class SubAgent:
    def __init__(
        self,
        parent_ctx: AgentContext,
        subagent_type: str,
        prompt: str,
        agent_id: str,
        subject: str = "",
        share_parent_board: bool = False,
        parent_board: Scoreboard | None = None,
        model_type: str | None = None,
        max_steps: int | None = None,
        warn_steps: int | None = None,
        console: Console | None = None,
    ):
        ac = parent_ctx.agent_configs

        if model_type is None:
            model_type = ac.get(_CONFIG_KEY_MODEL_TYPE, SUBAGENT_DEFAULT_MODEL_TYPE)
        if max_steps is None:
            max_steps = ac.get(_CONFIG_KEY_MAX_STEPS, SUBAGENT_DEFAULT_MAX_STEPS)
        if not isinstance(max_steps, int):
            max_steps = SUBAGENT_DEFAULT_MAX_STEPS
        if warn_steps is None:
            warn_steps = ac.get(_CONFIG_KEY_WARN_STEPS, SUBAGENT_DEFAULT_WARN_STEPS)
        if not isinstance(warn_steps, int):
            warn_steps = SUBAGENT_DEFAULT_WARN_STEPS

        timeout_s_raw = ac.get(_CONFIG_KEY_TIMEOUT_S)
        if not isinstance(timeout_s_raw, int):
            timeout_s_raw = SUBAGENT_DEFAULT_TIMEOUT_S
        self.timeout_s: float | None = float(timeout_s_raw) if timeout_s_raw is not None else None
        api_retries_raw = ac.get(_CONFIG_KEY_API_RETRY, 0)
        self._api_retries: int = int(api_retries_raw) if api_retries_raw is not None else 0
        tool_result_limit_raw = ac.get(_CONFIG_KEY_TOOL_RESULT_LIMIT)
        self._tool_result_limit: int = int(tool_result_limit_raw) if tool_result_limit_raw is not None else SUBAGENT_TOOL_RESULT_DEFAULT_CHAR_LIMIT

        if subagent_type not in SUPPORTED_TYPES:
            raise ValueError(f"Unknown subagent type: {subagent_type}. Supported: {list(SUPPORTED_TYPES.keys())}")
        if model_type not in ("main", "medium", "fast"):
            raise ValueError(f"Unknown model_type: {model_type}. Supported: main, medium, fast")
        """manage input args"""
        self.ctx = clone_context(parent_ctx, agent_id, subagent_type)
        self._parent_session_uuid = parent_ctx.session_uuid

        self.subagent_type = subagent_type
        self.subject = subject
        self.prompt = prompt
        self.agent_id = agent_id
        # only plan agent can manage real scoreboard (other agent's scoreboard is independent)
        self._share_parent_board = share_parent_board
        if share_parent_board:
            if parent_board is None:
                raise ValueError("share_parent_board=True requires parent_board to be provided")
            self.board = parent_board
            self._own_board = False
        else:
            self.board = Scoreboard()
            self.board.session_uuid = self.ctx.session_uuid
            self._own_board = True

        self.model_type = model_type
        self.model = self.ctx.api_configs[f"{self.model_type.upper()}_MODEL_NAME"]
        self.max_steps = max_steps
        self.warn_steps = warn_steps
        self._parent_console = console
        self._dummy_progress = self._make_dummy_progress()
        """inner status"""
        self.status = AgentStatus.PENDING
        self.result: str | None = None
        self.error: str | None = None
        self._last_api_error: str | None = None
        self.start_time: float = 0.0
        self.stats: dict[str, int] = {  # for LLM statistics
            "user_prompts": 0,
            "content_prompts": 0,
            "reasoning_prompts": 0,
            "tool_calls_prompts": 0,
            "tool_results_prompts": 0,
            "total_llm_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_uncached_tokens": 0,
        }

        self.progress = SubAgentProgress(  # don't show tasks, because plan agent may toggle the real scoreboard but other don't
            agent_id=agent_id,
            subagent_type=subagent_type,
            subject=subject,
            status=AgentStatus.PENDING,
            last_activity=time.time(),
        )

        log_msg = f"SubAgent {agent_id} ({subagent_type}, {subject}) initialized: {self.prompt[:SUBAGENT_PROMPT_LOG_CHAR_LEN]}..."
        sys_log.debug(log_msg)
        if self._parent_console:
            self._parent_console.print(
                f"[{MAJOR_COLOR2}]SubAgent[/{MAJOR_COLOR2}] {subagent_type} [bright_black]{agent_id}[/bright_black] initialized"
            )

    def build_tools(self):
        allowed = SUPPORTED_TYPES.get(self.subagent_type, ())
        self.ctx.tools = tool_def.create_tools_prompts(self.ctx)

        if len(allowed) == 0:
            self.ctx.tools = [
                t for t in self.ctx.tools
                if t.get("function", {}).get("name", "") not in (
                    TOOL_NAME_ASK_QUESTION,
                    TOOL_NAME_CREATE_CRON,
                    TOOL_NAME_QUERY_CRON,
                    TOOL_NAME_REMOVE_CRON,
                )
            ]
        else:
            self.ctx.tools = [
                t for t in self.ctx.tools
                if t.get("function", {}).get("name", "") in allowed
                    and t.get("function", {}).get("name", "") != TOOL_NAME_ASK_QUESTION
            ]
        self.ctx.tools_prompts = len(self.ctx.tools)

    def build_messages(self):
        if self._share_parent_board:
            board_note = (
                f"Your scoreboard is SHARED with the main agent. Tasks you create appear immediately on the "
                f"main agent's task list.\n"
                f"Your role is PLANNING: create UNOWNED tasks for the main agent to execute. Do NOT execute tasks yourself "
                f"(you may claim a task only to delete it if it was created incorrectly).\n"
                f"Use `{TOOL_NAME_CREATE_TASK}` to break work into milestones, `{TOOL_NAME_UPDATE_TASK}` for dependencies "
                f"and corrections (claim then delete), and `{TOOL_NAME_QUERY_TASK}` to verify the task state.\n\n"
            )
        else:
            board_note = (
                f"You have your own INDEPENDENT scoreboard for tracking your workflow. Use `{TOOL_NAME_CREATE_TASK}` / "
                f"`{TOOL_NAME_UPDATE_TASK}` / `{TOOL_NAME_QUERY_TASK}` as needed.\n\n"
            )
        system_text = (
            f"You are a `{self.subagent_type}` subagent spawned by the main TECoSim agent.\n\n"
            f"Your task: {self.prompt}\n\n"
            f"{board_note}"
            "Work step by step. Use tools to gather information or make changes. When you are done, provide your final answer "
            "as plain text (no tool calls). Do not ask the user questions – you are running autonomously.\n"
            "The bash tool uses GNU bash (Git Bash on Windows). Do NOT use PowerShell/cmd.exe commands.\n\n"
            f"Available agent types for reference:\n"
            f"{', '.join(f'{k}: {v}' for k, v in SUPPORTED_TYPES_DESC.items())}"
        )
        self.ctx.messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": self.prompt},
        ]
        self.ctx.system_prompts = 1
        self.ctx.user_prompts = 1
        self.stats["user_prompts"] = 1

        sys_log.debug(f"SubAgent {self.agent_id} ({self.subagent_type}) init: model={self.model}, "
                      f"steps={self.max_steps}, msgs={len(self.ctx.messages)}, tools={len(self.ctx.tools)}, "
                      f"prompt={self.prompt[:SUBAGENT_PROMPT_LOG_CHAR_LEN]}...")

    def run(self) -> str | None:
        if self.status != AgentStatus.PENDING:
            return self.result
        self.status = AgentStatus.RUNNING
        self.progress.status = AgentStatus.RUNNING
        self.start_time = time.time()
        self.progress.start_time = self.start_time

        try:
            assert self.max_steps is not None
            for step in range(1, self.max_steps + 1):
                """check if timeout"""
                if self.timeout_s is not None and time.time() - self.start_time > self.timeout_s:
                    self.status = AgentStatus.TIMEOUT
                    self.error = f"Timeout after {self.timeout_s:.0f}s"
                    break
                """check step budget"""
                if (self.max_steps - step) <= self.warn_steps:
                    if step == self.max_steps:
                        info = (f"{SYS_REMINDER_START_LABEL}\n"
                                f"CRITICAL — This is your final step ({step}/{self.max_steps}) to gather the final results. "
                                f"From now on, NEVER EVER make any tool calls (including workflow tools)! If you call tools "
                                f"in your following content, the agent will be force-exited on the next round without returning "
                                f"any of your result to the main agent. Reply with your final results as plain text IMMEDIATELY!\n"
                                f"(If your step budget is too small to finish your tasks, ALWAYS report this warning in your "
                                f"final results)\n"
                                f"{SYS_REMINDER_END_LABEL}")
                        self.ctx.messages.append({"role": "user", "content": info})
                    else:
                        info = (f"{SYS_REMINDER_START_LABEL}\n"
                                f"WARNING — You have ONLY {self.max_steps - step + 1} steps left (step {step}/{self.max_steps}). "
                                f"Begin wrapping up. Avoid non-essential tool calls and prepare your final results. You "
                                f"will be force-exited when steps run out, losing all unsaved work.\n"
                                f"{SYS_REMINDER_END_LABEL}")
                        self.ctx.messages.append({"role": "user", "content": info})

                self.progress.step = step
                self.progress.status = AgentStatus.RUNNING
                self.progress.last_activity = time.time()

                response = self.llm_request()
                if response is None:
                    self.status = AgentStatus.ERROR
                    self.error = (f"LLM request failed after {1 + self._api_retries} attempts. Last error: "
                                  f"{self._last_api_error or UNKNOWN_LABEL}")
                    break

                tool_calls, content, reasoning = self.parse_response(response)

                if tool_calls:
                    self.execute_tool_calls(tool_calls)
                    count = len(tool_calls)
                    self.progress.tool_calls_done += count
                    self.stats["tool_calls_prompts"] += count
                    continue

                if content:
                    self.result = content
                    self.status = AgentStatus.DONE
                    self.progress.status = AgentStatus.DONE
                    break

                if reasoning:
                    self.result = reasoning
                    self.status = AgentStatus.DONE
                    self.progress.status = AgentStatus.DONE
                    sys_log.warning(f"SubAgent {self.agent_id}: final response is reasoning-only, falling back")
                    break

                sys_log.error(f"SubAgent {self.agent_id}: empty response at step {step}")
                self.status = AgentStatus.ERROR
                self.error = "No content, tool calls, or reasoning in response"
                break
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.error = str(e)
            sys_log.error(f"SubAgent {self.agent_id} failed: {e}")
        finally:
            if self.start_time > 0:
                self.progress.elapsed_s = time.time() - self.start_time
            self.dump()

        return self.result

    def llm_request(self):
        client: OpenAI = self.ctx.llm_client
        prefix = f"{self.model_type.upper()}_MODEL_"

        params: dict[str, Any] = {
            "model": self.model,
            "temperature": self.ctx.api_configs.get(f"{prefix}TEMPERATURE"),
            "max_tokens": self.ctx.api_configs.get(f"{prefix}MAX_TOKENS"),
            "stream": False,
            "messages": self.ctx.messages,
            "tools": self.ctx.tools,
            "timeout": self.ctx.api_configs.get("TIMEOUT_MS", DEFAULT_TIMEOUT_MS) / 1000,
        }

        if self.ctx.api_configs.get(f"{prefix}ENABLE_REASONING"):
            params["reasoning_effort"] = self.ctx.api_configs.get(f"{prefix}REASONING_EFFORT")

        if self.ctx.api_configs.get(f"{prefix}DEEPSEEK_SUPPORT"):
            if self.ctx.api_configs.get(f"{prefix}ENABLE_REASONING"):
                params["extra_body"] = {"thinking": {"type": "enabled"}}
            else:
                params["extra_body"] = {"thinking": {"type": "disabled"}}

        self.ctx.total_llm_requests += 1
        self.stats["total_llm_requests"] += 1

        msg_count = len(self.ctx.messages)
        if msg_count == 0:
            sys_log.error(f"SubAgent {self.agent_id}: empty messages list, aborting")
            return None

        sys_log.debug(f"SubAgent {self.agent_id} step: {msg_count} messages, model={self.model}, tools={len(self.ctx.tools)}")
        response = None
        total_attempts = 1 + self._api_retries
        self._last_api_error = None
        for attempt in range(1, total_attempts + 1):
            try:
                response = client.chat.completions.create(**params)
                break
            except Exception as e:
                self._last_api_error = str(e)
                sys_log.warning(f"SubAgent {self.agent_id} API call failed (attempt {attempt}/{total_attempts}): {e}")
                if attempt < total_attempts:
                    time.sleep(1)
        if response is None:
            sys_log.error(f"SubAgent {self.agent_id} API call failed after {total_attempts} attempts, "
                          f"model={self.model}, msgs={msg_count}, last_error={self._last_api_error}")
            return None
        assert isinstance(response, ChatCompletion)

        usage = response.usage
        if usage is not None:
            self.ctx.total_input_tokens += usage.prompt_tokens
            self.ctx.last_input_tokens = usage.prompt_tokens
            self.ctx.total_output_tokens += usage.completion_tokens
            self.ctx.last_output_tokens = usage.completion_tokens
            self.ctx.total_tokens += usage.total_tokens
            self.ctx.last_tokens = usage.total_tokens
            if usage.prompt_tokens_details is not None:
                cached_tokens = usage.prompt_tokens_details.cached_tokens or 0
                uncached_tokens = usage.prompt_tokens - cached_tokens
                self.ctx.total_uncached_tokens += uncached_tokens
                self.stats["total_uncached_tokens"] += uncached_tokens
            self.stats["total_input_tokens"] += usage.prompt_tokens
            self.stats["total_output_tokens"] += usage.completion_tokens
            self.stats["total_tokens"] += usage.total_tokens
            self.progress.input_tokens += usage.prompt_tokens
            self.progress.output_tokens += usage.completion_tokens

        return response

    def parse_response(self, response) -> tuple[list[dict[str, Any]] | None, str | None, str | None]:
        choice = response.choices[0]
        message = choice.message

        dumped_msg = message.model_dump(mode="json")
        if self.ctx.api_configs.get(f"{self.model_type.upper()}_MODEL_DEEPSEEK_SUPPORT"):
            dumped_msg = deepseek_support(dumped_msg)
        self.ctx.messages.append(dumped_msg)

        assistant_reasoning = get_reasoning(dumped_msg)
        content: str | None = dumped_msg.get("content", None)
        tool_calls: list[dict[str, Any]] | None = dumped_msg.get("tool_calls", None)

        if content is not None and len(content.strip()) == 0:
            content = None

        if assistant_reasoning is not None:
            self.ctx.reasoning_prompts += 1
            self.stats["reasoning_prompts"] += 1
        if content is not None:
            self.ctx.content_prompts += 1
            self.stats["content_prompts"] += 1

        return tool_calls, content, assistant_reasoning

    def execute_tool_calls(self, tool_calls: list[dict[str, Any]]):
        user_addons: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                self.ctx.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps({"status": FAIL_LABEL, "info": "Invalid tool call arguments"}, ensure_ascii=False),
                })
                continue

            self.progress.current_tool = format_tool_display(func_name, arguments)
            self.progress.last_activity = time.time()

            results, user_addon = call_tools(
                func_name, arguments, self.ctx, self.board, self._dummy_progress
            )
            result_str = truncate_tool_result(
                results, self._tool_result_limit, TOOL_RESULT_TRUNCATION_ROUNDS
            )
            self.ctx.messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result_str,
            })
            if self.ctx.api_configs.get(f"{self.model_type.upper()}_MODEL_DEEPSEEK_SUPPORT"):
                if user_addon is not None:
                    user_addons.append(user_addon)
            else:
                if user_addon is not None:
                    self.ctx.messages.append({
                        "role": "user",
                        "content": json.dumps(user_addon, ensure_ascii=False),
                    })

        if self.ctx.api_configs.get(f"{self.model_type.upper()}_MODEL_DEEPSEEK_SUPPORT"):
            for addon in user_addons:
                self.ctx.messages.append({
                    "role": "user",
                    "content": json.dumps(addon, ensure_ascii=False),
                })

        self.ctx.tool_results_prompts += len(tool_calls)
        self.stats["tool_results_prompts"] += len(tool_calls)

    @staticmethod
    def _make_dummy_progress() -> Progress:
        console = Console(quiet=True)
        progress = Progress(console=console, disable=True)
        progress.start()
        return progress

    def dump(self):
        try:
            agent_dir = os.path.join(SESSION_PATH, self._parent_session_uuid, SUBAGENT_DUMP_DIR, self.agent_id)
            os.makedirs(agent_dir, exist_ok=True)

            self.progress.status = self.status

            with open(os.path.join(agent_dir, CONTEXT_NAME), "w", encoding="utf-8") as f:
                json.dump(self.ctx.to_dict(self._parent_console or Console(quiet=True), mute=True),
                          f, indent=2, ensure_ascii=False)

            with open(os.path.join(agent_dir, MESSAGES_NAME), "w", encoding="utf-8") as f:
                json.dump(self.ctx.messages, f, indent=2, ensure_ascii=False)

            with open(os.path.join(agent_dir, "stats.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "agent_id": self.agent_id,
                    "subagent_type": self.subagent_type,
                    "model": self.model,
                    "model_type": self.model_type,
                    "prompt": self.prompt,
                    "parent_session": self._parent_session_uuid,
                    "session_uuid": self.ctx.session_uuid,
                    "status": self.status,
                    "result": self.result,
                    "error": self.error,
                    "timeout_s": self.timeout_s,
                    "max_steps": self.max_steps,
                    "stats": self.stats,
                }, f, indent=2, ensure_ascii=False)

            if self._own_board:
                with open(os.path.join(agent_dir, TASKS_NAME), "w", encoding="utf-8") as f:
                    json.dump(self.board.to_dict(), f, indent=2, ensure_ascii=False)

            self.progress.last_activity = time.time()
            sys_log.debug(f"SubAgent {self.agent_id} ({self.status.value}) dumped to {agent_dir}")
        except Exception as e:
            sys_log.error(f"SubAgent {self.agent_id} dump failed: {e}")


def merge_agent_stats(ctx: AgentContext, agent: SubAgent):
    """merge the subagent's statistic into context"""
    ctx.user_prompts += agent.stats["user_prompts"]
    ctx.content_prompts += agent.stats["content_prompts"]
    ctx.reasoning_prompts += agent.stats["reasoning_prompts"]
    ctx.tool_calls_prompts += agent.stats["tool_calls_prompts"]
    ctx.tool_results_prompts += agent.stats["tool_results_prompts"]
    ctx.total_llm_requests += agent.stats["total_llm_requests"]
    ctx.total_input_tokens += agent.stats["total_input_tokens"]
    ctx.total_output_tokens += agent.stats["total_output_tokens"]
    ctx.total_tokens += agent.stats["total_tokens"]
    ctx.total_uncached_tokens += agent.stats["total_uncached_tokens"]
