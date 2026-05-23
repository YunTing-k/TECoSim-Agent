# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.22\n
Description: Agent summarization support

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.22      Yu Huang     1.0               First implementation\n
2026.5.23      Yu Huang     1.1               Bugfix of possible none usage update\n

Details:
Support of summarizing the title of session history
------------------------------------------------------------------------------------------------------------------------
"""
import logging

from typing import Any
from openai.types.chat import ChatCompletion
from rich.console import Console
from src.utility import client
from src.utility.basic_utils import get_field
from src.context.agent_context import AgentContext, RequestLLMCancelled
from src.context.prompt import deepseek_support, get_reasoning

sys_log = logging.getLogger('logger')


summarize_session_system_prompt = "You are TECoSim Agent, developed by Yu Huang (黄雨) from Shanghai Jiao Tong University."


summarize_session_prompt_prefix = ("Generate a concise, sentence-case title (4-9 words) that captures the main topic or "
                                   "goal of this whole dialogue. Follow these rules:\n"
                                   "- IMPORTANT: Summarize in the SAME LANGUAGE as the user's input throughout the dialogue\n"
                                   "- If the conversation is in Chinese, output Chinese; if in English, output English; "
                                   "adapt to any language used\n"
                                   "- The title should be clear enough that the user can recognize the session in a list\n"
                                   "- Use sentence case: capitalize only the first word and proper nouns (for languages "
                                   "that have case)\n"
                                   "- Length guideline: 4-9 words; for Chinese, 5-15 characters\n"
                                   "- IMPORTANT: Only return a JSON object with a single \"title\" field. Do NOT wrap in "
                                   "markdown code blocks, do NOT add any explanations, do NOT include ```json``` markers. "
                                   "Output raw JSON only.\n\n"
                                   "Good examples:\n"
                                   "English:\n"
                                   "{\"title\": \"Fix login button on mobile\"}\n"
                                   "{\"title\": \"Add OAuth authentication\"}\n"
                                   "{\"title\": \"Debug failing CI tests\"}\n"
                                   "{\"title\": \"Refactor API client error handling\"}\n\n"
                                   "中文 (Chinese):\n"
                                   "{\"title\": \"修复移动端登录按钮无响应\"}\n"
                                   "{\"title\": \"添加用户权限管理功能\"}\n"
                                   "{\"title\": \"排查数据库连接超时问题\"}\n"
                                   "{\"title\": \"优化首页加载速度\"}\n"
                                   "{\"title\": \"讨论春节活动方案\"}\n\n"
                                   "Bad examples (too vague):\n"
                                   "{\"title\": \"Code changes\"}\n"
                                   "{\"title\": \"代码修改\"}\n"
                                   "{\"title\": \"问题\"}\n\n"
                                   "Bad (too long):\n"
                                   "{\"title\": \"Investigate and fix the issue where the login button does not respond "
                                   "on mobile devices\"}\n"
                                   "{\"title\": \"深入调查并修复移动端登录按钮在iOS和Android设备上均无响应的问题\"}\n\n"
                                   "Bad (wrong case):\n"
                                   "{\"title\": \"Fix Login Button On Mobile\"}\n\n"
                                   "Bad (markdown wrapping — DO NOT DO THIS):\n"
                                   "```json\n{\"title\": \"Some title\"}\n```\n\n"
                                   "REMEMBER: Output ONLY the raw JSON object. No markdown, no explanation, no extra text"
                                   " — just {\"title\": \"...\"}")


def create_summarize_session_prompts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """create the prompts for summarizing session"""
    prompts = []
    system_prompts = {"role": "system", "content":
                       f"{summarize_session_system_prompt}"}
    prompts.append(system_prompts)
    for msg in messages:
        if msg["role"] == "system":
            continue
        elif msg["role"] == "user":
            prompts.append(msg)
        elif msg["role"] == "assistant":
            prompts.append(msg)
        elif msg["role"] == "tool":
            prompts.append(msg)
        else:
            sys_log.debug(f"Unknown role: {msg["role"]} in history massages")
            prompts.append(msg)
    user_content = f"{summarize_session_prompt_prefix}"
    user_prompts = {"role": "user", "content": f"{user_content}"}
    prompts.append(user_prompts)
    return prompts


def summarize_session(ctx: AgentContext, console: Console) -> str | None:
    """summarize the session with prompt through LLM"""
    messages = create_summarize_session_prompts(ctx.messages)
    try:
        response: ChatCompletion = client.llm_request_with_spinner(client.request_branch_fast,
                                                   ctx.llm_client, messages, None, ctx.api_configs, ctx.agent_configs,
                                                   waiting_desc="Session summarizing ...",
                                                   done_desc="LLM response latency", spinner="arrow3")
        ctx.total_llm_requests += 1  # mail loop counter is in request function, branch request need to manually count
        usage = response.usage
        if usage is not None:
            ctx.total_input_tokens += usage.prompt_tokens
            ctx.total_output_tokens += usage.completion_tokens
            ctx.total_tokens += usage.total_tokens
            if usage.prompt_tokens_details is not None:
                cached_tokens = usage.prompt_tokens_details.cached_tokens
                uncached_tokens = usage.prompt_tokens - cached_tokens  # uncached input tokens
                ctx.total_uncached_tokens += uncached_tokens

        dumped_msg = response.choices[0].message.model_dump(mode="json")
        if ctx.agent_configs["DEEPSEEK_SUPPORT"]:
            dumped_msg = deepseek_support(dumped_msg)
        assistant_chat = str(dumped_msg["content"])

        title = get_field(assistant_chat)
        if title is not None:
            return title

        sys_log.warning(f"Could not extract title from assistant chat, fallback to assistant reasoning")
        console.print(f"Could not extract title from assistant chat, fallback to assistant reasoning", style="bold yellow")
        assistant_reasoning = get_reasoning(dumped_msg)
        title = get_field(assistant_reasoning)
        if title is not None:
            return title
        sys_log.error(f"Could not extract title from assistant reasoning")
        console.print(f"Could not extract title from assistant reasoning", style="bold red")
        return None
    except RequestLLMCancelled:
        sys_log.warning(
            f"Session summarize LLM process canceled, but the connection is not killed, token consumption can't be avoided")
        console.print(
            f"Session summarize LLM process canceled, but the connection is not killed, token consumption can't be avoided",
            style="bold yellow")
        return None
    except Exception as e:
        sys_log.error(f"Session summarize LLM process failed with error: {e}")
        console.print(f"Session summarize LLM process failed with error: {e}", style="bold red")
        return None