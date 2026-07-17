# 配置参数参考 | Configuration Reference

配置文件位于 `./config/` 目录下，包含两个 JSON 文件：`api_configs.json`（API 连接配置）和 `agent_configs.json`（Agent 运行参数）。
Configuration files are located in `./config/`, containing `api_configs.json` (API connection) and `agent_configs.json` (agent runtime).

---

## API 连接配置 | API Connection Configuration

配置文件 `api_configs.json` 定义了 LLM 的接入参数，包括主模型、中阶模型与快速模型的三层模型配置：
The `api_configs.json` file defines LLM connection parameters, including the three-tier model setup (primary + medium + fast model):

> **三层模型架构说明 | Three-Tier Model Architecture**
> - **主模型（MAIN_MODEL）**：驱动 Agent 主交互循环，支持流式输出、工具调用、推理模式，处理复杂/模糊任务
>   **Primary model**: drives the main agent loop with streaming, tool calls, reasoning — handles complex/ambiguous tasks
> - **中阶模型（MEDIUM_MODEL）**：用于子 Agent 的默认推理配置，平衡性能与成本
>   **Medium model**: default reasoning tier for subagents, balancing performance and cost
> - **快速模型（FAST_MODEL）**：用于非循环的辅助任务，如网页内容总结、搜索结果摘要等；固定为非流式，降低延迟与成本
>   **Fast model**: used for non-loop auxiliary tasks (web fetch summarization, search result summarization); non-streaming for lower latency & cost
> - 三个模型共享同一个 `TIMEOUT_MS` 超时配置 / All three models share the same `TIMEOUT_MS`

| 参数 Parameter | 说明 Description |
|-----------|-------------|
| `API_URL` | API 请求地址 / API request base URL |
| `API_KEY` | API 密钥 / API authentication key |
| `MAIN_MODEL_NAME` | 主模型名称 / Primary model name |
| `MAIN_MODEL_TEMPERATURE` | 主模型温度参数 / Primary model temperature |
| `MAIN_MODEL_MAX_TOKENS` | 主模型最大输出 Token 数 / Primary model max output tokens |
| `MAIN_MODEL_STREAM` | 主模型是否启用流式输出（推荐开启以提升交互体验）/ Enable streaming for primary model (recommended) |
| `MAIN_MODEL_CONTEXT` | 主模型上下文窗口大小，用于上下文阈值告警判断 / Primary model context window size, used for context threshold warnings |
| `MAIN_MODEL_ENABLE_REASONING` | 主模型是否启用推理（如 DeepSeek R1 的 thinking 模式）/ Enable reasoning for primary model (e.g. DeepSeek R1 thinking mode) |
| `MAIN_MODEL_REASONING_EFFORT` | 主模型推理强度（`low`/`medium`/`high`）/ Primary model reasoning effort |
| `MAIN_MODEL_DEEPSEEK_SUPPORT` | 主模型是否启用 DeepSeek 格式支持（处理 thinking/reasoning 特殊格式）/ Enable DeepSeek format support for primary model |
| `MEDIUM_MODEL_NAME` | 中阶模型名称，用于子 Agent 等中等复杂度任务 / Medium model name, used for subagents and moderate-complexity tasks |
| `MEDIUM_MODEL_TEMPERATURE` | 中阶模型温度参数 / Medium model temperature |
| `MEDIUM_MODEL_MAX_TOKENS` | 中阶模型最大输出 Token 数 / Medium model max output tokens |
| `MEDIUM_MODEL_CONTEXT` | 中阶模型上下文窗口大小 / Medium model context window size |
| `MEDIUM_MODEL_ENABLE_REASONING` | 中阶模型是否启用推理 / Enable reasoning for medium model |
| `MEDIUM_MODEL_REASONING_EFFORT` | 中阶模型推理强度（`low`/`medium`/`high`）/ Medium model reasoning effort |
| `MEDIUM_MODEL_DEEPSEEK_SUPPORT` | 中阶模型是否启用 DeepSeek 格式支持 / Enable DeepSeek format support for medium model |
| `FAST_MODEL_NAME` | 快速模型名称，用于处理简单/确定性任务 / Fast model name, used for simple/deterministic tasks |
| `FAST_MODEL_TEMPERATURE` | 快速模型温度参数 / Fast model temperature |
| `FAST_MODEL_MAX_TOKENS` | 快速模型最大输出 Token 数 / Fast model max output tokens |
| `FAST_MODEL_ENABLE_REASONING` | 快速模型是否启用推理 / Enable reasoning for fast model |
| `FAST_MODEL_REASONING_EFFORT` | 快速模型推理强度（`low`/`medium`/`high`）/ Fast model reasoning effort |
| `FAST_MODEL_DEEPSEEK_SUPPORT` | 快速模型是否启用 DeepSeek 格式支持（处理 thinking/reasoning 特殊格式）/ Enable DeepSeek format support for fast model |
| `FAST_MODEL_CONTEXT` | 快速模型上下文窗口大小 / Fast model context window size |
| `TIMEOUT_MS` | LLM 请求超时时间（毫秒）/ LLM request timeout (milliseconds) |

