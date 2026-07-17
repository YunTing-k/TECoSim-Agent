# WeChat 模式行为规范 | WeChat Mode Behavior Specification

TECoSim Agent 在通过 WeChat Bot SDK 与用户交互时，受 SDK 及设计约束，存在以下行为限制与机制。
When TECoSim Agent interacts with users via WeChat Bot SDK, the following behavioral constraints and mechanisms apply due to SDK limitations and design choices.

---

## 1. 被动交互模式 | Passive Interaction Mode

Agent 无法主动向用户发送消息，所有交互必须由用户首先发起。Agent 仅在收到用户消息后产生回复。
The Agent cannot initiate messages to the user — all interactions must be triggered by the user first. The Agent only responds after receiving a user message.

**实现方式 / Implementation：** Agent 主循环进入 `listen_tui()` 后持续监听 WeChat 消息队列 (`_msg_queue`)，由 `on_message` 回调在收到消息时填充。当队列非空时退出监听模式，处理消息并生成回复。
The main loop enters `listen_tui()` and continuously monitors the WeChat message queue (`_msg_queue`), which is populated by the `on_message` callback upon receiving messages. When the queue is non-empty, it exits listening mode, processes the message, and generates a reply.

---

## 2. 10 次回复预算 | 10-Reply Budget

每次用户发送消息后，Agent 最多可发送 10 条回复（定义于 `WECHAT_REPLY_BUDGET_MAX = 10`）。该预算耗尽后，Agent 将无法继续发送消息，直到用户发送新的消息重置预算。
After each user message, the Agent may send at most 10 replies (defined as `WECHAT_REPLY_BUDGET_MAX = 10`). Once this budget is exhausted, the Agent cannot send further messages until the user sends a new message to reset the budget.

### 预算计数器 | Budget Counter

计数器 `ctx.wechat_reply_count` 跟踪当前轮次已发送的回复数，每次成功调用 `reply_text_sync` 或 `reply_media_sync` 后自增。`ctx.wechat_reply_total_count` 记录会话累计回复数，**在会话保存时持久化**，恢复会话后继续累加。
The counter `ctx.wechat_reply_count` tracks the number of replies sent in the current round, incremented after each successful `reply_text_sync` or `reply_media_sync` call. `ctx.wechat_reply_total_count` tracks the session-wide total and **is persisted on session save**, continuing to accumulate after session resume.

### 预算生命周期 | Budget Lifecycle

| 阶段 Phase | 行为 Behavior |
|---|---|
| 用户新消息到达（首轮绑定）/ New user message arrives (first-round binding) | `wechat_reply_count` 设为 1（绑定确认消息消耗 1 次预算）/ Set to 1 (binding confirmation consumes 1 budget) |
| 用户新消息到达（非首轮）/ New user message arrives (non-first round) | `wechat_reply_count` 重置为 0 / Reset to 0 |
| 第 1-7 次回复 / Replies 1-7 (count 0..6) | 正常发送文本及媒体 / Normal text and media sending |
| 第 8 次回复 / Reply 8 (count == 7) | 正常发送 / Normal sending |
| 第 9 次回复 / Reply 9 (count == 8) | 文本消息尾部附加预算警告提示 `WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT` / Budget warning hint appended to text message |
| 第 10 次回复 / Reply 10 (count == 9) | 仅允许纯文本回复；媒体发送工具 `wechat_send_media` 将被拒绝（条件：`wechat_reply_count + 1 >= WECHAT_REPLY_BUDGET_MAX`）/ Text-only reply allowed; media send tool `wechat_send_media` is rejected |
| 预算耗尽后 / After budget exhausted (count >= 10) | 不再发送任何消息，直到用户发来新消息 / No more messages sent until the user sends a new message |

---

## 3. 消息 ID 单向性 | One-Way Message ID

由于 WeChat SDK 限制，Agent 发送的消息无法获取其自身的 WeChat 消息 ID（msg id）。Agent 仅能知道用户发来的消息的 ID。
Due to WeChat SDK limitations, the Agent cannot retrieve its own sent message's WeChat message ID (msg id). The Agent can only know the ID of incoming user messages.

