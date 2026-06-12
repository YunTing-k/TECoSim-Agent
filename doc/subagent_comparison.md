# Subagent/Task 架构对比分析：Claude Code · CodeWhale · Codex · OpenCode
# Subagent/Task Architecture Comparison: Claude Code · CodeWhale · Codex · OpenCode

## 1. 整体架构概览 | Architecture Overview

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **语言 Language** | TypeScript | Rust | Rust | TypeScript (Effect-TS) |
| **Agent 载体 Agent Carrier** | 独立会话（AsyncLocalStorage 隔离） / Independent session (ALS isolation) | 独立 Task（tokio spawn） / Independent task (tokio spawn) | 完整 Thread（含 session/rollout/tools） / Full thread with session/rollout/tools | 子 Session（SQLite parent_id）/ Child session (SQLite parent_id) |
| **并发模型 Concurrency Model** | 多 Agent 同进程 ALS 隔离 / Multi-agent in-process ALS isolation | 多 Task 同 tokio runtime / Multi-task on same tokio runtime | 多 Thread 同进程 / Multi-thread in same process | 多 Session 同 Effect runtime / Multi-session on same Effect runtime |
| **支持递归 spawn Recursive Spawn** | 是（默认允许）/ Yes (allowed by default) | 是（depth cap=3）/ Yes (depth cap=3) | 是（默认允许）/ Yes (allowed by default) | 否（默认 deny task tool）/ No (deny task tool by default) |
| **前台/后台 Foreground/Background** | 两种都可 / Both supported | 前台（block/eval）+ 后台（task_manager 单独系统） / Foreground (block/eval) + Background (separate task_manager) | 两种都可 / Both supported | 前台默认 / 后台实验性 / Foreground default, background experimental |
| **任务列表系统 Task List System** | V1 TodoWrite（内存）+ V2 Task（文件持久化）/ V1 in-memory + V2 file-persisted | checklist_write（内存）+ task_manager（文件持久化）/ in-memory + file-persisted task_manager | update_plan（纯流式 UI，无持久化）/ streaming UI only, no persistence | todowrite（SQLite 持久化）/ SQLite persisted |

---

## 2. Agent 定义与配置 | Agent Definition & Configuration

### 2.1 Claude Code

**Agent 类型系统（4 层） | Agent Type System (4 layers):**

```
BuiltInAgentDefinition → 硬编码（Explore/Plan/GeneralPurpose/Verification/StatuslineSetup/Guide）
                         Hardcoded (Explore/Plan/GeneralPurpose/Verification/StatuslineSetup/Guide)
CustomAgentDefinition  → ~/.claude/agents/ + .claude/agents/（Markdown/JSON）
PluginAgentDefinition  → 插件定义 / Plugin definition
PolicyAgentDefinition  → 策略/特性标志定义 / Policy/feature flag definition
```

**核心字段 | Core Fields**（`BaseAgentDefinition`）：
- `agentType` · `whenToUse` · `tools` / `disallowedTools`
- `skills` · `mcpServers` · `hooks` · `color` · `model`
- `effort` · `permissionMode` · `maxTurns` · `background`
- `initialPrompt` · `memory`（user/project/local 三级 / 3 tiers）
- `isolation`（worktree/remote）
- `omitClaudeMd`
- `criticalSystemReminder_EXPERIMENTAL`

**特点 | Highlights:**
- 每个 BuiltIn 有独立的 `getSystemPrompt()` 函数 / Each BuiltIn has its own `getSystemPrompt()` function
- 自定义 Agent 通过 **Markdown frontmatter** 或 JSON 定义 / Custom agents defined via Markdown frontmatter or JSON
- 加载优先级 | Load priority: built-in < plugin < user < project < flag < managed
- **Fork Agent**：特殊的合成 Agent，`subagent_type` 为空时自动 Fork 父会话，共享 prompt cache / A synthetic agent that auto-forks the parent session when `subagent_type` is empty, sharing prompt cache

### 2.2 CodeWhale

**Agent 类型系统（8 种 enum 变体）| Agent Type System (8 enum variants):**

