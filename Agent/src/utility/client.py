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

Details:
Client configuration, creation
------------------------------------------------------------------------------------------------------------------------
"""
import logging
import json

from openai import OpenAI
from rich.console import Console
from typing import Any
from src.constants import *
from src.context.session import AgentContext

sys_log = logging.getLogger('logger')


def load_configs(configs_path: str, name: str, console: Console) -> dict[str, Any]:
    """load JSON configs with given path"""
    try:
        with open(configs_path, 'r', encoding="utf-8") as file:
            api_configs = json.load(file)
            sys_log.debug(f"Load {name} configs from {configs_path} done")
            return api_configs
    except Exception as e:
        sys_log.error(f"Failed to load {name} configs from {configs_path} with error: {e}")
        console.print(f"Failed to load {name} configs from {configs_path} with error: {e}", style="bold red")
        raise RuntimeError(e)


def config_client(ctx: AgentContext, console: Console) -> OpenAI:
    """config LLM client with given API configs"""
    try:
        client = OpenAI(
            api_key=ctx.api_configs["API_KEY"],
            base_url=ctx.api_configs["API_URL"]
        )
        sys_log.debug("Config client with API configs done")
        console.print(f"LLM client model: [{MAJOR_COLOR2}]{ctx.api_configs["MODEL_NAME"]}[{MAJOR_COLOR2}]")
        return client
    except Exception as e:
        sys_log.error(f"Failed to config client with API configs with error: {e}")
        console.print(f"Failed to config client with API configs with error: {e}", style="bold red")
        raise RuntimeError(e)


def create_request(client: OpenAI, ctx: AgentContext):
    """Create LLM request with given LLM client, API configs and messages"""
    params: dict[str, Any] = {
        "model": ctx.api_configs["MODEL_NAME"],
        "temperature": ctx.api_configs["MODEL_TEMPERATURE"],
        "reasoning_effort": ctx.api_configs["MODEL_REASONING_EFFORT"],
        "max_tokens": ctx.api_configs["MODEL_MAX_TOKENS"],
        "messages": ctx.messages,
        "tools": ctx.tools,
        "timeout": ctx.api_configs["TIMEOUT_MS"] / 1000
    }
    if ctx.agent_configs["DEEPSEEK_SUPPORT"]:
        if ctx.api_configs["MODEL_ENABLE_REASONING"]:
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            params["extra_body"] = {"thinking": {"type": "disabled"}}
    response = client.chat.completions.create(**params)
    return response

class RequestLLMCancelled(Exception):
    """Raised when user cancels requesting LLM."""