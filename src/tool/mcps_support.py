# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.21
Description: MCPs support

Revision:
---------
2026.5.21-22   Yu Huang      1.0      First implementation
2026.5.31      Yu Huang      1.1      Add keyboard interrupt & Define used file/dir. paths in constants.py
2026.6.1       Yu Huang      1.2      Define all used status labels in constants.py
2026.6.12      Yu Huang      1.3      Add threading lock in MCP router for subagent coordination
2026.7.23      Yu Huang      1.4      Add launch support in arbitrary path

Details:
---------
MCP (Model Context Protocol) integration. Configures MCP clients via stdio/http/sse transports using fastmcp. `MCPToolRouter`
registers all MCP tool schemas (OpenAI-compatible) into the agent's tool list, maintains a tool-to-client registry, and
provides sync/async tool-call dispatch. Supports CLI operations for MCP server management (add/toggle/remove).
"""
import json
import asyncio
import logging
import threading

from typing import Any
from argparse import Namespace
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport, SSETransport
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from src.utility.basic_utils import load_configs, write_configs
from src.constants import *

sys_log = logging.getLogger('logger')


def config_mcps(configs: list[dict[str, Any]], init_timeout: int, timeout: int, console: Console) -> list[Client]:
    """configure MCPs from config file"""
    client_lists: list[Client] = []
    disabled_num = 0
    for config in configs:
        # get the client according to the config
        try:
            name = config["name"]
            if_disabled = config["if_disabled"]
            if if_disabled:
                disabled_num += 1
                continue
            mcp_type = config["type"]
            if mcp_type == "stdio":
                transport = StdioTransport(
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env"),
                    cwd=config.get("cwd"),
                    keep_alive=config.get("keep_alive", True),
                    log_file=config.get("log_file"),
                )
                client = Client(name=name, transport=transport, timeout=timeout, init_timeout=init_timeout)
                client_lists.append(client)
            elif mcp_type == "http":
                transport = StreamableHttpTransport(
                    url=config["url"],
                    headers=config.get("headers"),
                    auth=config.get("auth"),
                    sse_read_timeout=config.get("sse_read_timeout"),
                    httpx_client_factory=config.get("httpx_client_factory"),
                    verify=config.get("verify"),
                )
                client = Client(name=name, transport=transport, timeout=timeout, init_timeout=init_timeout)
                client_lists.append(client)
            elif mcp_type == "sse":
                transport = SSETransport(
                    url=config["url"],
                    headers=config.get("headers"),
                    auth=config.get("auth"),
                    sse_read_timeout=config.get("sse_read_timeout"),
                    httpx_client_factory=config.get("httpx_client_factory"),
                    verify=config.get("verify"),
                )
                client = Client(name=name, transport=transport, timeout=timeout, init_timeout=init_timeout)
                client_lists.append(client)
            else:
                raise RuntimeError(f"Unknown MCP type: {mcp_type}")
            sys_log.debug(f"MCP: {name} with type: {mcp_type} configured")
            console.print(f"MCP: [{MAJOR_COLOR2}]{name}[/{MAJOR_COLOR2}] with type: [{MAJOR_COLOR2}]{mcp_type}[/{MAJOR_COLOR2}] configured")
        except Exception as e:
            sys_log.warning(f"Configure MCP with config: {config} failed with error: {e}")
            console.print(f"Configure MCP with config: {config} failed with error: {e}", style="bold yellow")
            continue
    sys_log.debug(f"Configured {len(client_lists)} MCPs from config file. {disabled_num} out of {len(configs)} available MCPs disabled")
    console.print(f"Configured [{MAJOR_COLOR2}]{len(client_lists)}[/{MAJOR_COLOR2}] MCPs from config file. "
                  f"[{MAJOR_COLOR2}]{disabled_num}[/{MAJOR_COLOR2}] out of [{MAJOR_COLOR2}]{len(configs)}[/{MAJOR_COLOR2}] available MCPs disabled")
    return client_lists


class MCPToolRouter:
    """MCP tools router class"""
    def __init__(self, clients: list[Client]):
        self.clients: list[Client] = clients
        self.reg_tools: list[dict[str, Any]] = []  # all registered tools in OpenAI schema
        self.tool_registry: dict[str, Client] = {}  # tool name -> Client map
        self.mcps_ini_info: dict[str, dict[str, Any]] = {}  # MCP name -> MCP initialize info map
        self.mcps_tools: dict[str, list[dict[str, Any]]] = {}  # MCP name -> registered tools {name, desc} name map
        self._call_lock = threading.Lock()


    async def reg_all_tools(self, console: Console):
        """register the tool JSON schema of all configured MCP clients"""
        self.reg_tools = []
        self.tool_registry = {}
        self.mcps_ini_info = {}
        self.mcps_tools = {}
        try:
            for client in self.clients:
                async with client:
                    mcp_info = client.initialize_result
                    if mcp_info is None:
                        self.mcps_ini_info[client.name] = {"None": None}
                    else:
                        self.mcps_ini_info[client.name] = mcp_info.model_dump()
                    self.mcps_tools[client.name] = []
                    tools = await client.list_tools()
                    for tool in tools:
                        # same name tool
                        if tool.name in self.tool_registry:
                            sys_log.warning(f"Tool name of {tool.name} in MCP: {client.name} is not registered. A same-named "
                                            f"tool already exists in active MCP: {self.tool_registry[tool.name].name}")
                            console.print(f"Tool name of {tool.name} in MCP: {client.name} is not registered. A same-named "
                                          f"tool already exists in active MCP: {self.tool_registry[tool.name].name}", style="bold yellow")
                            continue
                        # register tool
                        self.tool_registry[tool.name] = client
                        self.reg_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            }
                        })
                        self.mcps_tools[client.name].append({"name": tool.name, "description": tool.description})
            sys_log.debug(f"Registered {len(self.reg_tools)} MCP tools from {len(self.clients)} active MCPs")
            console.print(f"Registered [{MAJOR_COLOR2}]{len(self.reg_tools)}[/{MAJOR_COLOR2}] MCP tools from "
                          f"[{MAJOR_COLOR2}]{len(self.clients)}[/{MAJOR_COLOR2}] active MCPs")
        except Exception as e:
            sys_log.error(f"Register MCP tools failed with error: {e}")
            console.print(f"Register MCP tools failed with error: {e}", style="bold red")
            raise RuntimeError(f"Register MCP tools failed with error: {e}")


    def reg_all_tools_sync(self, console: Console):
        """register the tool JSON schema of all configured MCP clients (sync wrapper)"""
        asyncio.run(self.reg_all_tools(console))


    def update_mcp_permission(self, permissions: dict[str, bool], console: Console, enable_all_mcp: bool = False):
        """update permissions list with MCP tools"""
        num = 0
        for tool, _ in self.tool_registry.items():
            if tool in permissions:
                continue
            else:
                permissions[tool] = enable_all_mcp
                num += 1
        sys_log.debug(f"Updated {num} MCP tools' permission")
        console.print(f"Updated [{MAJOR_COLOR2}]{num}[/{MAJOR_COLOR2}] MCP tools' permission")


    async def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: int, console: Console)\
            -> tuple[dict[str, Any] | None, str]:
        """try to call the input tool with name"""
        client = self.tool_registry.get(tool_name)
        if not client:
            return None, f"Tool {tool_name} is not registered"
        try:
            async with client:
                raw_results = await client.call_tool_mcp(name=tool_name, arguments=arguments, timeout=timeout)
                results = raw_results.model_dump()
                return results, SUCCESS_LABEL
        except KeyboardInterrupt:
            sys_log.warning(f"Call tool with name: {tool_name} in MCP {client.name} is cancelled by user")
            console.print(f"Call tool with name: {tool_name} in MCP {client.name} is cancelled by user", style="bold yellow")
            return None, f"Call tool with name: {tool_name} in MCP {client.name} is cancelled by user"
        except Exception as e:
            sys_log.error(f"Call tool with name: {tool_name} in MCP {client.name} failed with error: {e}")
            console.print(f"Call tool with name: {tool_name} in MCP {client.name} failed with error: {e}", style="bold red")
            return None, f"Call tool with name: {tool_name} in MCP {client.name} failed with error: {e}"


    def call_tool_sync(self, tool_name: str, arguments: dict[str, Any], timeout: int, console: Console)\
            -> tuple[dict[str, Any] | None, str]:
        """try to call the input tool with name (sync wrapper, thread-safe)"""
        with self._call_lock:
            results, info = asyncio.run(self.call_tool(tool_name, arguments, timeout, console))
        return results, info


def mcp_entry_cli(args: Namespace, console: Console):
    """MCP CLI operations support"""
    if args.command != "mcp":
        return

    """read configs"""
    mcps_configs = load_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), name="MCPs", console=console)
    if not (isinstance(mcps_configs, list) and all(isinstance(item, dict) for item in mcps_configs)):
        sys_log.warning(f"MCPs configs should be list of dict")
        console.print(f"MCPs configs should be list of dict", style="bold yellow")

    """MCP operations"""
    if args.mcp_action == 'list':
        mcp_list_cli(mcps_configs, console)
    elif args.mcp_action == 'add':
        mcp_add_cli(mcps_configs, args, console)
    elif args.mcp_action == 'toggle':
        mcp_toggle_cli(mcps_configs, args, console)
    elif args.mcp_action == 'remove':
        mcp_remove_cli(mcps_configs, args, console)
    else:
        sys_log.warning(f"Unknown MCP action: {args.mcp_action}")
        console.print(f"Unknown MCP action: {args.mcp_action}", style="bold yellow")
        sys.exit(-1)

    """MCP action doesn't entry main program"""
    sys_log.info("Program end for MCP entry cli")
    sys.exit(0)