```rust
General | Explore | Plan | Review | Implementer | Verifier | ToolAgent | Custom
```

**别名系统（大小写不敏感）| Alias System (case-insensitive):**
```
general → worker, default, general-purpose
explore → explorer, exploration
plan → planning, planner, awaiter
review → reviewer, code-review
implementer → implement, implementation, builder
verifier → verify, verification, validator, tester
tool_agent → tool-agent, toolagent, executor, fin
```

**核心字段 | Core Fields**（`SubAgentTask`）：
- `agent_id` · `agent_type` · `whale_name`（确定性哈希昵称 / deterministic hash nickname）
- `max_steps`（默认无上限 / no limit by default）· `step_api_timeout`（120s 可配置 / configurable）
- `fork_context` · `model`（可按 role 覆盖 / overridable per role）
- `resident_file`（缓存感知常驻文件 / cache-aware resident file）

**特点 | Highlights:**
- 硬编码 8 种角色，无外部自定义配置 / 8 hardcoded roles, no external customization
- **ToolAgent** 专为 DeepSeek V4 Flash 优化（thinking=off，"Fin" 通道 / "Fin" channel）/ Optimized for DeepSeek V4 Flash with thinking=off
- `fork_context: true` 保留父 prompt 的字节等价性，利用 DeepSeek prefix-cache / Preserves byte-level equivalence with parent prompt for prefix-cache reuse
- 默认子 Agent 继承完整工具注册表（v0.6.6+ 无障碍）/ Child agents inherit full tool registry by default (v0.6.6+)

### 2.3 Codex

**Agent 类型系统 | Agent Type System:**

```
SubAgentSource:
  Review       → 系统内部（guardian/auto-review）/ Internal system (guardian/auto-review)
  Compact      → 上下文压缩 / Context compaction
  ThreadSpawn  → LLM 显式 spawn / Explicit LLM spawn
  MemoryConsolidation
  Other(String)
```

**内置角色（`role.rs`）| Built-in Roles:**

| 角色 Role | 配置文件 Config | 描述 Description |
|------|----------|------|
| `default` | 无 / None | 默认 Agent / Default agent |
| `explorer` | explorer.toml | 代码库探索 / Codebase exploration |
| `worker` | 无 / None | 实现/执行工作 / Implementation & execution |

`AgentRoleConfig` 包含 / contains: `description`, `config_file`（TOML）, `nickname_candidates`

**特点 | Highlights:**
- 角色配置通过 TOML 文件覆盖 model/reasoning/service_tier / Role configs override model/reasoning/service_tier via TOML
- 子 Agent = 完整的 `CodexThread`（含自己的 session、rollout、tools、状态）/ Child agent = full `CodexThread` with its own session, rollout, tools, and state
- 与父 Agent 在技术上完全等价，仅 `SessionSource::SubAgent` 标记区分 / Technically equivalent to parent agent, differentiated only by `SessionSource::SubAgent` marker
- 多 Agent 版本：V1（ThreadId 寻址）→ V2（AgentPath 层级寻址 `/root/task1/task_3`）/ Multi-agent versions: V1 (ThreadId) → V2 (AgentPath hierarchical addressing `/root/task1/task_3`)
- Feature gate：`[features.multi_agent_v2]` 控制是否启用 / Controls V2 enablement via feature gate

### 2.4 OpenCode

**Agent 类型系统 | Agent Type System:**

```ts
mode: "subagent" | "primary" | "all"
```

三种 mode | Three modes:
- **`subagent`**：只能被 Task tool 调用，不在 @ 菜单中显示 / Only callable via Task tool, not shown in @ menu
- **`primary`**：用户可见的主 Agent（如 `build`, `plan`）/ User-visible primary agent (e.g., `build`, `plan`)
- **`all`**：既对用户可见，也可被调用为子 Agent / Both user-visible and callable as subagent

**内置原生 Agent | Built-in Native Agents:**