> **上下文阈值机制**： Agent 使用 `MAIN_MODEL_CONTEXT` 与 `agent_configs.json` 中的 `CONTEXT_THRESHOLD` 配合，当输入 Token 数达到 `CONTEXT × THRESHOLD` 时，向用户发出告警提示（黄色警告），帮助避免上下文溢出。
> 
> **Context Threshold Mechanism**: The agent uses `MAIN_MODEL_CONTEXT` together with `CONTEXT_THRESHOLD` from `agent_configs.json`: when input tokens reach `CONTEXT × THRESHOLD`, a yellow warning is shown to prevent context overflow.

> **推理模式**： `ENABLE_REASONING` + `REASONING_EFFORT` 专为支持推理能力的模型设计（如 DeepSeek V4）。启用后，Agent 会在 API 请求中附加 `thinking`/`reasoning_effort` 参数。需要配合 `api_configs.json` 中对应模型的 `MAIN_MODEL_DEEPSEEK_SUPPORT` / `MEDIUM_MODEL_DEEPSEEK_SUPPORT` / `FAST_MODEL_DEEPSEEK_SUPPORT` 使用。
> 
> **Reasoning Mode**: `ENABLE_REASONING` + `REASONING_EFFORT` are designed for models with reasoning capabilities (e.g., DeepSeek V4). When enabled, the agent attaches `thinking`/`reasoning_effort` params to API requests. Requires the corresponding `MAIN_MODEL_DEEPSEEK_SUPPORT` / `MEDIUM_MODEL_DEEPSEEK_SUPPORT` / `FAST_MODEL_DEEPSEEK_SUPPORT` in `api_configs.json`.

---

## Agent 运行参数 | Agent Runtime Configuration

配置文件 `agent_configs.json` 定义了 Agent 的核心运行时行为：
The `agent_configs.json` file defines the agent's core runtime behavior:

> **⚠️ 高危参数警告**：以下参数错误配置可能导致 Agent 功能异常、安全策略失效或系统损坏
> 
> **⚠️ High-Risk Parameters**: Incorrect configuration of the following may break agent functionality, bypass security policies, or cause system damage
> - `BASH_PATH` — 指向非 GNU Bash 的 shell 会使风险检测失效，**所有命令都会绕过权限控制** / Points to non-GNU Bash; risk evaluation becomes ineffective and **all commands bypass permission controls**
> - `RIPGREP_PATH` — 指向无效路径会使 `grep_file` 全文搜索工具完全不可用 / Invalid path disables the `grep_file` full-text search tool completely
> - `READ_FILE_MB_LIMIT` — 设置过大可能导致 OOM 或 LLM 上下文溢出 / Excessively large value may cause OOM or LLM context overflow
> - `WECHAT_BOT_PERMISSION` — 微信模式下**直接覆盖主 Agent 全部权限**，误操作可能导致微信用户获得危险工具访问权 / **Fully overrides main agent permissions** in WeChat mode; misconfiguration may grant dangerous tool access to WeChat users
> - `MAIN_TOOL_RESULT_CHAR_LIMIT` — 设置过大会将大量工具结果注入 LLM 上下文，快速耗尽上下文窗口 / Excessively large value injects massive tool result into LLM context, quickly exhausting the context window
> - `READ_FILE_LLM_KB_LIMIT` — 设置过大会将超大文件内容直接注入 LLM 上下文，单次读取即可撑爆 / Excessively large value injects huge file content directly into LLM context; a single read may overflow
> - `SKILL_DESC_CHAR_LIMIT` — 设置过大会导致技能描述占据大量系统提示词，挤占有效上下文空间 / Excessively large value makes skill descriptions consume a large portion of the system prompt, crowding out effective context
> - `WEB_FETCH_LLM_CHAR_LIMIT` — 设置过大会将过量网页内容注入 LLM 上下文 / Excessively large value injects excessive web fetch content into LLM context
> - `WEB_SEARCH_RAW_CHAR_LIMIT` — 搜索原始结果字符限制，过高会导致工具结果截断失效 / Raw search result char limit; too high disables truncation and may bloat tool results
> - `WEB_SEARCH_LLM_CHAR_LIMIT` — 设置过大会将大段搜索结果注入 LLM 上下文 / Excessively large value injects large search result chunks into LLM context

