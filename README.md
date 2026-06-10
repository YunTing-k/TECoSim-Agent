# TECoSim Agent: 从跨层次建模到智能体设计
# TECoSim Agent: From Cross-level Modeling to Intelligent Design

<div align="center" style="margin-top: 50px;">
  <img src="./doc/img/logo.png" width="75%" />
</div>

## 简介 | Introduction
### 背景 | Background
现代显示系统一个是典型的具有**多个层次的耦合嵌套的复杂系统**，并可按照设计层次大致划分为物理层、器件层、电路层、面板/宏电路层、驱动/应用层与系统性能层等六个层次。
The modern display systems represent a **complex multi-level coupled hierarchical system**, which can be fundamentally categorized into six design layers: Physical layer, Device layer, Circuit layer, Panel/macro-circuit layer, Driver/application layer, System performance layer.

<div align="center">
  <img src="./doc/img/hierarchy_of_displays.png" width="100%" />
</div>

之前的个人项目[TECoSim仿真器](https://github.com/YunTing-k/TECoSim) （暂未开源），采用**自底向上逐层抽象** + **系统级端到端仿真** 的**跨层次协同的仿真方法**对显示系统进行建模与仿真。
With my previous project [TECoSim Simulator](https://github.com/YunTing-k/TECoSim) (not open yet), we can model the display system with a **cross-level co-simulation methodology** that combines **bottom-up hierarchical abstraction** with **system-level end-to-end simulation**.

建模的层级包括 | The modeling levels includes:
1. - **物理层（Material/Interface）**：底层物理材料、界面的光、电学特性
   - **Material/Interface**: The optoelectronic properties of physical materials and interfaces
2. - **器件层（Semiconductor Device）**：驱动晶体管的电流电压、温敏、迟滞特性
   - **Semiconductor Device**: I-V characteristics, thermal sensitivity, and hysteresis behaviors of semiconductor devices
3. - **电路层（Pixel Circuit）**：多个半导体器件组成的像素电路
   - **Pixel Circuit**: Pixel circuits integrate multiple semiconductor devices
4. - **面板/宏电路层（Display Panel）**：由规模化集成的像素电路，考虑寄生电阻/电容的电源网络，以及宏观材质构成的显示面板
   - **Display Panel**: Display panel consisting of a large-scale integrated pixel circuits, power supply network considering parasitic resistance/capacitance, and macro-scale material property
5. - **驱动/应用层（Driving Scheme）**：显示面板的刷新率、灰阶映射算法、颜色抖动算法、亮度控制算法等
   - **Driving Scheme**: Refresh rate, gray-scale mapping algorithms, color dithering, and brightness control schemes, etc.
6. - **系统性能层（Display Quality）**：由以上所有嵌套耦合层次所共同决定的系统最终性能,如显示面板的显示不均一性、色偏、伪影
   - **Display Quality**: The final system performance co-determined by all the above nested coupled hierarchies, such as display non-uniformity, color shift, and artifacts in the display panel

### 敏捷设计的困境 | Dilemma of Agile Design
TECoSim仿真器的提出是为了对多层次耦合的复杂显示系统进行建模与仿真，以便为显示面板设计提供量化的指导，加快前期设计、验证等流程的迭代收敛。
The TECoSim simulator was proposed to model and simulate complex multi-level coupled display systems, aiming to provide quantitative guidance for display panel design and accelerate the iterative convergence of early-stage design, verification, and related processes.

1. 然而TECoSim的跨层级的建模范式使得其使用**门槛较高**，使用者既需要理解从底层到顶层多个不同的设计领域，还需要对数值计算方法也需要有基本的了解，才能针对性地进行参数调优，开展设计与仿真工作。
However, the cross-level modeling paradigm of TECoSim results in a **high barrier to entry**. Users need to understand multiple different design domains ranging from the bottom level to the top level, as well as have a basic understanding of numerical computation methods, in order to perform targeted parameter tuning and carry out design and simulation work effectively.

2. 此外，TECoSim只提供了“设计输入-结果输出”范式的仿真，对于显示系统的优化只能**依赖专家调优**，缺乏高效的自动化调优方法以实现“指标输入-设计输出”的高效设计范式。
Furthermore, TECoSim only provides a "design input → result output" simulation paradigm. Optimization of the display system can only **rely on expert tuning**, lacking efficient automated optimization methods to achieve an efficient "specification input → design output" design paradigm.

---

以上问题限制了TECoSim及其背后的跨层次建模思想在真实场景下的能力，因此诞生了**TECoSim Agent**项目。
These issues limit the capability of TECoSim and the underlying cross-layer modeling philosophy in real-world scenarios, which led to the creation of the **TECoSim Agent** project.

---

### 项目贡献 | Contribution of this Project

**TECoSim Agent** 是一个嵌入了 TECoSim 仿真器的 LLM 智能体——通过 Harness 封装调用 TECoSim，提供端到端的显示面板设计能力：
**TECoSim Agent** is an LLM-powered agent that embeds the TECoSim simulator — invoking it through a dedicated harness for end-to-end display panel design:

---

**核心能力 | Core Capabilities**

- **端到端面板设计** — 根据用户指标，自动完成面板初始化设计、仿真配置、运行与结果分析
  **End-to-end panel design** — handles design initialization, simulation configuration, execution, and result analysis per user specifications
- **自然语言交互** — 无需深入了解底层仿真参数，通过对话即可完成设计迭代
  **Natural language interface** — iterate designs through conversation, no need to master low-level simulation parameters

**主要特性 | Key Features**

| # | 特性 Feature | 说明 Description |
|---|-------------|------------------|
| 1 | **自然语言驱动** Natural language driven | 描述目标，智能体自动完成设计、仿真、验证全流程 / Describe goals, the agent handles the full workflow |
| 2 | **TECoSim 无缝集成** Seamless integration | 自动配置仿真参数、调用仿真器、解析输出结果 / Auto-configures params, invokes simulator, parses results |
| 3 | **内置工具** built-in tools | 文件操作、Shell、网页获取、网络搜索、定时任务、任务看板等 / File I/O, bash, web fetch/search, cron, scoreboard |
| 4 | **双模型架构** Dual-model | 主模型处理复杂任务，快速模型处理简单任务，兼顾能力与效率 / Primary for complex, fast for simple — balancing capability and efficiency |
| 5 | **任务看板** Scoreboard | 线程安全的任务系统，支持创建/更新/查询、状态流转与依赖管理 / Thread-safe task management with status transitions and dependency tracking |
| 6 | **权限控制** Permission control | 所有敏感操作需用户 TUI 确认 / All sensitive operations require user confirmation via TUI |
| 7 | **会话管理** Session management | 多会话创建/恢复/删除，自动保存上下文与消息历史 / Multi-session create/resume/delete with auto-save |
| 8 | **技能系统** Skill system | Anthropic 式技能框架，支持渐进式披露与按需加载 / Anthropic-style skill framework with on-demand loading |
| 9 | **MCP 协议** MCP protocol | 支持 stdio/http/sse 传输的 MCP 服务器接入 / MCP server integration via stdio/http/sse transports |
| 10 | **定时任务** Cron tasks | 标准 cron 表达式，支持一次性与重复任务，REPL 空闲时自动触发 / Standard cron, one-shot/recurring, auto-triggered when REPL is idle |

---

## 快速开始 | Quick Start

### 环境要求 | Requirements

- **Python**: 3.12.x
- **操作系统 OS**: Windows / Linux / macOS
- **可选 Optional**: TECoSim 仿真器（仿真功能需要，如有需求请联系作者获取）/ TECoSim simulator (required for simulation features, contact the author if needed)

### 安装 | Installation

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

### 首次启动 | First Launch

```bash
python -m src.main
```

首次启动时，Agent 会自动创建默认配置文件。你需要根据环境配置它们（见下文）。
On first launch, the agent will create default config files. You'll need to configure them before use (see below).

---

## 上手配置 | Onboarding: Essential Configurations

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

### 3. Bash 与 ripgrep 路径说明 | Bash & ripgrep Notes

#### Bash 路径 | Bash Path

**`BASH_PATH` 必须指向标准 GNU Bash**，不可使用 `cmd.exe` 或 `PowerShell`。
**`BASH_PATH` must point to standard GNU Bash**, not cmd.exe or PowerShell.

原因如下 | Why:
- Agent 通过 `bash -c "<command>"` 的方式调用子进程执行命令（见 `tool_def.py` 的 `bash` 函数），`-c` 是 GNU Bash 的标准参数
  The agent uses `bash -c "<command>"` via `subprocess.Popen` (function `bash` in `tool_def.py`), and `-c` is the standard GNU Bash flag
- `cmd.exe` 使用 `/c`，PowerShell 使用 `-Command`，三者互不兼容
  `cmd.exe` uses `/c`, PowerShell uses `-Command` — they are incompatible with each other
- Agent 内置了命令风险检测引擎（`evaluate_bash_risk`），该检测基于 Bash 语义设计，若替换为 cmd/pwsh 可能导致风险判断失效
  The built-in command risk detection (`evaluate_bash_risk`) is designed for Bash semantics; using cmd/pwsh may bypass security checks

#### ripgrep 路径 | ripgrep Path

Agent 通过 `grep_file` 工具调用 ripgrep（`rg`）进行文件内容搜索。安装方式：
The agent calls ripgrep (`rg`) via the `grep_file` tool for content search. Install with:

- **Windows**: `winget install BurntSushi.ripgrep` 或 `scoop install ripgrep`
- **Linux**: `sudo apt install ripgrep`（或其他包管理器 / or your package manager）
- **macOS**: `brew install ripgrep`

安装后确保 `rg` 在系统 PATH 中，或在 `agent_configs.json` 中配置 `RIPGREP_PATH`。
Then ensure `rg` is in your system PATH, or configure `RIPGREP_PATH` in `agent_configs.json`.

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

> **仿真工作流示例 | Example Workflow**:
> 1. `check_simulator` — 验证仿真器路径与可执行文件 / Verify simulator path and executable
> 2. `init_design` — 初始化设计（自动生成默认配置）/ Initialize a design with default configs
> 3. `launch_sim` — 启动仿真 / Launch the simulation
> 4. `query_run` — 查看运行状态（DONE/FAIL/TIMEOUT）/ Check run status
> 5. `read_log` — 读取仿真日志分析结果 / Read logs to analyze results

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
| `/update_title` | 用 LLM 自动更新当前会话标题 / Auto-update current session title with LLM |
| `/set_title <TITLE>` | 手动设置当前会话标题 / Manually set current session title |

---

## 项目结构 | Project Structure

```
TECoSimAgent/
├── src/
│   ├── main.py                  # 入口与主循环 / Entry point & agent loop
│   ├── constants.py             # 全局常量与默认参数 / All global constants & defaults
│   ├── context/
│   │   ├── agent_context.py     # 集中式Agent状态管理 / Central agent state management
│   │   ├── prompt.py            # 提示词组装与LLM响应处理 / Prompt assembly & LLM response handling
│   │   └── session.py           # 会话持久化管理 / Session persistence management
│   ├── tool/
│   │   ├── tool_def.py          # 工具定义与实现（24+工具）/ Tool definitions & implementations
│   │   ├── tool_execute.py      # 工具执行调度器 / Tool execution dispatcher
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
│       └── agent_listen.py      # 监听TUI（cron/任务监控）/ Listening TUI for cron/task monitoring
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
│   └── mcp_skills_setup.md      # MCP 与 Skills 详细设置指南 / MCP & Skills detailed setup guide
└── requirements.txt
```

---

## 延伸阅读 | Further Reading

- [配置参数参考 | Configuration Reference](./doc/configuration.md) — `api_configs.json` & `agent_configs.json` 完整参数说明 / All parameter descriptions
- [常量参考 | Constants Reference](./doc/constants_reference.md) — `constants.py` 完整参考：工具名称、Bash风险等级、UI配置等 / Tool names, bash risk levels, UI configs, etc.
- [MCP 与 Skills 设置指南 | MCP & Skills Setup Guide](./doc/mcp_skills_setup.md) — MCP 服务器与技能详细设置指南 / Detailed setup guide for MCP servers and skills

## 致谢 | Acknowledgement

- [isinglch@github](https://github.com/isinglch) — 帮助发现并定位项目中的 Bug，参与了功能测试与验证工作 / Helped identify and locate bugs, participated in feature testing and verification