**实现细节 / Implementation Detail：** 用户消息 ID 来源于 `msg.raw.get("message_id", "")`，在 `_store_msg_history()` 中存入 `_msg_history` 字典。Agent 发出的回复通过 `reply_text_sync` / `reply_media_sync` 发送，调用返回仅包含成功/失败状态，不包含消息 ID。
The user message ID comes from `msg.raw.get("message_id", "")` and is stored in the `_msg_history` dictionary via `_store_msg_history()`. Agent replies are sent through `reply_text_sync` / `reply_media_sync`, whose return values only contain success/failure status, not message IDs.

---

## 4. 引用消息的来源歧义 | Quoted Message Source Ambiguity

SDK 返回的引用消息仅提供一个 msg id（来自 `ref_msg.message_item.msg_id`），无法直接标识该消息的发送者。用户引用的消息可能是用户自己发送的，也可能是 Agent 此前发送的，Agent 无法直接区分。
The SDK only returns a raw msg id for quoted messages (from `ref_msg.message_item.msg_id`), without identifying the sender. A quoted message could be from the user themselves or from the Agent — the Agent cannot directly distinguish between the two.

**解决方案 / Solution：** Agent 维护一个历史消息记录 `_msg_history`，仅记录用户消息的 ID。当解析引用消息时（`_collect_quoted_msg()`），在该记录中查询 msg id：
The Agent maintains a historical message record `_msg_history` that tracks only user message IDs. When resolving a quoted message (`_collect_quoted_msg()`), it queries this record:

- **命中 / Match found**：该引用来自用户，正常展示引用文本及媒体 / The quote is from the user, displayed normally with text and media.
- **未命中 / No match**：该引用来源未知（可能来自 Agent 自身），显示 `"(Quoted message is unavailable)"` / The quote source is unknown (possibly from the Agent itself), displayed as `"(Quoted message is unavailable)"`.

**持久化 / Persistence：** `_msg_history` 在会话保存时序列化至 `session/<uuid>/msg_history.json`，恢复会话时通过 `load_msg_history()` 重新加载，确保进程重启后引用解析仍然有效。
`_msg_history` is serialized to `session/<uuid>/msg_history.json` on session save and reloaded via `load_msg_history()` on session resume, ensuring quoted message resolution survives process restarts.

此设计避免了 Agent 错误解读自己发送的内容，但也意味着 Agent 无法看到用户引用的 Agent 历史消息。
This design prevents the Agent from misinterpreting its own messages, but also means the Agent cannot see its own historical messages when quoted by the user.

---

## 5. 单用户绑定 | Single-User Binding

WeChat Bot 启动后，第一个发送消息的用户将被绑定为会话的唯一用户。后续来自其他用户的消息将被拒绝。
After the WeChat Bot starts, the first user to send a message is bound as the session's exclusive user. Subsequent messages from other users are rejected.

**实现方式 / Implementation：** `on_message` 回调中检查 `_bound_user_id`：若为空则绑定当前用户并发送随机锁定确认语（`WECHAT_BOT_LOCKED_LIST`）；若已绑定但不匹配则发送随机拒绝语（`WECHAT_BOT_BLOCK_REPLY_LIST`）并丢弃消息。
In the `on_message` callback, `_bound_user_id` is checked: if empty, the current user is bound and a random lock confirmation (`WECHAT_BOT_LOCKED_LIST`) is sent; if already bound to a different user, a random rejection message (`WECHAT_BOT_BLOCK_REPLY_LIST`) is sent and the message is discarded.

---

## 6. 监听模式 TUI | Listening Mode TUI

