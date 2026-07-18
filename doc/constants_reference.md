# 常量参考 | Constants Reference

本文档提供了 `src/constants.py` 中所有常量的完整参考。
This document provides the full reference for all constants defined in `src/constants.py`.

> **⚠️ 警告**：`constants.py` 中的参数直接影响 Agent 的运行行为与安全策略。**除非你完全理解每个参数的作用，请勿随意修改**。错误修改可能导致 Agent 行为异常、安全策略绕过或工具功能异常。如需调整行为，建议优先通过 `agent_configs.json` 或 `api_configs.json` 配置。
> 
> **⚠️ WARNING**: Parameters in `constants.py` directly affect the agent's runtime behavior and security policies. **Do not modify them unless you fully understand each parameter's purpose**. Incorrect modifications may lead to agent malfunction, security bypass, or tool malfunctions. Prefer adjusting behavior via `agent_configs.json` or `api_configs.json` instead.

---

## 状态标签 | Status Labels

Agent 工具和内部操作通过标准化的状态标签返回结果，便于调用方统一处理。定义如下：
Agent tools and internal operations return standardized status labels for unified handling:

| 常量 Constant | 标签 Label | 含义 Meaning |
|----------|-----------|-------------|
| `FAIL_LABEL` | `FAIL` | 操作失败，附带错误信息 / Operation failed with error info |
| `FALLBACK_LABEL` | `FALLBACK` | 操作降级回退，如 query_task ID 无效时回退到列出所有任务 / Operation fell back to alternative behavior (e.g., query_task falls back to list all tasks when ID is invalid) |
| `SUCCESS_LABEL` | `SUCCESS` | 操作成功 / Operation succeeded |
| `DENIED_LABEL` | `DENIED` | 用户拒绝了权限请求 / User denied the permission request |
| `DISABLED_LABEL` | `DISABLED` | 工具被禁用（如 `--notools` 模式）/ Tool is disabled (e.g. `--notools` mode) |
| `TRUNCATED_LABEL` | `TRUNCATED` | 操作成功但结果被截断（如文件读取超过 `READ_FILE_LLM_KB_LIMIT`）/ Succeeded but result was truncated |
| `TIMEOUT_LABEL` | `TIMEOUT` | 操作超时 / Operation timed out |
| `CANCELLED_LABEL` | `CANCELLED` | 操作被用户取消（如仿真运行）/ Operation cancelled by user |
| `DONE_LABEL` | `DONE` | 仿真运行正常完成 / Simulation run completed normally |
| `UNKNOWN_LABEL` | `UNKNOWN` | 未知状态标记 / Unknown status marker |
| `TASK_PENDING_LABEL` | `pending` | Scoreboard 任务待处理 / Scoreboard task is pending |
| `TASK_IN_PROGRESS_LABEL` | `in_progress` | Scoreboard 任务进行中 / Scoreboard task is in progress |
| `TASK_COMPLETED_LABEL` | `completed` | Scoreboard 任务已完成 / Scoreboard task is completed |
| `TASK_DELETED_LABEL` | `deleted` | Scoreboard 任务已删除 / Scoreboard task is deleted |
| `RUN_PENDING_LABEL` | `PENDING` | 仿真运行等待中 / Simulation run is pending |
| `RUN_CANCELLED_LABEL` | `CANCELLED` | 仿真运行被取消 / Simulation run was cancelled |
| `RUN_TIMEOUT_LABEL` | `TIMEOUT` | 仿真运行超时 / Simulation run timed out |
| `RUN_RUNTIME_ERROR_LABEL` | `RUNTIME_ERROR` | 仿真运行发生运行时错误 / Simulation run encountered a runtime error |
| `RUN_DONE_LABEL` | `DONE` | 仿真运行成功完成 / Simulation run completed successfully |

> **状态流转说明 | Status Flow**
> - 工具操作状态 / Tool operation status: `FAIL` / `FALLBACK` / `SUCCESS` / `DENIED` / `DISABLED` / `TRUNCATED` / `TIMEOUT` are mutually exclusive; one per invocation
> - Scoreboard 任务状态 / Scoreboard task status: `pending → in_progress → completed` (irreversible); any status can be marked as `deleted`
> - 仿真运行状态 / Simulation run status: `PENDING → DONE` / `CANCELLED` / `TIMEOUT` / `RUNTIME_ERROR`

---

## 消息标签 | Message Labels

Agent 在向 LLM 消息中插入特殊内容时使用标准化的标签进行标记，便于在恢复会话时识别和选择性显示。定义如下：
The agent wraps special content inserted into LLM messages with standardized label constants for identification and selective display when resuming sessions:

| 常量 Constant | 标签 Label | 用途 Purpose |
|----------|-----------|-------------|
| `SYS_REMINDER_START_LABEL` | `<system_reminder>` | 系统提醒内容起始标记（任务管理提醒等）/ Marks the start of system reminder content (task management reminders, etc.) |
| `SYS_REMINDER_END_LABEL` | `</system_reminder>` | 系统提醒内容结束标记 / Marks the end of system reminder content |
| `SKILL_START_LABEL` | `<skill_content>` | 技能内容起始标记 / Marks the start of skill content |
| `SKILL_END_LABEL` | `</skill_content>` | 技能内容结束标记 / Marks the end of skill content |
| `CRON_START_LABEL` | `<cron_tasks>` | 定时任务内容起始标记 / Marks the start of cron task content |
| `CRON_END_LABEL` | `</cron_tasks>` | 定时任务内容结束标记 / Marks the end of cron task content |
| `WECHAT_PROMPT_START_LABEL` | `<wechat_bot>` | 微信消息内容起始标记 / Marks the start of WeChat message content |
| `WECHAT_PROMPT_END_LABEL` | `</wechat_bot>` | 微信消息内容结束标记 / Marks the end of WeChat message content |
| `SUBAGENT_START_LABEL` | `<subagent>` | 子 Agent 记录内容起始标记 / Marks the start of subagent record content |
| `SUBAGENT_END_LABEL` | `</subagent>` | 子 Agent 记录内容结束标记 / Marks the end of subagent record content |

> **显示控制**： 恢复会话时，可通过 `agent_configs.json` 中的 `RESUME_DISPLAY_SYS_REMINDER`、`RESUME_DISPLAY_SKILLS`、`RESUME_DISPLAY_CRONS`、`RESUME_DISPLAY_SUBAGENT` 分别控制是否显示这些标签包裹的内容；通过 `RESUME_DISPLAY_WRITE_PREVIEW`、`RESUME_DISPLAY_BASH_PREVIEW`、`RESUME_DISPLAY_BASH_RESULT` 控制是否预览 write/bash 工具调用的内容/命令/输出；
>
> **Display Control**: When resuming a session, you can control whether these labeled contents are displayed via `RESUME_DISPLAY_SYS_REMINDER`, `RESUME_DISPLAY_SKILLS`, `RESUME_DISPLAY_CRONS`, and `RESUME_DISPLAY_SUBAGENT` in `agent_configs.json`; use `RESUME_DISPLAY_WRITE_PREVIEW`, `RESUME_DISPLAY_BASH_PREVIEW`, `RESUME_DISPLAY_BASH_RESULT` to control write/bash tool call previews.

---

## 工具名称列表 | Tool Names List

`src/constants.py` 中集中定义了所有 Agent 工具的字符串名称（`TOOL_NAME_*` 常量）。如需修改某个工具的名称（例如避免与 MCP 工具重名），只需在此修改一处即可全局生效：
All agent tool names are defined centrally as `TOOL_NAME_*` constants in `src/constants.py`. To rename a tool (e.g., to avoid conflicts with MCP tools), change it here — it takes effect everywhere:

