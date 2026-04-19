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

Details:
Main entry point of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import sys
import openai

from src.utility import sys_logger, cli_args, ui_info, client
from rich.console import Console
from rich.markdown import Markdown
from src.context import session, prompt
from src.tool import tool_def, tool_execute
from src.constants import *

"""program's parser"""
args = cli_args.tecosim_agent_args()

"""create logger"""
sys_log = sys_logger.Logger(os.path.basename(__file__)[0:-3], args.log).logger

"""create console"""
console = Console()

if __name__ == '__main__':
    """start banner and TECoSim agent dev info"""
    ui_info.log_tecosim_agent_info()
    ui_info.console_tecosim_agent_info(console)

    """create agent context"""
    ctx = session.AgentContext()
    sys_log.debug("Context of TECoSim Agent created")
    console.print(f"Context of [{MAJOR_COLOR2}]TECoSim Agent[/{MAJOR_COLOR2}] created")

    """create/resume session"""
    [ctx.session_uuid, agent_session] = session.query_session(session_uuid=args.resume, console=console)

    """config agent context"""
    # read context
    if args.resume is not None:
        ctx.load_context(console=console)
    # config signals
    ctx.task_end = True  # previous task is ended

    """load API configs and config LLM client"""
    ctx.api_configs = client.load_configs(configs_path="./config/api_configs.json", name="API", console=console)
    llm_client = client.config_client(ctx=ctx, console=console)

    """load Agent configs and query prompts"""
    ctx.agent_configs = client.load_configs(configs_path="./config/agent_configs.json", name="Agent", console=console)
    ctx.messages = prompt.query_prompts(ctx, args.resume, console)
    ctx.tools = tool_def.create_tools_prompts(console)

    """core agent loop"""
    while True:
        try:
            if ctx.task_end:
                """user prompts & request"""
                user_input = agent_session.prompt("> ")
                ctx.messages.append({"role": "user", "content": user_input})
            else:
                """second response with previous loop's tool results"""
                pass
            sys_log.debug("LLM request start")
            with ui_info.loading_spinner():
                response = client.create_request(llm_client, ctx)

            """append history and get context"""
            sys_log.debug("LLM request end")
            usage = response.usage
            ctx.total_input_tokens += usage.prompt_tokens
            ctx.total_output_tokens += usage.completion_tokens
            ctx.total_tokens += usage.total_tokens
            sys_log.debug(f"Token usage: input= +{usage.prompt_tokens} ({ctx.total_input_tokens}), "
                          f"output= +{usage.completion_tokens} ({ctx.total_output_tokens}), "
                          f"total= +{usage.total_tokens} ({ctx.total_tokens})")
            ctx.messages.append(response.choices[0].message.model_dump())
            assistant_chat = response.choices[0].message.content
            assistant_toolcalls = response.choices[0].message.tool_calls
            if (assistant_chat is None) and (assistant_toolcalls is None):
                raise RuntimeError("Content and Tool calls in LLM message are both empty")

            """display chat"""
            if assistant_chat is not None:
                console.print("\n")
                if ctx.agent_configs["RENDER_RESPONSE_AS_MD"]:
                    console.print(Markdown(assistant_chat))
                else:
                    console.print(assistant_chat)
                console.print("\n")

            """call tools"""
            if assistant_toolcalls is not None:
                ctx.task_end = False
                sys_log.debug("Tools call start")
                with ui_info.loading_spinner(waiting_desc="Tools calling", done_desc="Tools execution done") as progress:
                    tools_response = tool_execute.execute_tools(tool_calls=assistant_toolcalls, ctx=ctx, progress=progress)
                    ctx.messages.extend(tools_response)
            else:
                ctx.task_end = True
        except openai.APITimeoutError:
            if ctx.task_end:
                ctx.messages.pop()
            else:
                pass
            sys_log.warning(f"LLM request timeout: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry")
            console.print(f"[bold yellow]LLM request timeout: {ctx.api_configs["TIMEOUT_MS"] / 1000} s, please retry[/bold yellow]")
            continue
        except KeyboardInterrupt:
            prompt.save_messages(ctx, console)
            ctx.save_context(console=console)
            sys_log.debug("TECoSim Agent exits with KeyboardInterrupt")
            console.print(f"[{MAJOR_COLOR2}]TECoSim Agent exits with KeyboardInterrupt[/{MAJOR_COLOR2}]")
            sys.exit(-1)
        except Exception as e:
            prompt.save_messages(ctx, console)
            ctx.save_context(console=console)
            sys_log.error(f"TECoSim Agent exits with error: {e}")
            console.print(f"[bold red]TECoSim Agent exits with error: {e}[/bold red]")
            sys.exit(-1)