当 WeChat Bot 启用时，Agent 在等待用户输入阶段进入监听模式。与普通终端模式不同，WeChat 监听模式下**任意按键（除 Ctrl+C 外）无法退出监听** —— 仅 Ctrl+C 可触发 KeyboardInterrupt。监听循环中依次检查 WeChat 消息、定时任务、后台子Agent 三种事件，全部命中后再决定退出（而非命中一个立即退出），确保所有事件在同一轮中被捕获处理。
When WeChat Bot is enabled, the Agent enters listening mode while waiting for user input. Unlike normal terminal mode, **no keypress (except Ctrl+C) can exit listening** — only Ctrl+C triggers KeyboardInterrupt. The listen loop sequentially checks WeChat messages, cron tasks, and background subagents — only after processing ALL event types does it decide to exit (rather than exiting on the first match), ensuring all concurrent events are captured in one round.

**实现位置 / Implementation Location：** `src/utility/agent_listen.py` — `listen_tui()` 函数中，当 `enable_wechat_bot=True` 时，按键事件（除 Ctrl+C）被忽略，尾部提示为 `"Press Ctrl+C to quit this session"`（普通模式为 `"Press any key to quit listening mode and type your words"`）。
In `src/utility/agent_listen.py` — the `listen_tui()` function, when `enable_wechat_bot=True`, keypress events (except Ctrl+C) are ignored and the footer reads `"Press Ctrl+C to quit this session"` (normal mode shows `"Press any key to quit listening mode and type your words"`).

---

## 7. 权限覆盖 | Permission Override

WeChat 模式下，Agent 的工具权限由 `agent_configs.json` 中的 `WECHAT_BOT_PERMISSION` 配置项覆盖，替代终端模式下的交互式权限询问 TUI。MCP 工具的权限也可通过 `WECHAT_BOT_PERMISSION.ALL_MCP_TOOLS` 批量启用/禁用。
In WeChat mode, the Agent's tool permissions are overridden by the `WECHAT_BOT_PERMISSION` configuration in `agent_configs.json`, replacing the interactive permission-request TUI used in terminal mode. MCP tool permissions can also be batch-enabled/disabled via `WECHAT_BOT_PERMISSION.ALL_MCP_TOOLS`.

---

## 8. 工具调用期间的回复策略 | Reply-During-Tool-Call Strategy

通过 `WECHAT_BOT_REPLY_DURING_TOOL_CALL` 配置项控制：Agent 在执行工具调用的中间轮次是否将文本/推理内容发送给用户。
Controlled by the `WECHAT_BOT_REPLY_DURING_TOOL_CALL` configuration: whether the Agent sends text/reasoning content to the user during intermediate tool-call rounds.

- **启用 / Enabled**：每次 LLM 响应（含工具调用）的文本/推理部分实时推送至用户，受预算限制。发送前检查 `(wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX` 确保预算至少为最终的 task-end 回复预留 1 次 / Text/reasoning from each LLM response is pushed to the user in real time, subject to budget limits. Before sending, checks `(wechat_reply_count + 1) >= WECHAT_REPLY_BUDGET_MAX` to always reserve at least 1 budget slot for the final task-end reply.
- **禁用 / Disabled**：仅在任务结束（无工具调用）的最终轮次发送文本回复，中间轮次的工具调用消息不推送给用户 / Only the final round (no tool calls) sends a text reply; intermediate tool-call messages are not pushed to the user.

### 工具调用中的消息插入 | Mid-Tool-Call Message Insertion

自 `0.3.1` 起，LLM 响应处理后、上下文溢出检查之前，`check_wechat()` 在主循环中被调用。若用户在工具执行期间发送新消息，该消息将以 `<wechat_bot>` XML 标签注入 LLM 上下文，Agent 立即响应而不必等待当前轮工具调用全部完成。这实现了**双向即时交互**：Agent 可在工具执行中向用户推送中间结果，用户也可随时插入新指令。

Since `0.3.1`, `check_wechat()` is called in the main loop after each LLM response but before the context overflow check. If the user sends a new message during tool execution, it is injected into the LLM context wrapped in `<wechat_bot>` XML tags, and the Agent responds immediately without waiting for the current round's tool calls to finish. This enables **bidirectional real-time interaction**: the Agent can push intermediate results during tool execution, and the user can inject new instructions at any time.

