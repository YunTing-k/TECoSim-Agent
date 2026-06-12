# 任务管理机制对比研究 | Task Management Comparison

对 Claude Code、CodeWhale、Codex、OpenCode 四款主流 coding agent 的任务管理机制进行横向对比，归纳共性模式与差异化设计，为 TECoSimAgent 任务系统升级提供参考。
A horizontal comparison of task management mechanisms across four mainstream coding agents — Claude Code, CodeWhale, Codex, and OpenCode — summarizing common patterns and differentiated designs to provide references for upgrading TECoSimAgent's task system.

---

## 1. 核心对比总览 | Overview

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode | TECoSimAgent |
|------|-------------|-----------|-------|----------|-------------|
| 任务工具 Task tools | TodoWrite(V1)/TaskCreate+(V2) | checklist_write/update/list | update_plan | todowrite | create/update/query_task |
| 数据模型 Data model | flat list + dependencies(V2) | flat checklist + durable tasks | flat plan items | flat list + priority | flat list + dependencies + owner |
| 状态系统 Status system | pending/in_progress/completed | pending/in_progress/completed | pending/in_progress/completed | pending/in_progress/completed/cancelled | pending/in_progress/completed/deleted |
| 层级支持 Hierarchy | 无 None | checklist + durable tasks + plan + goal | plan items only | 无 None | 无 None |
| 持久化 Persistence | 内存(V1, in-memory)/JSON文件(V2, JSON file) | 内存(checklist, in-memory) + JSON(durable, JSON file) | 内存(transcript, in-memory) | SQLite | JSON文件 JSON file |
| 子代理任务 Sub-agent tasks | followup_task + background | agent_open (多种类型 multiple types) | spawn_agent + followup_task | subtask commands | 无 None |
| 强制/建议 Enforcement | 软提示 + turn提醒 Soft prompt + turn reminder | Constitution强制(5+步) Constitution mandates (5+ steps) | 软提示 + 质量示例 Soft prompt + quality examples | 弱建议 Weak suggestion | CONSTRAINT级强制 + turn提醒 + 工具结果反馈 CONSTRAINT-level mandate + turn reminder + tool result nudge |

---

## 2. 任务工具设计 | Tool Design

### 2.1 替换 vs 增量 | Replace vs Incremental

| 策略 Strategy | 代表 Representatives | 设计 Design |
|------|------|------|
| **全量替换 Full replace** | OpenCode `todowrite`、CodeWhale `checklist_write`、Codex `update_plan` | 每次调用覆盖整个列表，LLM 必须提交完整状态 / Each call overwrites the entire list; LLM must submit the full state |
| **增量更新 Incremental update** | Claude Code `TaskCreate`/`TaskUpdate`、TECoSimAgent `create_task`/`update_task` | 每次调用增删一条，LLM 按需操作 / Each call adds or removes one item; LLM operates on demand |

**优势分析：** | **Pros and Cons:**
- **全量替换 Full replace**：LLM 每次都必须"看到"整个列表，天然避免了状态不同步，减少"忘了更新某一条"的问题。但 list 变大后 token 开销高。
  The LLM must "see" the entire list every time, naturally avoiding state synchronization issues and reducing the problem of "forgetting to update an item." However, token overhead increases as the list grows.
- **增量更新 Incremental update**：token 效率高，但 LLM 容易忘记在多次操作间更新不相关的任务。
  Token-efficient, but the LLM tends to forget to update unrelated tasks across multiple operations.

### 2.2 层级任务 vs 扁平列表 | Hierarchical vs Flat

| 模式 Pattern | 代表 Representatives | 说明 Description |
|------|------|------|
| **扁平 Flat** | OpenCode、Codex、TECoSimAgent | 所有任务同等地位，无父子关系 / All tasks are peers with no parent-child relationships |
| **双层 Two-tier** | Claude Code V2、TECoSimAgent | flat list + `blocks`/`blocked_by` 依赖 / flat list + `blocks`/`blocked_by` dependencies |
| **多层 Multi-tier** | CodeWhale | Goal → Plan → Checklist → Durable Tasks → Automations 五层金字塔 / Five-tier pyramid |

CodeWhale 的层级最丰富：| CodeWhale has the richest hierarchy:
- `update_goal` — 会话级目标 / Session-level goal
- `update_plan` — 3-6 个高层阶段（策略元数据）/ 3-6 high-level phases (strategic metadata)
- `checklist_write` — 具体叶子任务（带完成百分比）/ Concrete leaf tasks (with completion percentage)
- `task_create` — 持久化后台任务（支持断点恢复）/ Persistent background tasks (with resume support)
- `automation_*` — 定时循环任务 / Scheduled recurring tasks

