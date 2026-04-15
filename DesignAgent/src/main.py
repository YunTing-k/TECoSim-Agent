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

Details:
Main entry point of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import sys
import openai

from src.utility import sys_logger, cli_args, ui_info, client
from rich.console import Console
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

    """create/resume session"""
    [session_uuid, agent_session] = session.query_session(session_uuid=args.resume, console=console)

    """load API configs and config LLM client"""
    api_configs = client.load_configs(configs_path="./config/api_configs.json", name="API")
    llm_client = client.config_client(api_configs, console=console)

    """load Agent configs and query prompts"""
    agent_configs = client.load_configs(configs_path="./config/agent_configs.json", name="Agent")
    messages = prompt.query_prompts(api_configs, agent_configs, args.resume, console)
    tools = tool_def.create_tools_prompts(console)

    """signal and params definition"""
    task_end = True  # if the previous task is ended
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    """core agent loop"""
    while True:
        try:
            if task_end:
                """user prompts & request"""
                user_input = agent_session.prompt("> ")
                messages.append({"role": "user", "content": user_input})
            else:
                """second response with previous loop's tool results"""
                pass
            sys_log.debug("LLM request start")
            with ui_info.loading_spinner():
                response = client.create_request(llm_client, api_configs, messages, tools)

            """append history and get context"""
            sys_log.debug("LLM request end")
            usage = response.usage
            total_input_tokens += usage.prompt_tokens
            total_output_tokens += usage.completion_tokens
            total_tokens += usage.total_tokens
            sys_log.debug(f"Token usage: input= +{usage.prompt_tokens} ({total_input_tokens}), "
                          f"output= +{usage.completion_tokens} ({total_output_tokens}), "
                          f"total= +{usage.total_tokens} ({total_tokens})")
            messages.append(response.choices[0].message.model_dump())
            assistant_chat = response.choices[0].message.content
            assistant_toolcalls = response.choices[0].message.tool_calls
            if (assistant_chat is None) and (assistant_toolcalls is None):
                raise RuntimeError("Content and Tool calls in LLM message are both empty")

            """display chat"""
            if assistant_chat is not None:
                console.print("\n")
                console.print(assistant_chat)
                console.print("\n")

            """call tools"""
            if assistant_toolcalls is not None:
                task_end = False
                sys_log.debug("Tools call start")
                with ui_info.loading_spinner(waiting_desc="Tools calling", done_desc="Tools execution done") as progress:
                    tools_response = tool_execute.execute_tools(tool_calls=assistant_toolcalls, progress=progress)
                    messages.extend(tools_response)
            else:
                task_end = True
        except openai.APITimeoutError:
            messages.pop()
            sys_log.warning(f"LLM request timeout: {api_configs["TIMEOUT_MS"] / 1000} s, please retry")
            console.print(f"[bold yellow]LLM request timeout: {api_configs["TIMEOUT_MS"] / 1000} s, please retry[/bold yellow]")
            continue
        except KeyboardInterrupt:
            prompt.save_messages(messages, session_uuid, console)
            sys_log.debug("TECoSim Agent exits with KeyboardInterrupt")
            console.print(f"[{MAJOR_COLOR2}]TECoSim Agent exits with KeyboardInterrupt[/{MAJOR_COLOR2}]")
            sys.exit(-1)
        except Exception as e:
            prompt.save_messages(messages, session_uuid, console)
            sys_log.error(f"TECoSim Agent exits with error: {e}")
            console.print(f"[bold red]TECoSim Agent exits with error: {e}[/bold red]")
            sys.exit(-1)