| Agent | Mode | 特点 Description |
|-------|------|------|
| `build` | primary | 默认，全权限 / Default, full permissions |
| `plan` | primary | 只读 + 仅允许修改 plan 文件 / Read-only, only plan file modifications |
| `general` | subagent | 通用研究，deny todowrite / General research, deny todowrite |
| `explore` | subagent | 快速探索，仅 grep/glob/read/bash / Quick exploration, grep/glob/read/bash only |
| `compaction` | primary (hidden) | 上下文压缩，deny 所有 tools / Context compaction, deny all tools |
| `title` | primary (hidden) | 生成标题 / Generate title |
| `summary` | primary (hidden) | 生成摘要 / Generate summary |

**自定义 Agent（Markdown 配置）| Custom Agent (Markdown config):**
```yaml
---
mode: subagent
model: opencode/gpt-5.4-nano
color: "#44BA81"
permission:
  "*": false
  "github-triage": true
steps: 10
---
系统提示词正文... / System prompt body...
```

**特点 | Highlights:**
- Agent 定义来自三处：硬编码原生 + `.opencode/agent/*.md` + `opencode.jsonc` / Agent definitions from three sources: hardcoded native + `.opencode/agent/*.md` + `opencode.jsonc`
- 每个 Agent 可绑定独立的 system prompt（`prompt` 字段）/ Each agent can bind its own system prompt via `prompt` field
- 权限系统分层合并（父 deny → 子 deny 继承传播）/ Hierarchical permission merging (parent deny propagates to child)
- **默认禁止递归 spawn**（子 Agent default-deny `task` tool）/ Recursive spawn disabled by default (child agents default-deny `task` tool)

---

## 3. 启动与生命周期管理 | Launch & Lifecycle Management

### 3.1 启动工具对比 | Launch Tool Comparison

| 特性 Feature | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **启动工具名 Launch Tool** | `Agent` | `agent_open` / `agent_eval` / `agent_close` / `tool_agent` | `spawn_agent` / `followup_task` / `send_message` / `wait_agent` / `list_agents` / `interrupt_agent` | `task` |
| **子 Agent 查询 Query Child** | 内联（Agent tool description 动态列出）/ Inline in tool description | `agent_list` | `list_agents` | 内联（task tool description 动态列出）/ Inline in tool description |
| **等待子 Agent Wait** | 同步返回结果 / 异步通知 / Sync return or async notification | `agent_eval(block=true)` | `wait_agent` | 同步返回 / `background.wait()` / Sync return or background wait |
| **中断子 Agent Interrupt** | TaskStop tool | `agent_close` | `interrupt_agent` | cancel via controller |
| **消息传递 Messaging** | 隐式（prompt）/ Implicit via prompt | `agent_eval` 可带后续消息 / With follow-up messages | `followup_task` / `send_message` | 隐式（prompt）/ Implicit via prompt |
| **Agent 命名 Naming** | 无（按 agent_type）/ None, by agent_type | whale nickname（确定性哈希）/ Deterministic hash nickname | AgentPath 层级路径 + 随机昵称 / Hierarchical path + random nickname | session title 描述 / Session title |
| **Fork/上下文继承 Context Inheritance** | Fork Agent（共享 prompt cache）/ Shared prompt cache | `fork_context: true`（prefix-cache 复用）/ Prefix-cache reuse | `SpwnAgentForkMode::FullHistory / LastNTurns` | 不支持（fresh session only）/ Not supported |

### 3.2 生命周期状态 | Lifecycle States

| 状态 State | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| 启动 Launching | async_launched | Pending → Running | PendingInit | running |
| 运行中 Running | running（progress tracking） | Running | Running | running |
| 完成 Completed | completed | Completed | Completed(final_message) | completed |
| 失败 Failed | error | Failed(reason) | Errored(String) | error |
| 中断 Cancelled | cancelled | Cancelled / Interrupted(reason) | Interrupted | cancelled |
| 后台 Background | backgroundable mid-run | N/A | N/A | background（实验性 / experimental） |

