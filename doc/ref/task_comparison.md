# 任务管理机制对比研究 | Task Management Comparison

对 Claude Code、CodeWhale、Codex、OpenCode、deepseek-harness 五款主流 coding agent 的任务管理机制进行横向对比，归纳共性模式与差异化设计。
A horizontal comparison of task management mechanisms across five mainstream coding agents — Claude Code, CodeWhale, Codex, OpenCode, and deepseek-harness — summarizing common patterns and differentiated designs.

> 分析日期 | Date：2026-08-17（deepseek-harness 补充）
> 子代理架构对比另见 | See also: `subagent_comparison.md`

---

## 1. 核心对比总览 | Overview

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|------|-------------|-----------|-------|----------|------|
| 任务工具 Task tools | TodoWrite(V1)/TaskCreate+(V2) | checklist_write/update/list | update_plan | todowrite | 无 todo 工具；后台 jobs + 会话级 goal / No todo tool; background jobs + session-level goal |
| 数据模型 Data model | flat list + dependencies(V2) | flat checklist + durable tasks | flat plan items | flat list + priority | 扁平 job 队列（5 态）+ goal（4 相）/ flat job queue (5 states) + goal (4 phases) |
| 状态系统 Status system | pending/in_progress/completed | pending/in_progress/completed | pending/in_progress/completed | pending/in_progress/completed/cancelled | jobs: running/stopping/completed/killed/failed；goal: active/paused/blocked/complete |
| 层级支持 Hierarchy | 无 None | checklist + durable tasks + plan + goal | plan items only | 无 None | 无任务层级（jobs 扁平；goal 单层）/ no task hierarchy (flat jobs; single-layer goal) |
| 持久化 Persistence | 内存(V1, in-memory)/JSON文件(V2, JSON file) | 内存(checklist, in-memory) + JSON(durable, JSON file) | 内存(transcript, in-memory) | SQLite | jobs 纯内存（无持久化）；Session 事件溯源日志持久化 / in-memory jobs; event-sourced session logs |
| 子代理任务 Sub-agent tasks | followup_task + background | agent_open (多种类型 multiple types) | spawn_agent + followup_task | subtask commands | subagent(run_in_background) + job kind 'subagent' + report 工具 / subagent + job kind 'subagent' + report tool |
| 强制/建议 Enforcement | 软提示 + turn提醒 Soft prompt + turn reminder | Constitution强制(5+步) Constitution mandates (5+ steps) | 软提示 + 质量示例 Soft prompt + quality examples | 弱建议 Weak suggestion | 无强制（无 todo 工具）；jobs 提示段"结算时通知，不要 busy-poll" / none (no todo tool); jobs prompt "notified on settlement, no busy-poll" |

---

## 2. 任务工具设计 | Tool Design

### 2.1 替换 vs 增量 | Replace vs Incremental

| 策略 Strategy | 代表 Representatives | 设计 Design |
|------|------|------|
| **全量替换 Full replace** | OpenCode `todowrite`、CodeWhale `checklist_write`、Codex `update_plan` | 每次调用覆盖整个列表，LLM 必须提交完整状态 / Each call overwrites the entire list; LLM must submit the full state |
| **增量更新 Incremental update** | Claude Code `TaskCreate`/`TaskUpdate` | 每次调用增删一条，LLM 按需操作 / Each call adds or removes one item; LLM operates on demand |
| **无任务列表 No task list** | deepseek-harness | 不提供 todo/plan/checklist；任务管理职责由后台 jobs（队列）+ 会话级 goal 承担，LLM 无需维护规划列表 / No todo/plan/checklist; task management is delegated to background jobs (queue) + session-level goals — the LLM never maintains a planning list |

**优势分析：** | **Pros and Cons:**
- **全量替换 Full replace**：LLM 每次都必须"看到"整个列表，天然避免了状态不同步，减少"忘了更新某一条"的问题。但 list 变大后 token 开销高。
  The LLM must "see" the entire list every time, naturally avoiding state synchronization issues and reducing the problem of "forgetting to update an item." However, token overhead increases as the list grows.
- **增量更新 Incremental update**：token 效率高，但 LLM 容易忘记在多次操作间更新不相关的任务。
  Token-efficient, but the LLM tends to forget to update unrelated tasks across multiple operations.

