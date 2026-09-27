# deepseek-harness 动态工作流机制解析 | Dynamic Workflow Mechanism

deepseek-harness（dsh）的动态工作流（dynamic workflow）机制说明：模型用 `workflow` 工具写一段 JavaScript 编排脚本，runtime 在独立 worker 线程 + vm 上下文中执行该脚本，脚本通过 `agent()` 等钩子调度子代理并回收其结果，最终把脚本的返回值交还给调用方 Agent。
An explanation of deepseek-harness's dynamic workflow mechanism: the model writes a JavaScript orchestration script via the `workflow` tool, the runtime executes it in a dedicated worker thread + vm context, the script schedules subagents through hooks like `agent()` and collects their results, and the script's return value is handed back to the calling Agent.

> 分析日期 | Date：2026-09
> 源码基准 | Based on：deepseek-harness 仓库 `master` 分支，commit `47f943859bef60e4160492346772ded9b24f765a`（2026-08-13）

---

## 1. 机制概览 | Overview

执行循环 | The execution loop：

1. **模型写脚本 | The model writes a script**：模型调用 `workflow` 工具，提交 `script`（纯 JS 函数体，非 TypeScript）+ `meta`（JSON 身份块）+ 可选 `args`。工具描述本身就是脚本写作规范。
   The model calls the `workflow` tool with `script` (plain-JS body, not TypeScript) + `meta` (JSON identity block) + optional `args`; the tool description is itself the authoring spec.
2. **runtime 执行脚本 | The runtime executes the script**：`ctx.workflowEngine`（抽象 seam，实现为 `dsh-workflow-worker-thread` 引擎）在发布前校验 meta 并预解析脚本，随后为本次运行启动一个独立 worker 线程，脚本在 `node:vm` 上下文中以顶层 await 执行，host 主循环不被阻塞。
   The abstract `ctx.workflowEngine` seam (implemented by `dsh-workflow-worker-thread`) validates meta and pre-parses the body before publication, then starts one dedicated worker thread per run; the script runs in a `node:vm` context with top-level await, never blocking the host loop.
3. **脚本调度 agent | The script schedules agents**：脚本通过全局钩子调度工作——`agent()` 经 message-port RPC 桥接到 subagent seam 启动 one-shot 子代理，`parallel()`/`pipeline()` 提供并发与流水线组合，`phase()`/`log()` 报告进度；并发、总量、单次条数均受上限约束。
   The script schedules work through globals — `agent()` bridges via message-port RPC to the subagent seam to start one-shot children, `parallel()`/`pipeline()` provide concurrency and pipelining, `phase()`/`log()` report progress — under concurrency, total, and per-call caps.
4. **前台同步执行 | Foreground synchronous execution**：工具调用阻塞到脚本结算；非 `completed` 结局（`cancelled`/`error`）映射为 `isError` 工具结果，脚本最终 `return` 的 JSON 值作为工具结果交还给父 Agent 上下文。
   The tool call blocks until the script settles; non-`completed` outcomes (`cancelled`/`error`) map to `isError` tool results, and the script's final JSON value becomes the tool result returned to the parent Agent context.

交接的两个层次 | Handoff at two layers：

- **父 Agent → 脚本 | Parent Agent → Script**：父 Agent 通过一次工具调用把执行权交给脚本，期间脚本的循环、分支与中间结果都不进入父 Agent 上下文，父 Agent 只收到一个最终 JSON 返回值。多步编排因此从"对话逐轮协调"变成"脚本持有控制流"。
  The parent Agent hands execution to the script through one tool call; the script's loops, branches, and intermediate results never enter the parent context — the parent receives a single final JSON value. Multi-step orchestration thus moves from "turn-by-turn conversation coordination" to "the script holds the control flow."
- **脚本 → 子代理 | Script → Children**：脚本里每次 `agent()` 都启动一个 one-shot 子代理，子代理以 `parentSession` 单亲树归属到调用 `workflow` 工具的父 Agent（`WorkflowStartRequest.parent`，见 §5.2；`origin: subagent`、`delegationDepth + 1`），结果回收进脚本（文本或结构化对象），失败的子代理解析为 `null`。
  Each `agent()` call starts a one-shot subagent attributed to the parent Agent that called the `workflow` tool (`WorkflowStartRequest.parent`, see §5.2; `parentSession` single-parent tree, `origin: subagent`, `delegationDepth + 1`); results return into the script (text or structured object), and failed children resolve to `null`.

要点 | Key points：

- 脚本不是任意程序：**没有 fs、网络、定时器或任何 Node API**——"活是 agent 干的，脚本只负责协调"（`the agents do the work, the script only coordinates them`）。
  The script is not an arbitrary program: **no filesystem, network, timers, or Node APIs** are provided.
- 信任模型：脚本与模型的 bash 访问同级信任，vm + worker 提供的是主机隔离与强制终止，**不是恶意代码的安全边界**。
  Trust model: scripts carry the same trust as the model's bash access — vm + worker provide host-loop isolation and forced termination, **not a security boundary against hostile code**.