| 参数 Parameter | 说明 Description                                                                                                                       |
|-----------|--------------------------------------------------------------------------------------------------------------------------------------|
| `SIMULATOR_PATH` | TECoSim 仿真器路径（空则不启用仿真功能）/ Path to TECoSim simulator (leave empty to disable simulation)                                              |
| `SIMULATOR_TIMEOUT_S` | 仿真超时时间（秒）/ Simulation timeout (seconds)                                                                                              |
| `BASH_PATH` | **GNU Bash** 路径，Agent 通过 `bash -c` 执行命令，不支持 cmd/pwsh / Path to **GNU Bash** — agent uses `bash -c`; cmd/pwsh not supported           |
| `RIPGREP_PATH` | ripgrep 可执行文件路径（用于 `grep_file` 工具）/ Path to ripgrep executable (used by `grep_file` tool)                                            |
| `MERGE_SYSTEM_PROMPTS` | 是否将多条系统提示词合并为单条消息发送 / Whether to merge multiple system prompts into a single message                                                 |
| `CONTEXT_THRESHOLD` | 上下文阈值比例（如 `0.8` 表示 80%），超过时发出告警 / Context threshold ratio (e.g. `0.8` = 80%), triggers warning when exceeded                         |
| `LLM_SUMMARY_TRIGGER` | 自动摘要触发次数——用户输入达到该次数后自动总结会话 / LLM summary trigger — auto-summarizes session after this many user prompts                              |
| `LLM_SUMMARY_MODEL` | 自动摘要使用的模型类型：`"main"`、`"medium"` 或 `"fast"` / Model type used for auto-summary                                                        |
| `REMIND_TASK_TOOL_GAP` | 工具调用轮次提醒阈值——超过此轮数未使用任务工具则插入系统提醒 / Tool call rounds before reminding LLM to use task tools                                            |
| `REMIND_TASK_CHAT_GAP` | 对话轮次提醒阈值——超过此轮数未使用任务工具则插入系统提醒 / Chat rounds before reminding LLM to use task tools                                                   |
| `MAIN_TOOL_RESULT_CHAR_LIMIT` | 主 Agent 工具结果最大字符数（超出截断）/ Main agent tool result char limit (truncated if exceeded)                                                   |
| `FLATTEN_BEFORE_SUMMARY` | 摘要前是否将多层消息扁平化为单层 / Whether to flatten multi-layer messages before summarization                                                      |
| `RANDOM_PROGRESS_TITLE` | 是否在 Spinner 中随机显示趣味标题（定义于 `constants.py`）/ Show random fun titles in spinner (defined in `constants.py`)                             |
| `RENDER_RESPONSE_AS_MD` | 是否以 Markdown 格式渲染 LLM 响应 / Render LLM responses as Markdown                                                                          |
| `DISPLAY_RESPONSE_REASON` | 是否显示 LLM 的推理过程内容（关闭则显示 "Thinking ..." 占位）/ Whether to display LLM reasoning content (shows "Thinking ..." placeholder when disabled) |
| `RESUME_DISPLAY_SYS_REMINDER` | 恢复会话时是否显示系统提醒内容 / Whether to display system reminder content when resuming session                                                   |
| `READ_FILE_MB_LIMIT` | 文件读取大小限制（MB），超限文件将被拒绝读取 / File read size limit (MB); larger files will be rejected                                                   |
| `READ_FILE_LLM_KB_LIMIT` | 文件读取 LLM 上下文限制（KB），超出部分将被截断 / File read LLM context limit (KB); exceeding part will be truncated                                     |
| `URL_TIMEOUT_S` | 网页获取超时（秒）/ Web fetch timeout (seconds)                                                                                               |
| `URL_CACHE_TIME_S` | URL 缓存时间（秒）/ URL cache time (seconds)                                                                                                |
| `WEB_SEARCH_BACKEND` | 网络搜索后端，可选：`Exa`、`Tavily`、`Linkup`、`DDGS` / Web search backend                                                                        |
| `WEB_SEARCH_API_KEY` | 网络搜索 API Key / Web search API key                                                                                                    |
| `WEB_SEARCH_TIMEOUT_S` | 网络搜索超时（秒）/ Web search timeout (seconds)                                                                                              |
| `RIPGREP_TIMEOUT_S` | 文件搜索超时（秒）/ File search (ripgrep) timeout (seconds)                                                                                   |
| `MCP_INIT_TIMEOUT_S` | MCP 初始化超时（秒）/ MCP init timeout (seconds)                                                                                             |
| `MCP_TIMEOUT_S` | MCP 调用超时（秒）/ MCP call timeout (seconds)                                                                                              |
| `SKILL_DESC_CHAR_LIMIT` | 技能描述最大字符数 / Skill description char limit                                                                                             |
| `WEB_FETCH_MODEL` | 网页内容总结使用的模型类型：`"main"`、`"medium"` 或 `"fast"` / Model type for web fetch summarization                                                |
| `WEB_FETCH_LLM_CHAR_LIMIT` | 网页获取内容传给 LLM 的最大字符数 / Web fetch content char limit for LLM                                                                           |
| `WEB_SEARCH_API_MODE` | 网络搜索 API 模式（如 `deep`）/ Web search API mode                                                                                           |
| `WEB_SEARCH_PROXY` | 网络搜索代理地址 / Web search proxy                                                                                                          |
| `WEB_SEARCH_INCLUDE_DOMAINS` | 网络搜索限定包含的域名 / Web search included domains                                                                                            |
| `WEB_SEARCH_EXCLUDE_DOMAINS` | 网络搜索排除的域名 / Web search excluded domains                                                                                              |
| `WEB_SEARCH_MAX_ENTRY` | 网络搜索最大返回条目数 / Web search max entries                                                                                                 |
| `WEB_SEARCH_RAW_CHAR_LIMIT` | 网络搜索原始结果字符限制 / Web search raw result char limit                                                                                      |
| `WEB_SEARCH_MODEL` | 网络搜索摘要使用的模型类型：`"main"`、`"medium"` 或 `"fast"` / Model type for web search summarization                                               |
| `WEB_SEARCH_LLM_CHAR_LIMIT` | 网络搜索结果传给 LLM 的最大字符数 / Web search result char limit for LLM                                                                           |
| `RESUME_DISPLAY_SKILLS` | 恢复会话时是否显示已加载的技能内容 / Whether to display loaded skills content when resuming session                                                   |
| `RESUME_DISPLAY_CRONS` | 恢复会话时是否显示定时任务内容 / Whether to display cron tasks content when resuming session                                                        |
| `RESUME_DISPLAY_WRITE_PREVIEW` | 恢复会话时是否预览 write_file 写入的文件内容 / Whether to preview file content for write_file tool calls                                             |
| `RESUME_DISPLAY_BASH_PREVIEW` | 恢复会话时是否预览 bash 执行的命令 / Whether to preview bash commands when resuming session                                                        |
| `RESUME_DISPLAY_BASH_RESULT` | 恢复会话时是否预览 bash 命令的输出结果 / Whether to preview bash command results when resuming session                                               |
| `RESUME_DISPLAY_GLOB_PREVIEW` | 恢复会话时是否预览 glob 匹配的文件列表 / Whether to preview glob file match results when resuming session                                               |
| `RESUME_DISPLAY_GLOB_RESULT` | 恢复会话时是否预览 glob 匹配的详细结果 / Whether to preview glob match detailed results when resuming session                                               |
| `RESUME_DISPLAY_GREP_PREVIEW` | 恢复会话时是否预览 grep 搜索的文件匹配 / Whether to preview grep file search matches when resuming session                                               |
| `RESUME_DISPLAY_GREP_RESULT` | 恢复会话时是否预览 grep 搜索的详细信息 / Whether to preview grep search detailed results when resuming session                                               |
| `RESUME_DISPLAY_SUBAGENT` | 恢复会话时是否显示子 Agent 运行记录 / Whether to display subagent run records when resuming session                                                |
| `SUBAGENT_MAX_STEPS` | 子 Agent 最大步骤数（LLM 请求次数），超出后自动终止 / Max steps for subagents                                                                            |
| `SUBAGENT_MODEL_TYPE` | 子 Agent 模型类型：`"main"`、`"medium"` 或 `"fast"` / Model type for subagents                                                               |
| `SUBAGENT_TIMEOUT_S` | 子 Agent 超时时间（秒），超时后自动终止 / Subagent timeout in seconds                                                                                |
| `SUBAGENT_API_RETRY_COUNT` | 子 Agent API 临时故障重试次数 / Subagent API retry count on transient failures                                                                |
| `SUBAGENT_TOOL_RESULT_CHAR_LIMIT` | 子 Agent 工具结果最大字符数（超出截断）/ Subagent tool result char limit (truncated if exceeded)                                                     |
| `SUBAGENT_EARLY_WARN_STEPS` | 子 Agent 提前提醒步数（剩余步数低于此值时发出警告，默认 2）/ Subagent early warning steps (warn when remaining steps fall below this, default 2)                    |
| `WECHAT_BOT_LOGIN_TIMEOUT_S` | WeChat Bot 登录超时时间（秒）/ WeChat Bot login timeout (seconds) |
| `WECHAT_BOT_STOP_TIMEOUT_S` | WeChat Bot 停止超时时间（秒）/ WeChat Bot stop timeout (seconds) |
| `WECHAT_BOT_HEAD_CDN_TIMEOUT_S` | WeChat Bot 头像 CDN 获取超时时间（秒）/ WeChat Bot head CDN fetch timeout (seconds) |
| `WECHAT_BOT_TEXT_REPLY_TIMEOUT_S` | WeChat Bot 文本回复超时时间（秒）/ WeChat Bot text reply timeout (seconds) |
| `WECHAT_BOT_MEDIA_REPLY_TIMEOUT_S` | WeChat Bot 媒体回复超时时间（秒）/ WeChat Bot media reply timeout (seconds) |
| `WECHAT_BOT_MUTE_NONFATAL_ERROR` | 是否禁止 WeChat Bot 的 Non-Fatal Error 打印 / Whether to mute WeChat Bot non-fatal error output |
| `WECHAT_BOT_REPLY_DURING_TOOL_CALL` | LLM 执行工具调用时是否仍允许 WeChat Bot 回复中间内容 / Whether WeChat Bot can reply with intermediate content during LLM tool calls |
| `WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB` | WeChat 媒体下载阈值（MB），超过此大小的媒体文件将被拒绝下载 / WeChat media download threshold (MB); larger files will be rejected |
| `WECHAT_MEDIA_UPLOAD_THRESHOLD_MB` | WeChat 媒体上传阈值（MB），超过此大小的媒体文件将被拒绝上传 / WeChat media upload threshold (MB); larger files will be rejected |
| `WECHAT_BOT_PERMISSION` | WeChat Bot 的独立权限配置（覆盖主 Agent 默认权限），键名为工具的内部 TOOL_NAME_ 标识符或 Bash 风险标签 / WeChat Bot standalone permission config (overrides default agent permissions); keys are internal TOOL_NAME_ identifiers or Bash risk labels |