### 2.2 层级任务 vs 扁平列表 | Hierarchical vs Flat

| 模式 Pattern | 代表 Representatives | 说明 Description |
|------|------|------|
| **扁平 Flat** | OpenCode、Codex | 所有任务同等地位，无父子关系 / All tasks are peers with no parent-child relationships |
| **双层 Two-tier** | Claude Code V2 | flat list + `blocks`/`blocked_by` 依赖 / flat list + `blocks`/`blocked_by` dependencies |
| **多层 Multi-tier** | CodeWhale | Goal → Plan → Checklist → Durable Tasks → Automations 五层金字塔 / Five-tier pyramid |
| **无规划列表 No planning list** | deepseek-harness | jobs 扁平队列（无父子）+ goal 单层会话目标（无层级）/ flat job queue (no parent-child) + single-layer session goals (no hierarchy) |

CodeWhale 的层级最丰富：| CodeWhale has the richest hierarchy:
- `update_goal` — 会话级目标 / Session-level goal
- `update_plan` — 3-6 个高层阶段（策略元数据）/ 3-6 high-level phases (strategic metadata)
- `checklist_write` — 具体叶子任务（带完成百分比）/ Concrete leaf tasks (with completion percentage)
- `task_create` — 持久化后台任务（支持断点恢复）/ Persistent background tasks (with resume support)
- `automation_*` — 定时循环任务 / Scheduled recurring tasks

### 2.3 依赖管理 | Dependencies

仅 **Claude Code V2** 支持任务间依赖（`blocks`/`blocked_by`）。Claude Code V2 对此有严格的利用：依赖未解决的任务不能被 claim，claim 时检查 blocked_by 状态。
Only **Claude Code V2** support inter-task dependencies (`blocks`/`blocked_by`). Claude Code V2 enforces this strictly: tasks with unresolved dependencies cannot be claimed, and blocked_by status is checked at claim time.

**deepseek-harness**：无任务间依赖；jobs 仅按 owner session 隔离（access control），goal 无依赖关系。
**deepseek-harness**: No inter-task dependencies; jobs are isolated per owner session (access control), goals have no dependencies.

---

## 3. 系统提示词策略 | System Prompt Strategy

### 3.1 触发条件 | When to Use Tasks

| Agent | 提示词生效条件 Prompt Trigger Conditions |
|-------|---------------|
| **CodeWhale** | **最强约束 Strongest constraint**：Constitution 规定"5+ 步必须用 checklist_write"；Agent mode 要求"多步写入前必须先排 checklist" / Constitution mandates "5+ steps must use checklist_write"; Agent mode requires "checklist before multi-step work" |
| **Codex** | 详细指导 Detailed guidance：非平凡任务、有逻辑阶段、需检查点反馈、用户显式要求时创建 plan；"最简 25% 的任务跳过" / Create plan for non-trivial tasks, logical phases, checkpoint feedback, or user request; "skip ~25% simplest tasks" |
| **Claude Code** | 中强度指导 Medium guidance：3+ 步、非平凡、用户提供多任务、收到新指令时使用；Exactly ONE in_progress / Use for 3+ steps, non-trivial, multi-task requests, or new instructions; exactly ONE in_progress |
| **OpenCode** | 最弱 Weakest：仅工具描述中说"用于跟踪多步工作进度"，无强制要求 / Only the tool description says "track multi-step progress"; no enforcement |
| **deepseek-harness** | 无 todo 工具 → 无任务触发条件 / No todo tool → no task trigger condition；后台任务用 `subagent`(run_in_background) 或 jobs 启动，提示段 order 106："记录每个后台 job id；结算时会通知，不要 busy-poll；最终答复前用 job_output 收集所有仍相关的 job" / background tasks start via `subagent`(run_in_background) or jobs; prompt: "record each background job id; you will be notified on settlement; don't busy-poll; collect still-relevant jobs with job_output before the final answer" |

### 3.2 提示词中"任务拆分"的强调程度 | Decomposition Emphasis