- 该机制是对 **Claude Code dynamic workflows** 的移植与严格化（脚本契约兼容 CC，差异见 §8）。
  The mechanism is a port and tightening of **Claude Code dynamic workflows** (script contract CC-compatible; divergences in §8).

---

## 2. 总体架构 | Architecture

`packages/workflow/` 采用与 bash seam 相同的三段式（服务定义 / 服务提供 / 消费方）：
`packages/workflow/` follows the same three-part bash-seam shape (Service Definition / Service Provider / Consumer):

| 层 Layer | 包 Package | 职责 Responsibility |
|------|------|------|
| 服务定义 Service Definition | `packages/workflow/workflow`（dsh-workflow） | 抽象 seam `ctx.workflowEngine` + 词汇表（请求/运行/结果类型 + `workflow/*` 事件）。每个上下文只允许**一个**引擎实现，无命名 provider 注册表（引擎是部署替换件，不是并存件）/ Abstract seam `ctx.workflowEngine` + vocabulary (request/run/result types + `workflow/*` events). One engine per context, no named-provider registry |
| 服务提供 Service Provider | `packages/workflow/workflow-worker-thread` | `node:worker_threads` 引擎——每次运行一个 worker，脚本的 vm context 在 worker 内 / A `node:worker_threads` engine — one worker per run, the script's vm context inside it |
| 消费方（模型侧）Consumer (model-facing) | `packages/workflow/tool-workflow` | 面向模型的 `workflow` 工具：schema、生命周期、结果渲染（另负责 run 的持久化展示记录，见 §7.2）/ The model-facing `workflow` tool: schema, lifecycle, result rendering (also owns the run's durable display records, see §7.2) |
| 消费方（衍生）Derivative consumer | `packages/workflow/tool-ralph` | 固定脚本的 Ralph 循环：每轮启动一个全新结构化输出子代理，只携带不变目标 + 上一轮有界交接（最直观的"交接"形态）/ A fixed-script Ralph loop: one fresh structured-output child per round carrying only the immutable objective + the previous bounded handoff |
| 基础 Foundation | `packages/subagent/subagent`（dsh-subagent） | 子代理 seam 的 `outputSchema` 结构化输出（workflow 的 `agent({schema})` 依赖它）/ The subagent seam's `outputSchema` structured output |

关键契约 | Key contracts：
- `start(request): WorkflowRun` —— 无法开始的脚本（meta 校验失败/语法错误/provider 路由失败/总量上限超限）在发布前同步抛错。
  `start(request): WorkflowRun` — a script that cannot begin (meta validation / parse failure / provider routing failure / total-cap exceedance) throws synchronously before publication.
- `WorkflowRun.result` **永不 reject**：脚本失败解析为 `stopReason: 'error' | 'cancelled'`。
  `WorkflowRun.result` **never rejects**: failures resolve as `stopReason: 'error' | 'cancelled'`.
- 消费方必须 `dispose()`（幂等）：cancel + 有界结算 + 子代理静默，永不挂死。
  Consumers MUST `dispose()` (idempotent): cancel + bounded settlement + child quiescence.

---

## 3. 脚本契约：模型写什么 | The Script Contract: What the Model Writes

`workflow` 工具调用由三部分组成（工具描述本身就是面向模型的写作规范，系统提示词只加"explicit-ask-only"使用策略，order 115）：
The `workflow` tool call has three parts (the tool description IS the model-facing authoring spec; the system prompt adds only the explicit-ask usage policy, order 115):

| 参数 Parameter | 类型 Type | 说明 Description |
|------|------|------|
| `script` | string | 纯 JavaScript 函数体（**不是 TypeScript**），允许顶层 await，以 `return <json-value>` 结尾（写作规范；无 return 或返回 undefined 时引擎以 `null` 兜底结算，仍为 completed）/ Plain-JS body (NOT TypeScript), top-level await allowed, ends with `return <json-value>` (authoring convention; without a return / returning undefined the engine settles with `null`, still completed) |
| `meta` | JSON object | 工作流身份块：必填 `name`（约定 kebab-case 短名，引擎仅校验非空）、`description`；可选 `whenToUse`、`phases[]`（`{title, detail?, provider?, model?}`）。**纯数据，永不作为代码执行**（引擎做严格白名单形状校验，未知字段逐条点名拒绝）/ Identity block: required `name` (kebab-case by convention; the engine only requires non-empty) and `description`; optional `whenToUse` and `phases[]`. **Plain data, never evaluated as code** (the engine validates against a strict allowlist, rejecting unknown fields by name) |
| `args` | JSON object | 可选输入，原样暴露给脚本作为 `args` 全局（裸列表必须包成字段，如 `{"files": [...]}`）/ Optional input exposed verbatim to the script as the `args` global (a bare list must be wrapped, e.g. `{"files": [...]}`) |

脚本体内的全局钩子 | In-script globals：

| 钩子 Hook | 签名 Signature | 语义 Semantics |
|------|------|------|
| `agent()` | `agent(prompt, opts?): Promise<any>` | 跑完一个子代理。无 `opts.schema` → 子代理最终文本；有 `schema`（对象根 JSON Schema：约束关键词仅 type/properties/required/additionalProperties/items/enum/const/oneOf，另允许 description/title/default/examples 注解键（不参与校验），**无** pattern/format/数值边界）→ 校验后的结构化对象。子代理失败 → `null`（用 `.filter(Boolean)` 过滤）。`opts` 仅接受 `label`/`phase`/`schema`/`provider`/`model`，其他（`effort`/`isolation`/`agentType`）大声拒绝 / Runs one subagent to completion. Without `schema` → the child's final text; with `schema` (object-rooted subset: constraint keywords type/properties/required/additionalProperties/items/enum/const/oneOf plus annotation keywords description/title/default/examples; no pattern/format/numeric bounds) → the validated object. Failed child → `null` (filter with `.filter(Boolean)`). Only `label`/`phase`/`schema`/`provider`/`model` options; anything else rejects loudly |
| `pipeline()` | `pipeline(items, ...stages): Promise<any[]>` | 每个 item 独立走全部 stage，**stage 间无屏障**（多阶段工作的首选）。stage 收到 `(prev, item, index)`；普通 stage 异常只把该 item 置 `null` 并跳过其余 stage / Each item runs through all stages independently with NO cross-stage barrier (preferred for multi-stage work). Stages receive `(prev, item, index)`; an ordinary stage throw drops that ITEM to `null` |
| `parallel()` | `parallel(thunks): Promise<any[]>` | 并发执行零参函数并等待**全部**（有屏障，仅当某阶段确实需要所有前置结果时使用）。抛出异常的 thunk 解析为 `null` / Runs zero-argument functions concurrently and awaits ALL (a barrier; use only when a stage genuinely needs every prior result). A throwing thunk resolves to `null` |
| `phase()` | `phase(title)` | 进入进度阶段（仅观测/UI 分组，无执行语义）/ Progress grouping for observers; no execution semantics |
| `log()` | `log(message)` | 叙述进度 / Narrate progress |
| `args` | global | 工具调用的 `args` 输入，原样（被克隆，脚本修改不影响初始化数据）/ The call's `args`, verbatim (cloned so script mutation cannot alter init data) |

**一个真实的最小脚本**（来自 e2e 快照 | from an e2e snapshot）：

```js
phase('Run')
const reply = await agent('Reply with exactly the word WF_CHILD_OK and nothing else.')
return { reply }
```

**一个更完整的示意**（fan-out 研究 + 对抗验证 | multi-angle research + adversarial verification）：

```js
phase('Research')
const drafts = await parallel([
  () => agent(`Investigate angle A of ${args.topic}`),
  () => agent(`Investigate angle B of ${args.topic}`),
])
phase('Verify')
const verdicts = await pipeline(drafts.filter(Boolean), async (draft) => {
  return agent(`Adversarially verify this finding; reply only "pass" or "refute":\n${draft}`, {
    phase: 'Verify',
    schema: { type: 'object', properties: { verdict: { type: 'string', enum: ['pass', 'refute'] } }, required: ['verdict'] },
  })
})
return { verdicts }
```

---

## 4. 运行时如何执行脚本 | How the Runtime Executes the Script

执行链路（host 侧在发布前先校验 meta 并预解析脚本体，**meta 绝不作为代码求值**——这堵住了"读 CC 风格 `export const meta` 对象时被脚本 getter 劫持 host"的漏洞）：
Execution pipeline (the host validates meta and pre-parses the body before publication; **meta is never evaluated** — this closes the hole where reading a CC-style `export const meta` object would run script-controlled getters on the host):

```
workflow 工具 (dsh-tool-workflow)
  └─ ctx.workflowEngine.start({ script, meta, args?, parent, signal })
       └─ WorkerThreadWorkflowEngine (index.ts；每 run 的 host 侧生命周期在 host.ts)
            ├─ meta 白名单校验 + 脚本预解析 + provider 路由解析 + 总量上限解析（任一失败同步抛错，不发布）
            ├─ 每次运行新起一个 node:worker_threads worker（workerData 跨线程结构化克隆）
            │    └─ worker 内 (runtime.ts)
            │         ├─ new vm.Script(`(async () => {\n${body}\n})()`, { filename: `workflow:${meta.name}`, lineOffset: -1 })
            │         ├─ vm.createContext({})  ← 全局只注入 agent/parallel/pipeline/phase/log/args（函数被 Object.freeze）
            │         └─ runInContext({ timeout: syncTimeoutMs })  ← 覆盖初始同步片
            └─ message-port RPC 桥接脚本的 agent() → host 侧 subagent seam（children.startAgent）
```

关键设计点 | Key design points：

| 设计 Design | 说明 Description |
|------|------|
| **一运行一 worker** | 不池化；worker 防止脚本同步工作阻塞 host，提供序列化边界，并允许取消后**强制终止**（in-process vm 方案被否决：同步 spin 杀不掉，`dispose` 只能丢弃悬置脚本）/ One unpooled worker per run; it unblocks the host, provides a serialization boundary, and permits forced termination after cancellation (in-process vm was rejected: a synchronous spin past the first await cannot be killed, and dispose() could only abandon an unsettled script on the host loop) |
| **值边界 Value boundary** | `materializeFromRealm` 把离开脚本 realm 的值复制为纯 JSON：拒绝函数、符号、bigint、symbol 键属性、嵌套 `undefined`、异类原型（Date/Map/类实例）、循环引用、稀疏数组、带非索引属性的数组、非有限数；数据属性复制使 `"__proto__"` 安全；getter 正常读取，抛出的 getter 大声失败 / Values leaving the realm are copied to plain JSON, rejecting functions, symbols, bigint, symbol-keyed properties, nested `undefined`, exotic prototypes, cycles, sparse arrays, arrays with non-index properties, and non-finite numbers |
| **信任前提 Trust premise** | 脚本与模型 bash 访问同级信任：引擎防**有缺陷的**脚本（保证结算、JSON 安全值、取消静默），不防**恶意**代码——vm/worker 不是安全边界，脚本可逃逸到 Node API；真正沙箱需 isolated-vm/独立进程引擎（deferred）/ Scripts carry the same trust as bash: the engine contains buggy scripts, not hostile code — vm/worker is not a security boundary; real sandboxing needs an isolated-vm or separate-process engine (deferred) |
| **前台同步 Foreground sync** | 工具调用 `await run.result`，脚本跑完才返回（后台收集 deferred，与 shell/subagent 后台统一设计）/ The tool awaits `run.result`; the call returns when the whole script finishes (background collection deferred) |
| **worker 环境 Worker env** | 清除环境变量（不携带 ambient 凭据）与 `execArgv`；Windows 下注入 host 真实 temp 路径；未构建（tsx）形态另转发 `TSX_TSCONFIG_PATH` 供路径解析 / Scrubbed environment (no ambient credentials) and `execArgv`; the host's real temp path injected on Windows; the unbuilt (tsx) shape additionally forwards `TSX_TSCONFIG_PATH` for path resolution |
| **启动握手与竞态账本 Ready/Go & race ledger** | worker 先发 `Ready`、等 host 的 `Go` 才 drive（`Cancel` 消息兼作开门——启动即取消时脚本同步前缀不执行）；host 维护 pending starts 与已发布 child records，结算/取消/死亡后拒绝新的子启动，quiescence 等两者清空后 dispose 才返回 / The worker posts `Ready` and waits for the host's `Go` before driving (`Cancel` doubles as gate-open — a run cancelled before start never executes its synchronous prefix); the host keeps pending starts and published child records, refuses new child starts after settlement/cancellation/death, and disposal returns only after both drain |

引擎配置默认值 | Engine config defaults（`dsh-workflow-worker-thread`）：

| 配置 Config | 默认 Default | 作用 Role |
|------|------|------|
| `provider` | `spawn` | 子代理跑在哪个 subagent provider 上 / Which subagent provider children run on |
| `maxConcurrentAgents` | `0` → `min(16, max(1, availableParallelism() - 2))` | `agent()` 并发上限（FIFO 槽位）/ Concurrent `agent()` ceiling (FIFO slots) |
| `maxTotalAgents` | `1000` | 单次运行 `agent()` 总调用上限（失控循环回止）/ Total `agent()` ceiling per run (runaway-loop backstop) |
| `maxItemsPerCall` | `4096` | `parallel`/`pipeline` 单次 item 数上限 / Per-call item cap |
| `syncTimeoutMs` | `5000` | 脚本初始同步片超时 / Initial synchronous slice timeout |
| `disposeGraceMs` | `5000` | 取消后有界结算宽限，同时是 dispose() 整体时长上界 / Bounded settlement grace after cancellation; also bounds dispose() overall |

---

## 5. 调度与交接细节 | Orchestration & Handoff Details

### 5.1 `agent()` 的完整流程 | The Full `agent()` Flow

取消重查（hook 入口）→ 校验 prompt/opts（realm 物化 + 白名单）→ 总量 cap 检查 → `acquireSlot()`（FIFO 并发槽）→ 取消重查 → RPC `children.startAgent({prompt, schema?, provider?, model?})` → host 侧经 subagent seam 启动 one-shot 子代理 → 取消重查（start 往返窗口；已取消则 dispose 新子代理并抛 `CANCELLED`，不发布事件）→ 发布 `workflow/agent-start` → `await run.result` → 回收结果 → `workflow/agent-end` → `run.dispose()` → 释放槽位。
Cancellation re-check (hook entry) → validate prompt/opts (realm materialization + allowlist) → total-cap check → `acquireSlot()` (FIFO) → cancellation re-check → RPC `children.startAgent(...)` → host starts a one-shot child via the subagent seam → cancellation re-check (start round-trip window; if cancelled, dispose the fresh child and throw `CANCELLED` without emitting events) → emit `workflow/agent-start` → `await run.result` → collect → `workflow/agent-end` → `run.dispose()` → release slot.

### 5.2 归属机制（交接的基础）| Attribution (the Basis of Handoff)

- `WorkflowStartRequest.parent` 是**必填**项——脚本启动的每个子代理都归属到这个活体 Agent 名下。
  `parent` is REQUIRED — every child the script starts is attributed to that live Agent.
- cwd、lineage（`parentSession` 单亲树）、delegation depth 经 subagent seam 传递；子会话事件日志带 `origin: subagent`、`delegationDepth + 1`（见 e2e 快照）。
  cwd, lineage (`parentSession` single-parent tree), and delegation depth pass through the subagent seam; child session logs carry `origin: subagent`, `delegationDepth + 1` (seen in the e2e snapshot).
- 子代理由此继承父 Agent 的工作区、权限范围与深度计数（父深度 +1；绝对深度上限由 subagent seam 的 `depthLimit` 能力与默认策略管辖，workflow 引擎不传 maxDepth）——这是交接中责任与权限传递的载体。
  Children thus inherit the parent's workspace, permission scope, and delegation depth (parent depth + 1; the absolute ceiling is governed by the subagent seam's `depthLimit` capability and default policy — the workflow engine passes no maxDepth) — the carrier of responsibility and authority in the handoff.