### 3.3 并发控制 | Concurrency Control

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **最大并发 Max Concurrency** | 可配置 / Configurable | 可配置（default 10, max 20）/ Configurable (default 10, max 20) | `max_concurrent_threads_per_session`（default 4） | 无显式上限（Effect fiber pool）/ No explicit limit |
| **深度限制 Depth Limit** | 无显式上限 / No explicit limit | `max_spawn_depth`=3 | 无显式上限 / No explicit limit | 默认 depth=0（拒绝递归）/ Default depth=0 (deny recursion) |
| **容量检查 Capacity Check** | AgentExecutionLimiter | `running_count() >= max_agents` → 拒绝 / Reject | `try_increment_spawned()` CAS 原子计数 / CAS atomic counter | 无 / None |
| **后台运行 Background** | 支持 + coordinator mode / Supported + coordinator mode | 无（前台阻塞或 task_manager 独立系统）/ None (blocking or separate task_manager) | 支持 / Supported | 支持（实验性 feature flag）/ Supported (experimental) |

---

## 4. 任务/Todo 系统 | Task/Todo System

### 4.1 任务数据模型对比 | Data Model Comparison

**Claude Code V2 Task：**

```ts
Task {
  id: string           // 自增数字 / Auto-incrementing number
  subject: string      // 标题 / Title
  description: string  // 描述 / Description
  activeForm?: string  // 进行时态（spinner 显示）/ Active form for spinner display
  owner?: string       // Agent ID
  status: "pending" | "in_progress" | "completed"
  blocks: string[]     // 阻塞的任务 ID / Task IDs this blocks
  blockedBy: string[]  // 被哪些任务阻塞 / Task IDs blocking this
  metadata?: Record
}
```

**CodeWhale Checklist/TaskManager：**

```rust
// 轻型 Checklist（LLM 可见）/ Lightweight checklist (LLM-visible)
ChecklistItem { id, content, status, completion_pct, in_progress_id }

// 重型 TaskRecord（持久化后台任务队列）/ Heavyweight TaskRecord (persisted background queue)
TaskRecord {
  id, prompt, model, workspace, mode
  status: Queued → Running → Completed | Failed | Canceled
  timeline, tool_calls, checklist, gates, attempts, artifacts
}
```

**Codex Plan：**

```rust
PlanItemArg { step: String, status: Pending | InProgress | Completed }
UpdatePlanArgs { explanation: Option<String>, plan: Vec<PlanItemArg> }
```

**OpenCode Todo：**

```ts
Todo.Info {
  content: string
  status: "pending" | "in_progress" | "completed" | "cancelled"
  priority: "high" | "medium" | "low"
}
```

### 4.2 持久化对比 | Persistence Comparison

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **Todo 持久化 Todo Persistence** | V1: 内存 / V2: 文件（JSON per task，`~/.claude/tasks/<id>.json`）/ V1: in-memory, V2: file JSON | checklist: 内存（per subagent fresh）/ task_manager: 文件 JSON / checklist: in-memory, task_manager: file JSON | **无持久化**（纯流式 UI 事件）/ No persistence (streaming UI only) | SQLite（`TodoTable` per session） |
| **并发安全 Concurrency Safety** | 文件锁（`proper-lockfile`，30 次重试）/ File lock with 30 retries | 无（单线程 checklist）/ task_manager 文件锁 / None (single-thread) / file lock for task_manager | N/A | 事务性 delete+insert / Transactional delete+insert |
| **恢复能力 Recovery** | V2 支持进程重启恢复 / V2 supports process restart recovery | task_manager 重启恢复（running → Failed）/ task_manager restart recovery (running → Failed) | N/A | SQLite 自动恢复 / SQLite auto-recovery |
| **多 Agent 共享 Multi-Agent Sharing** | 是（task list per team/session）/ Yes (per team/session) | 否（per agent fresh checklist）/ No (fresh checklist per agent) | 否 / No | 否（per session 隔离）/ No (isolated per session) |

### 4.3 工具集对比 | Tool Set Comparison

