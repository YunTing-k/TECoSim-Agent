# -*- coding: utf-8 -*-
"""
Unit tests for Scoreboard class (direct methods, not tool wrappers).
Run: python -m unittest test.scoreboard_test
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tool.scoreboard import Scoreboard, TaskStatus


class TestScoreboardCreate(unittest.TestCase):
    def setUp(self):
        self.board = Scoreboard()

    def test_create_task(self):
        ok, info = self.board.create_task("Do X", "Desc X")
        self.assertTrue(ok)
        self.assertIn("Task with id 1 created", info)

    def test_create_multiple(self):
        self.board.create_task("T1", "D1")
        self.board.create_task("T2", "D2")
        self.board.create_task("T3", "D3")
        self.assertEqual(len(self.board.list_all_tasks()), 3)

    def test_initial_status_is_pending(self):
        self.board.create_task("Test", "Desc")
        ok, task, _ = self.board.get_task(1)
        self.assertTrue(ok)
        self.assertEqual(task["status"], TaskStatus.PENDING)

    def test_initial_owner_is_none(self):
        self.board.create_task("Test", "Desc")
        ok, task, _ = self.board.get_task(1)
        self.assertIsNone(task["owner"])


class TestScoreboardUpdate(unittest.TestCase):
    def setUp(self):
        self.board = Scoreboard()
        self.board.create_task("T1", "D1")
        self.board.create_task("T2", "D2")
        self.board.create_task("T3", "D3")

    def _update(self, task_id, **kw):
        info = {
            "task_id": task_id,
            "if_claim": kw.get("if_claim", False),
            "requester": kw.get("requester", "agent-1"),
            "subject": kw.get("subject"),
            "description": kw.get("description"),
            "status": kw.get("status"),
            "add_blocks": kw.get("add_blocks"),
            "add_blocked_by": kw.get("add_blocked_by"),
        }
        ok, msg = self.board.update_task(info)
        return ok, msg

    def test_claim_unowned_task(self):
        ok, _ = self._update(1, if_claim=True)
        self.assertTrue(ok)
        _, task, _ = self.board.get_task(1)
        self.assertEqual(task["owner"], "agent-1")

    def test_claim_blocked_task_fails(self):
        # task 1 blocks task 2, so task 2 cannot be claimed (it is blocked)
        self._update(1, add_blocks=[2])
        ok, msg = self._update(2, if_claim=True)
        self.assertFalse(ok)
        self.assertIn("blocked", msg)

    def test_status_transition(self):
        self._update(1, if_claim=True)
        self._update(1, status="in_progress")
        _, task, _ = self.board.get_task(1)
        self.assertEqual(task["status"], TaskStatus.IN_PROGRESS)

    def test_complete_task_clears_blocks(self):
        self._update(1, if_claim=True, status="in_progress")
        self._update(1, add_blocks=[2])
        self._update(1, status=TaskStatus.COMPLETED)
        _, task, _ = self.board.get_task(1)
        self.assertEqual(task["blocks"], [])

    def test_add_blocks(self):
        self._update(1, add_blocks=[2, 3])
        _, task, _ = self.board.get_task(1)
        self.assertEqual(set(task["blocks"]), {2, 3})
        _, t2, _ = self.board.get_task(2)
        self.assertIn(1, t2["blocked_by"])
        _, t3, _ = self.board.get_task(3)
        self.assertIn(1, t3["blocked_by"])

    def test_add_blocked_by(self):
        self._update(3, add_blocked_by=[1, 2])
        _, task, _ = self.board.get_task(3)
        self.assertEqual(set(task["blocked_by"]), {1, 2})
        _, t1, _ = self.board.get_task(1)
        self.assertIn(3, t1["blocks"])

    def test_block_nonexistent_task_ignored(self):
        ok, msg = self._update(1, add_blocks=[999])
        self.assertFalse(ok)
        self.assertIn("does not exist", msg)

    def test_blocked_by_nonexistent_task_ignored(self):
        ok, msg = self._update(1, add_blocked_by=[999])
        self.assertFalse(ok)
        self.assertIn("does not exist", msg)

    def test_self_block_ignored(self):
        ok, msg = self._update(1, add_blocks=[1])
        self.assertFalse(ok)
        self.assertIn("can't block itself", msg)
        _, task, _ = self.board.get_task(1)
        self.assertEqual(task["blocks"], [])

    def test_circular_dependency_detected(self):
        self._update(1, add_blocks=[2])
        self._update(2, add_blocks=[3])
        ok, msg = self._update(3, add_blocks=[1])
        self.assertFalse(ok)
        self.assertIn("circular dependency", msg)

    def test_nonexistent_task_id(self):
        ok, msg = self._update(999, subject="X")
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_completed_task_cannot_be_deleted(self):
        self._update(1, if_claim=True, status="in_progress")
        self._update(1, status=TaskStatus.COMPLETED)
        ok, msg = self._update(1, status=TaskStatus.DELETED)
        self.assertFalse(ok)
        self.assertIn("already resolved", msg)
        _, task, _ = self.board.get_task(1)
        self.assertEqual(task["status"], TaskStatus.COMPLETED)  # unchanged

    def test_completed_task_cannot_change_status(self):
        self._update(1, if_claim=True, status=TaskStatus.COMPLETED)
        ok, msg = self._update(1, status=TaskStatus.IN_PROGRESS)
        self.assertFalse(ok)
        self.assertIn("already resolved", msg)


class TestScoreboardQuery(unittest.TestCase):
    def setUp(self):
        self.board = Scoreboard()
        self.board.create_task("T1", "D1")
        self.board.create_task("T2", "D2")
        self.board.create_task("T3", "D3")
        # claim and complete T2
        self.board.update_task({
            "task_id": 2, "if_claim": True, "requester": "agent-1",
            "subject": None, "description": None, "status": None,
            "add_blocks": None, "add_blocked_by": None,
        })
        self.board.update_task({
            "task_id": 2, "status": "completed", "requester": "agent-1",
            "subject": None, "description": None,
            "if_claim": False, "add_blocks": None, "add_blocked_by": None,
        })

    def test_get_existing_task(self):
        ok, task, info = self.board.get_task(1)
        self.assertTrue(ok)
        self.assertEqual(task["subject"], "T1")

    def test_get_nonexistent_task(self):
        ok, task, info = self.board.get_task(999)
        self.assertFalse(ok)
        self.assertIn("not found", info)

    def test_list_all(self):
        tasks = self.board.list_all_tasks()
        self.assertEqual(len(tasks), 3)

    def test_list_non_archived(self):
        tasks = self.board.list_tasks()
        self.assertEqual(len(tasks), 3)

    def test_list_archived_hides_completed(self):
        for _ in range(6):
            self.board.archive_tasks()
        tasks = self.board.list_tasks()
        self.assertEqual(len(tasks), 2)

    def test_list_unresolved(self):
        tasks = self.board.list_unresolved_tasks()
        self.assertEqual(len(tasks), 2)

    def test_list_by_agent(self):
        tasks = self.board.list_tasks("agent-1")
        self.assertEqual(len(tasks), 1)

    def test_list_by_nonexistent_agent(self):
        tasks = self.board.list_tasks("agent-unknown")
        self.assertEqual(len(tasks), 0)


if __name__ == "__main__":
    unittest.main()
