# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.7
Description: Main script of the TECoSim agent

Revision:
---------
2026.4.7       Yu Huang      1.0      First implementation
2026.4.15      Yu Huang      1.1      Tool calls, Query prompts and message history
2026.4.16      Yu Huang      1.2      Agent context realization with logic merge
2026.4.25-26   Yu Huang      1.3      Reasoning support
2026.4.26      Yu Huang      1.4      Quick interrupt support
2026.4.28      Yu Huang      1.5      Exit TUI support
2026.4.29      Yu Huang      1.6      Builtin commands support
2026.5.13      Yu Huang      1.7      Bugfix of LLM context detection
2026.5.15      Yu Huang      1.8      Agent skills support
2026.5.19      Yu Huang      1.9      Model classification support
2026.5.20      Yu Huang      2.0      Refactor llm_request_with_spinner and move to client.py
2026.5.21-22   Yu Huang      2.1      Agent MCPs support
2026.5.22      Yu Huang      2.2      Summarize session title support & Save session with higher frequency
2026.5.23      Yu Huang      2.3      Stream response display update & Move response management to prompt.py
2026.5.28      Yu Huang      2.4      Add read-only paths support & Multi-line user prompt input support
2026.5.29      Yu Huang      2.5      Add auto session summary trigger threshold
2026.5.30      Yu Huang      2.6      Random spinner title support & Revise spinner logic with SIGINT pass through
2026.5.31      Yu Huang      2.7      Add CLI session management support
2026.6.1       Yu Huang      2.8      Define all used status labels in constants.py
2026.6.2       Yu Huang      2.9      Add CLI command support of skill list
2026.6.3       Yu Huang      3.0      Add cron tasks support
2026.6.5       Yu Huang      3.1      Add --nosystem, --notools, --nocrons support
2026.6.6       Yu Huang      3.2      Basic support of agent tasks as Scoreboard with lock
2026.6.7       Yu Huang      3.3      Support of agent tasks display & Refactor agent listening
2026.6.9       Yu Huang      3.4      Add design and run support for simulator
2026.6.10      Yu Huang      3.5      Add reminder for LLM to manage workflow proactively & Revise the live TUI with the
                                       same console instance
2026.6.13      Yu Huang      3.6      Subagent integration: spawn, agent_list registry, background agent orchestration,
2026.6.14      Yu Huang      3.7      Fix: summary trigger >= with if_summarized guard, tool calls spinner board pass args
                                      stale agent cleanup on session resume
2026.6.30      Yu Huang      3.8      Refactor the Markdown render style with custom theme
2026.7.15-16   Yu Huang      3.9      Add WeChat bot interaction support

Details:
---------
Main entry point and core agent loop. Initializes all subsystems (logger, CLI args, LLM client, agent context, skills,
MCPs, cron, sessions, builtin commands, scoreboard, design/run managers), then runs the interactive loop:
user input (with task reminder injection) → LLM request → tool execution (with task usage tracking and reminder injection)
→ response. Handles API timeout, cancellation, keyboard interrupt, and unexpected errors.
"""
import os
import openai

from pathlib import Path
from src.utility import sys_logger, cli_args, ui_info, client, command, agent_listen
from src.context import session, prompt
from src.context.agent_context import AgentContext, RequestLLMCancelled
from src.tool.scoreboard import Scoreboard
from src.tool.tool_dispatch import ToolCallsCancelled
from src.tool import (
    tool_def, tool_execute, skills_support, wechat_support, mcps_support, summarize_support, file_io_support, cron_support)
from src.utility.basic_utils import load_configs, get_console
from src.constants import *

"""program's parser"""
arguments = cli_args.tecosim_agent_args()

"""create logger"""
sys_log = sys_logger.Logger(str(os.path.basename(__file__))[0:-3], arguments.log)

"""create console"""
console = get_console()