def mcp_list_cli(mcps_configs: list[dict[str, Any]], console: Console):
    """MCP CLI operations support for listing all MCP servers"""
    title = f"Available MCPs ({len(mcps_configs)})"

    cmd_str = Text()
    for config in mcps_configs:
        cmd_str.append(f"{config["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f", MCP transport type: ", style=f"white")
        cmd_str.append(f"{config["type"]}", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f", if enabled: ", style=f"white")
        if not config["if_disabled"]:
            cmd_str.append("True\n", style=f"bold {MAJOR_COLOR1}")
        else:
            cmd_str.append("False\n", style="bright_black")
    if cmd_str.plain.endswith("\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))


def mcp_add_cli(mcps_configs: list[dict[str, Any]], args: Namespace, console: Console):
    """MCP CLI operations support for adding an MCP server"""
    try:
        """find the target MCP server"""
        for idx, config in enumerate(mcps_configs):
            if config["name"] == args.name:
                sys_log.error(f"There is already an MCP server with name: {args.name}")
                console.print(f"There is already an MCP server with name: {args.name}", style="bold red")
                return

        params = json.loads(args.params)
        if not isinstance(params, dict):
            sys_log.error(f"MCP params must be a JSON object (dictionary), not array or primitive")
            console.print(f"MCP params must be a JSON object (dictionary), not array or primitive", style="bold red")
            return
        params["if_disabled"] = False
        """check and modify MCP params"""
        name = args.name
        params["name"] = name
        mcp_type = args.type
        params["type"] = mcp_type
        if mcp_type == "stdio":
            if not params.get("command"):
                raise RuntimeError(f"stdio MCP need argument of \"{"command"}\"")
            if not params.get("args"):
                raise RuntimeError(f"stdio MCP need argument of \"{"args"}\"")
            if not params.get("env"):
                params["env"] = None
            if not params.get("cwd"):
                params["cwd"] = None
            if not params.get("keep_alive"):
                params["keep_alive"] = True
            elif type(params["keep_alive"]) != bool:
                params["keep_alive"] = True
            if not params.get("log_file"):
                params["log_file"] = None
        elif mcp_type == "http":
            if not params.get("url"):
                raise RuntimeError(f"http MCP need argument of \"{"url"}\"")
            if not params.get("headers"):
                params["headers"] = None
            if not params.get("auth"):
                params["auth"] = None
            if not params.get("sse_read_timeout"):
                params["sse_read_timeout"] = None
            if not params.get("httpx_client_factory"):
                params["httpx_client_factory"] = None
            if not params.get("verify"):
                params["verify"] = None
        elif mcp_type == "sse":
            if not params.get("url"):
                raise RuntimeError(f"sse MCP need argument of \"{"url"}\"")
            if not params.get("headers"):
                params["headers"] = None
            if not params.get("auth"):
                params["auth"] = None
            if not params.get("sse_read_timeout"):
                params["sse_read_timeout"] = None
            if not params.get("httpx_client_factory"):
                params["httpx_client_factory"] = None
            if not params.get("verify"):
                params["verify"] = None
        else:
            raise RuntimeError(f"Unknown MCP type: {mcp_type}")
        """update config file"""
        write_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), configs=mcps_configs, name="MCPs", console=console)
        mcps_configs.append(params)
        sys_log.debug(f"MCP: {name} with type: {mcp_type} configuration added")
        console.print(
            f"MCP: [{MAJOR_COLOR2}]{name}[/{MAJOR_COLOR2}] with type: [{MAJOR_COLOR2}]{mcp_type}[/{MAJOR_COLOR2}] configuration added")
    except Exception as e:
        sys_log.error(f"Add MCP configuration with args: {args} failed with error: {e}")
        console.print(f"Add MCP configuration with args: {args} failed with error: {e}", style="bold red")