| 常量 Constant | 默认名称 Default Name | 用途 Purpose                                                                                  |
|----------|--------------|---------------------------------------------------------------------------------------------|
| `TOOL_NAME_VERSION` | `agent_version` | 获取 Agent 版本 / Get agent version                                                             |
| `TOOL_NAME_ASK_QUESTION` | `ask_user_question` | 向用户提问 / Ask user structured questions                                                       |
| `TOOL_NAME_CREATE_CRON` | `create_cron` | 创建定时任务 / Create a cron task                                                                 |
| `TOOL_NAME_QUERY_CRON` | `query_cron` | 查询定时任务列表 / Query cron task list                                                             |
| `TOOL_NAME_REMOVE_CRON` | `remove_cron` | 删除定时任务 / Remove a cron task                                                                 |
| `TOOL_NAME_CREATE_TASK` | `create_task` | 创建任务 / Create a task                                                                        |
| `TOOL_NAME_UPDATE_TASK` | `update_task` | 更新任务 / Update a task                                                                        |
| `TOOL_NAME_QUERY_TASK` | `query_task` | 查询任务（获取详情或列表）/ Query task (get detail or list)                                              |
| `TOOL_NAME_BASH` | `bash` | 执行 Shell 命令 / Execute shell commands                                                        |
| `TOOL_NAME_GLOB_FILE` | `glob_file` | 文件通配匹配 / Glob file patterns                                                                 |
| `TOOL_NAME_GREP_FILE` | `grep_file` | 文件内容搜索 / Search file contents                                                               |
| `TOOL_NAME_READ_FILE` | `read_file` | 读取文件 / Read file                                                                            |
| `TOOL_NAME_WRITE_FILE` | `write_file` | 写入文件 / Write file                                                                           |
| `TOOL_NAME_EDIT_FILE` | `edit_file` | 编辑文件 / Edit file                                                                            |
| `TOOL_NAME_SKILL` | `skill` | 调用技能 / Invoke a skill                                                                       |
| `TOOL_NAME_WEB_FETCH` | `web_fetch` | 获取网页内容 / Fetch web content                                                                  |
| `TOOL_NAME_WEB_SEARCH` | `web_search` | 网络搜索 / Search the web                                                                       |
| `TOOL_NAME_WECHAT_STATUS` | `wechat_status` | 获取微信机器人当前连接状态（登录、绑定用户、消息队列、CDN 下载统计）/ Get WeChat Bot connection status (login, bound user, message queue, CDN stats) |
| `TOOL_NAME_WECHAT_SEND_FILE` | `wechat_send_file` | 向当前连接的微信用户发送文件（图片/视频/文件）/ Send image/video/file to the current connected WeChat user |
| `TOOL_NAME_CALL_MCP` | `call_mcp` | 调用 MCP 工具 / Call an MCP tool                                                                |
| `TOOL_NAME_CHECK_SIMULATOR` | `check_simulator` | 检查仿真器可用性 / Check simulator availability                                                     |
| `TOOL_NAME_INIT_DESIGN` | `init_design` | 创建设计 / Initialize a design                                                                  |
| `TOOL_NAME_QUERY_DESIGN` | `query_design` | 查询设计列表 / Query design list                                                                  |
| `TOOL_NAME_LAUNCH_SIM` | `launch_sim` | 启动仿真 / Launch a simulation                                                                  |
| `TOOL_NAME_QUERY_RUN` | `query_run` | 查询运行记录 / Query simulation run records                                                       |
| `TOOL_NAME_READ_LOG` | `read_log` | 读取仿真日志 / Read simulation logs                                                               |

---

## Bash 风险等级 | Bash Risk Levels

Agent 在执行 Bash 命令前会调用 `evaluate_bash_risk()` 进行风险检测，根据命令类型分配风险等级，并据此决定是否需要用户权限确认。等级数字越小风险越高：
The agent calls `evaluate_bash_risk()` before executing any bash command, classifying risk by command type to determine whether user permission is required. Lower number = higher risk:

| 常量 Constant | 风险等级 Risk | 说明 Description |
|----------|------------|-------------|
| `BASH_HIGH_RISK_LABEL` | 高 High (0) | sudo、dd、iptables、防火墙等 / sudo, dd, iptables, firewall, etc. |
| `BASH_PACKAGE_LABEL` | 高 High (0) | 包管理器修改系统 / Package manager modifies system |
| `BASH_NETWORK_LABEL` | 高 High (0) | 网络命令（curl、wget、ssh 等）/ Network commands (curl, wget, ssh, etc.) |
| `BASH_REMOVAL_RF_LABEL` | 中 Med (1) | 递归强制删除 `rm -rf` / Recursive forced removal |
| `BASH_REMOVAL_R_LABEL` | 中 Med (2) | 递归删除 `rm -r` / Recursive removal |
| `BASH_REMOVAL_F_LABEL` | 中 Med (2) | 强制删除 `rm -f` / Forced removal |
| `BASH_REMOVAL_LABEL` | 中 Med (3) | 普通删除 `rm` / Normal removal |
| `BASH_INLINE_SCRIPT_LABEL` | 中 Med (3) | 内联脚本执行（python -c、node -e 等）/ Inline script execution |
| `BASH_CHMOD_LABEL` | 低 Low (4) | 修改文件权限 / Change file permissions |
| `BASH_CHOWN_LABEL` | 低 Low (4) | 修改文件所有者 / Change file owner |
| `BASH_FILE_LABEL` | 低 Low (4) | 文件操作（cp、mv、mkdir 等）/ File operations |
| `BASH_REPOSITORY_MODIFY_LABEL` | 中 Med (5) | Git 修改仓库历史 / Git modifies repo history |
| `BASH_STAGE_CHANGE_LABEL` | 中 Med (6) | Git 暂存更改 / Git stages changes |
| `BASH_UNKNOWN_LABEL` | 未知 Unknown (7) | 未分类命令 / Unclassified command |
| `BASH_SAFE_LABEL` | 安全 Safe (8) | 安全命令（ls、cat、grep 等）/ Safe commands |
| `BASH_EMPTY_LABEL` | 安全 Safe (9) | 空命令 / Empty command |

---

## UI 配置 | UI Configuration

### 主题色 | Theme Colors

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `MAJOR_COLOR1` | `#FF9FF3`（亮粉 bright pink） | 强调色、内容图标、进度条终点 / Accent, content icon, progress bar end |
| `MAJOR_COLOR2` | `#54A0FF`（蓝 blue） | 主色调、命令名称、进度条起点 / Primary color, command names, progress bar start |
| `REASONING_COLOR` | `MAJOR_COLOR2`（#54A0FF） | 推理文本颜色 / Reasoning text color |
| `EDIT_FUZZY_WARN_COLOR` | `MAJOR_COLOR1`（#FF9FF3） | 模糊匹配警告颜色 / Fuzzy match warning color |
| `EDIT_SUBTLE_COLOR` | `bright_black`（灰 grey） | 精确匹配族回退模式标签 / Subtle label for exact-family fallback modes |