> **路径类参数说明 | Path Parameters**
> - `SIMULATOR_PATH`：设置为空字符串 `""` 时可禁用全部仿真功能，Agent 的 `check_simulator` 工具会返回"不可用"。需指向 TECoSim.exe 所在目录（而非 exe 本身）
>   Set to `""` to disable all simulation features. Point to the directory containing TECoSim.exe (not the exe itself)
> - `BASH_PATH`：默认 `"bash"`（即从系统 PATH 中查找）。Windows 用户通常需要设置为 Git Bash 的完整路径（如 `"C:\\Program Files\\Git\\bin\\bash.exe"`）。Agent 通过 `bash -c "command"` 执行，并使用 `evaluate_bash_risk()` 做命令风险分级
>   Default is `"bash"` (lookup from system PATH). Windows users typically set the full path to Git Bash. The agent executes via `bash -c "command"` and classifies risk via `evaluate_bash_risk()`
> - `RIPGREP_PATH`：默认 `"rg"`。如果 ripgrep 不在 PATH 中，需设置完整路径。用于 `grep_file` 工具的全文搜索
>   Default is `"rg"`. Set full path if ripgrep is not in system PATH. Used by the `grep_file` tool

> **上下文与摘要 | Context & Summary**
> - `CONTEXT_THRESHOLD`（推荐 `0.8`）：与 `api_configs.json` 中的 `MAIN_MODEL_CONTEXT` 配合使用。当 `input_tokens >= CONTEXT × THRESHOLD` 时输出黄色告警。设为 `1.0` 可关闭告警
>   Used with `MAIN_MODEL_CONTEXT`. Warning triggers when `input_tokens >= CONTEXT × THRESHOLD`. Set to `1.0` to disable warnings
> - `LLM_SUMMARY_TRIGGER`：用户输入达到该次数后，自动调用 LLM 总结当前会话并更新标题。设为 `0` 可关闭自动摘要
>   After this many user prompts, the agent auto-summarizes the session and updates the title. Set to `0` to disable
> - `FLATTEN_BEFORE_SUMMARY`：摘要前是否将多轮工具调用的嵌套消息展开为扁平结构，提高摘要质量
>   Whether to flatten nested tool-call messages before summarization for better quality

