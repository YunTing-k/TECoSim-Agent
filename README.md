# TECoSim Agent

<div align="center">
  <img src="./doc/img/logo.png" width="100%" />
</div>

> 从**跨层次建模**到**智能体设计**
> From **Cross-level Modeling** to **Agent Design**

## 简介 | Introduction
### 背景 | Background
现代显示系统是**多层次嵌套的复杂系统**（物理层 → 器件层 → 电路层 → 面板层 → 应用层 → 系统性能层）。层次间的深度耦合产生了横跨多层级的复杂现象——**电压降效应**（IR Drop）、**热电耦合效应**（Thermo-Electrical Coupling）、**显示残影**（Ghost Shadow）等，这些不良现象严重影响显示质量，且无法在单个层次分析捕捉。
Modern display systems are **multi-level nested complex systems** (Physical → Device → Circuit → Panel → Application → System Performance). The deep inter-level coupling produces complex phenomena spanning multiple layers — **IR drop**, **thermo-electrical coupling**, **ghost shadow** — which severely degrade display quality and cannot be captured by single-level analysis.

<div align="center">
  <img src="./doc/img/hierarchy_of_displays.png" width="100%" />
</div>

[TECoSim仿真器](https://github.com/YunTing-k/TECoSim)（暂未开源）正是为建模这些跨层次耦合效应而生，采用**自底向上逐层抽象**与**系统级端到端仿真**相结合的**跨层次协同仿真方法**。
The [TECoSim Simulator](https://github.com/YunTing-k/TECoSim) (not open-source yet) was built specifically to model these cross-level coupling effects, using a **cross-level co-simulation** approach combining **bottom-up abstraction** with **system-level end-to-end simulation**.

### 敏捷设计的困境 | Dilemma of Agile Design
TECoSim 面临两个核心瓶颈：
TECoSim faces two fundamental bottlenecks:

1. **门槛高** — 跨层级建模范式要求使用者同时掌握多个领域知识，难以快速上手
   **High barrier to entry** — mastering cross-level modeling requires knowledge across multiple domains
2. **依赖人工** — 仅有"设计→仿真"的单向流程，缺乏"指标→设计"的自动化优化
   **Manual tuning** — only "design→simulate" flow exists, lacking "spec→design" automation

以上问题催生了 **TECoSim Agent** 项目。
These limitations led to the **TECoSim Agent** project.

---

### 项目贡献 | Contribution of this Project

**意图-物理跨层对齐的设计范式 | Intent-Physics Cross-Level Alignment Paradigm**

传统设计流程中，设计意图需要专家 **手动拆解** 为可执行的设计-仿真迭代步骤，同时各仿真工具仅 **孤立考虑各个层级**、严重忽略层间耦合。最终导致系统性能 **缺乏全局可参考依据**，**设计效率低下**。
Traditional design requires experts to **manually translate** design intent into executable design-simulation iteration steps, while simulation tools **address each layer in isolation**, severely neglecting cross-level coupling. The result is a system-level evaluation with **no reliable global reference** and **inefficient design workflows**.

**TECoSim Agent** 深度嵌入跨层次建模的 TECoSim 仿真器到 LLM 智能体，结合专家工具和工作流编排，**实现设计意图到物理仿真的全层级贯通**。
**TECoSim Agent** deeply embeds the cross-level modeling TECoSim simulator into an LLM agent, combining expert tools and workflow orchestration — **achieving cross-level alignment from design intent to physical simulation**.

<div align="center">
  <img src="./doc/img/agent_tui.png" width="100%" />
</div>

**主要特性 | Key Features**

| # | 特性 Feature | 说明 Description |
|---|-------------|------------------|
| 1 | **通用智能体平台** General Agent Platform | 内置文件读写编辑、Bash执行、网页搜索获取、定时任务、多Agent并发协作、任务看板、MCP协议、技能框架等丰富工具，结合权限系统 / File I/O & edit, Bash execution, web search & fetch, cron tasks, parallel subagents, scoreboard, MCP, skill framework — with permission system |
| 2 | **跨层次工具无缝集成** Cross-Level Tool Integration | 自然语言描述目标，智能体自动完成从设计、仿真到验证的全流程，深度整合 TECoSim 跨层次协同仿真 / Describe goals in natural language — the agent handles the full design→simulate→verify workflow, deeply integrated with TECoSim cross-level co-simulation |
| 3 | **微信交互** WeChat Interaction | 通过微信 Bot 接收文字、语音（ASR 转写）、图片、视频、文件，支持双向多媒体回复 / Interact via WeChat Bot — text, voice (ASR), images, video, files — with bidirectional multimedia reply |

---

## 快速开始 | Quick Start

### 环境要求 | Requirements

- **Python**: 3.12.x
- **操作系统 OS**: Windows / Linux / macOS
- **可选 Optional**: TECoSim 仿真器（如有需求请联系作者获取）/ TECoSim simulator (contact the author if needed)

### 安装与配置 | Installation and Configuration

以下以 `venv` 为例创建虚拟环境（也可使用 `conda` 等工具）：
The following uses `venv` as an example (`conda` or other virtual environment tools also work):

```bash
# 1. 克隆仓库 | Clone the repository
git clone https://github.com/YunTing-k/TECoSimAgent.git
cd TECoSimAgent

# 2. 创建虚拟环境（推荐）| Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

# 3. 安装依赖 | Install dependencies
pip install -r requirements.txt
```

安装后，还需要配置 `./config/` 下的文件：

#### 1. API 连接配置 | API Connection (`api_configs.json`)

必须设置 LLM API 端点与密钥：
You must set your LLM API endpoint and key:

| 参数 Parameter | 说明 Description |
|-----------|-------------|
| `API_URL` | API 基地址 / API base URL (e.g., `https://api.deepseek.com`) |
| `API_KEY` | API 认证密钥 / API authentication key |
| `TIMEOUT_MS` | 请求超时（毫秒）/ Request timeout (ms) |
| `MAIN_MODEL_NAME` | 主模型，用于复杂多步推理 / Main model for complex multi-step reasoning |
| `MAIN_MODEL_*` | 主模型配套参数（上下文窗口、温度、推理开关、`max_tokens` 等）/ Companion params for the main model (context, temperature, reasoning, `max_tokens`, etc.) |
| `MEDIUM_MODEL_NAME` | 中等模型，用于结构化决策等中等复杂度任务 / Medium model for structured decisions and moderate-complexity tasks |
| `MEDIUM_MODEL_*` | 中等模型配套参数 / Companion params for the medium model |
| `FAST_MODEL_NAME` | 快速模型，用于分类、校验等简单任务 / Fast model for classification, validation, and simple tasks |
| `FAST_MODEL_*` | 快速模型配套参数 / Companion params for the fast model |

#### 2. Agent 运行参数 | Agent Runtime (`agent_configs.json`)

| 参数 Parameter | 默认值 Default | 说明 Description |
|-----------|---------|----------------|
| `SIMULATOR_PATH` | `" "` | **如使用 TECoSim 必须设置** — 仿真器可执行文件路径 / **Must set** if using TECoSim |
| `BASH_PATH` | `"bash"` | **GNU Bash** 的路径（不支持 cmd/pwsh，见下文）/ Path to **GNU Bash** (cmd/pwsh not supported) |
| `RIPGREP_PATH` | `"rg"` | `ripgrep` 可执行文件路径 / Path to `ripgrep` executable |
| `WEB_SEARCH_BACKEND` | `" "` | 网络搜索后端，可选：`Exa`、`Tavily`、`Linkup`、`DDGS` / Set to enable web search |
| `WEB_SEARCH_API_KEY` | `" "` | 网络搜索 API Key / API key for your web search backend |

**`BASH_PATH` 必须指向 GNU Bash**（不可用 `cmd`, `PowerShell` etc.,）。Agent 通过 `bash -c` 执行命令，并内置基于 Bash 语义的风险检测引擎。Windows操作系统可使用`git bash`。
**`BASH_PATH` must point to GNU Bash** (not `cmd`, `PowerShell` etc.,). The agent executes commands via `bash -c` with Bash-semantics-based risk detection. For Windows OS, please use `git bash`.

> **⚠️ 安全建议 | Security Advisory** — Agent 可通过 `bash` 执行任意系统命令，风险检测并非绝对可靠。强烈建议在沙箱环境（Docker/VM/隔离服务器）中以最小权限账户运行，并用 `/readonly_add` 保护关键路径。
> The agent can execute arbitrary system commands via `bash`. Risk detection is not infallible. Run in a sandbox (Docker/VM/isolated server) with least-privilege account; use `/readonly_add` to protect critical paths.

**ripgrep** — `grep_file` 工具依赖 ripgrep（`rg`）。安装：`winget install BurntSushi.ripgrep`（Win）/ `sudo apt install ripgrep`（Linux）/ `brew install ripgrep`（macOS）。或在 `agent_configs.json` 中设 `RIPGREP_PATH`。
**ripgrep** — the `grep_file` tool requires ripgrep (`rg`). Install via your package manager, or set `RIPGREP_PATH` in `agent_configs.json`.

> 完整参数列表请参阅 | See [Configuration Reference](./doc/configuration.md) for all available parameters.

### 首次启动 | First Launch

```bash
python -m src.main
```

加载完毕后即可在输入框下达指令，开始你的使用 / Once loaded, type your instructions in the prompt and start your first usage.

## 微信集成 | WeChat Integration

通过 CLI 参数 `-wc` / `--wechat` 启用微信机器人模式，使用微信消息与 Agent 交互：
Enable WeChat Bot mode via `-wc` / `--wechat` to interact with the agent through WeChat messages:

**首次登录 | First Login**

```
python -m src.main -wc
```

启动后终端会显示二维码链接，使用微信扫码确认登录。若服务器要求配对验证码，终端会提示输入手机上的验证码。登录凭证保存于 `./config/wechat_bot_cred.json`，下次启动自动恢复，无需重复扫码。
After launch, a QR code link is shown in the terminal — scan it with WeChat to confirm login. If the server requires a pairing code, the terminal prompts you to enter the code from your phone. Credentials are saved to `./config/wechat_bot_cred.json` and auto-restored on subsequent launches.

**行为特性 | Behavior**

| 特性 Feature | 说明 Description |
|-------------|------------------|
| 用户绑定 User Binding | 首个发送消息的用户自动绑定，建立独占会话；其他用户消息被自动拒绝并回复提示 / First user auto-bound — exclusive session; other users blocked with auto-reply |
| 多模态消息 Multimodal Messaging | 支持接收文字、语音（服务器 ASR 转写为文本）、图片、视频、文件。可主动发送媒体文件（通过 `wechat_send_media` 工具）/ Receive text, voice (server ASR), images, video, files. Can send media proactively via `wechat_send_media` tool |
| 监听 TUI Listen TUI | 启动后 Agent 进入强制监听模式（仅 Ctrl+C 退出），确保第一时间捕获微信消息 / Agent enters mandatory listen mode (only Ctrl+C exits) to capture WeChat messages immediately |
| 权限隔离 Permission Isolation | 微信模式下主 Agent 权限被 `WECHAT_BOT_PERMISSION` 完全覆盖，与终端模式独立配置 / Main agent permissions fully overridden by `WECHAT_BOT_PERMISSION`, independent from terminal mode |
| 工具执行中回复 Mid-Tool Reply | 可配置在 LLM 执行工具调用期间是否仍允许向微信发送中间回复（`WECHAT_BOT_REPLY_DURING_TOOL_CALL`）/ Configurable mid-tool-call reply to WeChat during LLM tool execution |
| CDN 缓存 CDN Cache | 接收的媒体文件缓存跟随会话持久化，恢复同一会话时避免重复下载 / Media cache is persisted with the session — no re-download when resuming the same session |

---

## 多Agent协作 | Subagent Coordination

Agent 支持通过 `spawn_agent` 工具并发启动多个专业化子Agent，实现任务的并行分解与异步执行。每个子Agent类型拥有不同的工具集与权限预设：
The agent supports concurrent subagent spawning via `spawn_agent` for parallel task decomposition. Each subagent type has a distinct toolset and permission preset:

| Agent 类型 Type | 工具集 Toolset | 能力 Capability |
|----------------|---------------|----------------|
| `explorer` | 探索工具 + 任务工具 / Explore tools + task tools | 代码探索、文件搜索、网页获取、Bash 执行 / Code exploration, file search, web fetch, Bash execution |
| `worker` | 全工具集（排除问答与定时任务）/ Full toolset (exclude ask question & cron) | 通用任务执行 / General-purpose task execution |
| `scheduler` | 任务工具 + 探索工具 / Task tools + explore tools | 共享任务看板，负责任务分解与依赖规划 / Shared scoreboard for task decomposition & planning |

子Agent 支持**前台**（阻塞等待所有子Agent完成后汇总结果）和**后台**（异步运行，完成时通过监听 TUI 自动递交结果作为用户消息）两种模式。主 Agent 在一轮中可以同时启动多个不同类型的前台和后台子Agent。
Subagents support **foreground** (blocking — waits for all spawned agents, returns aggregated results) and **background** (async — completion detected by listen TUI, results injected as user messages) modes. The main agent can launch multiple foreground and background subagents of different types in a single round.

---

## 仿真管理 | Simulation Management

Agent 集成了 TECoSim 仿真器的完整工作流管理，支持以下操作：
The agent integrates full TECoSim simulator workflow management:

| 操作 Operation | 说明 Description |
|---------------|------------------|
| `check_simulator` | 检查仿真器是否可用 / Check if simulator is available |
| `init_design` | 从默认模板创建新面板设计 / Create a new panel design from default template |
| `query_design` | 查询设计列表与修订历史 / Query design list and revision history |
| `launch_sim` | 启动仿真运行 / Launch a simulation run |
| `query_run` | 查询仿真运行记录 / Query simulation run records |
| `read_log` | 读取仿真 stdout/stderr 日志 / Read simulation stdout/stderr logs |

在 Agent 交互界面中，也可通过内建命令快速查询：
Inside the agent interface, use built-in commands for quick queries:
- `/design_list` — 列出所有设计 / List all designs
- `/run_list` — 列出所有仿真运行 / List all simulation runs

---

## 基本使用 | Basic Usage

### 命令行参数 | CLI Arguments

```bash
python -m src.main                         # 启动Agent / Launch agent
python -m src.main -l                      # 启用开发者日志 / Launch with developer logs
python -m src.main -r <UUID>               # 恢复指定会话 / Resume a session
python -m src.main --nosystem              # 禁用系统提示词 / Disable system prompts
python -m src.main --notools               # 禁用工具 / Disable agent tools
python -m src.main --nocrons               # 禁用定时任务 / Disable cron tasks
python -m src.main --noskills              # 禁用技能 / Disable skills
python -m src.main --nomcps                # 禁用MCP / Disable MCPs
python -m src.main --dangerously_allow_all # ⚠️ 允许所有权限 （危险！） / Allow all permissions (dangerous!)
```

### 子命令 | Sub-commands

```bash
# 会话管理 | Session management
python -m src.main session list              # 列出所有会话 / List all sessions
python -m src.main session remove <UUID>     # 删除指定会话 / Remove a session

# 持久化定时任务管理 | Durable cron management
python -m src.main cron list                 # 列出持久化定时任务 / List durable cron tasks
python -m src.main cron remove <ID>          # 删除持久化定时任务 / Remove a durable cron task

# 技能管理 | Skill management
python -m src.main skill list                # 列出所有可用技能 / List all available skills

# MCP 管理 | MCP management
python -m src.main mcp list                  # 列出所有 MCP 服务器 / List all MCP servers
python -m src.main mcp add <name> <type> <params>  # 添加 MCP 服务器 / Add an MCP server
python -m src.main mcp toggle <name>         # 启用/禁用 MCP 服务器 / Enable/disable an MCP server
python -m src.main mcp remove <name>         # 移除 MCP 服务器 / Remove an MCP server
```

### 内建命令 | Built-in Commands

在 Agent 交互界面中，所有命令以 `/` 开头：
All commands start with `/` in the agent interaction interface:

| 命令 Command | 功能 Description |
|---------|-------------|
| `/help` | 查看所有可用命令 / Show all available commands |
| `/design_list` | 查询设计列表 / Query design list |
| `/run_list` | 查询仿真运行记录 / Query simulation run records |
| `/context` | 查看 Token 用量与上下文统计 / View token usage and context stats |
| `/fread_list` | 查看所有已读文件 / View all read files |
| `/url_caches` | 查看缓存的 URL / View cached URLs |
| `/session_list` | 查看所有会话 / View all sessions |
| `/session_remove <UUID>` | 删除指定会话 / Remove a session |
| `/readonly_list` | 查看只读路径 / View read-only paths |
| `/readonly_add <PATH> [PATH...]` | 添加只读路径 / Add read-only paths |
| `/readonly_remove <idx> [idx...]` | 移除只读路径 / Remove read-only paths |
| `/permission_list` | 查看权限配置 / View permission configs |
| `/permission_toggle <NAME>` | 切换权限开关 / Toggle a permission |
| `/skill_list` | 列出可用技能 / List available skills |
| `/skills_loaded` | 列出已加载技能 / List loaded skills |
| `/<skill_name>` | 手动加载技能 / Manually load a skill |
| `/mcp_list` | 查看 MCP 信息 / View MCP information |
| `/cron_list` | 查看定时任务列表 / View cron task list |
| `/cron_remove <ID>` | 删除定时任务 / Remove a cron task |
| `/task_list` | 查看未归档的 Agent 任务 / List non-archived agent tasks |
| `/task_list_all` | 查看所有历史的 Agent 任务 / List all history agent tasks |
| `/agent_list` | 查看所有子Agent（活跃和已归档）/ List all subagents (active and archived) |
| `/update_title` | 用 LLM 自动更新当前会话标题 / Auto-update current session title with LLM |
| `/set_title <TITLE>` | 手动设置当前会话标题 / Manually set current session title |

---

## 项目结构 | Project Structure

```
TECoSimAgent/
├── src/
│   ├── main.py                  # 入口与主循环 / Entry point & agent loop
│   ├── constants.py             # 全局常量与默认参数 / All global constants & defaults
│   ├── agent/
│   │   ├── subagent.py          # 子Agent核心（初始化/运行/输出）/ Subagent core (init, run, results)
│   │   └── progress.py          # 子Agent状态枚举与进度数据类 / Agent status enum & progress dataclass
│   ├── context/
│   │   ├── agent_context.py     # 集中式Agent状态管理 / Central agent state management
│   │   ├── prompt.py            # 提示词组装与LLM响应处理 / Prompt assembly & LLM response handling
│   │   └── session.py           # 会话持久化管理 / Session persistence management
│   ├── tool/
│   │   ├── tool_def.py          # 工具定义与实现 / Tool definitions & implementations
│   │   ├── tool_execute.py      # 工具执行调度器（含子Agent spawn）/ Tool dispatcher (incl. subagent spawn)
│   │   ├── tool_dispatch.py     # 工具调用分发（call_tools）/ Tool call dispatch
│   │   ├── wechat_support.py    # 微信桥接（登录/长轮询/消息管道/媒体缓存/回复）/ WeChat bridge (login, long-poll, message queue, media cache, reply)
│   │   ├── simulator_support.py # 设计/运行管理与仿真器启动 / Design/run management & simulator launch
│   │   ├── simulator_param.py   # 仿真器配置参数类型定义 / Simulator configuration TypedDicts
│   │   ├── file_io_support.py   # 文件读写编辑支持 / File read/write/edit support
│   │   ├── file_filter_support.py  # 文件通配/内容搜索 / Glob/grep file search
│   │   ├── bash_support.py      # Bash 命令执行与风险检测 / Bash execution & risk evaluation
│   │   ├── ask_question.py      # 结构化提问工具 / Structured question asking
│   │   ├── ask_permission.py    # 权限请求 TUI / Permission request TUI
│   │   ├── web_support.py       # 网页获取与网络搜索 / Web fetch & search support
│   │   ├── cron_support.py      # 定时任务管理 / Cron task management
│   │   ├── skills_support.py    # 技能框架支持 / Skill framework support
│   │   ├── summarize_support.py # 会话摘要支持 / Session summarization support
│   │   ├── mcps_support.py      # MCP 工具路由 / MCP tool router
│   │   └── scoreboard.py        # 多Agent任务看板 / Task board for multi-agent coordination
│   ├── wechat/
│   │   ├── __init__.py          # 微信 Bot SDK 包（基于 wechatbot-sdk）/ WeChat Bot SDK package (based on wechatbot-sdk)
│   │   ├── client.py            # WeChatBot 编排层 / WeChatBot orchestrator
│   │   ├── auth.py              # QR 登录流程与凭证持久化 / QR login flow & credential persistence
│   │   ├── protocol.py          # iLink API HTTP 调用 / iLink API low-level HTTP client
│   │   ├── types.py             # 数据类型定义（IncomingMessage, CDNMedia 等）/ Dataclass types (IncomingMessage, CDNMedia, etc.)
│   │   ├── crypto.py            # AES-128-ECB 加解密 / AES-128-ECB encrypt/decrypt
│   │   └── errors.py            # 错误类型体系 / Error hierarchy
│   └── utility/
│       ├── basic_utils.py       # 共享工具函数 / Shared utilities (config, platform, markdown)
│       ├── command.py           # 内建命令系统 / Built-in command system
│       ├── cli_args.py          # 命令行参数解析 / CLI argument parsing
│       ├── sys_logger.py        # 日志系统 / Logging system
│       ├── client.py            # LLM 客户端封装 / LLM client wrapper
│       ├── ui_info.py           # TUI 组件 / TUI components (spinner, gradients, prompts)
│       └── agent_listen.py      # 监听TUI（cron/后台Agent/任务/微信监控）/ Listening TUI for cron, background agents, tasks, WeChat
├── config/
│   ├── api_configs.json         # API 连接配置 / API connection configuration
│   └── agent_configs.json       # Agent 运行参数 / Agent runtime parameters
├── skills/                      # 技能定义（每个技能一个子文件夹）/ Skill definitions
├── mcps/
│   ├── mcps_configs.json        # MCP 服务器配置 / MCP server configuration
│   └── sources/                 # MCP 源文件 / MCP source files
├── session/                     # 会话持久化 / Session persistence
├── cron/                        # 持久化定时任务 / Durable cron task persistence
├── log/                         # 日志文件 / Log files
├── doc/                         # 文档 / Documentation
│   ├── img/                     # 图片资源 / Image resources
│   ├── configuration.md         # 完整配置参数参考 / Full configuration reference
│   ├── constants_reference.md   # constants.py 完整参考 / Complete constants.py reference
│   ├── mcp_skills_setup.md      # MCP 与 Skills 详细设置指南 / MCP & Skills detailed setup guide
│   ├── bash_comparison.md       # Bash 命令风险检测对比 / Bash risk evaluation comparison
│   ├── rich_pitfalls.md         # Rich 库开发注意事项 / Rich development pitfalls
│   ├── task_management_comparison.md  # 任务管理机制对比研究 / Task management comparison
│   ├── subagent_comparison.md   # Subagent 架构对比分析 / Subagent architecture comparison
│   └── ref/                     # 参考系统提示词 / Reference system prompts
├── test/                        # 单元测试 / Unit tests
└── requirements.txt
```

---

## 延伸阅读 | Further Reading

- [配置参数参考 | Configuration Reference](./doc/configuration.md) — `api_configs.json` & `agent_configs.json` 完整参数说明 / All parameter descriptions
- [常量参考 | Constants Reference](./doc/constants_reference.md) — `constants.py` 完整参考：工具名称、Bash风险等级、UI配置等 / Tool names, bash risk levels, UI configs, etc.
- [MCP 与 Skills 设置指南 | MCP & Skills Setup Guide](./doc/mcp_skills_setup.md) — MCP 服务器与技能详细设置指南 / Detailed setup guide for MCP servers and skills
- [Rich 开发注意事项 | Rich Development Pitfalls](./doc/rich_pitfalls.md) — 终端 TUI 预览功能开发中遇到的 Rich 库关键问题与解决方案 / Key issues and solutions when developing TUI preview features with the Rich library
- [任务管理机制对比研究 | Task Management Comparison](./doc/task_management_comparison.md) — 四款主流 coding agent 任务管理机制横向对比与设计参考 / Horizontal comparison of task management across four major coding agents
- [Subagent 架构对比分析 | Subagent Architecture Comparison](./doc/subagent_comparison.md) — Claude Code · CodeWhale · Codex · OpenCode 四款 Agent 架构深度对比 / In-depth comparison of subagent/task architectures across four coding agents

## 致谢 | Acknowledgement

- [isinglch@github](https://github.com/isinglch) — 帮助发现并定位项目中的 Bug，参与了功能测试与验证工作 / Helped identify and locate bugs, participated in feature testing and verification