def mcp_toggle_cli(mcps_configs: list[dict[str, Any]], args: Namespace, console: Console):
    """MCP CLI operations support for disabling/enabling an MCP server"""
    try:
        """find the target MCP server"""
        name = args.name
        toggle_idx: list[int] = []
        for idx, config in enumerate(mcps_configs):
            if config["name"] == name:
                toggle_idx.append(idx)

        """toggle and update"""
        if len(toggle_idx) == 0:
            sys_log.warning(f"MCP with name: {name} doesn't exist")
            console.print(f"MCP with name: {name} doesn't exist", style="bold yellow")
        elif len(toggle_idx) == 1:
            token = mcps_configs[toggle_idx[0]]["if_disabled"]
            mcps_configs[toggle_idx[0]]["if_disabled"] = not token
            write_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), configs=mcps_configs, name="MCPs", console=console)
            if token:
                sys_log.debug(f"MCP: {name} is enabled")
                console.print(f"MCP: [{MAJOR_COLOR2}]{name}[/{MAJOR_COLOR2}] is [{MAJOR_COLOR1}]enabled[/{MAJOR_COLOR1}]")
            else:
                sys_log.debug(f"MCP: {name} is disabled")
                console.print(f"MCP: [{MAJOR_COLOR2}]{name}[/{MAJOR_COLOR2}] is [bright_black]disabled[/bright_black]")
        else:
            token = mcps_configs[toggle_idx[0]]["if_disabled"]
            mcps_configs[toggle_idx[0]]["if_disabled"] = not token
            write_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), configs=mcps_configs, name="MCPs", console=console)
            if token:
                sys_log.warning(f"There are {len(toggle_idx)} MCPs with the same name: {name}. The first one is enabled")
                console.print(f"There are {len(toggle_idx)} MCPs with the same name: {name}. The first one is enabled", style="bold yellow")
            else:
                sys_log.warning(f"There are {len(toggle_idx)} MCPs with the same name: {name}. The first one is disabled")
                console.print(f"There are {len(toggle_idx)} MCPs with the same name: {name}. The first one is disabled",style="bold yellow")
    except Exception as e:
        sys_log.error(f"Toggle MCP configuration with args: {args} failed with error: {e}")
        console.print(f"Toggle MCP configuration with args: {args} failed with error: {e}", style="bold red")


