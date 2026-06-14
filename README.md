# TECoSim Agent: 从跨层次建模到智能体设计
# TECoSim Agent: From Cross-level Modeling to Intelligent Design

<div align="center" style="margin-top: 50px;">
  <img src="./doc/img/logo.png" width="75%" />
</div>

## 简介 | Introduction
### 背景 | Background
现代显示系统是**多层次嵌套的复杂系统**（物理层 → 器件层 → 电路层 → 面板层 → 应用层 → 系统性能层）。层次间的深度耦合产生了横跨多层级的复杂现象——**电压降效应**（IR Drop）、**热电耦合效应**（Thermo-Electrical Coupling）、**显示残影**（Ghost Shadow）等，这些不良现象严重影响显示质量，且无法在单个层次分析捕捉。
Modern display systems are **multi-level nested complex systems** (Physical → Device → Circuit → Panel → Application → System Performance). The deep inter-level coupling produces complex phenomena spanning multiple layers — **IR drop**, **thermo-electrical coupling**, **ghost shadow** — which severely degrade display quality and cannot be captured by single-level analysis.

<div align="center">
  <img src="./doc/img/hierarchy_of_displays.png" width="100%" />
</div>

[TECoSim仿真器](https://github.com/YunTing-k/TECoSim)（暂未开源）正是为建模这些跨层次耦合效应而生，采用**自底向上逐层抽象**与**系统级端到端仿真**相结合的**跨层次协同仿真方法**。
The [TECoSim Simulator](https://github.com/YunTing-k/TECoSim) (not yet open-source) was built specifically to model these cross-level coupling effects, using a **cross-level co-simulation** approach combining **bottom-up abstraction** with **system-level end-to-end simulation**.

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
| 1 | **自然语言驱动** Natural language driven | 描述目标，智能体自动完成设计、仿真、验证全流程 / Describe goals, the agent handles the full workflow |
| 2 | **TECoSim 无缝集成** Seamless integration | 自动配置仿真参数、调用仿真器、解析输出结果 / Auto-configures params, invokes simulator, parses results |
| 3 | **子Agent协作** Subagent | 并发启动 explorer/worker/scheduler 类型子Agent，支持前台阻塞/后台异步模式，共享任务看板 / Parallel subagents with foreground/background modes and shared scoreboard |
| 5 | **任务看板** Scoreboard | 线程安全的任务系统，依赖管理与状态流转，子Agent任务可被主Agent认领 / Thread-safe tasks with dependency tracking, subagent-created tasks claimable by main agent |
| 6 | **内置工具与权限** Tools & permissions | 文件I/O、Shell、网页获取/搜索、定时任务；所有敏感操作需用户TUI确认 / File I/O, bash, web fetch/search, cron; TUI permission for all sensitive ops |
| 7 | **MCP 与技能** MCP & skills | stdio/http/sse MCP 服务器接入，Anthropic 式技能框架按需加载 / MCP server integration + Anthropic-style skill framework with on-demand loading |

---

## 快速开始 | Quick Start

### 环境要求 | Requirements

- **Python**: 3.12.x
- **操作系统 OS**: Windows / Linux / macOS
- **可选 Optional**: TECoSim 仿真器（如有需求请联系作者获取）/ TECoSim simulator (contact the author if needed)

### 安装与配置 | Installation and Configuration

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

首次使用前需修改默认配置文件，见 [基础配置](#基础配置--essential-configurations)。
Configure the default config files before first use, see [Configuration](#基础配置--essential-configurations).

### 首次启动 | First Launch

```bash
python -m src.main
```

加载完毕后即可在输入框下达指令 / Once loaded, type your instructions in the prompt.

## 多Agent协作 | Subagent Coordination

Agent 支持通过 `spawn_agent` 工具并发启动多个专业化子Agent，实现任务的并行分解与异步执行：
The agent supports concurrent subagent spawning via `spawn_agent` for parallel task decomposition:

| Agent 类型 Type | 能力 Capability |
|----------------|---------------|
| `explorer` | 只读代码探索、文件搜索、网页获取 / Read-only exploration & search |
| `worker` | 完整工具集的通用任务执行 / General-purpose with full toolset |
| `scheduler` | 共享任务看板，负责任务分解与依赖规划 / Shares scoreboard for task planning |

子Agent 支持**前台**（阻塞等待结果）和**后台**（异步运行，完成时自动通知）两种模式。后台 Agent 在 REPL 空闲时通过监听 TUI 自动递交结果。主Agent可自动调用，或者用户显式要求。
Subagents support **foreground** (blocking) and **background** (async with auto-notification) modes. Background agent results are delivered automatically when the REPL is idle.

---

## 基础配置 | Essential Configurations

安装后，需要配置 `./config/` 下的文件：
After installation, configure these files in `./config/`:

### 1. API 连接配置 | API Connection (`api_configs.json`)

必须设置 LLM API 端点与密钥：
You must set your LLM API endpoint and key:

| 参数 Parameter | 需设置 What to set |
|-----------|-------------|
| `API_URL` | API 请求地址 / Your API base URL (e.g., OpenAI, DeepSeek, etc.) |
| `API_KEY` | API 密钥 / Your API authentication key |
| `MAIN_MODEL_NAME` | 主模型（复杂任务）/ Model for complex tasks (e.g., `gpt-4o`, `deepseek-v4-pro`) |
| `FAST_MODEL_NAME` | 快速模型（简单任务）/ Model for simple tasks (e.g., `gpt-4o-mini`) |

### 2. Agent 运行参数 | Agent Runtime (`agent_configs.json`)

| 参数 Parameter | 默认值 Default | 说明 Why it matters |
|-----------|---------|----------------|
| `SIMULATOR_PATH` | _(空 empty)_ | **如使用 TECoSim 必须设置** — 仿真器可执行文件路径 / **Must set** if using TECoSim |
| `BASH_PATH` | `"bash"` | **GNU Bash** 的路径（不支持 cmd/pwsh，见下文）/ Path to **GNU Bash** (cmd/pwsh not supported) |
| `RIPGREP_PATH` | `"rg"` | `ripgrep` 可执行文件路径 / Path to `ripgrep` executable |
| `WEB_SEARCH_BACKEND` | _(空 empty)_ | 网络搜索后端，可选：`Exa`、`Tavily`、`Linkup`、`DDGS` / Set to enable web search |
| `WEB_SEARCH_API_KEY` | _(空 empty)_ | 网络搜索 API Key / API key for your web search backend |
| `DISPLAY_RESPONSE_REASON` | `true` | 是否显示 LLM 推理过程（关闭时显示 "Thinking ..." 占位）/ Whether to display LLM reasoning content |

### 3. Bash 与 ripgrep 路径说明 | Bash & ripgrep Notes

**`BASH_PATH` 必须指向 GNU Bash**（不可用 cmd/PowerShell）。Agent 通过 `bash -c` 执行命令，并内置基于 Bash 语义的风险检测引擎。
**`BASH_PATH` must point to GNU Bash** (not cmd/PowerShell). The agent executes commands via `bash -c` with Bash-semantics-based risk detection.

> **⚠️ 安全建议 | Security Advisory** — Agent 可通过 `bash` 执行任意系统命令，风险检测并非绝对可靠。强烈建议在沙箱环境（Docker/VM/隔离服务器）中以最小权限账户运行，并用 `/readonly_add` 保护关键路径。
> The agent can execute arbitrary system commands via `bash`. Risk detection is not infallible. Run in a sandbox (Docker/VM/isolated server) with least-privilege account; use `/readonly_add` to protect critical paths.

**ripgrep** — `grep_file` 工具依赖 ripgrep（`rg`）。安装：`winget install BurntSushi.ripgrep`（Win）/ `sudo apt install ripgrep`（Linux）/ `brew install ripgrep`（macOS）。或在 `agent_configs.json` 中设 `RIPGREP_PATH`。
**ripgrep** — the `grep_file` tool requires ripgrep (`rg`). Install via your package manager, or set `RIPGREP_PATH` in `agent_configs.json`.

> 完整参数列表请参阅 | See [Configuration Reference](./doc/configuration.md) for all available parameters.

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
python -m src.main                        # 启动Agent / Launch agent
python -m src.main -l                     # 启用开发者日志 / Launch with developer logs
python -m src.main -r <UUID>              # 恢复指定会话 / Resume a session
python -m src.main --nosystem             # 禁用系统提示词 / Disable system prompts
python -m src.main --notools              # 禁用工具 / Disable agent tools
python -m src.main --nocrons              # 禁用定时任务 / Disable cron tasks
python -m src.main --noskills             # 禁用技能 / Disable skills
python -m src.main --nomcps               # 禁用MCP / Disable MCPs
python -m src.main --dangerously_allow_all # ⚠️ 允许所有权限 / Allow all permissions
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
│   └── utility/
│       ├── basic_utils.py       # 共享工具函数 / Shared utilities (config, platform, markdown)
│       ├── command.py           # 内建命令系统 / Built-in command system
│       ├── cli_args.py          # 命令行参数解析 / CLI argument parsing
│       ├── sys_logger.py        # 日志系统 / Logging system
│       ├── client.py            # LLM 客户端封装 / LLM client wrapper
│       ├── ui_info.py           # TUI 组件 / TUI components (spinner, gradients, prompts)
│       └── agent_listen.py      # 监听TUI（cron/后台Agent/任务监控）/ Listening TUI for cron/background agents/task monitoring
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