- **CodeWhale** 最激进 Most aggressive："For any task estimated to take 5+ concrete steps: 1. checklist_write 列出叶子任务..."
- **Codex** 有质量判例 Quality examples：展示了高质量 vs 低质量 plan 的具体例子（好坏对比），教 LLM 拆分粒度 / Shows concrete examples of good vs. bad plans (side-by-side comparison), teaching LLM decomposition granularity
- **Claude Code** TodoWrite prompt 181 行，但更偏操作规范（何时用、何时不用、状态流转），拆分指导较少 / 181-line TodoWrite prompt, but focused more on operational rules (when to use, when not to, status transitions) than decomposition guidance
- **OpenCode** 提示词中缺少"拆分粒度"的具体示例 / Lacks concrete decomposition examples in prompts
- **deepseek-harness** 无 todo 工具，无拆分指导；子代理 spawn 提示段要求"把自包含任务委派给子代理，以免消耗本会话上下文"（委派替代拆分）/ No todo tool, no decomposition guidance; the subagent spawn prompt asks to "delegate self-contained tasks to a subagent to avoid consuming this session's context" (delegation instead of decomposition)

**关键发现：** Codex 的"好坏示例对比"是全区唯一的——直接给 LLM 看一个 bad plan 和一个 good plan，这种方法比规则描述更有效。
**Key insight:** Codex's "good vs. bad example comparison" is unique across all agents — showing the LLM a bad plan and a good plan directly is more effective than rule descriptions.

---

## 4. 提醒/推动机制 | Reminder & Nudge Mechanisms

### 4.1 回合计数提醒 | Turn-based Reminder

| Agent | 机制 Mechanism |
|-------|------|
| **Claude Code** | `TODO_REMINDER_CONFIG = {TURNS_SINCE_WRITE: 10, TURNS_BETWEEN_REMINDERS: 10}` — 10 轮未用 task tool 且 10 轮未发提醒时注入 system-reminder；含当前 task list 内容 / Injects system-reminder after 10 turns without task tool use and 10 turns since last reminder; includes current task list |

### 4.2 工具结果中的推动 | Tool Result Nudge

- **Claude Code** TodoWrite 结果："Please proceed with the current tasks if applicable"
- **Claude Code** TaskUpdate 完成时："Call TaskList now to find your next available task"
- **CodeWhale** checklist 输出带 `completion_pct` percentage，给 LLM 量化反馈 / Checklist output includes `completion_pct` percentage, giving LLM quantitative feedback
- **deepseek-harness** jobs 结算自动通知父代理（"Background subagent … finished/stopped"），提示"不要 busy-poll" / jobs settlement auto-notifies the parent; prompt says "don't busy-poll"

### 4.3 UI 可见性 | UI Visibility

- **Claude Code** 和 **CodeWhale** 在 spinner 中显示当前 in_progress 任务名 / Display current in_progress task name in spinner
- **Codex** 在终端标题栏显示 `Tasks {completed}/{total}` / Shows `Tasks {completed}/{total}` in terminal title bar
- **deepseek-harness** 无任务列表 UI（jobs 结算以消息通知形式呈现）/ No task-list UI (job settlement surfaces as message notices)

---

## 5. 任务拆分与子代理 | Subdivision & Sub-agents

### 5.1 子代理指派任务 | Sub-agent Task Assignment

| Agent | 子代理系统 Sub-agent System | 任务委派 Task Delegation |
|-------|-----------|---------|
| **Claude Code** | 团队模式 + 后台任务 Team mode + background tasks | `TaskCreate` 时设置 `owner` 字段委派给特定 teammate；`TaskStop` 停止后台任务 / Set `owner` field in `TaskCreate` to delegate to a specific teammate; `TaskStop` to stop background tasks |
| **CodeWhale** | `agent_open` (8 种类型 8 types) | 子代理完成任务后，主代理被指示"更新 checklist_update 反映子代理贡献"；子代理输出必须含 SUMMARY/EVIDENCE/CHANGES/RISKS/BLOCKERS / After sub-agent completes, primary agent is instructed to "update checklist_update to reflect sub-agent contributions"; sub-agent output must include SUMMARY/EVIDENCE/CHANGES/RISKS/BLOCKERS |
| **Codex** | `spawn_agent` + `followup_task` | `followup_task` 向子代理发任务消息并触发 turn / Sends task message to sub-agent and triggers a turn |
| **OpenCode** | `general`/`explore`/`plan` 子代理 sub-agents | `general` 子代理**禁止**使用 `todowrite`（任务管理权中央化）/ `general` sub-agent is **prohibited** from using `todowrite` (centralized task management) |
| **deepseek-harness** | provider 注册制（spawn/fork/acp/claude-code/codex）+ continuable 常驻会话 | jobs 按 owner session 隔离；子代理后台任务 = job kind `'subagent'`（`JobKindMap { bash, subagent }`）；子侧 `report` 工具主动交付结果 / jobs isolated per owner session; subagent background = job kind `'subagent'`; child-side `report` tool for proactive delivery |