| 功能 Feature | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| 创建任务 Create Task | TaskCreate | checklist_write / checklist_add | update_plan | todowrite |
| 更新状态 Update Status | TaskUpdate | checklist_update | update_plan | todowrite（全量替换 / full replacement） |
| 列表查询 List Tasks | TaskList | checklist_list | 无（plan 内联于消息）/ None (plan inline in message) | 无（内联于消息）/ None (inline in message) |
| 获取详情 Get Details | TaskGet | N/A | N/A | N/A |
| 依赖关系 Dependencies | blocks / blockedBy | N/A | N/A | N/A |
| Agent 分配 Agent Assignment | owner 字段 / owner field | N/A | N/A | N/A |
| 删除任务 Delete Task | TaskUpdate (status) | 无独立工具 / no dedicated tool | N/A | 移除 plan item / remove plan item |
| 任务输出读取 Read Output | TaskOutput | N/A | N/A | N/A |

---

## 5. System Prompt 中 LLM 指令对比 | LLM Instructions in System Prompts

### 5.1 何时使用子 Agent | When to Spawn Sub-agents

| 产品 Product | 指令风格 Style | 核心策略 Strategy |
|------|----------|----------|
| **Claude Code** | 详细示例驱动 / Example-driven | "Launch multiple agents concurrently... use a single message with multiple tool uses" · "Brief the agent like a smart colleague" · Fork 模式：省略 subagent_type 共享上下文 / Fork mode: omit subagent_type to share context |
| **CodeWhale** | 数字驱动 / Cost-driven | "Sub-agents are cheap — DeepSeek V4 Flash costs $0.14/M input. Use them liberally" · 并行调查：每个目标一个只读子 Agent / Parallel exploration: one read-only agent per target · 并行实现：每个独立叶子任务一个子 Agent / Parallel implementation: one agent per leaf task · 并发上限 10，达到上限时批处理 / Max concurrency 10, batch when full |
| **Codex** | 约束驱动 / Constraint-driven | "Default to doing the work yourself" · 只为具体、有界的独立并行子任务 spawn / Only spawn for well-bounded, independent parallel subtasks · 不委托简单任务、小编辑、例行搜索 / Don't delegate simple tasks, small edits, routine searches · Message 通道区分 NEW_TASK/MESSAGE/FINAL_ANSWER / Message channel distinguishes NEW_TASK/MESSAGE/FINAL_ANSWER |
| **OpenCode** | 工具匹配驱动 / Tool-matching driven | "When doing file search prefer the Task tool to reduce context usage" · "Proactively use Task with specialized agents when task matches agent description" · 告知子 Agent 是写代码还是做研究 / Tell subagent whether it's coding or researching |

### 5.2 子 Agent 完成后处理 | Post-Completion Handling

| 产品 Product | 指令 Instruction |
|------|------|
| **Claude Code** | "The result is not visible to the user... send a text message summarizing the result" · "Trust agent outputs generally" |
| **CodeWhale** | `<codewhale:subagent.done>` 哨兵 + human summary line / Sentinel + summary · "Integrate findings — don't re-do what the child already did" · "Process multiple sentinels then synthesize" |
| **Codex** | `InterAgentCommunication` + `FINAL_ANSWER` 消息类型 / Message types · "Integrate results, don't redo delegated work" |
| **OpenCode** | `<task_result>` XML 包裹 / XML wrapper · "The result returned by the agent is not visible to the user" · "Show the user a concise summary" |

---

## 6. 持久化与监控 | Persistence & Observability

### 6.1 持久化范围 | Persistence Scope

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| Session 持久化 Session Persistence | 是（sidechain transcript）/ Yes | 是（subagents.v1.json 状态文件）/ Yes (state file) | 是（thread store，完整 rollout）/ Yes (full rollout) | 是（SQLite，完整 messages/parts）/ Yes (SQLite, full messages/parts) |
| Agent 记忆 Agent Memory | 三级记忆（user/project/local, MEMORY.md）/ 3-tier memory | 无 / None | 无 / None | 无 / None |
| 任务持久化 Task Persistence | V2：文件 JSON / File JSON | task_manager：文件 JSON / File JSON | N/A | SQLite |
| 后台任务持久化 Background Task Persistence | 否（进程重启丢失）/ No (lost on restart) | 否（task_manager 除外）/ No (except task_manager) | 否 / No | 否 / No |

