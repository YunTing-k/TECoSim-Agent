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
    messages = prompt.create_prompts(api_configs, agent_configs, console)

    """core agent loop"""
    while True:
        try:
            """get user prompts"""
            user_input = agent_session.prompt("> ")

            messages.append({"role": "user", "content": user_input})
            sys_log.debug("LLM request start")
            with ui_info.loading_spinner():
                response = client.create_request(llm_client, api_configs, messages)
            console.print("\n")
            assistant_response = response.choices[0].message.content

            console.print(assistant_response)
            messages.append({"role": "assistant", "content": assistant_response})
        except openai.APITimeoutError:
            messages.pop()
            sys_log.warning(f"LLM request timeout: {api_configs["TIMEOUT_MS"] / 1000} s, please retry")
            console.print(f"[bold yellow]LLM request timeout: {api_configs["TIMEOUT_MS"] / 1000} s, please retry[/bold yellow]")
            continue
        except KeyboardInterrupt:
            sys_log.debug("TECoSim Agent exits with KeyboardInterrupt")
            console.print("TECoSim Agent exits with KeyboardInterrupt")
            sys.exit(-1)
        except Exception as e:
            sys_log.error(f"TECoSim Agent exits with error: {e}")
            console.print(f"[bold red]TECoSim Agent exits with error: {e}[/bold red]")
            sys.exit(-1)
