from ddgs import DDGS
from exa_py import Exa
from tavily import TavilyClient
from linkup import LinkupClient
from test_config import *  # a test_config.py is need to store you URL and API key


def exa_web_search(query: str, allowed_domains: list[str] = None, blocked_domains: list[str] = None, max_results: int = 5) -> list[dict]:
    exa = Exa(api_key=EXA_API_KEY)
    search_args = {
        "query": query,
        "num_results": max_results,
        "type": "auto",
    }
    if allowed_domains:
        search_args["include_domains"] = allowed_domains
    if blocked_domains:
        search_args["exclude_domains"] = blocked_domains

    response = exa.search(**search_args)
    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.text[:300] if r.text else ""   # 用前300字符作为摘要
        }
        for r in response.results
    ]


def tavily_web_search(query: str, allowed_domains: list[str] = None, blocked_domains: list[str] = None, max_results: int = 5) -> list[dict]:
    client = TavilyClient(api_key=TAVILY_API_KEY)
    search_params = {
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
    }
    if allowed_domains:
        search_params["include_domains"] = allowed_domains
    if blocked_domains:
        search_params["exclude_domains"] = blocked_domains

    response = client.search(**search_params)
    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")  # Tavily 的 content 字段即为摘要
        })
    return results


def linkup_web_search( query: str, allowed_domains: list[str] = None, blocked_domains: list[str] = None, max_results: int = 5) -> list[dict]:
    client = LinkupClient(api_key=LINKUP_API_KEY)

    search_params = {
        "query": query,
        "depth": "deep",
        "output_type": "searchResults",
        "max_results": max_results,
        "timeout": 20,
    }
    if allowed_domains:
        search_params["include_domains"] = allowed_domains
    if blocked_domains:
        search_params["exclude_domains"] = blocked_domains
    response = client.search(**search_params)
    results = []

    for r in response.results:
        results.append({
            "title": r.name,
            "url": r.url,
            "snippet": r.content
        })

        if len(results) >= max_results:
            break

    return results


def ddgs_web_search(query: str, max_results: int = 5) -> list[dict]:
    with DDGS() as ddgs:
        results = []
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r["title"],
                "url": r["href"],
                "snippet": r["body"]
            })
        return results

print(exa_web_search("what is deepseek"))
print(tavily_web_search("what is deepseek"))
print(linkup_web_search("what is deepseek"))
print(ddgs_web_search("what is deepseek"))