### 6.2 监控/可观测性 | Monitoring & Observability

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **进度跟踪 Progress Tracking** | ProgressTracker（toolUseCount + tokens + recentActivities + summary） | Mailbox 事件流（ToolCallStarted/Completed/TokenUsage）/ Mailbox event stream | EventMsg::TurnStarted/Complete/Aborted | FooterSubagentTab（状态 + tool calls + 时间戳 / status + tool calls + timestamps） |
| **定期摘要 Periodic Summary** | 每 30s fork Agent 生成进度摘要 / Fork agent every 30s for summary | 心跳超时检测（300s 无活跃 → cancel）/ Heartbeat timeout (300s inactivity → cancel) | 无 / None | 无 / None |
| **成本统计 Cost Tracking** | Token 统计 / Token stats | 实时 token → cost（cost_status.rs）/ Real-time token → cost | Token 统计 per session | SQLite tokens/cost per session |
| **分析/遥测 Analytics/Telemetry** | tengu_agent_tool_selected/terminated 等 | AgentStats（spawns/successes/failures + success_rate_pct） | SubAgentThreadStarted + subagent_tool_call count + 遥测 counter / Telemetry counters | 无专用子 Agent 分析 / No dedicated subagent analytics |
| **Hook 事件 Hook Events** | 子 Agent start/stop hooks | subagent_spawn / subagent_complete hooks | SubagentStart / SubagentStop hooks | 无（todo.updated 事件）/ None (todo.updated event) |
| **Sentinel/Completion 通知 Notification** | XML user-message 块（task ID/status/summary/output path） | `<codewhale:subagent.done>` JSON 哨兵 / JSON sentinel | InterAgentCommunication FINAL_ANSWER | `<task_result>` XML |

---

## 7. 关键差异与独特设计 | Key Differences & Unique Designs

### 7.1 Claude Code 的独特设计 | Claude Code's Unique Design

1. **Fork Agent（上下文共享 Agent / Context-Sharing Agent）**：不指定 `subagent_type` 时，自动 Fork 当前会话，保留完整上下文和 prompt cache 字节等价性。这使得上下文密集型任务无需重新构建上下文。/ When `subagent_type` is not specified, auto-forks the current session, preserving full context and prompt cache byte-equivalence, so context-intensive tasks don't need to rebuild context.
2. **AsyncLocalStorage 并发隔离 / ALS Concurrency Isolation**：多个后台 Agent 在同一 Node.js 进程中通过 ALS 隔离，避免 AppState 泄漏。/ Multiple background agents are isolated via ALS within the same Node.js process, preventing AppState leakage.
3. **Coordinator 模式 / Coordinator Mode**：主 Agent 变为纯协调者（仅 Agent/SendMessage/TaskStop 工具），所有实际工作委托给后台 Worker。/ The main agent becomes a pure coordinator (only Agent/SendMessage/TaskStop tools), delegating all actual work to background workers.
4. **Verification Agent（合约化验证 / Contractual Verification）**：3+ 文件/后端/基础设施变更必须 spawn verification Agent，产生 PASS/FAIL/PARTIAL 结构化裁决。/ Changes to 3+ files, backend, or infrastructure must spawn a verification agent, producing PASS/FAIL/PARTIAL structured rulings.
5. **Agent Memory（三级持久记忆 / 3-Tier Persistent Memory）**：`~/.claude/agent-memory/<type>/MEMORY.md` 多会话跨项目记忆共享。/ Multi-session, cross-project memory sharing.
6. **Worktree/Remote 隔离 / Worktree & Remote Isolation**：Agent 可在独立 git worktree 或远程 CCR 环境中运行。/ Agents can run in independent git worktrees or remote CCR environments.
7. **Handoff 分类 / Handoff Detection**：子 Agent 完成后自动检测是否"交接"了未完成工作，并警告父 Agent。/ Automatically detects if a child agent has handed off incomplete work and warns the parent agent.