### 5.3 结果回收矩阵 | Result Collection Matrix

| 子代理结局 Child Outcome | `agent()` 返回值 Return Value |
|------|------|
| `completed`，无 schema | 子代理最终文本（text blocks 拼接）/ The child's final text |
| `completed`，有 schema | 经强制 capture tool 提交并校验的结构化对象；无结构化值视同子失败 → `null` / The validated structured object; missing structured value counts as child failure → `null` |
| 子代理自身失败（非 completed） | `null`（脚本用 `.filter(Boolean)` 过滤）/ `null` |
| 基础设施故障（result reject） | `WorkflowError('AGENT_RESULT')` **fatal** → 杀死整个脚本，绝不溶解成 `null` / Fatal `WorkflowError` → kills the whole script, never dissolves into `null` |

### 5.4 Ralph：最纯粹的"交接"形态 | Ralph: the Purest Handoff Shape

`tool-ralph` 在 workflow seam 之上实现一个固定脚本的前台循环：每轮启动一个**全新**结构化输出子代理，只携带不可变目标 + 上一轮有界交接内容（`maxHandoffChars` 默认 16384），轮数上限 `maxRounds` 默认 256——"只传递交接，不传递上下文"的接力模型。
`tool-ralph` implements a fixed-script foreground loop over the workflow seam: each round starts a **fresh** structured-output child carrying only the immutable objective + the previous bounded handoff (default 16384 chars), capped at 256 rounds — a relay model where "only the handoff travels, not the context."

