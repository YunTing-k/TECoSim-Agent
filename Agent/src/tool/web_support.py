# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.19\n
Description: Web support of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.19      Yu Huang     1.0               First implementation\n

Details:
Web fetch and web search support of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import httpx
import socket
import ipaddress
from urllib.parse import urlparse
import logging

from typing import Any
from datetime import datetime, timedelta
from trafilatura import extract
from rich.console import Console
from src.context.agent_context import AgentContext
from src.utility import ui_info, client
from src.context import prompt
from src.constants import *

sys_log = logging.getLogger('logger')


PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    # ipaddress.ip_network("100.64.0.0/10"),   # CGNAT
    # ipaddress.ip_network("192.0.2.0/24"),    # TEST-NET-1
    # ipaddress.ip_network("198.51.100.0/24"), # TEST-NET-2
    # ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3

    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
]


def check_url(url: str, console: Console) -> tuple[str, bool]:
    """check if the url is valid"""
    try:
        parsed = urlparse(url)
    except Exception as e:
        sys_log.error(f"URL: {url} parse failed with error {e}")
        console.print(f"URL: {url} parse failed with error {e}", style="bold red")
        return f"URL: {url} parse failed with error {e}", False

    if parsed.scheme not in ("http", "https"):
        return f"URL: {url} is not start with http or https", False

    hostname = parsed.hostname
    if not hostname:
        return f"URL: {url} has no valid hostname", False

    if parsed.username is not None or parsed.password is not None:
        return f"URL: {url} contains username or password, which is not allowed", False

    try:
        ip = socket.getaddrinfo(hostname, None)[0][4][0]
    except Exception as e:
        sys_log.error(f"URL: {url} DNS resolution failed with error {e}")
        console.print(f"URL: {url} DNS resolution failed with error {e}", style="bold red")
        return f"URL: {url} DNS resolution failed with error {e}", False

    ip_addr = ipaddress.ip_address(ip)

    # if ip_addr.version == 6:
    #     return f"URL: {url} is ipv6, which is not allowed", False

    for net in PRIVATE_NETS:
        if ip_addr in net:
            return f"URL: {url} is within private network", False
    return "SUCCESS", True


def query_url_cache(url: str, ctx: AgentContext) -> str | None:
    """query the cache with URL"""
    now = datetime.now()
    for idx, url_cache in enumerate(ctx.url_caches):
        if url == url_cache["url"]:
            previous = url_cache["time"]
            if now - previous < timedelta(seconds=ctx.agent_configs["URL_CACHE_TIME_S"]):
                cache = url_cache["content"]
                return cache
            else:
                del ctx.url_caches[idx]
    return None


def web_single_fetch(url_in: str, ctx: AgentContext, console: Console) -> tuple[str | None, str, bool, str]:
    """fetch single URL's content and process it"""
    url = url_in
    if url_in.startswith("http://"):
        url = url_in.replace("http://", "https://", 1)

    """query the cache"""
    content = query_url_cache(url, ctx)
    if content is not None:
        return content, "SUCCESS", False, url

    """fetch content from URL"""
    try:
        with httpx.Client(
                timeout=httpx.Timeout(timeout=ctx.agent_configs["URL_TIMEOUT_S"]),
                follow_redirects=True,
                headers={"User-Agent": "TECoSimAgent-WebFetch"}
        ) as httpx_client:
            resp = httpx_client.get(url)
            final_url = str(resp.url)
            if_redirect = final_url != url
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        sys_log.error(f"Fetch content from URL: {url} failed with error {e}")
        console.print(f"Fetch content from URL: {url} failed with error {e}", style="bold red")
        return None, f"Fetch content from URL: {url} failed with error {e}", False, url

    """convert content to markdown"""
    markdown = extract(html, output_format="markdown", url=url)
    if markdown is None:
        sys_log.error(f"Convert content from URL: {url} to markdown failed")
        console.print(f"Convert content from URL: {url} to markdown failed", style="bold red")
        return None, f"Convert content from URL: {url} to markdown failed", if_redirect, final_url

    """write to cache"""
    ctx.url_caches.append({"url": url, "time": datetime.now(), "content": markdown})
    return markdown, "SUCCESS", if_redirect, final_url


web_fetch_system_prompt = "You are TECoSim Agent, developed by Yu Huang (黄雨) from Shanghai Jiao Tong University."


web_fetch_prompt_prefix = ("Provide a concise response based only on the content above. Follow these rules:\n"
                           "- When quoting directly, use quotation marks and keep each quote under 150 characters\n"
                           "- Content outside quotation marks must be paraphrased in your own words. Do not reproduce full "
                           "passages verbatim\n"
                           "- Do not output complete song lyrics, full poems, or long verbatim excerpts from the source\n"
                           "- Do not comment on legal matters or make statements about your own compliance\n"
                           "- If the content is insufficient to answer the question, clearly state that rather than fabricating\n")


def create_web_fetch_prompts(in_prompt: str, content: str) -> list[dict[str, Any]]:
    """create the prompts for web fetch"""
    prompts = []
    system_prompts = {"role": "system", "content":
                       f"{web_fetch_system_prompt}"}
    prompts.append(system_prompts)

    user_content = f"{content}\n\n{in_prompt}\n\n{web_fetch_prompt_prefix}"
    user_prompts = {"role": "user", "content": f"{user_content}"}
    prompts.append(user_prompts)
    return prompts


def web_fetch_process(in_prompt: str, content: str, ctx: AgentContext, console: Console) -> tuple[str, bool]:
    """process the Markdown content with prompt through LLM"""
    messages = create_web_fetch_prompts(in_prompt, content)
    try:
        response = ui_info.llm_request_with_spinner(client.request_branch_fast,
                                                    ctx.llm_client, messages, None, ctx.api_configs, ctx.agent_configs,
                                                    waiting_desc = "Web fetching ...", done_desc = "LLM Web fetch latency", spinner = "arrow3")
        ctx.total_llm_requests += 1  # mail loop counter is in request function, branch request need to manually count
        usage = response.usage
        ctx.total_input_tokens += usage.prompt_tokens
        ctx.total_output_tokens += usage.completion_tokens
        ctx.total_tokens += usage.total_tokens
        cached_tokens = usage.prompt_tokens_details.cached_tokens
        uncached_tokens = usage.prompt_tokens - cached_tokens  # uncached input tokens
        ctx.total_uncached_tokens += uncached_tokens

        dumped_msg = response.choices[0].message.model_dump(mode="json")
        if ctx.agent_configs["DEEPSEEK_SUPPORT"]:
            dumped_msg = prompt.deepseek_support(dumped_msg)
        assistant_chat = str(dumped_msg["content"])
        limit = ctx.agent_configs["WEB_FETCH_LLM_CAHR_LIMIT"]
        if len(assistant_chat) > limit:
            assistant_chat = assistant_chat[:limit] + f"...(content is longer than {limit} chars, truncated)"
        return assistant_chat, True
    except ui_info.RequestLLMCancelled:
        sys_log.warning(f"Web fetch LLM process canceled, but the connection is not killed, token consumption can't be avoided")
        console.print(f"Web fetch LLM process canceled, but the connection is not killed, token consumption can't be avoided",
                      style="bold yellow")
        return "(Web fetch LLM process canceled by user)", False
    except Exception as e:
        sys_log.error(f"Web fetch LLM process failed with error: {e}")
        console.print(f"Web fetch LLM process failed with error: {e}", style="bold red")
        return f"(Web fetch LLM process failed with error: {e})", False