### 7.2 CodeWhale 的独特设计 | CodeWhale's Unique Design

1. **ToolAgent（"Fin" 快速通道 / "Fin" Fast Channel）**：专为 DeepSeek V4 Flash 设计（thinking=off），用于简单 OCR/搜索/获取任务，成本极低。/ Designed for DeepSeek V4 Flash (thinking=off) for simple OCR/search/fetch tasks at minimal cost.
2. **Mailbox 系统 / Mailbox System**：结构化的 pub/sub 进度流，支持 TUI 多面板实时渲染（DelegateCard / FanoutCard）。/ Structured pub/sub progress stream with real-time TUI multi-panel rendering.
3. **双重取消层级 / Dual Cancel Hierarchy**：`child_runtime()`（父取消 = 子取消）vs `background_runtime()`（`agent_open` 脱离父生命周期）。/ Parent cancel = child cancel vs background runtime independent of parent lifecycle.
4. **Whale 昵称系统 / Whale Nickname System**：基于 Agent ID 确定性哈希分配鲸名（如"蓝鲸""虎鲸"），人性化标识。/ Deterministic hash-based whale nicknames (e.g., "Blue Whale", "Orca") for human-friendly identification.
5. **深度硬上限 / Hard Depth Limit**：`max_spawn_depth=3`，防止过度递归。/ Prevents excessive recursion.
6. **task_manager 与 subagent 分离 / Separate task_manager & Subagent**：独立的持久化后台任务队列系统，与 subagent API 不同路径。/ Independent persisted background task queue system on a separate path from the subagent API.
7. **Checklist 与 Task 双重系统 / Dual Checklist & Task System**：轻型 checklist（LLM 可见/内存）vs 重型 task_manager（后台/持久化/多 attempt/artifact 附带）。/ Lightweight in-memory checklist vs heavyweight persisted task_manager with attempts and artifacts.

### 7.3 Codex 的独特设计 | Codex's Unique Design

1. **AgentPath 层级寻址 / Hierarchical AgentPath Addressing**：`/root/task1/task_3` 树状路径 + 相对名称引用（`task_3` 可指当前路径）。/ Tree path with relative name references (e.g., `task_3` refers to current scope).
2. **Inter-Agent Communication 通道 / Inter-Agent Communication Channel**：加密消息（`InterAgentCommunication`），区分 NEW_TASK / MESSAGE / FINAL_ANSWER 三种消息类型，支持 `trigger_turn` 标志控制是否启动新回合。/ Encrypted messages with three types (NEW_TASK/MESSAGE/FINAL_ANSWER) and `trigger_turn` flag for new turn control.
3. **Approval Forwarding / 权限转发**：子 Agent 的权限批准请求（exec/apply_patch）转发到父 session 决策（`codex_delegate.rs`）。/ Child agent permission approval requests (exec/apply_patch) are forwarded to the parent session for decision.
4. **Skills Guard / 技能守卫**：明确禁止主 Agent 将 skill 指令的阅读/理解委托给子 Agent。/ Explicitly prohibits the main agent from delegating skill instruction reading/comprehension to child agents.
5. **V1 → V2 多版共存 / Multi-Version Coexistence**：V1 使用 flat ThreadId，V2 使用 AgentPath + 加密通信 + mailbox；feature gate 控制。/ V1 uses flat ThreadId, V2 uses AgentPath + encrypted communication + mailbox; controlled by feature gate.
6. **Plan 工具零持久化 / Zero-Persistence Plan Tool**：`update_plan` 是纯流式 UI 事件，无服务端存储。/ Pure streaming UI events with no server-side storage.
7. **Role 配置通过 TOML / TOML-based Role Config**：每个角色独立的 TOML 文件覆盖 model/reasoning/permissions。/ Each role has its own TOML file to override model/reasoning/permissions.

### 7.4 OpenCode 的独特设计 | OpenCode's Unique Design