### 图标与符号 | Icons & Symbols

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `AGENT_CONSOLE_ICON` | `✦` | 控制台输入提示符 / Console input prompt marker |
| `REASON_ICON` | `⟡` | 推理内容标记 / Reasoning content marker |
| `CONTENT_ICON` | `●` | 普通内容标记 / Regular content marker |
| `PROGRESS_BAR_FULL` | `█` | 进度条填充字符 / Progress bar filled block |
| `PROGRESS_BAR_EMPTY` | `░` | 进度条空白字符 / Progress bar empty block |
| `OPTIONS_TO_SELECT_PREFIX` | `❯ ` | TUI 选项中当前聚焦项的前缀 / Focused option prefix in TUI |
| `OPTIONS_UN_SELECT_PREFIX` | `  ` | TUI 选项中未聚焦项的前缀 / Unfocused option prefix in TUI |
| `OPTIONS_SELECTED_PREFIX` | ` ✓` | TUI 选项中已选择项的标记 / Selected option suffix in TUI |
| `OPTIONS_UNSELECTED_PREFIX` | `` | TUI 选项中未选择项的前缀 / Unselected option prefix in TUI |
| `SELECTED_QUESTION_OPTION_COLOR` | `#A6CEFF` | TUI 中已选择的选项颜色 / Color for selected option |
| `TUI_USER_COMMENT_COLOR` | `#A6CEEF` | 用户注释文本颜色 / Color for user comment text |
| `SYS_REMINDER_ICON` | `⚑` | 系统提醒标记图标 / System reminder icon |
| `SUBAGENT_ICON` | `▲` | 子 Agent 标记图标 / Subagent marker icon |
| `SKILL_ICON` | `❖` | 技能标记图标 / Skill marker icon |
| `CRON_ICON` | `⬟` | 定时任务标记图标 / Cron marker icon |
| `WECHAT_PROMPT_ICON` | `▶` | 微信消息标记图标 / WeChat message marker icon |

### 样式与格式 | Styles & Formatting

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `REASON_ICON_SYLTE` | `bold #54A0FF` | 推理图标样式 / Reasoning icon style |
| `CONTENT_ICON_SYLTE` | `bold #FF9FF3` | 内容图标样式 / Content icon style |
| `REASON_STYLE` | `italic #54A0FF` | 推理文本样式 / Reasoning text style |
| `CONTENT_STYLE` | `none` | 内容文本样式 / Content text style |
| `MESSAGE_PRINT_MARGIN` | `4` | 消息打印左侧缩进宽度 / Left margin width for message printing |
| `USER_PROMPT_FIXED_PREFIX` | `(Shift+Tab: New line, Enter: Submit)` | 用户输入提示固定文字 / Fixed prompt prefix for user input |

### Markdown 渲染 | Markdown Rendering

通过 `get_console()` 创建带 `Theme` 的 `Console`，统一控制 Agent 响应中 Markdown 各元素的终端样式：
The `get_console()` function creates a `Console` with a `Theme` for uniform markdown element styling:

