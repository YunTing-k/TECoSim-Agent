# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.5
Description: Task scoreboard for multi-agent coordination

Revision:
---------
2026.6.5-7       Yu Huang       1.0      First implementation
2026.6.9         Yu Huang       1.1      Revise the highlight of the IO console print
2026.6.10        Yu Huang       1.2      Add reminder for LLM to manage workflow proactively

Details:
---------
Scoreboard is a shared, thread-safe task board visible to all agents (main + subagents).
Each task has an ID, subject, description, status, owner, dependency links, and metadata.
All CRUD operations are protected by a threading.Lock for concurrent safety.

Status transitions (forward-only, no rollback):
  pending ──→ in_progress ──→ completed
       │                        │
       └──────→ deleted ←───────┘
  - completed / deleted are resolved states, cannot be changed further.
  - in_progress cannot go back to pending.
  - Any state can be marked as deleted.

Dependency management:
  - blocks: IDs of tasks that this task blocks (outgoing edges).
  - blocked_by: IDs of tasks that block this task (incoming edges).
  - Setting add_blocks auto-syncs the target's blocked_by, and vice versa.
  - Circular dependencies are detected recursively (both directions) and rejected.
  - Resolved tasks (completed/deleted) are skipped during cycle traversal.
  - Self-blocking and blocking resolved tasks are filtered out.