### 2.3 依赖管理 | Dependencies

仅 **Claude Code V2** 和 **TECoSimAgent** 支持任务间依赖（`blocks`/`blocked_by`）。Claude Code V2 对此有严格的利用：依赖未解决的任务不能被 claim，claim 时检查 blocked_by 状态。TECoSimAgent 支持依赖定义但缺少 claim 时的依赖检查。
Only **Claude Code V2** and **TECoSimAgent** support inter-task dependencies (`blocks`/`blocked_by`). Claude Code V2 enforces this strictly: tasks with unresolved dependencies cannot be claimed, and blocked_by status is checked at claim time. TECoSimAgent supports dependency definitions but lacks dependency checking during claiming.

---

## 3. 系统提示词策略 | System Prompt Strategy

### 3.1 触发条件 | When to Use Tasks

| Agent | 提示词生效条件 Prompt Trigger Conditions |
|-------|---------------|
| **CodeWhale** | **最强约束 Strongest constraint**：Constitution 规定"5+ 步必须用 checklist_write"；Agent mode 要求"多步写入前必须先排 checklist" / Constitution mandates "5+ steps must use checklist_write"; Agent mode requires "checklist before multi-step work" |
| **Codex** | 详细指导 Detailed guidance：非平凡任务、有逻辑阶段、需检查点反馈、用户显式要求时创建 plan；"最简 25% 的任务跳过" / Create plan for non-trivial tasks, logical phases, checkpoint feedback, or user request; "skip ~25% simplest tasks" |
| **Claude Code** | 中强度指导 Medium guidance：3+ 步、非平凡、用户提供多任务、收到新指令时使用；Exactly ONE in_progress / Use for 3+ steps, non-trivial, multi-task requests, or new instructions; exactly ONE in_progress |
| **OpenCode** | 最弱 Weakest：仅工具描述中说"用于跟踪多步工作进度"，无强制要求 / Only the tool description says "track multi-step progress"; no enforcement |
| **TECoSimAgent** | CONSTRAINT 级约束（"For any request requiring 3+ distinct actions, you MUST call `create_task` FIRST... You MUST NOT create a single catch-all task"） + 拆分规则 / CONSTRAINT-level mandate ("3+ actions → MUST create_task first, MUST NOT single catch-all task") + decomposition rules |

### 3.2 提示词中"任务拆分"的强调程度 | Decomposition Emphasis