def mcp_remove_cli(mcps_configs: list[dict[str, Any]], args: Namespace, console: Console):
    """MCP CLI operations support for removing an MCP server"""
    try:
        """find the target MCP server"""
        name = args.name
        del_idx: list[int] = []
        for idx, config in enumerate(mcps_configs):
            if config["name"] == name:
                del_idx.append(idx)

        """delete and update"""
        if len(del_idx) == 0:
            sys_log.warning(f"MCP with name: {name} doesn't exist")
            console.print(f"MCP with name: {name} doesn't exist", style="bold yellow")
        elif len(del_idx) == 1:
            del mcps_configs[del_idx[0]]
            write_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), configs=mcps_configs, name="MCPs", console=console)
            sys_log.debug(f"MCP: {name} removed")
            console.print(f"MCP: [{MAJOR_COLOR2}]{name}[/{MAJOR_COLOR2}] removed")
        else:
            del mcps_configs[del_idx[0]]
            write_configs(configs_path=str(AGENT_PATH / MCPS_CONFIGS_PATH), configs=mcps_configs, name="MCPs", console=console)
            sys_log.warning(f"There are {len(del_idx)} MCPs with the same name: {name}. The first one is removed")
            console.print(f"There are {len(del_idx)} MCPs with the same name: {name}. The first one is removed", style="bold yellow")
    except Exception as e:
        sys_log.error(f"Remove MCP configuration with args: {args} failed with error: {e}")
        console.print(f"Remove MCP configuration with args: {args} failed with error: {e}", style="bold red")
