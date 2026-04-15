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

Details:
Client configuration, creation
------------------------------------------------------------------------------------------------------------------------
"""
import logging
import json

from openai import OpenAI
from rich.console import Console
from typing import Dict, Any
from src.constants import *
sys_log = logging.getLogger('logger')


def load_configs(configs_path: str, name: str = "") -> Dict[str, Any]:
    """load json configs with given path"""
    try:
        with open(configs_path, 'r') as file:
            api_configs = json.load(file)
            sys_log.debug(f"Load {name} configs from {configs_path} done")
            return api_configs
    except Exception as e:
        sys_log.error(f"Failed to load {name} configs from {configs_path} with error: {e}")
        return {"NULL": None}


def config_client(api_configs: Dict[str, Any], console: Console) -> OpenAI:
    """config LLM client with given API configs"""
    try:
        client = OpenAI(
            api_key=api_configs["API_KEY"],
            base_url=api_configs["API_URL"]
        )
        sys_log.debug("Config client with API configs done")
        console.print(f"LLM client model: [{MAJOR_COLOR2}]{api_configs["MODEL_NAME"]}[{MAJOR_COLOR2}]")
        return client
    except Exception as e:
        sys_log.error(f"Failed to config client with API configs with error: {e}")
        console.print(f"[bold red]Failed to config client with API configs with error: {e}[/bold red]")
        client = OpenAI()
        return client


def create_request(client: OpenAI, api_configs: Dict[str, Any], messages, tools):
    """Create LLM request with given LLM client, API configs and messages"""
    response = client.chat.completions.create(
        model=api_configs["MODEL_NAME"],
        messages=messages,
        tools=tools,
        temperature=api_configs["MODEL_TEMPERATURE"],
        timeout=api_configs["TIMEOUT_MS"] / 1000
    )
    return response