---

## 6. 失败纪律与取消 | Failure Discipline & Cancellation

### 6.1 Fatal 错误 vs 逐项 null | Fatal Errors vs Per-item null

- **Fatal**（`WorkflowError`，`fatal: true`）：hook 误用（坏参数、未知/deferred 选项、超集外 schema）、触顶上限、seam 启动失败、结果物化失败（`RESULT_UNSERIALIZABLE`）、取消——`parallel()`/`pipeline()` **重抛** fatal 错误而不是把 item 置 `null`。一个拼错的选项必须大声杀死脚本，绝不溶解成"看起来像普通子失败"的 `null`。
  **Fatal** (`WorkflowError`, `fatal: true`): hook misuse (bad args, unknown/deferred options, out-of-subset schema), tripped caps, seam start failures, result materialization failure (`RESULT_UNSERIALIZABLE`), cancellation — the combinators **re-throw** fatal errors instead of nulling the item. A typo'd option must kill the script loudly, never dissolve into a `null` indistinguishable from a child failure.
- **逐项 null**：仅保留给子代理失败（非 completed 结局）与普通 stage 异常。
  **Per-item null**: reserved for child failures and ordinary in-stage errors.
- 错误代码 | Error codes（其中 `META_INVALID` / `SCRIPT_PARSE` 在 `start()` 发布前同步抛出，从不进入脚本体）：`META_INVALID` / `INVALID_ARGUMENT` / `UNSUPPORTED_OPTION` / `UNSUPPORTED_SCHEMA` / `AGENT_CAP` / `ITEM_CAP` / `AGENT_START` / `AGENT_RESULT` / `SCRIPT_PARSE` / `RESULT_UNSERIALIZABLE` / `CANCELLED`。
  Error codes (`META_INVALID` / `SCRIPT_PARSE` throw synchronously in `start()` before publication, never entering the body): `META_INVALID` / `INVALID_ARGUMENT` / `UNSUPPORTED_OPTION` / `UNSUPPORTED_SCHEMA` / `AGENT_CAP` / `ITEM_CAP` / `AGENT_START` / `AGENT_RESULT` / `SCRIPT_PARSE` / `RESULT_UNSERIALIZABLE` / `CANCELLED`.