"""
import os
import json
import uuid
import logging
import threading

from datetime import datetime
from typing import Any, TypedDict
from enum import Enum
from rich.console import Console, Text
from src.utility.basic_utils import is_list_of_int
from src.constants import *

sys_log = logging.getLogger('logger')


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = TASK_PENDING_LABEL
    IN_PROGRESS = TASK_IN_PROGRESS_LABEL
    COMPLETED = TASK_COMPLETED_LABEL
    DELETED = TASK_DELETED_LABEL


"""status level of task"""
TaskStatusLevel: dict[TaskStatus, int] = {
    TaskStatus.PENDING: 0,
    TaskStatus.IN_PROGRESS: 1,
    TaskStatus.COMPLETED: 2,
    TaskStatus.DELETED: 2,
}


class Task(TypedDict):
    """Single task on the scoreboard"""
    task_id: int
    subject: str
    description: str
    status: TaskStatus  # status of the task
    blocks: list[int]  # IDs of tasks that this task blocks
    blocked_by: list[int]  # IDs of tasks that block this task
    owner: str | None  # owner of this task
    if_archived: bool  # if a resolved task is archived
    displays: int  # how many times this task is displayed


class TaskUpdate(TypedDict):
    """Data pack to update a task on the scoreboard"""
    task_id: int  # input task id
    if_claim: bool  # if claim the task
    requester: str  # input id of requester
    subject: str | None  # input subject
    description: str | None  # input description
    status: TaskStatus | None  # input status
    add_blocks: list[int] | None  # input blocks to add
    add_blocked_by: list[int] | None  # input blocked_by to add


class Scoreboard:
    """Shared, thread-safe task board for multi-agent coordination.

    All agents (main loop + subagents) read/write tasks through this class.
    Internal threading.Lock serializes all operations for concurrent safety.
    """

    def __init__(self):
        self.session_uuid = ""  # don't dump
        self._lock = threading.Lock()
        self._tasks: dict[int, Task] = {}
        self._next_id: int = 1


    def _would_create_cycle(self, source_id: int, target_id: int, visited: set[int] | None = None,
                            reverse: bool = False) -> bool:
        """Check if adding source -> target would create a circular dependency. (only used in lock)

        Forward (reverse=False): start from target, follow its 'blocks' chain.
            If we ever reach source, then source blocking target would create a cycle.
            Used in add_blocks scenario.

        Reverse (reverse=True): start from target, follow its 'blocked_by' chain.
            If we ever reach source, then source being blocked by target would create a cycle.
            Used in add_blocked_by scenario.

        Resolved tasks (completed/deleted) are skipped during traversal since their
        dependency links are no longer active.
        """
        if visited is None:
            visited = set()
        assert visited is not None  # narrow type for static analysis

        dep_key = "blocked_by" if reverse else "blocks"
        assert dep_key in ("blocked_by", "blocks")
        for dep_id in self._tasks[target_id][dep_key]:
            if dep_id == source_id:
                return True
            if dep_id in visited:
                continue
            # skip resolved tasks — their dependency links are stale
            if self._tasks[dep_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                continue
            visited.add(dep_id)
            if self._would_create_cycle(source_id, dep_id, visited, reverse):
                return True
        return False


    def create_task(self, subject: str, description: str) -> tuple[bool, str]:
        """create a new task on the scoreboard"""
        with self._lock:
            try:
                task = Task(
                    task_id=self._next_id,
                    subject=subject,
                    description=description,
                    status=TaskStatus.PENDING,
                    blocks=[],
                    blocked_by=[],
                    owner=None,
                    if_archived=False,
                    displays=0,
                )
                self._tasks[self._next_id] = task
                self._next_id += 1
                return True, f"Task with id {task["task_id"]} created"
            except Exception as e:
                return False, f"Create task failed with error: {e}"


    def update_task(self, task_info: TaskUpdate) -> tuple[bool, str]:
        """Update a task's fields. Returns (ok, error_msg | updated_task).

        Status rules (enforced):
          - Resolved states (completed, deleted) cannot be changed.
          - in_progress cannot roll back to pending.

        Permission rules (enforced):
          - Only owner can change: subject, description, status.
          - Anyone can change: blocks, blocked_by, owner (not-claimed).

        Agents should call list_all() before update() to get the latest state.
        Agents SHOULD NOT overhaul subject/description — mark as deleted and recreate instead.
        """
        with (self._lock):
            """check if task exists"""
            if task_info["task_id"] not in self._tasks:
                return False, f"Task with id {task_info["task_id"]} not found"

            try:
                t_id = task_info["task_id"]
                t_claim = task_info["if_claim"]
                t_requester = task_info["requester"]
                t_subject = task_info["subject"]
                t_description = task_info["description"]
                t_status = task_info["status"]
                t_add_blocks = task_info["add_blocks"]
                t_add_blocked_by = task_info["add_blocked_by"]

                has_change = False
                info = ""

                """update a task without owner"""
                if self._tasks[t_id]["owner"] is None:
                    """
                    If a task has no owner, can claim it when
                    1). Task is not blocked by any task
                    """
                    if t_claim:
                        if len(self._tasks[t_id]["blocked_by"]) == 0:
                            has_change = True
                            self._tasks[t_id]["owner"] = t_requester
                            info += f"Task (id {t_id}) claimed by you. "
                        else:
                            return False, f"Task (id {t_id}) is blocked by following list of tasks: {self._tasks[t_id]["blocked_by"]}. Claim failed."
                    """
                    If a task has no owner, can update subject/description when:
                    1). Requester try to claim
                    
                    If requester do not claim but modified it, dependency chain is dependent on subject/description, so it is 
                    hard to synchronize among agents. Therefore, requester try to claim task is also reponsibe for updateing 
                    blocks and blocked_by when they modified the subject and description
                    """
                    if t_subject is not None:
                        if t_claim:
                            has_change = True
                            self._tasks[t_id]["subject"] = t_subject
                            info += f"Task (id {t_id})'s subject updated by you. "
                        else:
                            info += (f"Task (id {t_id})'s subject unchanged (subject of task without owner can't be updated by "
                                     f"a non-claimer). ")
                    if t_description is not None:
                        if t_claim:
                            has_change = True
                            self._tasks[t_id]["description"] = t_description
                            info += f"Task (id {t_id})'s description updated by you. "
                        else:
                            info += (f"Task (id {t_id})'s description unchanged (description of task without owner can't be "
                                     f"updated by a non-claimer). ")
                    """
                    If a task has no owner, can update status:
                    1). Requester try to claim
                    
                    Since status of task also effects dependency chain, non-claimer can't modify the task's status
                    """
                    if t_status is not None:
                        if t_claim:
                            # status is pending now, can be any status
                            if self._tasks[t_id]["status"] == t_status:
                                info += f"Task (id {t_id})'s status unchanged. "
                            else:
                                has_change = True
                                self._tasks[t_id]["status"] = t_status
                                info += f"Task (id {t_id})'s status update to {t_status} by you. "
                                """update the block status of all tasks"""
                                if self._tasks[t_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    self._tasks[t_id]["blocks"] = []  # clean this task's blocks
                                    for task in self._tasks.values():
                                        if t_id in task["blocked_by"]:  # the task is previously blocked by this task
                                            blocked_by = list(set(task["blocked_by"]) - {self._tasks[t_id]["task_id"]})
                                            self._tasks[task["task_id"]]["blocked_by"] = blocked_by
                        else:
                            info += (f"Task (id {t_id})'s status unchanged (status of task without owner can't be updated by a "
                                     f"non-claimer). ")
                    """
                    If a task has no owner, can update blocks when:
                    1). Task is non-resolved and requester do not try to claim
                    2). Task is non-resolved and requester try to claim
                    
                    Only claimer can modify subject/description, since they can effect dependency chain. Both claimer and non-claimer
                    are responsible to maintain the blocks and blocked_by. (We can't stop a non-claimer to modify, their own
                    task also need to maintain)
                    """
                    if self._tasks[t_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                        if (t_add_blocks is not None and t_add_blocks) or (t_add_blocked_by is not None and t_add_blocked_by):
                            info += f"Task (id {t_id}) is already resolved, you can't modify its dependency. "
                    else:
                        if t_add_blocks is not None and t_add_blocks:
                            has_change = True
                            clean_add_blocks = list(set(t_add_blocks) - set(self._tasks[t_id]["blocks"]))
                            validated_new_blocks: list[int] = []
                            for task_id in clean_add_blocks:
                                # block itself
                                if task_id == self._tasks[t_id]["task_id"]:
                                    info += f"Task (id {t_id}) can't block itself, self block dependency ignored. "
                                    continue
                                # block resolved
                                if self._tasks[task_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    info += f"Task (id {t_id}) can't blocks a resolved task (id {task_id}), ignored. "
                                    continue
                                # circular dependency detection
                                if self._would_create_cycle(t_id, task_id):
                                    info += f"Task (id {t_id}) blocking task (id {task_id}) would create a circular dependency, ignored. "
                                    continue
                                validated_new_blocks.append(task_id)
                            # merge blocks
                            new_blocks = list(set(self._tasks[t_id]["blocks"]) | set(validated_new_blocks))
                            self._tasks[t_id]["blocks"] = new_blocks
                            # synchronize all tasks' blocked_by
                            for blocked_id in validated_new_blocks:  # always not a resolved task
                                self._tasks[blocked_id]["blocked_by"] = list(set(self._tasks[blocked_id]["blocked_by"]) | {t_id})
                        if t_add_blocked_by is not None and t_add_blocked_by:
                            has_change = True
                            clean_blocked_by = list(set(t_add_blocked_by) - set(self._tasks[t_id]["blocked_by"]))
                            validated_new_blocked_by: list[int] = []
                            for task_id in clean_blocked_by:
                                # block itself
                                if task_id == self._tasks[t_id]["task_id"]:
                                    info += f"Task (id {t_id}) can't block itself, self block dependency ignored. "
                                    continue
                                # block resolved
                                if self._tasks[task_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    info += f"Task (id {t_id}) can't be blocked by a resolved task (id {task_id}), ignored. "
                                    continue
                                # circular dependency detection
                                if self._would_create_cycle(t_id, task_id, reverse=True):
                                    info += f"Task (id {t_id}) being blocked by task (id {task_id}) would create a circular dependency, ignored. "
                                    continue
                                validated_new_blocked_by.append(task_id)
                            # merge blocked_by
                            new_blocked_by = list(set(self._tasks[t_id]["blocked_by"]) | set(validated_new_blocked_by))
                            self._tasks[t_id]["blocked_by"] = new_blocked_by
                            for blocker_id in validated_new_blocked_by:  # always not a resolved task
                                self._tasks[blocker_id]["blocks"] = list(set(self._tasks[blocker_id]["blocks"]) | {t_id})
                    if has_change:
                        return True, info
                    if info.strip():
                        return False, f"Nothing changes in target task, details: {info}"
                    else:
                        return False, f"Nothing changes in target task, please check your params"

                else:  # update a task with owner
                    """
                    If a task has owner, no one can try to claim it
                    """
                    if t_claim:
                        if self._tasks[t_id]["owner"] == t_requester:
                            info += f"Task (id {t_id}) is already claimed by you. "
                        else:
                            # update behavior for claimer and non-claimer are different, so need to fail immediately
                            return False, f"Task (id {t_id}) is already claimed by agent (id {t_requester}), update failed."
                    """
                    If a task has owner, can update subject/description when:
                    1). Requester is owner
                    """
                    if t_subject is not None:
                        if self._tasks[t_id]["owner"] == t_requester:
                            has_change = True
                            self._tasks[t_id]["subject"] = t_subject
                            info += f"Task (id {t_id})'s subject updated by you. "
                        else:
                            info += f"Task (id {t_id})'s subject unchanged (subject of task can only be updated by owner)"
                    if t_description is not None:
                        if self._tasks[t_id]["owner"] == t_requester:
                            has_change = True
                            self._tasks[t_id]["description"] = t_description
                            info += f"Task (id {t_id})'s description updated by you. "
                        else:
                            info += f"Task (id {t_id})'s description unchanged (description of task can only be updated by owner)"
                    """
                    If a task has owner, can update status:
                    1). Requester is owner and the direction of status is forward
                    """
                    if t_status is not None:
                        if self._tasks[t_id]["owner"] == t_requester:
                            if self._tasks[t_id]["status"] == t_status:
                                info += f"Task (id {t_id})'s status unchanged: {t_status}. "
                            elif TaskStatusLevel[t_status] < TaskStatusLevel[self._tasks[t_id]["status"]]:
                                info += f"Task (id {t_id})'s status can't be rolled back. "
                            else:
                                has_change = True
                                self._tasks[t_id]["status"] = t_status
                                info += f"Task (id {t_id})'s status update to {t_status} by you. "
                                """update the block status of all tasks"""
                                if self._tasks[t_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    self._tasks[t_id]["blocks"] = []  # clean this task's blocks
                                    for task in self._tasks.values():
                                        if t_id in task["blocked_by"]:  # the task is previously blocked by this task
                                            blocked_by = list(set(task["blocked_by"]) - {self._tasks[t_id]["task_id"]})
                                            self._tasks[task["task_id"]]["blocked_by"] = blocked_by
                        else:
                            info += f"Task (id {t_id})'s status unchanged (status of task can only be updated by owner)"
                    """
                    If a task has owner, can update blocks when:
                    1). Task is non-resolved and requester do not try to claim
                    2). Task is non-resolved and owner try to claim (non-owner case is blocked)
                    """
                    if self._tasks[t_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                        if (t_add_blocks is not None and t_add_blocks) or (t_add_blocked_by is not None and t_add_blocked_by):
                            info += f"Task (id {t_id}) is already resolved, you can't modify its dependency. "
                    else:
                        if t_add_blocks is not None and t_add_blocks:
                            has_change = True
                            clean_add_blocks = list(set(t_add_blocks) - set(self._tasks[t_id]["blocks"]))
                            validated_new_blocks: list[int] = []
                            for task_id in clean_add_blocks:
                                # block itself
                                if task_id == self._tasks[t_id]["task_id"]:
                                    info += f"Task (id {t_id}) can't block itself, self block dependency ignored. "
                                    continue
                                # block resolved
                                if self._tasks[task_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    info += f"Task (id {t_id}) can't blocks a resolved task (id {task_id}), ignored. "
                                    continue
                                # circular dependency detection
                                if self._would_create_cycle(t_id, task_id):
                                    info += f"Task (id {t_id}) blocking task (id {task_id}) would create a circular dependency, ignored. "
                                    continue
                                validated_new_blocks.append(task_id)
                            # merge blocks
                            new_blocks = list(set(self._tasks[t_id]["blocks"]) | set(validated_new_blocks))
                            self._tasks[t_id]["blocks"] = new_blocks
                            # synchronize all tasks' blocked_by
                            for blocked_id in validated_new_blocks:  # always not a resolved task
                                self._tasks[blocked_id]["blocked_by"] = list(set(self._tasks[blocked_id]["blocked_by"]) | {t_id})
                        if t_add_blocked_by is not None and t_add_blocked_by:
                            has_change = True
                            clean_blocked_by = list(set(t_add_blocked_by) - set(self._tasks[t_id]["blocked_by"]))
                            validated_new_blocked_by: list[int] = []
                            for task_id in clean_blocked_by:
                                # block itself
                                if task_id == self._tasks[t_id]["task_id"]:
                                    info += f"Task (id {t_id}) can't block itself, self block dependency ignored. "
                                    continue
                                # block resolved
                                if self._tasks[task_id]["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                                    info += f"Task (id {t_id}) can't be blocked by a resolved task (id {task_id}), ignored. "
                                    continue
                                # circular dependency detection
                                if self._would_create_cycle(t_id, task_id, reverse=True):
                                    info += f"Task (id {t_id}) being blocked by task (id {task_id}) would create a circular dependency, ignored. "
                                    continue
                                validated_new_blocked_by.append(task_id)
                            # merge blocked_by
                            new_blocked_by = list(set(self._tasks[t_id]["blocked_by"]) | set(validated_new_blocked_by))
                            self._tasks[t_id]["blocked_by"] = new_blocked_by
                            for blocker_id in validated_new_blocked_by:  # always not a resolved task
                                self._tasks[blocker_id]["blocks"] = list(set(self._tasks[blocker_id]["blocks"]) | {t_id})
                    if has_change:
                        return True, info
                    if info.strip():
                        return False, f"Nothing changes in target task, details: {info}"
                    else:
                        return False, f"Nothing changes in target task, please check your params"
            except Exception as e:
                return False, f"Update task failed with error: {e}"


    def get_task(self, task_id: int) -> tuple[bool, Task | None, str]:
        """get a task from the scoreboard"""
        with self._lock:
            """check if task exists"""
            if task_id not in self._tasks:
                return False, None, f"Task with id: {task_id} not found"
            """get the task"""
            try:
                task = self._tasks[task_id]
                return True, task, SUCCESS_LABEL
            except Exception as e:
                return False, None, f"Get task failed with error: {e}"


    def list_all_tasks(self, agent_id: str | None = None) -> list[Task]:
        """list all or agent's tasks (exclude unclaimed) in the scoreboard"""
        with self._lock:
            if agent_id is None:
                return [task for task in self._tasks.values()]
            else:
                return [task for task in self._tasks.values() if task["owner"] == agent_id]


    def list_tasks(self, agent_id: str | None = None) -> list[Task]:
        """list all non-archived or agent's non-archived tasks (exclude unclaimed) in the scoreboard"""
        with self._lock:
            if agent_id is None:
                return [task for task in self._tasks.values() if not task["if_archived"]]
            else:
                return [task for task in self._tasks.values() if (not task["if_archived"]) and (task["owner"] == agent_id)]


    def list_unresolved_tasks(self, agent_id: str | None = None) -> list[Task]:
        """list all unresolved or agent's unresolved tasks (exclude unclaimed) in the scoreboard, """
        with self._lock:
            if agent_id is None:
                return [task for task in self._tasks.values() if task["status"]
                        not in (TaskStatus.COMPLETED, TaskStatus.DELETED)]
            else:
                return [task for task in self._tasks.values() if
                        (task["status"] not in (TaskStatus.COMPLETED, TaskStatus.DELETED)) and (task["owner"] == agent_id)]


    def list_unclaimed_tasks(self) -> list[Task]:
        """list all unclaimed tasks in the scoreboard"""
        with self._lock:
            return [task for task in self._tasks.values() if task["owner"] is None]


    def archive_tasks(self):
        """archive resolved tasks (completed/deleted).

        After archived the tasks, resolved tasks are archived so they won't appear in
        subsequent list() calls. A resolved task will not be archived immediately —
        instead, it will be displayed at most TASK_DISPLAYS_BEFORE_ARCHIVED times
        before being marked as archived, giving users a chance to see its final status.

        NOTE: This function is designed to be called only in code paths where tasks
        may potentially be created, ensuring timely archiving without unnecessary
        overhead in read-only contexts. This helps maintain a clean task list for
        a better user experience.
        """
        with self._lock:
            for task in self._tasks.values():
                if task["if_archived"]:
                    continue
                if task["status"] in (TaskStatus.COMPLETED, TaskStatus.DELETED):
                    if task["displays"] < TASK_DISPLAYS_BEFORE_ARCHIVED - 1:
                        self._tasks[task["task_id"]]["displays"] += 1
                    else:
                        self._tasks[task["task_id"]]["if_archived"] = True


    def save_to_file(self, console: Console, mute: bool = False):
        """save all tasks to a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                tasks_data = []
                for task in self._tasks.values():
                    task_copy = dict(task)
                    tasks_data.append(task_copy)

                data = {
                    "next_id": self._next_id,
                    "tasks": tasks_data,
                }
                path = os.path.join(SESSION_PATH, uuid_str, TASKS_NAME)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if not mute:
                    sys_log.debug(f"Scoreboard of session {self.session_uuid} saved")
                    console.print(f"[{MAJOR_COLOR2}]Scoreboard[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}[/bright_black] saved")
            except Exception as e:
                sys_log.error(f"Failed to save session {self.session_uuid}'s scoreboard with error: {e}")
                console.print(f"Failed to save session {self.session_uuid}'s scoreboard with error: {e}", style="bold red")
                raise RuntimeError(e)


    def load_from_file(self, console: Console, mute: bool = False):
        """load tasks from a JSON file (this method can't be called in other threads)"""
        with self._lock:
            try:
                uuid_obj = uuid.UUID(self.session_uuid)
                uuid_str = uuid_obj.__str__()
                path = os.path.join(SESSION_PATH, uuid_str, TASKS_NAME)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._tasks.clear()
                for task_data in data["tasks"]:
                    task_data["status"] = TaskStatus(task_data["status"])
                    task = Task(**task_data)
                    self._tasks[task["task_id"]] = task
                self._next_id = data["next_id"]
                if not mute:
                    sys_log.debug(f"Scoreboard of session {self.session_uuid} loaded")
                    console.print(f"[{MAJOR_COLOR2}]Scoreboard[/{MAJOR_COLOR2}] of session [bright_black]{self.session_uuid}"
                                  f"[/bright_black] loaded")
            except Exception as e:
                sys_log.error(f"Failed to load session {self.session_uuid}'s scoreboard with error: {e}")
                console.print(f"Failed to load session {self.session_uuid}'s scoreboard with error: {e}", style="bold red")
                raise RuntimeError(e)


def args_to_taskupdate(arguments: dict[str, Any], agent_id: str) -> tuple[bool, TaskUpdate | None, str]:
    """get taskupdate from arguments"""
    is_valid = True
    info = ""
    if not isinstance(arguments["task_id"], int):
        is_valid = False
        info += "task_id is not an integer. "
    if arguments.get("if_claim", None) is not None:
        if not isinstance(arguments["if_claim"], bool):
            is_valid = False
            info += "if_claim is not a boolean. "
    if arguments.get("status", None) is not None:
        if arguments["status"] not in [status.value for status in TaskStatus]:
            is_valid = False
            info += "status is not in enum. "
            status = None
        else:
            status = TaskStatus(arguments["status"])
    else:
        status = None
    if arguments.get("add_blocks", None) is not None:
        if not is_list_of_int(arguments["add_blocks"]):
            is_valid = False
            info += "add_blocks is not a list of integers. "
    if arguments.get("add_blocked_by", None) is not None:
        if not is_list_of_int(arguments["add_blocked_by"]):
            is_valid = False
            info += "add_blocked_by is not a list of integers. "
    if not is_valid:
        return False, None, info

    update = TaskUpdate(
        task_id=arguments["task_id"],
        if_claim=arguments.get("if_claim", False),
        requester=agent_id,
        subject=arguments.get("subject", None),
        description=arguments.get("description", None),
        status=status,
        add_blocks=arguments.get("add_blocks", None),
        add_blocked_by=arguments.get("add_blocked_by", None),
    )
    return True, update, SUCCESS_LABEL


def task_to_info(task: Task, agent_id: str) -> str:
    """convert task to info string"""
    info = ""
    info += f"Subject: {task["subject"]}\n"
    info += f"Description: {task["description"]}\n"
    if task["owner"] is None:
        info += f"Owner ID: (None)\n"
    elif task["owner"] == agent_id:
        info += f"Owner ID: {task["owner"]} (You)\n"
    else:
        info += f"Owner ID: {task["owner"]} (other agent)\n"
    info += f"Status: {task["status"]}\n"
    if len(task["blocks"]) == 0:
        info += f"Blocks: (None)\n"
    else:
        info += f"Blocks: {task["blocks"]}\n"
    if len(task["blocked_by"]) == 0:
        info += f"Blocked by: (None)\n"
    else:
        info += f"Blocked by: {task["blocked_by"]}\n"
    return info


def tasks_to_info(tasks: list[Task], agent_id: str) -> str:
    """convert tasks list to info string"""
    info = ""
    for task in tasks:
        info += f"Task ID: {task["task_id"]}\n"
        info += f" - Subject: {task["subject"]}\n"
        # info += f" - Description: {task["description"]}\n"
        if task["owner"] is None:
            info += f" - Owner ID: (None)\n"
        elif task["owner"] == agent_id:
            info += f" - Owner ID: {task["owner"]} (You)\n"
        else:
            info += f" - Owner ID: {task["owner"]} (other agent)\n"
        info += f" - Status: {task["status"]}\n"
        # if len(task["blocks"]) == 0:
        #     info += f" - Blocks: (None)\n"
        # else:
        #     info += f" - Blocks: {task["blocks"]}\n"
        if len(task["blocked_by"]) == 0:
            info += f" - Blocked by: (None)\n"
        else:
            info += f" - Blocked by: {task["blocked_by"]}\n"
    if len(tasks) == 0:
        info = f"(Task list is empty)"
    return info


def get_tasks_render(tasks: list[Task], now_time: datetime, base_time: datetime,
                     color_list1: list[str], color_list2: list[str]) -> Text:
    """Get a Text renderable showing current scoreboard tasks."""
    if len(tasks) == 0:
        return Text(TASK_EMPTY_TITLE, style="bright_black")

    text = Text()
    for task in tasks:
        subject = task["subject"]
        status = task["status"]
        if status == TaskStatus.PENDING:
            if task["owner"] is None:
                text.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITHOUT_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                            style=TASK_PENDING_WITHOUT_OWNER_ICON_STYLE)
                text.append(f"{subject}\n", style=TASK_PENDING_WITHOUT_OWNER_STYLE)
            else:
                time_diff = (now_time - base_time).total_seconds()
                position = time_diff % TASK_COLOR_PERIOD
                idx = int((position / TASK_COLOR_PERIOD) * len(color_list1)) % len(color_list1)
                color = color_list1[idx]
                text.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                            style=f"bold {color}")
                text.append(f"{subject}\n", style=f"{color}")
        elif status == TaskStatus.IN_PROGRESS:
            time_diff = (now_time - base_time).total_seconds()
            position = time_diff % TASK_COLOR_PERIOD
            idx = int((position / TASK_COLOR_PERIOD) * len(color_list2)) % len(color_list2)
            color = color_list2[idx]
            text.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_PENDING_WITH_OWNER_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {color}")
            text.append(f"{subject}\n", style=f"{color}")
        elif status == TaskStatus.COMPLETED:
            text.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_COMPLETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_COMPLETED_COLOR}")
            text.append(f"{subject}\n", style=TASK_COMPLETED_COLOR)
        elif status == TaskStatus.DELETED:
            text.append(f"{' ' * TASK_VIEW_LEFT_MARGIN}{TASK_DELETED_ICON}{' ' * TASK_VIEW_RIGHT_MARGIN}",
                        style=f"bold {TASK_DELETED_COLOR}")
            text.append(f"{subject}\n", style=f"strike {TASK_DELETED_COLOR}")
    if text.plain.endswith("\n"):
        text.rstrip()
    return text