if __name__ == '__main__':
    """Entry point for session operations"""
    session.session_entry_cli(arguments, console)

    """Entry point for cron operations"""
    cron_support.cron_entry_cli(arguments, console)

    """Entry point for skill operations"""
    skills_support.skill_entry_cli(arguments, console)

    """Entry point for MCP operations"""
    mcps_support.mcp_entry_cli(arguments, console)

    """start banner and TECoSim agent dev info"""
    ui_info.log_tecosim_agent_info()
    ui_info.console_tecosim_agent_info(console)

    """create agent context"""
    ctx = AgentContext()
    ctx.args = arguments
    ctx.console = console
    sys_log.debug("TECoSim Agent context created")
    console.print(f"TECoSim Agent [{MAJOR_COLOR2}]context[/{MAJOR_COLOR2}] created")

    """load API configs and config LLM client"""
    ctx.api_configs = load_configs(configs_path=API_CONFIGS_PATH, name="API", console=console)
    ctx.llm_client = client.config_client(ctx=ctx, console=console)

    """load agent configs"""
    ctx.agent_configs = load_configs(configs_path=AGENT_CONFIGS_PATH, name="Agent", console=console)

    """load skills and query prompts"""
    if not ctx.args.noskills:
        # skills are readonly in runtime
        ctx.skills = skills_support.load_all_skill_metas(skills_root=SKILLS_PATH, console=console)
    else:
        sys_log.debug("All skills are disabled in main agent and subagent")
        console.print("All skills are disabled in main agent and subagent", style=f"bold {MAJOR_COLOR1}")

    """load MCPs configs and configure MCPs"""
    if not ctx.args.nomcps:
        # MCPs are readonly in runtime
        ctx.mcps_configs = load_configs(configs_path=MCPS_CONFIGS_PATH, name="MCPs", console=console)
    else:
        sys_log.debug("All MCPs are disabled in main agent and subagent")
        console.print("All MCPs are disabled in main agent and subagent", style=f"bold {MAJOR_COLOR1}")
    mcp_clients = mcps_support.config_mcps(configs=ctx.mcps_configs, init_timeout=ctx.agent_configs["MCP_INIT_TIMEOUT_S"],
                                           timeout=ctx.agent_configs["MCP_TIMEOUT_S"], console=console)
    ctx.mcp_router = mcps_support.MCPToolRouter(clients=mcp_clients)
    ctx.mcp_router.reg_all_tools_sync(console=console)

    """add read-only paths"""
    ctx.system_read_only_paths.append(Path(os.getcwd()) / "session")
    ctx.system_read_only_paths.append(Path(os.getcwd()) / "log")
    if ctx.agent_configs.get("SIMULATOR_PATH"):
        ctx.system_read_only_paths.append(Path(ctx.agent_configs["SIMULATOR_PATH"]))

    """initialize builtin commands"""
    cmd_object = command.BuiltinCommands(console)  # basic commands
    cmd_object.register_skills(ctx.skills, console)  # tools to commands

    """query prompts"""
    """create/resume session"""
    [session_uuid, agent_session] = session.query_session(session_uuid=ctx.args.resume, console=console, cmd_object=cmd_object)
    ctx.session_uuid = session_uuid
    ctx.agent_session = agent_session

    ctx.messages = prompt.query_prompts(ctx, ctx.args.resume, console)

    """create/resume scoreboard"""
    board = Scoreboard()  # independent with agent context, clearer semantics
    board.session_uuid = ctx.session_uuid
    sys_log.debug("Scoreboard of this TECoSim Agent session created")
    console.print(f"[{MAJOR_COLOR2}]Scoreboard[/{MAJOR_COLOR2}] of this TECoSim Agent session created")
    if ctx.args.resume is not None:
        board.load_from_file(console=console, mute=False)

    """create/resume design manager"""
    ctx.design_man.session_uuid = ctx.session_uuid
    ctx.design_man.simulator_path = ctx.agent_configs["SIMULATOR_PATH"]
    sys_log.debug("Design manager of this TECoSim Agent session configured")
    console.print(f"[{MAJOR_COLOR2}]Design manager[/{MAJOR_COLOR2}] of this TECoSim Agent session configured")
    if ctx.args.resume is not None:
        ctx.design_man.load_from_file(console=console, mute=False)

    """create/resume run manager"""
    ctx.run_man.session_uuid = ctx.session_uuid
    ctx.run_man.simulator_path = ctx.agent_configs["SIMULATOR_PATH"]
    ctx.run_man.time_out = ctx.agent_configs["SIMULATOR_TIMEOUT_S"]
    sys_log.debug("Run manager of this TECoSim Agent session configured")
    console.print(f"[{MAJOR_COLOR2}]Run manager[/{MAJOR_COLOR2}] of this TECoSim Agent session configured")
    if ctx.args.resume is not None:
        ctx.run_man.load_from_file(console=console, mute=False)

    """load durable cron tasks"""
    if not ctx.args.nocrons:
        # cron tasks can be modified in runtime, first read durable tasks
        ctx.durable_crons = load_configs(configs_path=CRON_CONFIGS_PATH, name="Durable Crons", console=console)
    else:
        sys_log.debug("All cron tasks are disabled in main agent and subagent")
        console.print("All cron tasks are disabled in main agent and subagent", style=f"bold {MAJOR_COLOR1}")

    """config wechat bot"""
    if ctx.args.wechat:
        wechat_bot = wechat_support.WeChatBridge(console=console, prompt_session=ctx.agent_session,
                                                 session_uuid=ctx.session_uuid, config=ctx.agent_configs)
        login_flag = wechat_bot.login()
        if login_flag:
            ctx.wechat_bot = wechat_bot
            ctx.tui_mute = True  # mute permission TUI
            ctx.enable_wechat = True  # enable WeChat mode
            assert ctx.wechat_bot
            if ctx.args.resume is not None:
                ctx.wechat_bot.load_cdn_cache()
                ctx.wechat_bot.load_msg_history()
            ctx.wechat_bot.run()
        else:
            ctx.enable_wechat = False
            sys_log.info("WeChat Bot failed to launch and is disabled, fallback to CLI")
            console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] failed to launch and is [bold red]disabled[/bold red]"
                          f", fallback to CLI")

    """config agent context"""
    # resume context
    if ctx.args.resume is not None:
        # load session's context
        # 1). read main context JSON
        # 2). read session tasks (cron tasks can be modified in runtime)
        # all context will be saved in save_sessions
        ctx.load_context(console=console)
    ctx.cron_tasks, ctx.cron_ids = cron_support.config_cron(ctx.durable_crons, ctx.session_crons, console=console)  # config crons
    ctx.active_cron = len(ctx.cron_tasks)
    # override permission if WeChat is enabled
    if ctx.wechat_bot is not None and ctx.enable_wechat:
        ctx.config_wechat_permission(ctx.agent_configs["WECHAT_BOT_PERMISSION"])
        wechat_enable_all_mcp = bool(ctx.agent_configs["WECHAT_BOT_PERMISSION"]["ALL_MCP_TOOLS"])
        ctx.mcp_router.update_mcp_permission(permissions=ctx.permissions, console=console, enable_all_mcp=wechat_enable_all_mcp)
        sys_log.info("Permission in main agent is overridden by WeChat Bot")
        console.print(
            f"[{MAJOR_COLOR2}]Permission[/{MAJOR_COLOR2}] in main agent is overridden by [{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}]")
    # set MCP permission
    else:
        ctx.mcp_router.update_mcp_permission(permissions=ctx.permissions, console=console)
    # get all agent tools
    # 1). agent tools (basic, simulation, WeChat)
    # 2). MCPs tools
    if not ctx.args.notools:
        ctx.tools = tool_def.create_tools_prompts(ctx)
    else:
        sys_log.debug("All tools in main agent are disabled")
        console.print("All tools in main agent are disabled", style=f"bold {MAJOR_COLOR1}")
    ctx.task_end = True  # previous task is always ended

    """set the terminal title"""
    ui_info.set_terminal_title(ctx.session_title)

    """core agent loop"""
    while True:
        try:
            """save messages, context and scoreboard"""
            file_io_support.save_sessions(ctx, board, console, True)

            """user input or tool results"""
            if ctx.task_end:
                ui_info.usage_bar(ctx=ctx, console=console)
                """
                Listen agent when there are active cron tasks, pending tasks, foreground subagents, WeChat Bot is enabled
                1). check cron tasks
                    if cron tasks triggered, append messages and exits (else exits if user press any key)
                2). display agent tasks
                    (just display, exits if user press any key)
                3). check foreground subagents,
                    if any subagent stopped, append messages and exits (else exits if user press any key)
                    reason of listening here but not in top of loop is to avoid subagent to interrupt the main agent
                4). listen WeChat messages,
                    if WeChat Bot is enabled, WeChat messages will be the only source of user prompts and agent_listen is
                    always called, and can't exit if Ctrl+C is not pressed
                """
                listen_triggerd = agent_listen.listen_tui(ctx=ctx, board=board, console=console)
                if not listen_triggerd:
                    """user prompts & request"""
                    user_input = ui_info.get_user_prompt(ctx)
                    results = session.cmd_lexer(user_input, cmd_object)
                    if results is not None:  # command input
                        request_llm = cmd_object.execute_cmd(results[0], results[1], ctx, board, console)
                        if not request_llm:
                            continue
                    else:  # plain text input
                        task_reminder = prompt.get_task_reminder(ctx, board, "user_input")
                        if task_reminder is not None:
                            ctx.messages.append({"role": "user", "content": f"{SYS_REMINDER_START_LABEL}\n"
                                                                            f"{task_reminder}\n"
                                                                            f"{SYS_REMINDER_END_LABEL}"})
                        ctx.messages.append({"role": "user", "content": user_input})
                        ctx.user_prompts += 1
                        if not ctx.if_summarized and ctx.user_prompts >= ctx.agent_configs["LLM_SUMMARY_TRIGGER"]:
                            ctx.if_summarized = True
                            title = summarize_support.summarize_session(ctx=ctx, console=console)
                            ctx.session_title = title if title else ERROR_SESSION_TITLE
                            ui_info.set_terminal_title(ctx.session_title)
                else:
                    """pass prompts to LLM"""
                    pass
            else:
                """second response with previous loop's tool results or reminder"""
                pass

            """send LLM request"""
            sys_log.debug("LLM request start")
            response = client.llm_request_spinner(client.request_loop_main, ctx.llm_client, ctx,
                                                  console=console, if_random=ctx.agent_configs["RANDOM_PROGRESS_TITLE"])
            sys_log.debug("LLM request end")

            """manage the LLM response"""
            assistant_tool_calls = prompt.llm_response_manage(response=response, ctx=ctx, console=console)

            """call tools"""
            if assistant_tool_calls is not None:
                ctx.task_end = False
                sys_log.debug("Tools call start")
                ctx.tool_calls_prompts += len(assistant_tool_calls)
                tools_response = tool_execute.tool_calls_spinner_board(
                    tool_execute.execute_tools,
                    assistant_tool_calls, ctx, board,
                    board=board, console=console,
                    if_random=ctx.agent_configs["RANDOM_PROGRESS_TITLE"],
                    agent_list=ctx.agent_list)
                ctx.messages.extend(tools_response)
                ctx.tool_results_prompts += len(tools_response)
                """check task"""
                prompt.update_task_usage(ctx, assistant_tool_calls, "tool_call")
                task_reminder = prompt.get_task_reminder(ctx, board, "tool_call")
                if task_reminder is not None:
                    ctx.messages.append({"role": "user", "content": f"{SYS_REMINDER_START_LABEL}\n"
                                                                    f"{task_reminder}\n"
                                                                    f"{SYS_REMINDER_END_LABEL}"})
            else:
                ctx.task_end = True
                """check task"""
                # remind from chat is equivalent to remind from user input, so only update usage
                prompt.update_task_usage(ctx, None, "chat")

        except openai.APITimeoutError:
            """API timeout"""
            if ctx.task_end:  # no tool calls, only user prompt, so pop it
                ctx.messages.pop()
                if ctx.user_prompts >= 1:
                    ctx.user_prompts -= 1
            else:  # if send tool calls' results, retry
                pass
            sys_log.warning(f"LLM request {TIMEOUT_LABEL}: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry")
            console.print(f"LLM request {TIMEOUT_LABEL}: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry", style="bold yellow")
            continue
        except RequestLLMCancelled:
            """LLM API request cancelled"""
            if ctx.task_end:  # no tool calls, only user prompt, so pop it
                ctx.messages.pop()
                if ctx.user_prompts >= 1:
                    ctx.user_prompts -= 1
            else:  # if send tool calls' results, do noting
                pass
            sys_log.warning(f"LLM request canceled, but the connection is not killed, token consumption can't be avoided")
            console.print(f"LLM request canceled, but the connection is not killed, token consumption can't be avoided",
                          style="bold yellow")
            ui_info.normal_exit(ctx, board, console, "TECoSim Agent exits with RequestLLMCancelled")
        except ToolCallsCancelled:
            """Tool calls are cancelled and doesn't handle properly"""
            sys_log.error(f"Tool calls are cancelled, but the interrupt is not handled properly")
            console.print(f"Tool calls are cancelled, but the interrupt is not handled properly", style="bold red")
            ui_info.normal_exit(ctx, board, console, "TECoSim Agent exits with KeyboardInterrupt")
        except KeyboardInterrupt:
            """User interrupt"""
            ui_info.normal_exit(ctx, board, console, "TECoSim Agent exits with KeyboardInterrupt")
        except Exception as e:
            """Unexpected error"""
            ui_info.error_exit(ctx, board, console, e)