### 5.2 验证机制 | Verification

唯一有结构性验证的是 **Claude Code**：
The only agent with structural verification is **Claude Code**:
- 当 3+ 任务列表中所有任务完成且无 verification 相关任务时，tool result 中包含："Before writing your final summary, spawn the verification agent..."
  When all tasks in a 3+ task list are completed and no verification-related tasks exist, the tool result includes: "Before writing your final summary, spawn the verification agent..."
- `TaskComplete` hooks 可以机械阻止任务完成（退出码 2）/ `TaskComplete` hooks can mechanically prevent task completion (exit code 2)

**CodeWhale** 有 `task_gate_run` 工具附加 testing/verification evidence 到 durable task。
**CodeWhale** has a `task_gate_run` tool that appends testing/verification evidence to durable tasks.

**deepseek-harness**：无结构化验证（无 verification agent / gate 工具）；唯一相关机制是 goal-round-driver 驱动目标回合，非验证。
**deepseek-harness**: No structured verification (no verification agent / gate tool); the only related mechanism is goal-round-driver, which drives goal turns rather than verifying.

---

## 6. 跨轮次持久化 | Cross-Turn Persistence

| Agent | 持久化方式 Persistence Method | 会话恢复 Session Resume |
|-------|-----------|---------------|
| **Claude Code** | V1: 从 transcript 提取 todo 恢复 / Recover todo from transcript；V2: JSON 文件 JSON file | 完全恢复 Full recovery |
| **CodeWhale** | 内存 checklist In-memory checklist；durable tasks JSON 文件 JSON file | 完全恢复 Full recovery |
| **Codex** | Plan 存储在 transcript events 中 / Plan stored in transcript events | 从 transcript 恢复 Recover from transcript |
| **OpenCode** | SQLite `todo` 表（session 级外键 session-level foreign key） | 完全恢复 Full recovery |
| **deepseek-harness** | jobs 纯内存（无持久化，重启丢失）/ In-memory jobs (no persistence, lost on restart)；Session 事件溯源日志（JSONL+zstd / SQLite）持久化子代理会话 / event-sourced session logs (JSONL+zstd / SQLite) persist subagent sessions | 子代理会话冷恢复（descriptor + seedLength）/ subagent cold resume (descriptor + seedLength) |

---

## 7. 附录：各 Agent 关键源文件索引 | Appendix: Key Source Files Index

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

### deepseek-harness
- `packages/jobs/jobs/src/index.ts` — JobRegistry 服务定义（JobStatus 5 态 + JobKindMap {bash, subagent}）/ Service definition (5 job states + JobKindMap)
- `packages/jobs/jobs/src/types.ts` — JobOutcome / JobSnapshot / JobStart 类型 / types
- `packages/jobs/jobs-local/src/index.ts` — 纯内存实现（每 owner 并发默认 10，按 owner 隔离访问）/ in-memory implementation (per-owner concurrency 10, per-owner isolation)
- `packages/jobs/tool-jobs/src/index.ts` — job_output / job_list / job_kill 三工具 + 结算通知 / three tools + settlement notices
- `packages/goal/goal/src/index.ts` — 同会话目标领域（GoalPhase: active/paused/blocked/complete）/ in-session goal domain (4 phases)
- `packages/goal/goal-round-driver/src/index.ts` — 目标回合驱动（注入主 Agent inbox）/ goal-round driver (injects the main agent's inbox)
- `packages/subagent/tool-subagent/src/index.ts` — subagent 启动工具（run_in_background → jobs）/ subagent launch tool (run_in_background → jobs)
- `packages/subagent/subagent/src/index.ts` — SubagentRuntime provider 注册制 / provider registry