| 常量 Constant | 默认值 Default | 控制的 Rich 样式名 | 用途 Purpose |
|----------|---------|------|---------|
| `MARKDOWN_TABLE_COLOR` | `MAJOR_COLOR2`(#54A0FF) | `Table.border_style` | 表格边框线颜色 / Table border line color |
| `MARKDOWN_TABLE_HEADER_STYLE` | `bold #54A0FF` | `markdown.table.header` | 表头文字样式 / Table header text style |
| `MARKDOWN_H1_STYLE` | `bold underline #FF9FF3` | `markdown.h1` | H1 标题样式 / H1 heading style |
| `MARKDOWN_H2_STYLE` | `bold #FF9FF3` | `markdown.h2` | H2 标题样式 / H2 heading style |
| `MARKDOWN_H3_STYLE` | `#FF9FF3` | `markdown.h3` | H3 标题样式 / H3 heading style |
| `MARKDOWN_H4_STYLE` | `italic #FFBCF7` | `markdown.h4` | H4 标题样式 / H4 heading style |
| `MARKDOWN_H5_STYLE` | `italic #FFCAF8` | `markdown.h5` | H5 标题样式 / H5 heading style |
| `MARKDOWN_H6_STYLE` | `italic #FFD9FA` | `markdown.h6` | H6 标题样式 / H6 heading style |
| `MARKDOWN_INLINE_CODE_COLOR` | `#61D6D6` | `markdown.code` | 行内代码颜色 / Inline code text color |
| `MARKDOWN_LIST_BULLET_COLOR` | `#FF9FF3` | `markdown.item.bullet` | 无序列表符号颜色 / Unordered list bullet color |
| `MARKDOWN_LIST_NUMBER_COLOR` | `#FF9FF3` | `markdown.item.number` | 有序列表数字颜色 / Ordered list number color |
| `MARKDOWN_BLOCKQUOTE_STYLE` | `italic #696969` | `markdown.block_quote` | 引用块文字与竖线颜色 / Blockquote text & bar color |
| `MARKDOWN_LINK_COLOR` | `#F5A742` | `markdown.link_url` | 链接文字颜色 / Link text color |
| `MARKDOWN_HR_COLOR` | `#696969` | `markdown.hr` | 分割线颜色 / Horizontal rule line color |
| `MARKDOWN_IMAGE_STYLE` | `#F5A742` | `markdown.image` | 图片占位符文字颜色 / Image placeholder text color |

> **HTML 标签转义**：Rich 的 Markdown 解析器将 `<...>` 视为内联 HTML 并默认移除，导致 LLM 回复中的尖括号内容（如 `<html>`、`<head>`、`<!DOCTYPE>`）被静默丢弃。`_NoLeadingNewlinesMD` 基础类通过正则 `re.split` 分割代码块与正文，仅在代码块**外部**将 `<` / `>` 替换为 `&lt;` / `&gt;` 实体（Rich 会在渲染时解析回原字符），代码块内部（\`\`\`）保持原始符号不变。
>
> **HTML Tag Escaping**: Rich's Markdown parser treats `<...>` as inline HTML and strips it by default, causing angle-bracket content (e.g. `<html>`, `<head>`, `<!DOCTYPE>`) in LLM replies to be silently removed. The `_NoLeadingNewlinesMD` base class uses `re.split` to separate code blocks from body text and escapes `<` / `>` as `&lt;` / `&gt;` **only outside** fenced code blocks — Rich resolves these entities back to the original characters at render time.

> **控制字符与零宽字符展开**：`\t`、`\r`、`\b` 等终端控制字符及 `\u0301`（组合重音）、`\u200b`（零宽空格）等零宽字符在宽度测量中被误计为 1 列，导致背景填充错位。修复方案：`_char_display_width()` 正确识别 Unicode 类别（Mn/Mc/Me/Cf/Cc → 0），`_sanitize_control()` 将控制字符替换为等宽可见 Unicode Control Pictures（`\r`→`␍`，`\b`→`␈`，`\0`→`␀`），`.expandtabs(EDIT_VIEW_TAB_WIDTH)` 将 tab 展开为定宽空格。全部在 `fill_str_line()`、`_highlight_and_wrap()`、`_highlight_and_wrap_edit()` 中统一处理。
>
> **Control & Zero-Width Character Expansion**: Terminal control characters (`\t`, `\r`, `\b`) and zero-width characters (`\u0301` combining accent, `\u200b` ZWSP) were incorrectly measured as 1 column, causing background fill misalignment. Fix: `_char_display_width()` correctly handles Unicode categories (Mn/Mc/Me/Cf/Cc → 0), `_sanitize_control()` replaces control chars with visible Unicode Control Pictures (`\r`→`␍`, `\b`→`␈`, `\0`→`␀`), and `.expandtabs(EDIT_VIEW_TAB_WIDTH)` expands tabs to spaces. Applied uniformly in `fill_str_line()`, `_highlight_and_wrap()`, `_highlight_and_wrap_edit()`.

### 任务看板 | Task Board (Scoreboard)

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `TASK_DISPLAYS_BEFORE_ARCHIVED` | `6` | 已解决任务归档前的显示次数 / Displays before archiving resolved tasks |
| `MUTE_TASK_OP_INFO` | `true` | 是否在控制台静默任务操作日志 / Mute task operation logs in console |
| `TASK_EMPTY_TITLE` | `` | 空任务的占位标题 / Placeholder title for empty task |
| `TASK_VIEW_LEFT_MARGIN` | `6` | 任务列表状态图标左侧缩进 / Left margin for task status icons |
| `TASK_VIEW_RIGHT_MARGIN` | `1` | 任务列表状态图标右侧缩进 / Right margin for task status icons |
| `TASK_COLOR_GRADIENT` | `128` | 任务动画渐变阶数 / Gradient color steps for task animation |
| `TASK_COLOR_PERIOD` | `1.75` | 任务动画周期（秒）/ Task animation period (seconds) |
| `TASK_PENDING_WITHOUT_OWNER_ICON` | `○` | 无归属待处理任务图标 / Icon for pending task without owner |
| `TASK_PENDING_WITHOUT_OWNER_ICON_STYLE` | `bright_black` | 无归属待处理任务图标样式 / Style for pending task without owner icon |
| `TASK_PENDING_WITHOUT_OWNER_STYLE` | `bright_black` | 无归属待处理任务文本样式 / Style for pending task without owner text |
| `TASK_PENDING_WITH_OWNER_ICON` | `●` | 有归属待处理/进行中任务图标 / Icon for pending/in-progress task with owner |
| `TASK_COMPLETED_ICON` | `✓` | 已完成任务图标 / Icon for completed task |
| `TASK_DELETED_ICON` | `✗` | 已删除任务图标 / Icon for deleted task |
| `TASK_PENDING_COLOR_START` | `#202020` | 待处理任务渐变起始色 / Gradient start for pending tasks |
| `TASK_PENDING_COLOR_END` | `#808080` | 待处理任务渐变终止色 / Gradient end for pending tasks |
| `TASK_IN_PROGRESS_COLOR_START` | `#FF9FF3`（亮粉） | 进行中任务渐变起始色 / Gradient start for in-progress tasks |
| `TASK_IN_PROGRESS_COLOR_END` | `#54A0FF`（蓝） | 进行中任务渐变终止色 / Gradient end for in-progress tasks |
| `TASK_COMPLETED_COLOR` | `#8CDCA0`（绿） | 已完成任务颜色 / Color for completed tasks |
| `TASK_DELETED_COLOR` | `#767676`（灰） | 已删除任务颜色 / Color for deleted tasks |

### 监听 TUI | Listen TUI

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `LISTEN_TUI_COLOR_START` | `#FF9FF3`（亮粉） | 监听 TUI 标题渐变起始色 / Listen TUI gradient start |
| `LISTEN_TUI_COLOR_END` | `#54A0FF`（蓝） | 监听 TUI 标题渐变终止色 / Listen TUI gradient end |
| `LISTEN_TUI_COLOR_GRADIENT` | `128` | 监听 TUI 渐变色阶数 / Listen TUI gradient steps |
| `LISTEN_TUI_COLOR_PERIOD` | `1.75` | 监听 TUI 动画周期（秒）/ Listen TUI animation period (seconds) |
| `CRON_LISTEN_COLOR_START` | `#FF9FF3`（亮粉） | Cron 监听渐变起始色 / Cron listen gradient start |
| `CRON_LISTEN_COLOR_END` | `#54A0FF`（蓝） | Cron 监听渐变终止色 / Cron listen gradient end |
| `CRON_LISTEN_COLOR_GRADIENT` | `128` | Cron 监听渐变色阶数 / Cron listen gradient steps |
| `CRON_LISTEN_COLOR_PERIOD` | `1.75` | Cron 监听动画周期（秒）/ Cron listen animation period (seconds) |
| `KEY_LISTEN_SLEEP_TIME_MS` | `30` | 按键监听轮询间隔（毫秒）/ Key listen polling interval (ms) |
| `CRON_PROMPT_DISPLAY_CHAR_MAX` | `200` | Cron 任务提示显示最大字符数 / Max chars for cron task prompt display |

### 会话标题 | Session Titles

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `DEFAULT_SESSION_TITLE` | `(Empty session)` | 空会话的默认标题 / Default title for empty session |
| `UNKNOWN_SESSION_TITLE` | `(Unknown session)` | 无法识别会话的标题 / Title for unrecognizable session |
| `ERROR_SESSION_TITLE` | `(Summarize fail, try manually)` | 摘要失败时的回退标题 / Fallback title when summarization fails |

### 进度与 Spinner | Progress & Spinners

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `LLM_REQUEST_DONE_TITLE` | `LLM response latency` | LLM 请求完成提示 / LLM request done prompt |
| `LLM_REQUEST_INTRP_TITLE` | `LLM request interrupted` | LLM 请求中断提示 / LLM request interrupted prompt |
| `LLM_REQUEST_FAIL_TITLE` | `LLM request failed` | LLM 请求失败提示 / LLM request failed prompt |
| `LLM_REQUEST_SPINNER` | `dots2` | LLM 请求时的 spinner 样式 / Spinner style for LLM requests |
| `TOOLS_EXECUTION_DONE_TITLE` | `Tools execution done` | 工具执行完成提示 / Tools execution done prompt |
| `TOOLS_EXECUTION_INTRP_TITLE` | `Tools execution interrupted` | 工具执行中断提示 / Tools execution interrupted prompt |
| `TOOLS_EXECUTION_FAIL_TITLE` | `Tools execution failed` | 工具执行失败提示 / Tools execution failed prompt |
| `TOOLS_EXECUTION_SPINNER` | `bouncingBall` | 工具执行时的 spinner 样式 / Spinner style for tool execution |
| `SPINNER_LIVE_CHECK_GAP_MS` | `200` | Spinner 子线程轮询间隔（毫秒）/ Polling gap for spinner thread (ms) |
| `SPINNER_TERMINATE_WAIT_S` | `10` | 中断后等待子线程退出的最长时间（秒）/ Max wait for sub-thread exit after interrupt (s) |
| `PROGRESS_DISPLAY_REFRESH_RATE` | `30` | 进度条 TUI 刷新率（次/秒）/ Progress TUI refresh rate (fps) |

> **随机标题机制 | Random Title Mechanism**
> 
> 当 `agent_configs.json` 中的 `RANDOM_PROGRESS_TITLE` 设为 `true` 时，Agent 会在三个场景中随机循环显示趣味标题（定义于 `constants.py`）：
> When `RANDOM_PROGRESS_TITLE` is `true` in `agent_configs.json`, the agent cycles through random fun titles in three scenarios:
> 
> **LLM 请求时**（`LLM_REQUEST_TITLE_LIST`，7+ 条）— 如 `"Brain (but not mine) using ..."`、`"Staring into the abyss. The abyss is typing ..."`
> **During LLM requests** — e.g., `"Brain (but not mine) using ..."`
>
> **工具执行时**（`TOOLS_EXECUTION_TITLE_LIST`，23+ 条）— 如 `"Reaching into the toolbox ..."`、`"Finding the right screwdriver ..."`
> **During tool execution** — e.g., `"Reaching into the toolbox ..."`
> 
> **用户输入前**（`USER_PROMPT_PREFIX_LIST`，7+ 条）— 如 `"Type, and behold the breath of silica"`、`"Whisper your command into the chips"`
> **Before user input** — e.g., `"Type, and behold the breath of silica"`
> 
> 以上列表均可在 `constants.py` 中自由定制。设为 `false` 则使用固定的默认标题（见上表各 `*_TITLE` 常量）。
> All lists can be customized in `constants.py`. When disabled, fixed default titles are used (see `*_TITLE` constants above).

### 流式显示 | Streaming Display

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `STREAM_DISPLAY_REFRESH_RATE` | `20` | 流式响应 TUI 刷新率（次/秒）/ Stream response TUI refresh rate (fps) |
| `STREAM_DISPLAY_MAX_REASON_LINE` | `10` | 推理内容显示截断行数 / Max reasoning lines before truncation |
| `STREAM_DISPLAY_MAX_CONTENT_LINE` | `20` | 内容显示截断行数 / Max content lines before truncation |
| `MESSAGE_COLOR_GRADIENT` | `128` | 消息动态颜色渐变的阶数 / Gradient color steps for message color animation |
| `MESSAGE_COLOR_PERIOD` | `1.75` | 消息动态颜色变化周期（秒），与 `LISTEN_TUI_COLOR_PERIOD` 联动 / Message color animation period (seconds), synced with `LISTEN_TUI_COLOR_PERIOD` |

### 编辑视图 | Edit View (File Diff)

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `EDIT_VIEW_RMV_BG` | `#37222C`（暗红 dark red） | 删除行内容区域背景色 / Removed line content background |
| `EDIT_VIEW_ADD_BG` | `#20303B`（暗青 dark cyan） | 新增行内容区域背景色 / Added line content background |
| `EDIT_VIEW_NORMAL_BG` | `#141414`（深灰 dark gray） | 未修改行背景色 / Normal/context line background |
| `EDIT_VIEW_RMV_LINE_BG` | `#2D1F26`（暗红 dark red） | 删除行行号栏背景色 / Removed line number gutter background |
| `EDIT_VIEW_ADD_LINE_BG` | `#1B2B34`（暗青 dark cyan） | 新增行行号栏背景色 / Added line number gutter background |
| `EDIT_VIEW_RMV_SYMBOL_COLOR` | `#E26A75`（粉红 pink） | 删除行 `-` 符号颜色 / Remove `-` symbol color |
| `EDIT_VIEW_ADD_SYMBOL_COLOR` | `#B8DB87`（绿 green） | 新增行 `+` 符号颜色 / Add `+` symbol color |
| `EDIT_SYNTAX_THEME` | `one-dark` | 编辑预览语法高亮主题 / Syntax highlighting theme for edit preview |
| `EDIT_VIEW_LINE_MARGIN_SINGLE` | `3` | 单次编辑预览上下文行数 / Context lines for single edit preview |
| `EDIT_VIEW_LINE_MARGIN_MULTI` | `2` | 多次编辑预览上下文行数 / Context lines for multi edit preview |
| `EDIT_VIEW_LEFT_SPACE_MARGIN` | `5` | 行号左侧空格数 / Left space margin before line numbers |
| `EDIT_VIEW_LINE_SPACE_MARGIN` | `1` | 行号与内容间空格数 / Space margin between line number and content |
| `EDIT_VIEW_TAB_WIDTH` | `4` | Tab 字符展开宽度（空格数），确保含 tab 的代码/输出行背景填充对齐 / Tab expansion width in spaces, ensures background fill alignment for tab-containing lines |
| `EDIT_FUZZY_WARN_COLOR` | `MAJOR_COLOR1`（#FF9FF3） | 模糊匹配警告颜色（TUI 中非 exact-family 回退模式标签）/ Fuzzy match warning color (non-exact-family fallback mode label in TUI) |
| `EDIT_SUBTLE_COLOR` | `bright_black`（灰 grey） | exact-family 回退模式标签颜色（quote_norm / unicode_escape）/ Subtle label color for exact-family fallback modes (quote_norm / unicode_escape) |
| `MATCH_MODE_EXACT` | `exact` | 完全匹配 / Exact string match |
| `MATCH_MODE_QUOTE_NORM` | `quote_norm` | 引号标准化匹配（弯曲引号 → 直引号，含破折号/NBSP/全角空格）/ Quote + punctuation normalized match (curly quotes/dashes/NBSP/fullwidth-space → ASCII) |
| `MATCH_MODE_UNICODE_ESCAPE` | `unicode_escape` | Unicode 转义解码匹配（`\\uXXXX` → 实际字符）/ Unicode escape decoded match (`\\uXXXX` → actual character) |
| `MATCH_MODE_LINE_TRIMMED` | `line_trimmed` | 行尾空白裁剪匹配 / Line trailing whitespace trimmed match |
| `MATCH_MODE_FLEX_INDENT` | `flex_indent` | 弹性缩进匹配（忽略前导空格差异）/ Flexible indentation match (ignore leading whitespace differences) |
| `MATCH_MODE_ESCAPE_LITERAL` | `escape_literal` | 转义字面量校正匹配（`\\t`/`\\n` → 实际字符）/ Escape literal corrected match (`\\t`/`\\n` → actual tab/newline) |
| `MATCH_MODE_TRIMMED_BOUNDARY` | `trimmed_boundary` | 边界裁剪匹配（首尾空白去除）/ Boundary trimmed match (strip leading/trailing whitespace) |
| `MATCH_MODE_DESC` | _(字典 dict)_ | 匹配模式枚举到 UI 显示的映射 / Map from match mode enum to human-readable description |
| `MATCH_MODE_EXACT_FAMILY` | `{exact, quote_norm, unicode_escape}` | 精确匹配族（TUI 中灰色标签，非橙色警告）/ Exact match family (grey label in TUI, not orange warning) |

### Bash 视图 | Bash View (Command Preview & Result Output)

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `BASH_VIEW_LEFT_SPACE_MARGIN` | `5` | 行号左侧空格数 / Left space margin before line numbers |
| `BASH_VIEW_GUTTER_BG` | `#222222`（深灰 dark grey） | Bash 命令预览行号栏背景色 / Bash command gutter background |
| `BASH_VIEW_PADDING_LINES` | `1` | Bash 命令预览首尾空白过渡行数 / Blank padding lines above/below command block |
| `BASH_RESULT_GUTTER_BG` | `#222222`（深灰 dark grey） | Bash 结果输出行号栏背景色 / Bash result gutter background |
| `BASH_RESULT_CONTENT_BG` | `#141414`（深黑 dark black） | Bash 结果输出内容区背景色 / Bash result content background |
| `BASH_RESULT_MAX_LINES` | `60` | Bash 结果预览最大显示行数（超出截断）/ Max lines to display before truncation |
| `BASH_RESULT_MAX_CHARS` | `3000` | Bash 结果预览最大显示字符数（超出截断）/ Max chars to display before truncation |
| `BASH_RESULT_PADDING_LINES` | `1` | Bash 结果预览首尾空白过渡行数 / Blank padding lines above/below result block |

### Write 文件预览 | Write File Preview

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `WRITE_VIEW_GUTTER_BG` | `#222222`（深灰 dark grey） | Write 预览行号栏背景色 / Write preview gutter background |
| `WRITE_VIEW_CONTENT_BG` | `#141414`（线黑 line black） | Write 预览内容区背景色 / Write preview content background |
| `WRITE_VIEW_PADDING_LINES` | `1` | Write 预览首尾空白过渡行数 / Blank padding lines above/below write preview |
| `WRITE_VIEW_MAX_LINES` | `40` | Write 预览最大显示行数（超出截断）/ Max lines to display before truncation |
| `WRITE_VIEW_MAX_CHARS` | `2000` | Write 预览最大显示字符数（超出截断）/ Max chars to display before truncation |

### URL 缓存 | URL Cache

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `URL_CACHE_VIEW_MAX` | `8` | URL 缓存列表最大显示数 / Max displayed entries in URL cache view |
| `URL_CACHE_CONTENT_CHAR_MAX` | `100` | URL 缓存内容预览最大字符数 / Max chars for URL cached content preview |

### 子 Agent | SubAgent

子 Agent 的类型标签、状态枚举、工具集常量及 TUI 显示参数 / Subagent type labels, status enums, toolset constants, and display params.

#### Agent 状态与类型 | Status & Types

| 常量 Constant             | 默认值 Default     | 用途 Purpose |
|-------------------------|-----------------|---------|
| `MAIN_AGENT_ID`         | `"main"`        | 主 Agent 的标识 ID / Main agent identifier |
| `AGENT_ID_LEN`          | `8`             | 子 Agent ID 的随机十六进制长度 / Random hex length for subagent IDs |
| `EXPLORER_AGENT_LABEL`  | `"explorer"`    | 探索型子 Agent 类型标签 / Explore subagent type label |
| `WORKER_AGENT_LABEL`    | `"worker"`      | 通用型子 Agent 类型标签 / General subagent type label |
| `SCHEDULER_AGENT_LABEL` | `"scheduler"`   | 调度型子 Agent 类型标签（任务规划和依赖管理）/ Scheduler subagent type label (task planning & dependency management) |
| `AGENT_PENDING_LABEL`   | `"pending"`     | 子 Agent 等待启动 / Subagent pending |
| `AGENT_RUNNING_LABEL`   | `"running"`     | 子 Agent 运行中 / Subagent running |
| `AGENT_TIMEOUT_LABEL`   | `"timeout"`     | 子 Agent 超时终止 / Subagent timed out |
| `AGENT_ERROR_LABEL`     | `"error"`       | 子 Agent 异常终止 / Subagent errored |
| `AGENT_DONE_LABEL`      | `"done"`        | 子 Agent 正常完成 / Subagent done |
| `AGENT_UNKNOWN_LABEL`   | `"unknown"`     | 子 Agent 状态未知 / Subagent status unknown |
| `TOOL_NAME_SPAWN_AGENT` | `"spawn_agent"` | 子 Agent 创建工具名称 / Spawn subagent tool name |

#### 工具与配置 | Tools & Config

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `SUBAGENT_DUMP_DIR` | `"agents"` | 子 Agent 数据持久化子目录名 / Subagent dump subdirectory name |
| `SUBAGENT_SUMMARIES_NAME` | `"summaries.json"` | 子 Agent 摘要持久化文件名 / Subagent summaries file name |
| `SUBAGENT_DEFAULT_MAX_STEPS` | `30` | 子 Agent 默认最大步数 / Subagent default max steps |
| `SUBAGENT_DEFAULT_WARN_STEPS` | `2` | 子 Agent 默认提前提醒步数 / Subagent default early warning steps |
| `SUBAGENT_DEFAULT_TIMEOUT_S` | `600` | 子 Agent 默认超时（秒）/ Subagent default timeout (seconds) |
| `SUBAGENT_DEFAULT_MODEL_TYPE` | `"fast"` | 子 Agent 默认模型类型 / Subagent default model type |
| `SUBAGENT_RESULT_LOG_CHAR_LIMIT` | `200` | 子 Agent 结果日志截断长度 / Subagent result log char limit |
| `SUBAGENT_TOOL_DISPLAY_MAX_LEN` | `120` | 工具调用显示参数值最大长度 / Max len for tool display argument value |
| `SUBAGENT_PROMPT_LOG_CHAR_LEN` | `200` | 初始化日志中 prompt 预览长度 / Prompt preview length in init log |
| `SUBAGENT_SUBJECT_CHAR_LIMIT` | `40` | 子 Agent subject 字段最大字符数 / Subagent subject field char limit |
| `SUBAGENT_TOOL_RESULT_DEFAULT_CHAR_LIMIT` | `50000` | 子 Agent 工具结果默认截断字符数 / Default char limit for subagent tool results |
| `MAIN_TOOL_RESULT_DEFAULT_CHAR_LIMIT` | `20000` | 主 Agent 工具结果默认截断字符数 / Default char limit for main agent tool results |
| `TOOL_RESULT_TRUNCATION_ROUNDS` | `6` | 迭代截断最大轮数，耗尽后退到硬截断 / Max rounds for iterative field-level truncation |
| `TOOL_RESULT_TRUNCATION_MIN_BUDGET` | `1024` | 被截断字段保底字符数，防止截成空串 / Floor budget for truncated field content |
| `TOOL_RESULT_TRUNCATION_MARKER_RESERVE` | `60` | 为 `<truncated>` 标记预留字符数 / Char reserve for truncation marker overhead |
| `TOOL_RESULT_TRUNCATION_START_LABEL` | `<truncated>` | 截断标记起始标签 / Truncation marker start tag |
| `TOOL_RESULT_TRUNCATION_END_LABEL` | `</truncated>` | 截断标记结束标签 / Truncation marker end tag |

#### TUI 显示 | TUI Display

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `SUBAGENT_PENDING_ICON` | `"○"` | 等待中图标 / Pending icon |
| `SUBAGENT_IN_PROGRESS_ICON` | `"♦"` | 运行中图标 / Running icon |
| `SUBAGENT_DONE_ICON` | `"✓"` | 完成图标 / Done icon |
| `SUBAGENT_ERROR_ICON` | `"✗"` | 错误/超时图标 / Error/timeout icon |
| `SUBAGENT_COLOR_START` | `"#202020"` | 子 Agent 渐变起始色 / Gradient start color |
| `SUBAGENT_COLOR_END` | `"#808080"` | 子 Agent 渐变结束色 / Gradient end color |
| `SUBAGENT_COLOR_GRADIENT` | `128` | 渐变阶梯数 / Gradient step count |
| `SUBAGENT_COLOR_PERIOD` | `4.0` | 颜色循环周期（秒）/ Color cycle period (seconds) |

#### 权限控制 | Permission Control

| 常量 Constant | 默认值 Default                                                       | 用途 Purpose                                                                                           |
|----------|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `MUTE_PERMISSION_DENIED_INFO` | `"Permission request denied, you don't have access to this tool"` | 静默 TUI 权限请求并且权限拒绝时的提示信息 / Info shown when permission is denied when TUI permission request is muted  |
| `MAINAGENT_PERMISSION_DENIED_INFO` | `"Permission request denied by user"`                             | 主 Agent 权限拒绝时的提示信息 / Info shown when main agent permission is denied by user                         |
| `MAINAGENT_PERMISSION_DENIED_PREFIX_INFO` | `"Permission request denied by user with comment:"`               | 主 Agent 权限拒绝并附注释时的前缀 / Prefix when main agent permission is denied with user comment                 |

---

## 其他关键常量 | Other Key Constants

这些常量控制 Agent 的核心版本标识与基础行为参数：
These constants control the agent's core identity and basic behavior:

| 常量 Constant | 默认值 Default | 说明 Description |
|----------|---------|-------------|
| `TECOSIM_AGENT_MAJOR_VERSION` | `0` | Agent 主版本号 / Agent major version |
| `TECOSIM_AGENT_MINOR_VERSION` | `3` | Agent 次版本号 / Agent minor version |
| `TECOSIM_AGENT_UPDATE_VERSION` | `0` | Agent 更新版本号 / Agent update version |
| `CRON_TASK_ID_LEN` | `8` | 定时任务 ID 长度 / Cron task ID length |
| `API_CONFIGS_PATH` | `"./config/api_configs.json"` | API 配置路径 / API config path |
| `AGENT_CONFIGS_PATH` | `"./config/agent_configs.json"` | Agent 配置路径 / Agent config path |
| `MCPS_PATH` | `"./mcps"` | MCP 根目录 / MCP root directory |
| `SKILLS_PATH` | `"./skills"` | Skills 根目录 / Skills root directory |
| `MCPS_CONFIGS_PATH` | `"./mcps/mcps_configs.json"` | MCP 配置文件路径 / MCP config file path |
| `MCP_TOOL_DESC_CHAR_LIMIT` | `250` | MCP 工具描述显示截断长度 / MCP tool description display char limit |
| `LOG_PATH` | `"./log"` | 日志文件输出目录 / Log file output directory |
| `SESSION_PATH` | `"./session"` | 会话持久化目录（每个会话一个子文件夹）/ Session persistence directory (one subfolder per session) |
| `CRON_CONFIGS_PATH` | `"./cron/cron_configs.json"` | 持久化定时任务配置文件路径 / Durable cron config file path |
| `USER_HISTORY_NAME` | `"user_history"` | 用户历史文件名（会话目录下）/ User history file name (under session dir) |
| `MESSAGES_NAME` | `"messages.json"` | 消息记录文件名（会话目录下）/ Messages file name (under session dir) |
| `CONTEXT_NAME` | `"context.json"` | 上下文文件名（会话目录下）/ Context file name (under session dir) |
| `CRON_NAME` | `"cron_configs.json"` | 会话级定时任务文件名（会话目录下）/ Session cron configs file name (under session dir) |
| `TASKS_NAME` | `"tasks.json"` | Scoreboard 任务持久化文件名（存于 session 目录）/ Scoreboard task persistence file name (under session dir) |
| `RUNS_NAME` | `"runs.json"` | 仿真运行记录持久化文件名 / Simulation run records persistence file name |
| `DESIGNS_NAME` | `"designs.json"` | 面板设计持久化文件名 / Panel design persistence file name |
| `SIM_DESIGN_NAME` | `"design"` | 仿真设计目录名 / Simulation design directory name |
| `SIM_RUN_NAME` | `"run"` | 仿真运行目录名 / Simulation run directory name |
| `ASK_USER_QUESTION_MAX_QUESTION` | `4` | 单次提问最多问题数 / Max questions per ask_user_question call |
| `ASK_USER_QUESTION_MIN_QUESTION` | `1` | 单次提问最少问题数 / Min questions per ask_user_question call |
| `ASK_USER_QUESTION_MAX_OPTION` | `4` | 每个问题最多选项数 / Max options per question |
| `ASK_USER_QUESTION_MIN_OPTION` | `2` | 每个问题最少选项数 / Min options per question |
| `QUESTION_OTHER_LABEL` | `"<Other>"` | 用户自定义选项标签 / Custom option label |
| `QUESTION_OTHER_OPTION_DESC` | `"Type your ideas"` | 自定义选项描述 / Custom option description |
| `QUESTION_RECOMMEND_LABEL` | `"Recommended"` | 推荐选项标签 / Recommended option label |
| `QUESTION_NO_CHOICE_LABEL` | `"(User didn't choose any option)"` | 用户未选择选项时的占位文本 / Placeholder when user chooses no option |
| `GLOB_FILE_ENTRIES_DEFAULT` | `250` | `glob_file` 默认返回条目数 / Default entries for glob_file |
| `GREP_FILE_HEAD_LIMIT_DEFAULT` | `250` | `grep_file` 默认结果数上限 / Default head limit for grep_file |
| `READ_FILE_ENCODING_DEFAULT` | `utf-8` | `read_file` 默认编码 / Default encoding for read_file |
| `READ_LOG_ENCODING_DEFAULT` | `utf-8` | `read_log` 默认编码 / Default encoding for read_log |
| `WRITE_FILE_MODE_DEFAULT` | `write` | `write_file` 默认写入模式 / Default write mode for write_file |
| `WRITE_FILE_ENCODING_DEFAULT` | `utf-8` | `write_file` 默认编码 / Default encoding for write_file |
| `EDIT_FILE_ENCODING_DEFAULT` | `utf-8` | `edit_file` 默认编码 / Default encoding for edit_file |
| `WEB_SEARCH_QUERY_MIN` | `2` | 网络搜索最小查询字符数 / Min query chars for web search |
| `BASH_TIMEOUT_MS_DEFAULT` | `120000` (2 min) | Bash 命令默认超时。Agent 的 `bash` 工具若不指定 timeout 参数则使用此值 / Default bash command timeout; used when no timeout argument is given |
| `BASH_TIMEOUT_MS_MAX` | `600000` (10 min) | Bash 命令最大超时上限。Agent 拒绝任何超过此值的 timeout 参数，防止误设过长超时 / Max bash command timeout; the agent rejects any timeout exceeding this limit |
| `SIMULATOR_TIMEOUT_DEFAULT_S` | `3600` (1 hour) | 仿真运行默认超时（秒）/ Default simulation timeout (seconds) |
| `DEFAULT_TIMEOUT_MS` | `1000000` (~16 min) | LLM API 请求默认超时（毫秒）/ Default LLM API request timeout (ms) |
| `READ_FILE_MAX_LINE` | `10000` | 单次读取文件最大行数。超过此行数后不再继续读取 / Max lines per file read; stops reading beyond this limit |
| `READ_FILE_LINE_CHAR_LIMIT` | `2000` | LLM 输出单行最大字符数（超出截断并标记）/ Max chars per line in LLM output (truncated with marker) |
| `READ_LOG_MAX_LINE` | `10000` | 单次读取日志最大行数。与 `READ_FILE_MAX_LINE` 不同，此值专门针对仿真日志读取 / Max lines per log read (separate from `READ_FILE_MAX_LINE`, specific to simulation logs) |
| `PERMISSION_REQUEST_DSEC_CHAR_MAX` | `500` | 权限请求描述的最大字符数。用户在权限 TUI 中输入注释时超过此长度会被截断 / Max chars for permission request description; user comments exceeding this are truncated |
| `WECHAT_CRED_PATH` | `"./config/wechat_bot_cred.json"` | 微信机器人凭证配置文件路径 / WeChat bot credential config file path |
| `WECHAT_MEDIA_CACHE_DIR` | `"wechat_cache"` | 微信媒体缓存目录名（会话目录下）/ WeChat media cache directory name (under session dir) |
| `WECHAT_MEDIA_CACHE_NAME` | `"cdn_cache.json"` | 微信 CDN 缓存持久化文件名 / WeChat CDN cache persistence file name |
| `WECHAT_HISTORY_NAME` | `"msg_history.json"` | 微信消息历史持久化文件名 / WeChat message history persistence file name |
| `WECHAT_VERIFY_CODE_PREFIX1` | `"Please input the verify code on you phone"` | 微信验证码提示 1（首次输入）/ WeChat verify code prompt 1 (first input) |
| `WECHAT_VERIFY_CODE_PREFIX2` | `"Wrong verify code, please input the correct verify code on you phone"` | 微信验证码提示 2（验证码错误重试）/ WeChat verify code prompt 2 (retry after wrong code) |

---

## 微信机器人交互 | WeChat Bot Interaction

Agent 通过 `--wechat` CLI 参数启动微信机器人模式，与用户通过微信消息交互。以下常量控制微信机器人的登录超时、回复超时、媒体下载阈值、消息摘要长度、队列缓存等行为：
The agent can be started in WeChat bot mode via the `--wechat` CLI argument. The following constants control login timeouts, reply timeouts, media download thresholds, message summary limits, queue caching, and more:

### 超时参数 | Timeout Parameters

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `WECHAT_BOT_LOGIN_DEFAULT_TIMEOUT_S` | `120` | 微信扫码登录默认超时（秒）/ Default timeout for QR code scan login (seconds) |
| `WECHAT_BOT_STOP_DEFAULT_TIMEOUT_S` | `10` | 微信机器人优雅停止默认超时（秒）/ Default timeout for graceful bot shutdown (seconds) |
| `WECHAT_BOT_HEAD_CDN_DEFAULT_TIMEOUT_S` | `10` | CDN HEAD 请求（获取媒体大小）默认超时（秒）/ Default timeout for CDN HEAD requests (seconds) |
| `WECHAT_BOT_TEXT_REPLY_DEFAULT_TIMEOUT_S` | `30` | 文本回复默认超时（秒）/ Default timeout for text reply (seconds) |
| `WECHAT_BOT_MEDIA_REPLY_DEFAULT_TIMEOUT_S` | `60` | 媒体文件回复默认超时（秒）/ Default timeout for media file reply (seconds) |

### 消息与媒体参数 | Message & Media Parameters

| 常量 Constant | 默认值 Default | 用途 Purpose |
|----------|---------|---------|
| `WECHAT_BOT_MUTE_NONFATAL_ERROR_DEFAULT` | `False` | 是否静默非致命错误（`agent_configs.json` 中 `WECHAT_BOT_MUTE_NONFATAL_ERROR` 配置项的默认值）/ Whether to mute non-fatal errors (default for `WECHAT_BOT_MUTE_NONFATAL_ERROR` in agent_configs.json) |
| `WECHAT_BOT_MSG_SUMMARY_CHAR_MAX` | `100` | 微信消息摘要最大字符数 / Max chars for WeChat message summary |
| `WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB_DEFAULT` | `100` | 媒体文件自动下载阈值默认值（MB）/ Default threshold for automatic media download (MB) |
| `WECHAT_MEDIA_CACHE_KEY_MAX_LEN` | `8` | CDN 缓存键随机十六进制长度 / Random hex length for CDN cache keys |
| `WECHAT_BOT_QUOTED_CHAR_MAX` | `1000` | 引用消息的最大文本提取字符数 / Max chars extracted from quoted reply messages |
| `WECHAT_REPLY_BUDGET_MAX` | `10` | 每轮用户消息的回复预算上限 / Max replies per user message round |
| `WECHAT_BOT_LAST_REPLY_DURING_TOOL_CALL_HINT` | `> ℹ️ This is the last messgae during tool call ...` | 预算倒数第2条回复时附加的提示文本（提醒用户发送新消息以重置预算）/ Hint appended to the second-to-last reply during tool calls (prompts user to send a new message to reset budget) |

### 预置回复列表 | Preset Reply Lists

| 常量 Constant | 类型 Type | 用途 Purpose |
|----------|------|---------|
| `WECHAT_BOT_LOCKED_LIST` | `list[str]`（5 条） | 会话锁定时向绑定用户发送的确认消息列表 / Confirmation messages sent to the bound user when the session is locked |
| `WECHAT_BOT_BLOCK_REPLY_LIST` | `list[str]`（13 条） | 当机器人正服务其他用户时，向新请求用户发送的拒绝消息列表 / Rejection messages sent to new users when the bot is serving another user |
| `WECHAT_BOT_NORMAL_EXIT_LIST` | `list[str]`（5 条） | Agent 正常退出时向绑定用户发送的告别消息列表 / Farewell messages sent to the bound user on normal agent exit |
| `WECHAT_BOT_ERROR_EXIT_LIST` | `list[str]`（5 条） | Agent 异常退出时向绑定用户发送的错误通知消息列表 / Error notification messages sent to the bound user on abnormal agent exit |

> **实现说明 | Implementation Note**
> 
> **可配置覆盖 | Config Overridable**
> 所有超时参数（`WECHAT_BOT_*_TIMEOUT_S`）和 `mute_nonfatal_error` 可通过 `agent_configs.json` 中的同名键（去掉 `_DEFAULT` 后缀）覆盖默认值。例如 `WECHAT_BOT_LOGIN_TIMEOUT_S` 覆盖 `WECHAT_BOT_LOGIN_DEFAULT_TIMEOUT_S`。
> All timeout parameters and `mute_nonfatal_error` can be overridden via the same key (without the `_DEFAULT` suffix) in `agent_configs.json`. e.g. `WECHAT_BOT_LOGIN_TIMEOUT_S` overrides `WECHAT_BOT_LOGIN_DEFAULT_TIMEOUT_S`.
> 
> **媒体下载流程 | Media Download Flow**
> 收到微信媒体消息时，Agent 先通过 CDN HEAD 请求获取文件大小，仅当小于 `WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB` 时才下载（AES 解密 → magic-byte 扩展名检测 → CDN 缓存）。已下载的媒体通过 CDN 缓存（`WECHAT_MEDIA_CACHE_NAME`）持久化到磁盘，避免重复下载。
> On receiving media messages, the Agent first fetches the file size via CDN HEAD, downloading (AES decrypt → magic-byte extension detection → CDN cache) only when under the threshold. Downloaded media are persisted via CDN cache to avoid re-downloads.
> 
> **用户绑定 | User Binding**
> 微信机器人绑定第一个发送消息的用户作为会话拥有者。绑定期间，其他用户发送的消息被屏蔽（随机从 `WECHAT_BOT_BLOCK_REPLY_LIST` 中选取拒绝消息回复）。首用户锁定成功时，随机从 `WECHAT_BOT_LOCKED_LIST` 中选取确认消息回复。
> The WeChat bot binds the first user who sends a message as the session owner. During binding, messages from other users are blocked (randomly chosen reply from `WECHAT_BOT_BLOCK_REPLY_LIST`). The bound user receives a random lock confirmation from `WECHAT_BOT_LOCKED_LIST`.
> 
> **退出通知 | Exit Notification**
> Agent 正常退出（Ctrl+C 后确认退出）或异常退出时，会向绑定用户发送一条随机选择的告别/错误通知消息（分别来自 `WECHAT_BOT_NORMAL_EXIT_LIST` 和 `WECHAT_BOT_ERROR_EXIT_LIST`），随后停止机器人、保存缓存及消息历史。
> On normal exit (confirmed after Ctrl+C) or abnormal exit, the agent sends a randomly chosen farewell/error notification to the bound user (from `WECHAT_BOT_NORMAL_EXIT_LIST` and `WECHAT_BOT_ERROR_EXIT_LIST` respectively), then stops the bot, saves CDN cache and message history.
> 
> **监听 TUI 行为 | Listen TUI Behavior**
> 当微信机器人启用时，监听 TUI 强制进入且无法通过按键退出（仅 Ctrl+C 可退出）——确保所有微信消息在返回到终端输入模式前被捕获。微信消息到达时，监听循环退出并处理消息。
> When the WeChat bot is enabled, the listen TUI is always active and cannot be dismissed by keypress (only Ctrl+C exits) — ensuring all incoming WeChat messages are captured before returning to terminal input mode.
> 