---

## 9. 快速关闭机制 | Quick Shutdown

`stop()` 调用时，先设 `_stopped` 标志位关闭 long-poll 循环，再通过 `run_coroutine_threadsafe` 将 `task.cancel()` 投递到事件循环所在线程，同步取消所有运行中的协程。`CancelledError` 被 `client.py` 的 poll loop 捕获后秒退，`thread.join()` 不再因 `asyncio.sleep()` 阻塞而等满 `WECHAT_BOT_STOP_TIMEOUT_S` 秒。

On `stop()`, `_stopped` is set to shut down the long-poll loop, then `run_coroutine_threadsafe` dispatches `task.cancel()` into the event loop's thread to synchronously cancel all running coroutines. `CancelledError` is caught by the poll loop in `client.py` for immediate exit — `thread.join()` no longer blocks for `WECHAT_BOT_STOP_TIMEOUT_S` seconds waiting on `asyncio.sleep()`.

**跨线程安全 / Cross-Thread Safety：** `asyncio.all_tasks()` 必须在事件循环所在线程调用（非主线程），否则可能返回空集导致 cancel 无效。`run_coroutine_threadsafe` 确保 cancel 逻辑在正确线程上下文中执行。
`asyncio.all_tasks()` must be invoked from the event loop's own thread (not the main thread), otherwise it may return an empty set and cancel has no effect. `run_coroutine_threadsafe` ensures the cancel logic executes in the correct thread context.

---

## 10. 锁定/拒绝回复文案 | Lock/Block Reply Messages

用户绑定成功后发送的锁定确认消息和被拒绝用户的回复消息均以 `> ` 引用前缀发送，在微信中呈现为灰色引用块样式，与普通文本消息形成视觉区分。文案列表定义于 `constants.py` 的 `WECHAT_BOT_LOCKED_LIST` 和 `WECHAT_BOT_BLOCK_REPLY_LIST`，每次随机选取一条发送。
The lock confirmation (on successful binding) and block rejection (to non-bound users) messages are all sent with a `> ` quote prefix, rendering as grey quote blocks in WeChat — visually distinct from regular text. Message lists are defined in `constants.py` as `WECHAT_BOT_LOCKED_LIST` and `WECHAT_BOT_BLOCK_REPLY_LIST`; one is randomly selected per use.

---

## 11. 媒体文件处理 | Media File Handling

### 下载 / Download

用户发送的媒体文件（图片、文件、视频）通过 CDN 下载。Agent 首先 HEAD 请求获取文件大小，低于 `WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB` 阈值的文件自动下载并缓存至 `session/<uuid>/wechat_cache/`。已下载文件通过 `cdn_cache.json` 持久化索引，避免重复下载。
Media files (images, files, videos) sent by the user are downloaded via CDN. The Agent first sends a HEAD request to get the file size; files below the `WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB` threshold are automatically downloaded and cached to `session/<uuid>/wechat_cache/`. Downloaded files are indexed persistently via `cdn_cache.json` to avoid re-downloading.

语音消息直接提取 ASR 转写文本，不下载音频文件。
Voice messages directly extract ASR transcription text without downloading audio files.

### 上传 / Upload

Agent 通过 `wechat_send_media` 工具发送媒体文件时，文件扩展名自动分类：
When the Agent sends media files via the `wechat_send_media` tool, files are auto-classified by extension:

| 扩展名 Extension | 发送类型 Send Type |
|---|---|
| `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` `.svg` | 图片 / Image |
| `.mp4` `.mov` `.webm` `.mkv` `.avi` | 视频 / Video |
| 其他 / Others | 文件 / File |

文件大小受 `WECHAT_MEDIA_UPLOAD_THRESHOLD_MB` 限制，超限文件拒绝发送。
File size is limited by `WECHAT_MEDIA_UPLOAD_THRESHOLD_MB`; oversized files are rejected.