> **文件读取限制 | File Read Limits**
> - `READ_FILE_MB_LIMIT`：**硬限制**。超过此大小的文件**拒绝读取**，返回 FAIL 状态。防止意外读取大文件导致 OOM
>   **Hard limit**. Files exceeding this size are **rejected** with FAIL status. Prevents accidental OOM from large files
> - `READ_FILE_LLM_KB_LIMIT`：**软限制**。读取的内容超过此大小时，工具会截断并返回 TRUNCATED 状态（非错误），但仍可读取到部分内容
>   **Soft limit**. When read content exceeds this size, the tool truncates and returns TRUNCATED status (not an error), with partial content still available
> - 两个限制同时生效，`MB_LIMIT` 先检查文件大小，`LLM_KB_LIMIT` 后检查读取内容大小
>   Both limits apply: `MB_LIMIT` checks total file size first, `LLM_KB_LIMIT` checks read content size second

> **模型兼容性 | Model Compatibility**
> - `MAIN_MODEL_DEEPSEEK_SUPPORT` / `MEDIUM_MODEL_DEEPSEEK_SUPPORT` / `FAST_MODEL_DEEPSEEK_SUPPORT`（`api_configs.json`）：分别控制主模型、中阶模型和快速模型的 DeepSeek 格式支持。启用后 Agent 会在对应模型的响应中处理 `thinking` 特殊字段，将其转换为 `reasoning` 格式展示。如果使用非 DeepSeek 模型，建议保持 `false`
>   Per-model DeepSeek format support in `api_configs.json`. When enabled, the agent handles the `thinking` field in responses, converting it to `reasoning` format. Set to `false` for non-DeepSeek models
> - `RENDER_RESPONSE_AS_MD`：控制 LLM 响应是否用 Rich 库的 Markdown 渲染。关闭后以纯文本显示
>   Controls whether LLM responses are rendered as Markdown via the Rich library. Disable for plain text display

