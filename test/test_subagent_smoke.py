# -*- coding: utf-8 -*-
"""
Quick smoke test for SubAgent integration.
Run with: python test/test_subagent_smoke.py
Requires a configured api_configs.json with a valid model.
"""
import sys
import os
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.tool.tool_dispatch import call_tools
from src.agent.subagent import SubAgent
from src.agent.progress import AgentStatus, SubAgentProgress
from src.utility.basic_utils import load_configs
from src.utility.client import config_client
from src.constants import *
from rich.console import Console

console = Console()


def setup_ctx():
    ctx = AgentContext()
    ctx.session_uuid = "test-session-001"
    ctx.api_configs = load_configs(API_CONFIGS_PATH, "API", console)
    ctx.agent_configs = load_configs(AGENT_CONFIGS_PATH, "Agent", console)
    ctx.llm_client = config_client(ctx, console)
    ctx.args.dangerously_allow_all = True
    return ctx


def test_explore_subagent():
    """Test explore agent reads a file."""
    print("\n=== Test 1: Explore SubAgent ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    agent = SubAgent(
        parent_ctx=ctx,
        subagent_type="explore",
        prompt="Read the file src/constants.py with limit 5 lines and tell me what constants are defined at the start.",
        agent_id="test_exp_001",
        max_steps=3,
        console=console,
    )
    agent.build_tools()
    agent.build_messages()
    result = agent.run()
    print(f"Status: {agent.status.value}")
    print(f"Result: {result[:200] if result else 'None'}")
    print(f"Stats: {agent.stats}")
    assert agent.status == AgentStatus.DONE, f"Expected DONE, got {agent.status.value}"
    assert result is not None and len(result) > 0, "Expected non-empty result"


def test_subagent_stats():
    """Test that stats are correctly accumulated."""
    print("\n=== Test 2: Stats Accumulation ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    agent = SubAgent(
        parent_ctx=ctx,
        subagent_type="explore",
        prompt="Read src/constants.py with limit 10 lines.",
        agent_id="test_stat_001",
        max_steps=3,
        console=console,
    )
    agent.build_tools()
    agent.build_messages()
    agent.run()
    s = agent.stats
    print(f"Stats: {s}")
    assert s["total_llm_requests"] >= 1, "Should have at least 1 LLM request"
    assert s["total_input_tokens"] > 0, "Should have input tokens"
    assert s["total_output_tokens"] > 0, "Should have output tokens"


def test_subagent_dump():
    """Test that dump creates files."""
    print("\n=== Test 3: Dump File ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    agent = SubAgent(
        parent_ctx=ctx,
        subagent_type="explore",
        prompt="Read src/constants.py line 1 to 5.",
        agent_id="test_dump_001",
        max_steps=3,
        console=console,
    )
    agent.build_tools()
    agent.build_messages()
    agent.run()

    import json
    agent_dir = os.path.join(SESSION_PATH, ctx.session_uuid, SUBAGENT_DUMP_DIR, "test_dump_001")
    assert os.path.exists(os.path.join(agent_dir, CONTEXT_NAME)), "context.json missing"
    assert os.path.exists(os.path.join(agent_dir, MESSAGES_NAME)), "messages.json missing"
    assert os.path.exists(os.path.join(agent_dir, TASKS_NAME)), "tasks.json missing"
    with open(os.path.join(agent_dir, "stats.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["agent_id"] == "test_dump_001"
    assert data["status"] == "done"
    print(f"Dump files ok: {agent_dir}")


def test_agent_id_in_list():
    """Test that agent_list is populated correctly."""
    print("\n=== Test 4: Agent List Registration ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    agent = SubAgent(
        parent_ctx=ctx,
        subagent_type="explore",
        prompt="Read src/constants.py line 1 to 3 and report the constants.",
        agent_id="test_list_001",
        max_steps=3,
        console=console,
    )
    agent.build_tools()
    agent.build_messages()
    ctx.agent_list["test_list_001"] = agent.progress
    agent.run()

    assert "test_list_001" in ctx.agent_list
    p = ctx.agent_list["test_list_001"]
    assert p.status == AgentStatus.DONE
    d = p.to_dict()
    assert d["agent_id"] == "test_list_001"
    assert d["status"] == "done"
    print(f"Agent list ok: {len(ctx.agent_list)} agents")


def test_tool_dispatch_integration():
    """Test that call_tools handles spawn_agent as undefined (it should — dispatch at execute_tools level)."""
    print("\n=== Test 5: Tool Dispatch (spawn_agent in call_tools) ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    from rich.progress import Progress
    progress = Progress(console=Console(quiet=True), disable=True)
    progress.start()

    results, _ = call_tools(AGENT_SPAWN_TOOL_NAME, {"subagent_type": "explore", "prompt": "test"}, ctx, board, progress)
    progress.stop()
    print(f"call_tools result for spawn_agent: {results}")
    # spawn_agent should hit the "undefined" branch in call_tools since dispatch is at execute_tools level
    assert results["status"] == FAIL_LABEL


if __name__ == "__main__":
    test_explore_subagent()
    test_subagent_stats()
    test_subagent_dump()
    test_agent_id_in_list()
    test_tool_dispatch_integration()
    print("\n=== All tests passed! ===")