- **CodeWhale** 最激进 Most aggressive："For any task estimated to take 5+ concrete steps: 1. checklist_write 列出叶子任务..."
- **Codex** 有质量判例 Quality examples：展示了高质量 vs 低质量 plan 的具体例子（好坏对比），教 LLM 拆分粒度 / Shows concrete examples of good vs. bad plans (side-by-side comparison), teaching LLM decomposition granularity
- **Claude Code** TodoWrite prompt 181 行，但更偏操作规范（何时用、何时不用、状态流转），拆分指导较少 / 181-line TodoWrite prompt, but focused more on operational rules (when to use, when not to, status transitions) than decomposition guidance
- **OpenCode** 提示词中缺少"拆分粒度"的具体示例 / Lacks concrete decomposition examples in prompts
- **TECoSimAgent** create_task 工具描述中新增 Task Decomposition Rules + Good/Bad 示例（仿 Codex 做法）/ Added Task Decomposition Rules + Good/Bad examples in create_task tool description (following Codex's approach)

**关键发现：** Codex 的"好坏示例对比"是全区唯一的——直接给 LLM 看一个 bad plan 和一个 good plan，这种方法比规则描述更有效。TECoSimAgent 已采纳此模式。
**Key insight:** Codex's "good vs. bad example comparison" is unique across all agents — showing the LLM a bad plan and a good plan directly is more effective than rule descriptions. TECoSimAgent has adopted this pattern now.

---

## 4. 提醒/推动机制 | Reminder & Nudge Mechanisms

### 4.1 回合计数提醒 | Turn-based Reminder

| Agent | 机制 Mechanism |
|-------|------|
| **Claude Code** | `TODO_REMINDER_CONFIG = {TURNS_SINCE_WRITE: 10, TURNS_BETWEEN_REMINDERS: 10}` — 10 轮未用 task tool 且 10 轮未发提醒时注入 system-reminder；含当前 task list 内容 / Injects system-reminder after 10 turns without task tool use and 10 turns since last reminder; includes current task list |
| **TECoSimAgent** | `REMIND_TASK_TOOL_GAP = 8`（工具调用后 after tool call）、`REMIND_TASK_CHAT_GAP = 3`（用户输入后 after user input） |

### 4.2 工具结果中的推动 | Tool Result Nudge

- **Claude Code** TodoWrite 结果："Please proceed with the current tasks if applicable"
- **Claude Code** TaskUpdate 完成时："Call TaskList now to find your next available task"
- **CodeWhale** checklist 输出带 `completion_pct` percentage，给 LLM 量化反馈 / Checklist output includes `completion_pct` percentage, giving LLM quantitative feedback
- **TECoSimAgent** create_task 追加 "Mark your first task as in_progress via `update_task`"；update_task 到 in_progress → "Proceed with this task. Only ONE task in_progress..."；completed/deleted → "Use `query_task` to find your next available task" / Following Claude Code's pattern: create_task → "Mark your first task as in_progress..."; update_task in_progress → "Proceed..."; completed/deleted → "Use query_task for next task"
- **TECoSimAgent** **新增 query_task 汇总 New query_task summary**：`query_task` 列表尾部追加归属分组汇总 `[3 pending (2 unclaimed, 1 by you), 1 in_progress (1 by you), 1 completed (1 by you)]` / Appends ownership-grouped summary line to query_task listing

### 4.3 UI 可见性 | UI Visibility

- **Claude Code** 和 **CodeWhale** 在 spinner 中显示当前 in_progress 任务名 / Display current in_progress task name in spinner
- **Codex** 在终端标题栏显示 `Tasks {completed}/{total}` / Shows `Tasks {completed}/{total}` in terminal title bar
- **TECoSimAgent** 在 tool 执行时 live 渲染 scoreboard（spinner 下方），在用户输入前 listen_tui 也显示 / Live renders scoreboard during tool execution (below spinner) and in listen_tui before user input

---

## 5. 任务拆分与子代理 | Subdivision & Sub-agents

### 5.1 子代理指派任务 | Sub-agent Task Assignment

| Agent | 子代理系统 Sub-agent System | 任务委派 Task Delegation |
|-------|-----------|---------|
| **Claude Code** | 团队模式 + 后台任务 Team mode + background tasks | `TaskCreate` 时设置 `owner` 字段委派给特定 teammate；`TaskStop` 停止后台任务 / Set `owner` field in `TaskCreate` to delegate to a specific teammate; `TaskStop` to stop background tasks |
| **CodeWhale** | `agent_open` (8 种类型 8 types) | 子代理完成任务后，主代理被指示"更新 checklist_update 反映子代理贡献"；子代理输出必须含 SUMMARY/EVIDENCE/CHANGES/RISKS/BLOCKERS / After sub-agent completes, primary agent is instructed to "update checklist_update to reflect sub-agent contributions"; sub-agent output must include SUMMARY/EVIDENCE/CHANGES/RISKS/BLOCKERS |
| **Codex** | `spawn_agent` + `followup_task` | `followup_task` 向子代理发任务消息并触发 turn / Sends task message to sub-agent and triggers a turn |
| **OpenCode** | `general`/`explore`/`plan` 子代理 sub-agents | `general` 子代理**禁止**使用 `todowrite`（任务管理权中央化）/ `general` sub-agent is **prohibited** from using `todowrite` (centralized task management) |
| **TECoSimAgent** | 无子代理系统 No sub-agent system | N/A |

### 5.2 验证机制 | Verification

唯一有结构性验证的是 **Claude Code**：
The only agent with structural verification is **Claude Code**:
- 当 3+ 任务列表中所有任务完成且无 verification 相关任务时，tool result 中包含："Before writing your final summary, spawn the verification agent..."
  When all tasks in a 3+ task list are completed and no verification-related tasks exist, the tool result includes: "Before writing your final summary, spawn the verification agent..."
- `TaskComplete` hooks 可以机械阻止任务完成（退出码 2）/ `TaskComplete` hooks can mechanically prevent task completion (exit code 2)

**CodeWhale** 有 `task_gate_run` 工具附加 testing/verification evidence 到 durable task。
**CodeWhale** has a `task_gate_run` tool that appends testing/verification evidence to durable tasks.

---

## 6. 跨轮次持久化 | Cross-Turn Persistence

| Agent | 持久化方式 Persistence Method | 会话恢复 Session Resume |
|-------|-----------|---------------|
| **Claude Code** | V1: 从 transcript 提取 todo 恢复 / Recover todo from transcript；V2: JSON 文件 JSON file | 完全恢复 Full recovery |
| **CodeWhale** | 内存 checklist In-memory checklist；durable tasks JSON 文件 JSON file | 完全恢复 Full recovery |
| **Codex** | Plan 存储在 transcript events 中 / Plan stored in transcript events | 从 transcript 恢复 Recover from transcript |
| **OpenCode** | SQLite `todo` 表（session 级外键 session-level foreign key） | 完全恢复 Full recovery |
| **TECoSimAgent** | JSON 文件 `tasks.json` (JSON file) | 完全恢复 Full recovery |

---

## 7. TECoSimAgent 任务系统现状 | Current Task System

### 7.1 核心机制 | Core Mechanisms

TECoSimAgent 的多 agent 协作任务系统，经对比研究后已从以下 5 个维度对齐行业最佳实践：

1. **系统提示词 System Prompt** — CONSTAINT 级约束："For any request requiring 3+ distinct actions, you MUST call `create_task` FIRST... You MUST NOT create a single catch-all task"。单任务 `in_progress` 约束，禁止批量完成。

2. **create_task 工具描述 Tool Description** — 含 Task Decomposition Rules + Good/Bad 示例对比（"add dark mode toggle and run tests" → 4 tasks vs 1 task），仿 Codex 的示例教学策略。

3. **提醒间隔 Reminder Gap** — `REMIND_TASK_TOOL_GAP = 8`（接近 Claude Code 的 10 轮）。

4. **工具结果推动 Tool Result Nudge**（仿 Claude Code）：
   - `create_task` 成功 → "Mark your first task as in_progress via `update_task` and begin work."
   - `update_task` to `in_progress` → "Proceed with this task. Only ONE task in_progress at a time."
   - `update_task` to `completed`/`deleted` → "Task resolved. Use `query_task` to find your next available task."

5. **query_task 归属汇总 Ownership-Grouped Summary**：
   - 列表尾部追加 `[3 pending (2 unclaimed, 1 by you), 1 in_progress (1 by you), 1 completed (1 by you)]`
   - 仅显示与当前 agent 相关的归属信息，不引入其他 agent 的 claimed 任务干扰 LLM

### 7.2 关键文件变更 | Key Files Changed

| 文件 File | 变更 Change |
|------|------|
| `src/context/prompt.py` | Workflow Guidelines 升级为 CONSTRINT 级 + 单 in_progress 约束 |
| `src/tool/tool_def.py` | create_task 描述加 Decomposition Rules + Good/Bad 示例；create/update/query 工具结果加反馈和汇总 |
| `src/tool/scoreboard.py` | 新增 `count_by_status()`；task_to_info/tasks_to_info Status 改用 `.value` 显示 |
| `config/agent_configs.json` | `REMIND_TASK_TOOL_GAP` 1→8 |
| `test/task_tool_test.py` | 新增 11 个测试覆盖创建/更新/查询结果反馈和汇总行 |

### 7.3 与竞品差异点 | Differentiation from Peers

| 特性 Feature | TECoSimAgent | 竞品现状 Peers |
|------|-------------|------|
| 多 agent 协作 Multi-agent collaboration | 内置 owner/blocks/blocked_by 依赖 + claim 机制 | Claude Code V2 有，其他无 |
| 任务拆分教学 Decomposition teaching | Good/Bad 示例对比 | 仅 Codex 有 |
| 强制级约束 Mandate level | CONSTRINT（"MUST call FIRST"）| CodeWhale Constitution 最强 |
| 归属归属汇总 Ownership summary | 行为级过滤（仅显示本 agent 相关）| 无竞品有 |
| 全量替换清单 Full replace checklist | 否（增量更新保所有权）| OpenCode/Codex/CodeWhale 有 |
| 持久化后台任务 Durable background tasks | 无 | CodeWhale task_create + worker pool |

---

## 8. 后续改进方向 | Future Improvement Directions

| 优先级 Priority | 措施 Measure | 参考来源 Source |
|--------|------|------|
| **P1** | `completion_pct` 百分比进度反馈 / Percentage progress feedback | CodeWhale |
| **P2** | 全量替换兼容模式（与增量并存）/ Full replace compatible mode (coexist with incremental) | CodeWhale/OpenCode/Codex |
| **P2** | 3+ 任务全部完成时验证提示 / Verification nudge when all 3+ tasks complete | Claude Code |
| **P2** | 持久化后台任务队列 / Durable background task queue | CodeWhale |

---

## 9. 附录：各 Agent 关键源文件索引 | Appendix: Key Source Files Index

### Claude Code
- `src/tools/TodoWriteTool/TodoWriteTool.ts` — V1 TodoWrite 实现 / V1 TodoWrite implementation
- `src/tools/TaskCreateTool/TaskCreateTool.ts` — V2 TaskCreate
- `src/tools/TaskUpdateTool/TaskUpdateTool.ts` — V2 TaskUpdate（最复杂 / most complex）
- `src/tools/TodoWriteTool/prompt.ts` — 181 行 LLM prompt / 181-line LLM prompt
- `src/utils/tasks.ts` — 核心 CRUD + 锁（862 行）/ Core CRUD + lock (862 lines)
- `src/utils/attachments.ts` — `TODO_REMINDER_CONFIG` + 提醒注入 / reminder injection
- `src/constants/prompts.ts` — 系统提示词注入 task 指导 / System prompt task guidance injection

### CodeWhale
- `crates/tui/src/tools/todo.rs` — checklist_write/update/list/add 四件套 / four-piece set
- `crates/tui/src/tools/tasks.rs` — task_create/list/read/cancel/gate_run 持久化任务 / persistent tasks
- `crates/tui/src/tools/plan.rs` — update_plan 高层计划 / high-level plan
- `crates/tui/src/task_manager.rs` — 核心任务管理器（2095 行）/ Core task manager (2095 lines)
- `crates/tui/src/prompts/base.md` — Constitution 级"5+步必须"条款 / Constitution-level "5+ steps mandatory" clause
- `crates/tui/src/prompts/modes/agent.md` — Agent mode 前置 checklist 要求 / Agent mode pre-checklist requirement
- `crates/tui/src/tools/subagent/mod.rs` — 8 种子代理，输出契约含 SUMMARY/EVIDENCE / 8 sub-agent types, output contract includes SUMMARY/EVIDENCE

### Codex
- `core/src/tools/handlers/plan.rs` — PlanHandler，Plan Mode 中拒绝 / rejection in Plan Mode
- `core/src/tools/handlers/plan_spec.rs` — update_plan tool 定义 / tool definition
- `core/gpt_5_2_prompt.md` — 高质量 vs 低质量 plan 示例（L36-107）/ High vs. low quality plan examples (L36-107)
- `core/gpt_5_codex_prompt.md` — "最简 25% 跳过，不用单步 plan" / "Skip ~25% simplest, no single-step plans"
- `tui/src/history_cell/plans.rs` — checkbox UI 渲染 / checkbox UI rendering
- `tui/src/chatwidget/status_surfaces.rs` — 终端标题 `Tasks {n}/{total}` / terminal title

### OpenCode
- `packages/core/src/tool/todowrite.ts` — 唯一 task 工具，全量替换 / The only task tool, full replace
- `packages/core/src/session/todo.ts` — SessionTodo 数据模型 + 事件 / SessionTodo data model + events
- `packages/core/src/session/sql.ts` — SQLite DDL（`todo` 表 / `todo` table）
- `packages/core/src/plugin/agent.ts` — general 子代理 deny todowrite / general sub-agent denies todowrite
- `packages/core/src/session/compaction.ts` — 压缩模板含 Goal/Progress/NextSteps / Compaction template with Goal/Progress/NextSteps

### TECoSimAgent
- `src/tool/scoreboard.py` — Scoreboard 类（任务模型、CRUD、持久化、渲染）/ Scoreboard class (task model, CRUD, persistence, rendering)
- `src/tool/tool_def.py` — create/update/query_task 三工具定义与实现 / three tool definitions and implementations
- `src/context/prompt.py` — 系统提示词指导 + `update_task_usage()`/`get_task_reminder()` / System prompt guidance
- `src/main.py` — 提醒注入循环、scoreboard 创建/加载 / Reminder injection loop, scoreboard create/load
- `src/utility/ui_info.py` — `loading_spinner_with_board()` live 渲染 / live rendering
- `config/agent_configs.json` — `REMIND_TASK_TOOL_GAP=8`