> **WeChat Bot 集成 | WeChat Bot Integration**
> 
> 通过 CLI 参数 `-wc` / `--wechat` 启用。启动后 Agent 通过微信接收用户消息与指令，监听 TUI 变为强制停留模式（仅 Ctrl+C 可退出），所有权限被 `WECHAT_BOT_PERMISSION` 覆盖。首个发送消息的用户自动绑定为会话拥有者，其他用户的微信消息会被自动拒绝。
> Enable via CLI flag `-wc` / `--wechat`. When active, the agent receives user messages & commands via WeChat, the listen TUI becomes mandatory (only Ctrl+C exits), all permissions are overridden by `WECHAT_BOT_PERMISSION`, and the first user to send a message is auto-bound as the session owner — other users are auto-rejected.
> 
> `WECHAT_BOT_PERMISSION` 是一个嵌套 JSON 对象，键名为工具内部标识符（如 `TOOL_NAME_WRITE_FILE`）或 Bash 风险标签（如 `BASH_REMOVAL_LABEL`），值均为布尔类型。特殊键 `ALL_MCP_TOOLS`（布尔）控制所有 MCP 工具是否默认允许。
> `WECHAT_BOT_PERMISSION` is a nested JSON object whose keys are tool identifiers (e.g. `TOOL_NAME_WRITE_FILE`) or Bash risk labels (e.g. `BASH_REMOVAL_LABEL`), with boolean values. The special key `ALL_MCP_TOOLS` (boolean) controls whether all MCP tools are allowed by default.
> 
> WeChat 消息在终端和 LLM 上下文中通过 XML 标签包裹展示（`WECHAT_PROMPT_START_LABEL` / `WECHAT_PROMPT_END_LABEL`）。更多实现细节（锁定/拒绝回复文案列表、媒体下载流程等）参见 [constants_reference.md](./constants_reference.md)。
> WeChat messages are wrapped in XML tags in the terminal and LLM context (`WECHAT_PROMPT_START_LABEL` / `WECHAT_PROMPT_END_LABEL`). See [constants_reference.md](./constants_reference.md) for implementation details (lock/block reply lists, media download flow, etc.).

