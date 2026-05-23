# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.7\n
Description: Main script of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.7       Yu Huang     1.0               First implementation\n
2026.4.15      Yu Huang     1.1               Tool calls, Query prompts and message history\n
2026.4.16      Yu Huang     1.2               Agent context realization with logic merge\n
2026.4.25-26   Yu Huang     1.3               Reasoning support\n
2026.4.26      Yu Huang     1.4               Quick interrupt support\n
2026.4.28      Yu Huang     1.5               Exit TUI support\n
2026.4.29      Yu Huang     1.6               Builtin commands support\n
2026.5.13      Yu Huang     1.7               Bugfix of LLM context detection\n
2026.5.15      Yu Huang     1.8               Agent skills support\n
2026.5.19      Yu Huang     1.9               Model classification support\n
2026.5.20      Yu Huang     2.0               Refactor llm_request_with_spinner and move to client.py\n
2026.5.21-22   Yu Huang     2.1               Agent MCPs support\n
2026.5.22      Yu Huang     2.2               Summarize session title support & Save session with higher frequency\n
2026.5.23      Yu Huang     2.3               Stream response display update & Move response management to prompt.py\n

Details:
Main entry point of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import openai

from src.utility import sys_logger, cli_args, ui_info, client, command
from rich.console import Console
from src.context import session, prompt
from src.context.agent_context import AgentContext, RequestLLMCancelled
from src.tool import tool_def, tool_execute, skills_support, mcps_support, summarize_support, file_io_support
from src.utility.basic_utils import load_configs
from src.constants import *

"""program's parser"""
arguments = cli_args.tecosim_agent_args()

"""create logger"""
sys_log = sys_logger.Logger(str(os.path.basename(__file__))[0:-3], arguments.log).logger

"""create console"""
console = Console()