### 6.2 结算与取消 | Settlement & Cancellation

- `stopReason` 是**闭合联合**（引擎所有，消费方可穷尽）：`completed` | `cancelled` | `error`；非 completed 时 `error` 携带失败信息，消费方映射为 `isError` 工具结果，**不**把部分输出当成功。
  `stopReason` is a CLOSED union (engine-owned, consumers may exhaust): `completed` | `cancelled` | `error`; failures carry `error`, and the consumer maps them to an `isError` tool result rather than reporting partial output as success.
- 取消在**下一个 hook 边界**生效：`cancel()` 后每个 hook 调用都抛 `CANCELLED`（不止 `agent()`），等待中的槽位被拒绝；脚本若停在 hook 不拥有的 promise 上不结算，则 host 宽限计时器强制结算 `cancelled` 并**终止 worker 线程**——因此消费方 await `result` 永不因取消而卡死。
  Cancellation takes effect at the next hook boundary: after `cancel()` every hook throws `CANCELLED` (not just `agent()`), queued slot waiters reject; a script parked on a promise no hook owns is force-settled `cancelled` by the host's grace timer, which then **terminates the worker** — a consumer awaiting `result` is never wedged by cancellation.
- `drive()` 永不 reject（引擎的 result-never-rejects 契约）；脚本 promise 被丢弃时挂无操作 rejection 消费器，防止 unhandled rejection 杀死 worker。
  `drive()` never rejects (the seam's result-never-rejects contract); dropped script promises get a no-op rejection consumer so unhandled rejections cannot kill the worker.
- 反向故障路径（worker 死亡）：host 监听 worker 的 error/messageerror/exit，首个死亡信号成为消息准入屏障——之后到达的消息不得再创建子代理或叙事，host 收割子代理、为 stranded 的 `agent()` 合成 `cancelled` 结局，run 结算为 `error`（若取消先行则 `cancelled`）。这是 result 永不 reject 在引擎自身故障一侧的支撑。
  The reverse failure path (worker death): the host listens for the worker's error/messageerror/exit; the first death signal bars further message admission — later messages may no longer start children or narrate; the host reaps children, synthesizes `cancelled` endings for stranded `agent()` calls, and settles the run as `error` (or `cancelled` if cancellation came first). This is the other half of the result-never-rejects contract.
- 结算竞争与结果优先级：终端结果只能被认领一次；**取消已请求后**，即使脚本的 `completed` 结果随后到达，也报告 `cancelled`（worker 侧 post-settle 检查 + host 接收侧竞态窗口双保险）——"已请求取消的 run 报 completed 是谎言"。
  Settlement race and result precedence: the terminal result can be claimed only once; once cancellation has been requested, a `completed` result arriving afterwards is still reported as `cancelled` (worker-side post-settle check + host-side race window) — "a cancelled run reporting completed would be a lie."
- abort signal 链与取消级联：start 请求的 `signal` 被 host 安装监听 → `cancel('workflow signal aborted')`；每 run 一个 AbortController 作为全部子代理启动共享的 canonical signal，`cancel()` 立即 abort 在飞子代理；工具侧另有本地桥 `exec.signal` → `run.cancel('parent step aborted')`。
  Abort signal chain and cancellation cascade: the request's `signal` is wired on the host to `cancel('workflow signal aborted')`; each run owns one AbortController as the canonical signal shared by every child start, and `cancel()` immediately aborts in-flight children; the tool side additionally bridges `exec.signal` → `run.cancel('parent step aborted')`.

---

## 7. 可观测性与持久化 | Observability & Persistence

### 7.1 `workflow/*` 事件 | The `workflow/*` Events

六个事件全部是 **observe-only**（仅观察）发布，携带**数据快照**而非活体 run：
All six events are observe-only emits carrying DATA SNAPSHOTS, never the live run:

| 事件 Event | 载荷 Payload | 说明 Note |
|------|------|------|
| `workflow/start` | `WorkflowRunInfo`（id + meta） | 运行开始（meta 已校验）/ Run started (meta validated) |
| `workflow/phase` | + `title` | 脚本进入阶段 / Script entered a phase |
| `workflow/log` | + `message` | 叙述行 / Narration line |
| `workflow/agent-start` | + `WorkflowAgentInfo`（seq/label/phase/childId） | 一次 `agent()` 建立了已发布子运行 / A call established a published child |
| `workflow/agent-end` | + `outcome`（completed/failed/cancelled） | 一次 `agent()` 结算，与 start 按 `agent.seq` 严格配对；终止路径由引擎合成 cancelled 结局 / Paired with start by `seq`, exactly once per call on every stop path |
| `workflow/end` | `WorkflowResultInfo`（stopReason/error/agentsStarted，**刻意不含 value**） | 运行结算；观察者拿不到可变的结果值别名 / Run settled; deliberately WITHOUT the result value |

每个 emit 按监听器隔离：抛异常的订阅者被记录而不传播、不饿死后续监听者；载荷是脱离 run 的独立数据快照（不携带活体 run 句柄）。控制权始终留在 run 的持有者手里。
Every emit is per-listener contained (a throwing subscriber is logged, never propagated); payloads are independent data snapshots detached from the run (never the live run handle). Control stays with the run's holder.

### 7.2 持久化记录与 UI | Durable Records & UI

- `dsh-tool-workflow` 把展示事实投影进调用方父 Session（仅顶层工具调用写记录，嵌套传输调用不写）：`tool-workflow/run-start` → `agent-start`/`agent-end`（按 `runId + seq` 配对）→ `run-end`（结果已知且 dispose 到静默后才写）。首次 append 失败即禁用该运行后续写入，日志保持空或合法前缀，工具结果不受影响。
  The top-level consumer projects display facts into the calling parent Session (only top-level tool calls write records; nested transport calls do not): `tool-workflow/run-start` → paired member start/end → `run-end` (written only after the result is known and disposal reaches quiescence). The first append failure disables later writes for that run.
- `dsh-tool-workflow/invariant` 在提交前与 Session 加载时校验协议：每运行一次 start、成员 seq 为正整数且唯一（不重复）、start/end 配对、run 结束无未闭合成员、结束后无更新。
  The invariant validates the protocol before commit and on Session load: one start per run, unique positive member sequences, paired endings, no open members at run end, no updates after the ending.
- UI 侧 `dsh-client-ui-workflow-run` 把四类事件折叠成一个 `workflow-run` Chat 节点，锚定在 run-start 序列处（位于原 workflow 工具节点之后）；phase 分组只来自真实成员启动，保持精确字符串。
  The UI folds the four event kinds into one `workflow-run` Chat node anchored at the run-start sequence (after the original workflow tool node); phase groups come only from actual member starts, preserving exact strings.

---

## 8. 与 Claude Code dynamic workflows 的异同 | vs Claude Code Dynamic Workflows

该机制是 CC dynamic workflows 的移植；脚本契约兼容（body 可 drop-in），但有几处刻意差异：
A port of CC dynamic workflows; the script contract is compatible (the body is drop-in), with deliberate divergences:

| 维度 Dimension | Claude Code | deepseek-harness | 理由 Rationale |
|------|------|------|------|
| meta 载体 Meta carrier | 脚本内 `export const meta = {...}` | 工具 JSON 参数 | 避免为读 meta 而在 host 上求值模型写的文本（脚本 getter 可劫持 host）；CC 脚本只需把 meta 头挪进参数 / Avoids evaluating model-written text on the host to obtain meta; a CC script just moves its header into the parameter |
| hook 误用 Hook misuse | 静默退化（item → null） | `WorkflowError` fatal，组合子重抛 | 拼错选项不能溶解成与子失败不可区分的 null（本项目禁止 accepted-then-ignored 失败模式）/ A typo'd option must not dissolve into a child-failure-indistinguishable null |
| `args` 形态 Args shape | — | JSON object（裸列表包成字段） | 保持 wire schema 诚实 / Keeps the wire schema honest |
| 确定性限制 Determinism | 禁时钟/随机（为 journaling 恢复） | 暂不限制（journaling/resume deferred） | 兼容 body 今天可读时钟与随机 / Compatible bodies may read the clock and randomness today |
| 后台执行 Background | 默认后台 | 前台同步（后台收集 deferred） | 与 dsh-tool-subagent 的前台切法一致；后台语义跨 shell/subagent/workflow 只设计一次 / Matches dsh-tool-subagent's foreground cut; background designed once across seams |
| 沙箱 Sandbox | — | worker + vm（非安全边界） | isolated-vm / 独立进程引擎 deferred / deferred |

---

## 9. 边界与暂缓项 | Limits & Deferred Non-goals

- **已实现**：前台同步执行、结构化输出（subagent seam 的 capture tool 强制提交与校验）、fatal 失败纪律、有界取消、事件 + 持久化记录 + UI 节点。
  **Done**: foreground sync execution, structured output (forced capture tool on the subagent seam), fatal failure discipline, bounded cancellation, events + durable records + UI node.
- **Deferred**：后台收集（start → run id → 完成通知 → 收集）、journaling + resume（`resumeFromRunId`、缓存 `agent()` 前缀）、保存/打包工作流（`.deepseek/workflows/` 注册表、slash-command API）与脚本持久化到运行目录（工具调用事件已持久化脚本）、嵌套 `workflow()`、token `budget`、`effort`/`isolation`/`agentType` 选项、总 wall-clock 超时、isolated-vm/独立进程硬化沙箱、ACP 后端结构化输出与 `toolFilter`。
  **Deferred**: background collection, journaling + resume, saved/bundled workflows (a `.deepseek/workflows/` registry, slash-command API) and script persistence to a run directory (the tool-call event already records the script durably), nested `workflow()`, token budget, the `effort`/`isolation`/`agentType` options, overall wall-clock timeout, hardened sandboxing, ACP structured output and `toolFilter`.

---

## 10. 附录：关键源文件索引 | Appendix: Key Source Files

### 服务定义 Service Definition（`packages/workflow/workflow/`）
- `src/types.ts` — 浏览器安全词汇：`WorkflowMeta` / `WorkflowResult` / `WorkflowRunInfo` / `WorkflowAgentInfo` / `WorkflowResultInfo` 等 + `workflow/*` 事件载荷（`WorkflowStartRequest` / `WorkflowRun` 在 `runtime-types.ts`）/ Browser-safe vocabulary: `WorkflowMeta` / `WorkflowResult` / `WorkflowRunInfo` / `WorkflowAgentInfo` / `WorkflowResultInfo` etc. + `workflow/*` event payloads (`WorkflowStartRequest` / `WorkflowRun` live in `runtime-types.ts`)
- `src/index.ts` — 抽象 `WorkflowEngine` seam + 6 个 `workflow/*` 事件声明 / Abstract engine seam + the six events
- `src/runtime-types.ts` — host 请求与活体 run 句柄 / Host request and live-run handles

### 引擎 Engine（`packages/workflow/workflow-worker-thread/`）
- `src/host.ts` — host 侧：worker 启动、pending starts / published child records、取消宽限、worker 死亡收割、dispose 静默 / Host side: worker spawn, pending/published child records, cancellation grace, worker-death reaping, disposal quiescence
- `src/worker.ts` — worker 入口 / Worker entry
- `src/runtime.ts` — 每运行一次的 vm 执行体：编译 + vm context + `agent`/`parallel`/`pipeline`/`phase`/`log` 实现、并发槽、cap、取消、结果物化 / Per-run vm execution: compile + context + hook implementations, slots, caps, cancellation, result materialization
- `src/realm.ts` — `materializeFromRealm`（跨 realm 值物化）/`renderThrown`（总式错误渲染）/ Realm value materialization + total error rendering
- `src/protocol.ts` — 私有 enum-keyed 线协议 / Wire protocol
- `src/meta.ts` / `src/session.ts` — meta 校验 / worker 会话管理 / Meta validation / worker session management
- `src/index.ts` — 引擎插件与 Config 默认值 / Engine plugin + config defaults

### 消费方 Consumer
- `packages/workflow/tool-workflow/src/index.ts` — 模型侧 `workflow` 工具：DESCRIPTION 即写作规范、前台生命周期、abort 桥接、结果渲染（50000 字符截断）/ The model-facing tool: DESCRIPTION as authoring spec, foreground lifecycle, abort bridge, result rendering
- `packages/workflow/tool-workflow/src/invariant.ts` — `tool-workflow/*` 记录协议校验 / Record protocol invariant
- `packages/workflow/tool-workflow/src/types.ts` — 四个 `tool-workflow/*` 持久化事件的浏览器安全载荷类型 / Browser-safe payload types for the four `tool-workflow/*` record events
- `packages/workflow/tool-ralph/src/index.ts` — Ralph 固定脚本接力循环（maxRounds 256 / maxHandoffChars 16384）/ Fixed-script relay loop
- `packages/client/ui-workflow-run/README.md` — `workflow-run` Chat 节点 UI / UI node

### 文档与设计记录 Docs & Design Notes
- `docs/subsystems/workflow.md`（+zh）— 官方子系统文档 / Official subsystem doc
- `.agents/notes/implemented/feature/2026-07-05-dynamic-workflows.md`（+zh）— 提案与理由（问题/决策/备选方案/后果）/ Proposal & rationale
- `.agents/notes/implemented/feature/2026-08-10-durable-workflow-runs-in-chat.md` — Chat 持久化记录决策 / Durable records decision
- `.agents/notes/implemented/architecture/2026-07-12-agent-scope-runtime-design.md` — 子代理运行时竞态算法（pending starts / published records）/ Runtime race algorithms
- `examples/acp-agent/tests/snapshots/workflow-run/` — 端到端快照（真实脚本 + `origin: subagent` 子会话）/ e2e snapshot with a real script and child session
- `packages/subagent/subagent/`（dsh-subagent）— `outputSchema` 结构化输出基础（capture tool 实现在 in-process driver）/ Structured-output foundation
