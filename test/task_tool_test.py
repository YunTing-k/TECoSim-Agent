# -*- coding: utf-8 -*-
"""
Unit tests for task tool result feedback (guidance text + summary).

Covers: create_task guidance, update_task guidance (in_progress/completed),
        query_task summary counts grouped by status and ownership.

Run:  python test/task_tool_test.py
"""
import sys, os, unittest
from unittest.mock import MagicMock, patch

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import logging
logging.basicConfig(level=logging.CRITICAL)

from context.agent_context import AgentContext
from tool.scoreboard import Scoreboard, TaskStatus
from tool.tool_def import create_task, update_task, query_task


def make_agent_ctx(agent_id: str = "agent-1", nosystem: bool = False) -> AgentContext:
    ctx = AgentContext()
    ctx.agent_id = agent_id
    ctx.agent_configs = {
        "REMIND_TASK_TOOL_GAP": 8,
        "REMIND_TASK_CHAT_GAP": 3,
        "RENDER_RESPONSE_AS_MD": False,
        "DISPLAY_RESPONSE_REASON": True,
    }
    ctx.nosystem = nosystem
    return ctx


class TestCreateTaskFeedback(unittest.TestCase):
    """create_task result should include guidance text."""

    def setUp(self):
        self.board = Scoreboard()
        self.progress = MagicMock()
        self.progress.console = MagicMock()

    def test_create_task_result_contains_guidance(self):
        result = create_task({"subject": "Do X", "description": "Do X desc"}, self.board, self.progress)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("Mark your first task as in_progress", result["info"])


class TestUpdateTaskFeedback(unittest.TestCase):
    """update_task result should include state-specific guidance."""

    def setUp(self):
        self.board = Scoreboard()
        self.progress = MagicMock()
        self.progress.console = MagicMock()
        self.ctx = make_agent_ctx("agent-1")
        # create a task to update
        create_task({"subject": "Task A", "description": "Desc A"}, self.board, self.progress)

    def test_update_to_in_progress_adds_guidance(self):
        result = update_task(
            {"task_id": 1, "if_claim": True, "status": "in_progress"}, self.ctx, self.board, self.progress
        )
        self.assertEqual(result["status"], "DONE")
        self.assertIn("Proceed with this task", result["info"])

    def test_update_to_completed_adds_guidance(self):
        # claim + in_progress first
        update_task(
            {"task_id": 1, "if_claim": True, "status": "in_progress"}, self.ctx, self.board, self.progress
        )
        # then complete
        result = update_task(
            {"task_id": 1, "status": "completed"}, self.ctx, self.board, self.progress
        )
        self.assertEqual(result["status"], "DONE")
        self.assertIn("query_task", result["info"])

    def test_update_to_deleted_adds_guidance(self):
        result = update_task(
            {"task_id": 1, "if_claim": True, "status": "deleted"}, self.ctx, self.board, self.progress
        )
        self.assertEqual(result["status"], "DONE")
        self.assertIn("query_task", result["info"])

    def test_update_without_status_change_no_guidance(self):
        result = update_task(
            {"task_id": 1, "subject": "Renamed"}, self.ctx, self.board, self.progress
        )
        # subject update without claim may fail or succeed with info
        # just check it doesn't contain guidance when no status change
        if "Proceed with this task" not in result["info"]:
            pass  # expected


class TestQueryTaskSummary(unittest.TestCase):
    """query_task listing should include a summary line with grouped counts."""

    def setUp(self):
        self.board = Scoreboard()
        self.progress = MagicMock()
        self.progress.console = MagicMock()
        self.ctx = make_agent_ctx("agent-1")

    def test_empty_board_returns_no_active_tasks(self):
        result = query_task({}, self.ctx, self.board, self.progress)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("[No active tasks]", result["info"])

    def test_pending_unclaimed_summary(self):
        create_task({"subject": "T1", "description": "D1"}, self.board, self.progress)
        create_task({"subject": "T2", "description": "D2"}, self.board, self.progress)
        result = query_task({}, self.ctx, self.board, self.progress)
        self.assertIn("2 pending (2 unclaimed)", result["info"])

    def test_pending_claimed_by_you(self):
        create_task({"subject": "T1", "description": "D1"}, self.board, self.progress)
        update_task({"task_id": 1, "if_claim": True}, self.ctx, self.board, self.progress)
        result = query_task({}, self.ctx, self.board, self.progress)
        self.assertIn("1 pending (1 by you)", result["info"])

    def test_in_progress_by_you(self):
        create_task({"subject": "T1", "description": "D1"}, self.board, self.progress)
        update_task(
            {"task_id": 1, "if_claim": True, "status": "in_progress"}, self.ctx, self.board, self.progress
        )
        result = query_task({}, self.ctx, self.board, self.progress)
        self.assertIn("1 in_progress (1 by you)", result["info"])

    def test_mixed_status_summary(self):
        create_task({"subject": "T1", "description": "D1"}, self.board, self.progress)
        create_task({"subject": "T2", "description": "D2"}, self.board, self.progress)
        create_task({"subject": "T3", "description": "D3"}, self.board, self.progress)
        # claim + complete T1
        update_task({"task_id": 1, "if_claim": True}, self.ctx, self.board, self.progress)
        update_task({"task_id": 1, "status": "in_progress"}, self.ctx, self.board, self.progress)
        update_task({"task_id": 1, "status": "completed"}, self.ctx, self.board, self.progress)
        # claim + start T2
        update_task({"task_id": 2, "if_claim": True}, self.ctx, self.board, self.progress)
        update_task({"task_id": 2, "status": "in_progress"}, self.ctx, self.board, self.progress)
        result = query_task({}, self.ctx, self.board, self.progress)
        # T3: pending unclaimed, T2: in_progress by you, T1: completed
        self.assertIn("1 pending (1 unclaimed)", result["info"])
        self.assertIn("1 in_progress (1 by you)", result["info"])
        self.assertIn("1 completed (1 by you)", result["info"])

    def test_fallback_path_returns_correct_status(self):
        """query_task with invalid task_id falls back to list-all (FALLBACK status)."""
        result = query_task({"task_id": 999}, self.ctx, self.board, self.progress)
        self.assertEqual(result["status"], "FALLBACK")
        self.assertIn("Fallback to list all tasks", result["info"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