if __name__ == '__main__':
    """Entry commands for MCP operations"""
    mcps_support.mcp_entry_cli(arguments, console)

    """start banner and TECoSim agent dev info"""
    ui_info.log_tecosim_agent_info()
    ui_info.console_tecosim_agent_info(console)

    """create agent context"""
    ctx = AgentContext()
    ctx.args = arguments
    ctx.console = console
    sys_log.debug("Context of TECoSim Agent created")
    console.print(f"Context of [{MAJOR_COLOR2}]TECoSim Agent[/{MAJOR_COLOR2}] created")

    """load API configs and config LLM client"""
    ctx.api_configs = load_configs(configs_path="./config/api_configs.json", name="API", console=console)
    ctx.llm_client = client.config_client(ctx=ctx, console=console)

    """load agent configs"""
    ctx.agent_configs = load_configs(configs_path="./config/agent_configs.json", name="Agent", console=console)

    """load skills and query prompts"""
    if not ctx.args.noskills:
        ctx.skills = skills_support.load_all_skill_metas(skills_root="./skills", console=console)

    """load MCPs configs and configure MCPs"""
    if not ctx.args.nomcps:
        ctx.mcps_configs = load_configs(configs_path="./mcps/mcps_configs.json", name="MCPs", console=console)
    mcp_clients = mcps_support.config_mcps(configs=ctx.mcps_configs, init_timeout=ctx.agent_configs["MCP_INIT_TIMEOUT_S"],
                                           timeout=ctx.agent_configs["MCP_TIMEOUT_S"], console=console)
    ctx.mcp_router = mcps_support.MCPToolRouter(clients=mcp_clients)
    ctx.mcp_router.reg_all_tools_sync(console=console)

    """initialize builtin commands"""
    cmd_object = command.BuiltinCommands(console)  # basic commands
    cmd_object.register_skills(ctx.skills, console)  # tools to commands

    """query prompts"""
    ctx.messages = prompt.query_prompts(ctx, ctx.args.resume, console)

    """create/resume session"""
    [session_uuid, agent_session] = session.query_session(session_uuid=ctx.args.resume, console=console, cmd_object=cmd_object)
    ctx.session_uuid = session_uuid
    ctx.agent_session = agent_session

    """config agent context"""
    # resume context
    if ctx.args.resume is not None:
        ctx.load_context(console=console)
    # set MCP permission
    ctx.mcp_router.update_mcp_permission(permissions=ctx.permissions, console=console)
    # get tools
    ctx.tools = tool_def.create_tools_prompts(ctx)
    # config other filed of context
    ctx.task_end = True  # previous task is ended

    """set the terminal title"""
    ui_info.set_terminal_title(ctx.session_title)

    """core agent loop"""
    while True:
        try:
            """save messages and context"""
            file_io_support.save_sessions(ctx, console, True)

            """user input or tool results"""
            if ctx.task_end:
                """user prompts & request"""
                ui_info.usage_bar(ctx=ctx, console=console)
                user_input = agent_session.prompt("> ")
                results = session.cmd_lexer(user_input, cmd_object)
                if results is not None:  # command input
                    request_llm = cmd_object.execute_cmd(results[0], results[1], ctx, console)
                    if not request_llm:
                        continue
                else:  # plain text input
                    ctx.messages.append({"role": "user", "content": user_input})
                    ctx.user_prompts += 1
                    if ctx.user_prompts == 1:  # summarize according to user's first prompts
                        title = summarize_support.summarize_session(ctx=ctx, console=console)
                        ctx.session_title = title if title else ERROR_SESSION_TITLE
                        ui_info.set_terminal_title(ctx.session_title)
            else:
                """second response with previous loop's tool results"""
                pass

            """send LLM request"""
            sys_log.debug("LLM request start")
            response = client.llm_request_with_spinner(client.request_loop_main, ctx.llm_client, ctx)
            sys_log.debug("LLM request end")

            """manage the LLM response"""
            assistant_tool_calls = prompt.llm_response_manage(response=response, ctx=ctx, console=console)

            """call tools"""
            if assistant_tool_calls is not None:
                ctx.task_end = False
                sys_log.debug("Tools call start")
                ctx.tool_calls_prompts += len(assistant_tool_calls)
                with ui_info.loading_spinner(waiting_desc="Tools calling", done_desc="Tools execution done",
                                             spinner="bouncingBall") as progress:
                    tools_response = tool_execute.execute_tools(tool_calls=assistant_tool_calls, ctx=ctx, progress=progress)
                    ctx.messages.extend(tools_response)
                    ctx.tool_results_prompts += len(tools_response)
            else:
                ctx.task_end = True
        except openai.APITimeoutError:
            """API timeout"""
            if ctx.task_end:  # no tool calls, only user prompt, so pop it
                ctx.messages.pop()
                if ctx.user_prompts >= 1:
                    ctx.user_prompts -= 1
            else:  # if send tool calls' results, retry
                pass
            sys_log.warning(f"LLM request timeout: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry")
            console.print(f"LLM request timeout: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry", style="bold yellow")
            continue
        except RequestLLMCancelled:
            """LLM API request cancelled"""
            if ctx.task_end:  # no tool calls, only user prompt, so pop it
                ctx.messages.pop()
                if ctx.user_prompts >= 1:
                    ctx.user_prompts -= 1
            else:  # if send tool calls' results, retry
                pass
            sys_log.warning(f"LLM request canceled, but the connection is not killed, token consumption can't be avoided")
            console.print(f"LLM request canceled, but the connection is not killed, token consumption can't be avoided",
                          style="bold yellow")
            ui_info.normal_exit(ctx, console, "TECoSim Agent exits with RequestLLMCancelled")
        except KeyboardInterrupt:
            """User interrupt"""
            ui_info.normal_exit(ctx, console, "TECoSim Agent exits with KeyboardInterrupt")
        except Exception as e:
            """Unexpected error"""
            ui_info.error_exit(ctx, console, e)
