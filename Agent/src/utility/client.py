# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.7\n
Description: Client configs and methods

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.7       Yu Huang     1.0               First implementation\n
2026.4.15      Yu Huang     1.1               Tools requests realization\n
2026.4.16      Yu Huang     1.2               Agent context realization with logic merge\n
2026.4.26      Yu Huang     1.3               More LLM configs support\n
2026.4.29      Yu Huang     1.4               Builtin commands support\n
2026.5.19      Yu Huang     1.5               Model classification support\n
2026.5.20      Yu Huang     1.6               Refactor llm_request_with_spinner and move to client.py\n
2026.5.21      Yu Huang     1.7               Move load_configs to basic_utils.py\n
2026.5.23      Yu Huang     1.8               Stream response display update\n
2026.5.30      Yu Huang     1.9               Random spinner title support & Revise spinner logic with SIGINT pass through\n

Details:
Client configuration, creation
------------------------------------------------------------------------------------------------------------------------
"""
import random
import logging

from openai import OpenAI
from rich.console import Console
from typing import Callable, Any
from src.utility.ui_info import loading_spinner_rap
from src.context.agent_context import RequestLLMCancelled
from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def config_client(ctx: AgentContext, console: Console) -> OpenAI:
    """config LLM client with given API configs"""
    try:
        client = OpenAI(
            api_key=ctx.api_configs["API_KEY"],
            base_url=ctx.api_configs["API_URL"]
        )
        sys_log.debug("Config client with API configs done")
        console.print(f"Main LLM model: [{MAJOR_COLOR2}]{ctx.api_configs["MAIN_MODEL_NAME"]}[/{MAJOR_COLOR2}]")
        console.print(f"Fast LLM model: [{MAJOR_COLOR2}]{ctx.api_configs["FAST_MODEL_NAME"]}[/{MAJOR_COLOR2}]")
        return client
    except Exception as e:
        sys_log.error(f"Failed to config client with API configs with error: {e}")
        console.print(f"Failed to config client with API configs with error: {e}", style="bold red")
        raise RuntimeError(e)


def llm_request_with_spinner(func: Callable, *args,
                             waiting_desc: str | None = None, done_desc: str | None = None,
                             intrp_desc: str | None = None, fail_desc: str | None = None,
                             spinner: str | None = None, if_random: bool, **kwargs) -> Any:
    """LLM request with spinner through loading_spinner_rap"""
    if waiting_desc is not None:
        waiting_title = waiting_desc
    else:
        if if_random:
            waiting_title = random.choice(LLM_REQUEST_TITLE_LIST)
        else:
            waiting_title = LLM_REQUEST_TITLE_LIST[0]
    if done_desc is not None:
        done_title = done_desc
    else:
        done_title = LLM_REQUEST_DONE_TITLE
    if intrp_desc is not None:
        intrp_title = intrp_desc
    else:
        intrp_title = LLM_REQUEST_INTRP_TITLE
    if fail_desc is not None:
        fail_title = fail_desc
    else:
        fail_title = LLM_REQUEST_FAIL_TITLE
    if spinner is not None:
        spinner_choice = spinner
    else:
        spinner_choice = LLM_REQUEST_SPINNER
    result = loading_spinner_rap(func, *args,
                                 waiting_desc=waiting_title, done_desc=done_title,
                                 intrp_desc=intrp_title, fail_desc=fail_title,
                                 spinner=spinner_choice,
                                 out_except=RequestLLMCancelled("LLM request is cancelled by user"), **kwargs)
    return result


def request_loop_main(client: OpenAI, ctx: AgentContext):
    """Create main LLM model request with LLM client and AgentContext for main loop of agent"""
    params: dict[str, Any] = {
        "model": ctx.api_configs["MAIN_MODEL_NAME"],
        "temperature": ctx.api_configs["MAIN_MODEL_TEMPERATURE"],
        "max_tokens": ctx.api_configs["MAIN_MODEL_MAX_TOKENS"],
        "stream": ctx.api_configs["MAIN_MODEL_STREAM"],
        "messages": ctx.messages,
        "tools": ctx.tools,
        "timeout": ctx.api_configs["TIMEOUT_MS"] / 1000
    }
    """reasoning support"""
    if ctx.api_configs["MAIN_MODEL_ENABLE_REASONING"]:
        params["reasoning_effort"] = ctx.api_configs["MAIN_MODEL_REASONING_EFFORT"]
    else:
        params["reasoning_effort"] = None
    """deepseek support"""
    if ctx.agent_configs["DEEPSEEK_SUPPORT"]:
        if ctx.api_configs["MAIN_MODEL_ENABLE_REASONING"]:
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            params["extra_body"] = {"thinking": {"type": "disabled"}}
    ctx.total_llm_requests += 1
    response = client.chat.completions.create(**params)
    return response


def request_branch_fast(client: OpenAI, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
                        api_configs: dict[str, Any], agent_configs: dict[str, Any]):
    """Create fast LLM model request with LLM client, messages, tools, configs for non-loop of agent"""
    params: dict[str, Any] = {
        "model": api_configs["FAST_MODEL_NAME"],
        "temperature": api_configs["FAST_MODEL_TEMPERATURE"],
        "max_tokens": api_configs["FAST_MODEL_MAX_TOKENS"],
        "stream": False,  # Fast model disable stream response
        "messages": messages,
        "timeout": api_configs["TIMEOUT_MS"] / 1000
    }
    """tools"""
    if tools is not None:
        params["tools"] = tools
    """reasoning support"""
    if api_configs["FAST_MODEL_ENABLE_REASONING"]:
        params["reasoning_effort"] = api_configs["FAST_MODEL_REASONING_EFFORT"]
    else:
        params["reasoning_effort"] = None
    """deepseek support"""
    if agent_configs["DEEPSEEK_SUPPORT"]:
        if api_configs["FAST_MODEL_ENABLE_REASONING"]:
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            params["extra_body"] = {"thinking": {"type": "disabled"}}
    response = client.chat.completions.create(**params)
    return response