---

## 常量文件概览 | Constants File Overview

`src/constants.py` 集中管理所有全局常量与默认参数。**所有 Agent 工具名称均在此集中定义**，便于统一调整命名与重构。按功能划分为以下类别：
`src/constants.py` centralizes all global constants and default parameters. **All agent tool names are defined centrally here** for unified naming and refactoring. Organized into:

| 类别 Category | 说明 Description |
|---------------|------------------|
| 版本号 Version | Agent 当前版本号 / Current agent version |
| 基础路径 Base Paths | 日志、会话、配置、技能、MCP、cron、WeChat 凭证等路径 / Paths for logs, sessions, configs, skills, MCPs, crons, WeChat credentials |
| 文件命名 File Naming | 会话目录下的子文件命名 / File names under session directories |
| 状态标签 Status Labels | 工具/操作返回的状态标签（失败、成功、超时、禁用、拒绝等）及任务状态（pending/in_progress/completed/deleted）/ Status labels for tool returns (FAIL/SUCCESS/TIMEOUT/DENIED/etc.) and task statuses |
| 工具名称 Tool Names | 所有 Agent 工具的字符串名称（含 WeChat 工具 `wechat_send_media`），可统一修改 / All agent tool string names (incl. WeChat tool `wechat_send_media`), centrally managed |
| 工具参数 Tool Params | 各工具的默认参数与行为限制 / Default params and limits for tools |
| Bash 风险 Bash Risk | Bash 命令的风险分类标签（高风险/中风险/低风险/安全），Agent 据此控制权限 / Risk classification labels for bash commands (High/Med/Low/Safe), used for permission control |
| UI 配置 UI Configs | 颜色、图标、进度条、提示词列表等界面参数 / Colors, icons, progress bars, prompt lists |
| 任务看板 Task Board | Scoreboard 任务系统的图标、颜色、状态显示参数 / Task display params for Scoreboard |
| 监听 TUI Listen TUI | Agent 监听模式的渐变色彩与动画参数 / Listen TUI gradient color and animation params |
| 流式显示 Streaming | LLM 流式响应与 TUI 的显示参数 / Display params for streaming LLM responses |
| 编辑视图 Edit View | 文件编辑 TUI 的 diff 视图参数 / Diff view params for file edit TUI |
| Bash 视图 Bash View | Bash 命令输出的行号视图参数 / Line number view params for bash output |
| URL 缓存 URL Cache | URL 缓存显示参数 / URL cache display params |
| MCP 参数 MCP Params | MCP 工具描述显示限制 / MCP tool description limit |
| 子 Agent SubAgent | 子 Agent 状态、图标、色彩渐变、轮询间隔等参数 / Subagent status labels, icons, color gradients, poll intervals |
| WeChat Bot | WeChat 凭证路径、媒体缓存路径、消息历史路径、提示标签、默认超时、验证码/锁定/拒绝文案列表 / WeChat credential & media cache & msg history paths, prompt labels, default timeouts, verify/lock/block reply lists |



> 完整参数参考（工具名称列表、Bash 风险等级、UI 主题色、图标等）请参阅 | See [constants_reference.md](./constants_reference.md) for the full parameter reference.
