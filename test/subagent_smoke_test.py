# -*- coding: utf-8 -*-
"""
Quick smoke test for SubAgent integration.
Run with: python test/subagent_smoke_test.py
Requires a configured api_configs.json with a valid model.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.context.agent_context import AgentContext
from src.tool.scoreboard import Scoreboard
from src.tool.tool_dispatch import call_tools
from src.agent.subagent import SubAgent
from src.agent.progress import AgentStatus
from src.tool.tool_execute import execute_background_agents, check_background_agents
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


def test_explorer_subagent():
    """Test explore agent reads a file."""
    print("\n=== Test 1: Explore SubAgent ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    agent = SubAgent(
        parent_ctx=ctx,
        subagent_type="explorer",
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
        subagent_type="explorer",
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
        subagent_type="explorer",
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
        subagent_type="explorer",
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

    results, _ = call_tools(TOOL_NAME_SPAWN_AGENT, {"subagent_type": "explorer", "prompt": "test"}, ctx, board, progress)
    progress.stop()
    print(f"call_tools result for spawn_agent: {results}")
    # spawn_agent should hit the "undefined" branch in call_tools since dispatch is at execute_tools level
    assert results["status"] == FAIL_LABEL


def test_background_agent_launch():
    """Test execute_background_agents launches agents and returns placeholder."""
    print("\n=== Test 6: Background Agent Launch ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    from rich.progress import Progress
    import json
    progress = Progress(console=Console(quiet=True), disable=True)

    tc = {"function": {"name": TOOL_NAME_SPAWN_AGENT, "arguments": json.dumps({
        "subagent_type": "explorer", "subject": "check version", "prompt": "Read src/constants.py with limit 3 lines and report the version constant.",
        "if_background": True,
    })}, "id": "call_test_bg_001"}

    bg_initial_count = len(ctx.background_agents)

    messages = execute_background_agents([tc], ctx, board, progress)
    progress.stop()

    assert len(messages) == 1, "Should return exactly 1 placeholder message"
    assert messages[0]["tool_call_id"] == "call_test_bg_001"
    content = json.loads(messages[0]["content"])
    assert content["status"] == DONE_LABEL
    assert "started" in content["info"], f"Expected 'started' in info: {content['info']}"

    assert len(ctx.background_agents) == bg_initial_count + 1
    bg_tc, bg_agent, bg_thread, _ = ctx.background_agents[-1]
    assert bg_tc is tc
    assert bg_agent.subagent_type == "explorer"
    assert bg_thread.is_alive() or bg_agent.status != AgentStatus.PENDING
    assert bg_agent.agent_id in ctx.agent_list
    assert ctx.agent_list[bg_agent.agent_id].status in (AgentStatus.PENDING, AgentStatus.RUNNING)

    bg_thread.join(timeout=60)  # wait for completion or timeout
    print(f"Background agent: status={bg_agent.status.value}, result_preview={bg_agent.result[:100] if bg_agent.result else 'None'}")
    print("Background agent launch test ok")


def test_background_agent_collect():
    """Test check_background_agents collects completed agent results."""
    print("\n=== Test 7: Background Agent Collection ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    from rich.progress import Progress
    import json
    progress = Progress(console=Console(quiet=True), disable=True)

    tc = {"function": {"name": TOOL_NAME_SPAWN_AGENT, "arguments": json.dumps({
        "subagent_type": "explorer", "subject": "check version", "prompt": "Read src/constants.py with limit 3 lines and report the version constant.",
        "if_background": True,
    })}, "id": "call_test_collect_001"}

    execute_background_agents([tc], ctx, board, progress)
    progress.stop()

    bg_agent_id = ctx.background_agents[-1][1].agent_id
    msgs_before = len(ctx.messages)
    requests_before = ctx.total_llm_requests

    ctx.background_agents[-1][2].join(timeout=60)
    import time
    time.sleep(0.5)  # let thread fully exit

    result = check_background_agents(ctx)
    assert result, "check_background_agents should return True when agent completed"

    assert len(ctx.background_agents) == 0, "completed agent should be removed from background_agents"
    assert len(ctx.messages) > msgs_before, "result message should be injected"
    assert ctx.total_llm_requests > requests_before, "stats should be merged"

    last_msg = ctx.messages[-1]["content"]
    assert SUBAGENT_START_LABEL in last_msg
    assert bg_agent_id in last_msg
    assert ctx.agent_list[bg_agent_id].if_archived, "agent progress should be archived"

    print(f"Collected message preview: {last_msg[:200]}...")
    print("Background agent collection test ok")


def test_execute_tools_bg_fg_split():
    """Test that execute_tools correctly splits and executes bg/fg agents."""
    print("\n=== Test 8: Execute Tools BG/FG Split ===")
    ctx = setup_ctx()
    board = Scoreboard()
    board.session_uuid = ctx.session_uuid

    from rich.progress import Progress
    import json
    from src.tool.tool_execute import execute_tools

    progress = Progress(console=Console(quiet=True), disable=True)

    tcs = [
        {
            "function": {"name": TOOL_NAME_VERSION, "arguments": "{}"},
            "id": "call_ver_001",
        },
        {
            "function": {"name": TOOL_NAME_SPAWN_AGENT, "arguments": json.dumps({
                "subagent_type": "explorer",
                "subject": "check version bg",
                "prompt": "Read src/constants.py with limit 3 lines and report the version.",
                "if_background": True,
            })},
            "id": "call_bg_001",
        },
        {
            "function": {"name": TOOL_NAME_SPAWN_AGENT, "arguments": json.dumps({
                "subagent_type": "explorer",
                "subject": "check constants fg",
                "prompt": "Read src/constants.py with limit 5 lines and report the constants.",
                "if_background": False,
            })},
            "id": "call_fg_001",
        },
    ]

    msgs = execute_tools(tcs, ctx, board, progress)
    progress.stop()

    assert len(msgs) >= 3, f"Should have >= 3 messages (ver + bg + fg), got {len(msgs)}"

    ver_msg = next(m for m in msgs if m["tool_call_id"] == "call_ver_001")
    ver_content = json.loads(ver_msg["content"])
    assert ver_content["status"] == SUCCESS_LABEL

    bg_msg = next(m for m in msgs if m["tool_call_id"] == "call_bg_001")
    bg_content = json.loads(bg_msg["content"])
    assert "started" in bg_content.get("info", "")

    fg_msg = next(m for m in msgs if m["tool_call_id"] == "call_fg_001")
    fg_content = json.loads(fg_msg["content"])
    assert fg_content.get("status") in (DONE_LABEL, FAIL_LABEL)

    assert len(ctx.background_agents) >= 1, "Background agent should be registered"

    ctx.background_agents[-1][2].join(timeout=60)
    check_background_agents(ctx)
    assert len(ctx.background_agents) == 0, "Background agent should be cleaned up after collection"

    print(f"Normal: ver got status={ver_content['status']}")
    print(f"BG placeholder: {bg_content['info'][:80]}")
    print(f"FG result: status={fg_content['status']}")
    print("Execute tools bg/fg split test ok")


if __name__ == "__main__":
    test_explorer_subagent()
    test_subagent_stats()
    test_subagent_dump()
    test_agent_id_in_list()
    test_tool_dispatch_integration()
    test_background_agent_launch()
    test_background_agent_collect()
    test_execute_tools_bg_fg_split()
    print("\n=== All tests passed! ===")
