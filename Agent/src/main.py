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

Details:
Main entry point of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import os
import openai

from src.utility import sys_logger, cli_args, ui_info, client, command
from rich.console import Console
from rich.markdown import Markdown
from src.context import session, prompt
from src.context.agent_context import AgentContext
from src.tool import tool_def, tool_execute
from src.constants import *

"""program's parser"""
arguments = cli_args.tecosim_agent_args()

"""create logger"""
sys_log = sys_logger.Logger(str(os.path.basename(__file__))[0:-3], arguments.log).logger

"""create console"""
console = Console()

if __name__ == '__main__':
    """start banner and TECoSim agent dev info"""
    ui_info.log_tecosim_agent_info()
    ui_info.console_tecosim_agent_info(console)

    """create agent context"""
    ctx = AgentContext()
    ctx.console = console
    sys_log.debug("Context of TECoSim Agent created")
    console.print(f"Context of [{MAJOR_COLOR2}]TECoSim Agent[/{MAJOR_COLOR2}] created")

    """create/resume session"""
    [session_uuid, agent_session] = session.query_session(session_uuid=arguments.resume, console=console)
    ctx.session_uuid = session_uuid
    ctx.agent_session = agent_session

    """config agent context"""
    # read context
    if arguments.resume is not None:
        ctx.load_context(console=console)
    # config other filed of context
    ctx.args = arguments
    ctx.task_end = True  # previous task is ended

    """load API configs and config LLM client"""
    ctx.api_configs = client.load_configs(configs_path="./config/api_configs.json", name="API", console=console)
    llm_client = client.config_client(ctx=ctx, console=console)

    """load Agent configs and query prompts"""
    ctx.agent_configs = client.load_configs(configs_path="./config/agent_configs.json", name="Agent", console=console)
    ctx.messages = prompt.query_prompts(ctx, ctx.args.resume, console)
    ctx.tools = tool_def.create_tools_prompts(ctx)

    """core agent loop"""
    while True:
        try:
            if ctx.task_end:
                """user prompts & request"""
                user_input = agent_session.prompt("> ")
                results = session.cmd_lexer(user_input)
                if results is not None:  # command input
                    command.execute_cmd(results[0], results[1], ctx, console)
                    continue
                else:  # plain text input
                    ctx.messages.append({"role": "user", "content": user_input})
                    ctx.user_prompts += 1
            else:
                """second response with previous loop's tool results"""
                pass
            sys_log.debug("LLM request start")
            response = ui_info.llm_request_with_spinner(client.create_request, llm_client, ctx)
            sys_log.debug("LLM request end")

            """check finish reason"""
            finish_reason = response.choices[0].finish_reason
            sys_log.debug(f"Finish reason: {finish_reason}")
            if finish_reason == "length":
                sys_log.error(f"LLM out of input/output context")
                console.print(f"LLM out of input/output context", style="bold red")
            if finish_reason == "content_filter":
                sys_log.warning(f"LLM's response has been filtered")
                console.print(f"LLM's response has been filtered", style="bold yellow")

            """check the usage"""
            usage = response.usage
            ctx.total_input_tokens += usage.prompt_tokens
            ctx.last_input_tokens = usage.prompt_tokens
            ctx.total_output_tokens += usage.completion_tokens
            ctx.last_output_tokens = usage.completion_tokens
            ctx.total_tokens += usage.total_tokens
            ctx.last_tokens = usage.total_tokens
            cached_tokens = usage.prompt_tokens_details.cached_tokens
            uncached_tokens = usage.prompt_tokens - usage.prompt_tokens_details.cached_tokens  # uncached input tokens
            ctx.total_uncached_tokens += uncached_tokens
            sys_log.debug(f"Token usage: input= +{usage.prompt_tokens} ({ctx.total_input_tokens}), "
                          f"output= +{usage.completion_tokens} ({ctx.total_output_tokens}), "
                          f"total= +{usage.total_tokens} ({ctx.total_tokens}), "
                          f"cached= {cached_tokens}, "
                          f"uncached= +{uncached_tokens} ({ctx.total_uncached_tokens})")

            """message dump and conversion"""
            dumped_msg = response.choices[0].message.model_dump(mode="json")
            if ctx.agent_configs["DEEPSEEK_SUPPORT"]:
                dumped_msg = prompt.deepseek_support(dumped_msg)
            ctx.messages.append(dumped_msg)
            assistant_reasoning = prompt.get_reasoning(dumped_msg)
            assistant_chat = dumped_msg["content"]
            assistant_tool_calls = dumped_msg["tool_calls"]
            if (assistant_chat is None) and (assistant_tool_calls is None):
                if assistant_reasoning is None:
                    raise RuntimeError("Output and Tool calls in LLM's message are both empty")
                else:
                    sys_log.warning(f"There is only reasoning content in LLM's message")
                    console.print(f"There is only reasoning content in LLM's message", style="bold yellow")
            if ctx.total_input_tokens >= ctx.api_configs["MODEL_CONTEXT"]:
                sys_log.error(f"LLM out of context: {ctx.api_configs["MODEL_CONTEXT"]} tokens")
                console.print(f"LLM out of context: {ctx.api_configs["MODEL_CONTEXT"]} tokens", style="bold red")
                raise RuntimeError(f"LLM out of context: {ctx.api_configs["MODEL_CONTEXT"]} tokens")
            if ctx.total_input_tokens >= ctx.api_configs["MODEL_CONTEXT"] * ctx.agent_configs["CONTEXT_THRESHOLD"]:
                sys_log.warning(f"LLM's context >= {100*ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context")
                console.print(f"LLM's context >= {100*ctx.agent_configs["CONTEXT_THRESHOLD"]}% maximum context", style="bold yellow")

            """display reasoning"""
            if assistant_reasoning is not None and not "":
                ctx.reasoning_prompts += 1
                console.print("\n")
                if ctx.agent_configs["RENDER_RESPONSE_AS_MD"]:
                    console.print(Markdown("{Think}: " + assistant_reasoning), style=f"italic {REASONING_COLOR}")
                else:
                    console.print("{Think}: " + assistant_reasoning, style=f"italic {REASONING_COLOR}")
                if assistant_chat is None:
                    console.print("\n")
            """display chat"""
            if assistant_chat is not None:
                ctx.content_prompts += 1
                if assistant_reasoning is None and not "":
                    console.print("\n")
                if ctx.agent_configs["RENDER_RESPONSE_AS_MD"]:
                    console.print(Markdown(assistant_chat), style="bold")
                else:
                    console.print(assistant_chat, style="bold")
                console.print("\n")

            """call tools"""
            if assistant_tool_calls is not None:
                ctx.task_end = False
                sys_log.debug("Tools call start")
                ctx.tool_calls_prompts += len(assistant_tool_calls)
                with ui_info.loading_spinner(waiting_desc="Tools calling", done_desc="Tools execution done") as progress:
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
        except ui_info.RequestLLMCancelled:
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