1. **三层 Mode 模型 / Three-Tier Mode Model**：`subagent` / `primary` / `all` 清晰区分 Agent 的可见性和可调用性。/ Clearly distinguishes agent visibility and callability.
2. **默认防递归 / Anti-Recursion by Default**：子 Agent 的 `task` tool 默认 deny，显式允许才可递归 spawn。/ Child agent `task` tool is denied by default; explicit permission required for recursive spawn.
3. **权限继承传播 / Permission Inheritance Propagation**：子 Agent 权限 = 父 deny 合并 + session deny + 默认 deny task/todowrite。/ Child permissions = parent deny merge + session deny + default deny task/todowrite.
4. **SQLite 全量持久化 / Full SQLite Persistence**：Todo、Session、Messages、Parts 全部持久化于 SQLite，查询和恢复简单。/ All data (Todo, Session, Messages, Parts) persisted in SQLite for easy query and recovery.
5. **Markdown 自定义 Agent / Markdown Custom Agent**：通过 YAML frontmatter + Markdown body 定义 Agent 配置和 prompt。/ Define agent config and prompt via YAML frontmatter + Markdown body.
6. **动态 Tool Description / Dynamic Tool Description**：Task tool 的 description 在运行时动态追加可用 Agent 列表。/ Task tool description dynamically appends the available agent list at runtime.
7. **Background Job 引擎 / Background Job Engine**：Effect-TS 风格的 Job registry，支持 extend/promote/cancel/wait 操作。/ Effect-TS style job registry with extend/promote/cancel/wait operations.
8. **SubagentData 实时监控 / Real-time Subagent Monitoring**：TUI Footer 显示每个子 Agent 的状态、工具调用数、最后更新时间。/ TUI footer displays each subagent's status, tool call count, and last update time.

---

## 8. 设计哲学总结 | Design Philosophy Summary

| 维度 Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|------|-------------|-----------|-------|----------|
| **架构复杂度 Architecture Complexity** | 极高（ALS + 多模式 + 记忆系统）/ Very high (ALS + multi-mode + memory) | 高（Mailbox + 双重系统 + 深度控制）/ High (Mailbox + dual system + depth control) | 极高（V1/V2 + 加密通信 + 路径寻址）/ Very high (V1/V2 + encrypted comm + path addressing) | 中等（Effect-TS + Session 树 + SQLite）/ Medium (Effect-TS + session tree + SQLite) |
| **扩展性 Extensibility** | 自定义 Agent（Markdown/JSON）+ Plugin / Custom agents + plugins | 硬编码 8 种（无外部扩展）/ 8 hardcoded roles (no external extension) | 角色 TOML 配置 / Role TOML config | Markdown 自定义 Agent / Markdown custom agents |
| **安全性 Security** | Permission 分级 + Worktree 隔离 / Permission tiers + worktree isolation | 深度硬上限 + 工具白名单 / Hard depth limit + tool whitelist | Approval Forwarding + Skills Guard | 权限继承 + 默认防递归 / Permission inheritance + anti-recursion |
| **可观测性 Observability** | ProgresTracker + 30s 摘要 + 遥测 / Progress tracker + 30s summary + telemetry | Mailbox 事件流 + 心跳 + 成本统计 / Mailbox event stream + heartbeat + cost stats | 遥测 counter + Hook 事件 / Telemetry counters + hook events | Footer 监控 + SQLite 统计 / Footer monitoring + SQLite stats |
| **上下文效率 Context Efficiency** | Fork Agent + prompt cache 共享 / Fork agent + prompt cache sharing | fork_context prefix-cache + resident_file | ForkMode FullHistory/LastNTurns | 无缓存优化 / No cache optimization |
| **适合场景 Best For** | 大型多 Agent 协作 + 长记忆 / Large multi-agent collaboration + long memory | 高吞吐低成本 Agent 调用 / High-throughput low-cost agent calls | 企业级多 Agent 安全协作 / Enterprise-grade secure multi-agent | 轻量级、易配置的子 Agent 委托 / Lightweight, easily configurable subagent delegation |

