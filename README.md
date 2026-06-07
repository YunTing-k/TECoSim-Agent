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


### 项目贡献 | Contribution of this Project
本项目还在开发中，以下是本项目想要完成的基本目标：
This project is still under development. The basic goals are as follows:

**核心目标 | Core Goal**
- 基于TECoSim仿真器，实现一个基于大语言模型的智能体。只用自然语言交互与极少专家干预，根据用户预期的显示面板指标完成整体面板的设计、仿真、验证等工作
- Based on the TECoSim simulator, implement an intelligent agent powered by large language model. Using only natural language interaction and minimal expert intervention, the agent is able to complete the overall panel design, simulation, verification, and related tasks according to the user's expected display panel specifications.

**主要特性 | Main Features**
1. 智能体能够调用TECoSim，自动配置最优仿真参数，解析仿真器输出结果并给出优化建议
    The agent is able to invoke TECoSim, automatically configure the optimal simulation parameters, parse the simulator's output results, and provide optimization suggestions.
2. 智能体能够调用基于神经网络的代理模型，进一步加速耗时的物理场、电路的求解
    The agent is able to invoke neural network-based agent models to further accelerate the solution of time-consuming physical field and circuit simulations.
3. 智能体能基于BO等方法，实现高效的设计空间探索以及多目标的设计优化
    The agent is capable of efficient design space exploration and multi-objective design optimization using methods such as Bayesian Optimization (BO).

---

## 项目特性 | Features

- **自然语言驱动的显示面板设计**：只需用自然语言描述设计目标，智能体自动完成面板设计、仿真、验证全流程
  **Natural language driven display panel design**: Simply describe your design goals in natural language, and the agent automatically completes the entire workflow of panel design, simulation, and verification
- **TECoSim 仿真器无缝集成**：智能体自动配置仿真参数、调用仿真器、解析输出结果
  **Seamless TECoSim simulator integration**: The agent automatically configures simulation parameters, invokes the simulator, and parses output results
- **多工具协同**：内置 20+ 工具（文件操作、Shell 执行、网页获取、网络搜索、定时任务、任务看板等）
  **Multi-tool collaboration**: Built-in 20+ tools (file operations, shell execution, web fetching, web search, cron tasks, scoreboard tasks, etc.)
- **双模型架构**：主模型处理复杂/模糊任务，快速模型处理简单/确定性任务
  **Dual-model architecture**: Primary model handles complex/ambiguous tasks, fast model handles simple/deterministic tasks
- **Agent 任务看板（Scoreboard）**：线程安全的任务系统，支持任务创建/更新/查询/列表、状态流转与依赖管理，在监听 TUI 和执行 Spinner 中实时显示任务进度
  **Agent scoreboard task system**: Thread-safe task management with create/update/get/list operations, status transitions and dependency tracking, with real-time progress display in listening TUI and execution spinner
- **完善的权限控制**：所有敏感操作均需用户通过 TUI 确认
  **Comprehensive permission control**: All sensitive operations require user confirmation via TUI
- **会话管理**：支持多会话创建/恢复/删除，自动保存上下文与消息历史
  **Session management**: Supports multi-session create/resume/delete with automatic context and message history persistence
- **Agent 技能系统**：标准 Anthropic 式技能框架，支持渐进式披露与按需加载
  **Agent skill system**: Standard Anthropic-style skill framework with progressive disclosure and on-demand loading
- **MCP 协议支持**：支持 stdio/http/sse 传输的 MCP 服务器接入
  **MCP protocol support**: Supports MCP server integration via stdio/http/sse transports
- **定时任务系统**：标准 cron 表达式，支持一次性与重复任务，REPL 空闲时自动监听与触发
  **Cron task system**: Standard cron expressions, supports one-shot and recurring tasks, auto-monitoring and triggering when REPL is idle

---

## 安装 | Installation

### 环境要求 | Requirements

- **Python**: 3.12.11（推荐，其他 3.12.x 版本亦可）
  **Python**: 3.12.11 (recommended, other 3.12.x versions should also work)
- **操作系统**: Windows / Linux / macOS
  **OS**: Windows / Linux / macOS
- **可选依赖**: TECoSim 仿真器（如需使用仿真功能）
  **Optional dependency**: TECoSim simulator (required for simulation features)

### 步骤 | Steps

```bash
# 1. 克隆仓库 | Clone the repository
git clone https://github.com/YunTing-k/TECoSimAgent.git
cd TECoSimAgent

# 2. 创建虚拟环境（推荐） | Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Linux / macOS
# 或 | or
venv\Scripts\activate         # Windows

# 3. 安装依赖 | Install dependencies
pip install -r requirements.txt
```

---

## 使用方法 | Usage

### 启动 Agent | Launch the Agent

```bash
python -m src.main
```

### 命令行参数 | CLI Arguments

| 参数 Param | 说明 Description |
|------|-------------------|
| `-l`, `--log` | 启用开发者日志（输出到控制台） / Enable developer logger (output to console) |
| `-r <UUID>`, `--resume <UUID>` | 恢复指定会话 / Resume a session with given UUID |
| `--nosystem` | 禁用主智能体系统提示词 / Disable main agent's system prompts |
| `--notools` | 禁用主智能体工具 / Disable main agent's tools |
| `--nocrons` | 禁用所有定时任务 / Disable all cron tasks |
| `--noskills` | 禁用所有技能 / Disable all skills |
| `--nomcps` | 禁用所有 MCP / Disable all MCPs |
| `--dangerously_allow_all` | **危险**：允许所有权限（可能损坏您的文件或系统） / **Dangerous**: Allow all permissions (may damage your files or system) |

### 子命令 | Sub-commands

```bash
# 会话管理 | Session management
python -m src.main session list              # 列出所有会话 | List all sessions
python -m src.main session remove <UUID>     # 删除指定会话 | Remove a session

# 持久化定时任务管理 | Durable cron management
python -m src.main cron list                 # 列出持久化定时任务 | List durable cron tasks
python -m src.main cron remove <ID>          # 删除持久化定时任务 | Remove a durable cron task

# 技能管理 | Skill management
python -m src.main skill list                # 列出所有可用技能 | List all available skills

# MCP 管理 | MCP management
python -m src.main mcp list                  # 列出所有 MCP 服务器 | List all MCP servers
python -m src.main mcp add <name> <type> <params>    # 添加 MCP 服务器（params 为 JSON 字符串）
                                                     # Add an MCP server (params is JSON string)
python -m src.main mcp toggle <name>         # 启用/禁用 MCP 服务器 | Enable/disable an MCP server
python -m src.main mcp remove <name>         # 移除 MCP 服务器 | Remove an MCP server
```

---

## 内建命令 | Built-in Commands

在 Agent 交互界面中，所有命令以 `/` 开头：
All commands start with `/` in the agent interaction interface:

| 命令 Command | 功能 Description |
|------|--------------------|
| `/help` | 查看所有可用命令 / Show all available commands |
| `/design_list` | 查询设计列表 / Query design list |
| `/run_list` | 查询运行次数 / Query run count |
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
| `/update_title` | 更新当前会话标题 / Update current session title |

---

## MCP 与 Skills 配置 | MCP & Skills Setup

### Skills（技能）

Skills 存放在 `./skills/` 目录下，每个技能为一个子文件夹，内含 `SKILL.md` 文件，格式如下：
Skills are stored in the `./skills/` directory. Each skill is a subfolder containing a `SKILL.md` file with the following format:

```markdown
---
name: skill-name
description: Brief description of this skill
---

## Skill content

...
```

启动 Agent 时会自动扫描并注册所有技能。可通过 `/<skill_name>` 手动加载技能到上下文，或由 LLM 按需调用 `skill` 工具加载。
When the agent starts, all skills are automatically scanned and registered. You can manually load a skill into context via `/<skill_name>`, or let the LLM invoke the `skill` tool on demand.

### MCP（模型上下文协议）

MCP 配置文件路径为 `./mcps/mcps_configs.json`，支持三种传输类型。
MCP config file is located at `./mcps/mcps_configs.json`, supporting three transport types.

**推荐方式：通过命令行安装 | Recommended: Install via CLI**

优先使用命令行管理 MCP，命令行无法满足需求时再手动编辑配置文件。
Prefer using the CLI to manage MCPs. Only manually edit the config file when the CLI cannot meet your needs.

#### 命令行管理 | CLI Management

```bash
# 查看所有 MCP 服务器 | List all MCP servers
python -m src.main mcp list

# 添加 stdio 类型 MCP（PowerShell）| Add a stdio MCP (PowerShell)
python -m src.main mcp add my-server stdio '{"command": "node", "args": ["server.js"]}'

# 添加 stdio 类型 MCP（cmd.exe）| Add a stdio MCP (cmd.exe)
python -m src.main mcp add my-server stdio "{\"command\": \"node\", \"args\": [\"server.js\"]}"

# 添加 http 类型 MCP | Add an http MCP
python -m src.main mcp add my-server-http http '{"url": "http://localhost:8080/mcp"}'

# 添加 sse 类型 MCP | Add an sse MCP
python -m src.main mcp add my-server-sse sse '{"url": "http://localhost:8080/sse"}'

# 启用/禁用 MCP 服务器 | Enable/disable an MCP server
python -m src.main mcp toggle my-server

# 移除 MCP 服务器 | Remove an MCP server
python -m src.main mcp remove my-server
```

> **⚠️ Windows 引号问题 | Windows Quoting Issue**
>
> **cmd.exe** 不识别单引号，必须用双引号包裹 JSON，内部双引号用 `\"` 转义。
> **PowerShell** 支持单引号，可直接使用 `'{"key": "value"}'`。
>
> **cmd.exe** does not recognize single quotes. You must wrap the JSON with double quotes and escape inner double quotes with `\"`.
> **PowerShell** supports single quotes, so `'{"key": "value"}'` works directly.

#### 关于 `args` 参数 | Notes on `args`

`args` 必须是一个 **JSON 字符串数组**，而非单个字符串。错误示例中 `"args": "-m my_mcp_server"` 是单个字符串，会被 `json.loads` 解析为字符串而非数组：
`args` must be **a JSON array of strings**, not a single string. In the wrong example below, `"args": "-m my_mcp_server"` is a single string, which will be parsed as a string instead of an array:

```bash
# PowerShell ✅ 正确 | Correct — JSON array of strings
python -m src.main mcp add my-server stdio `
  '{"command": "python", "args": ["-m", "my_mcp_server", "--port", "8080"]}'

# cmd.exe ✅ 正确 | Correct — JSON array of strings (escaped)
python -m src.main mcp add my-server stdio ^
  "{\"command\": \"python\", \"args\": [\"-m\", \"my_mcp_server\", \"--port\", \"8080\"]}"

# ❌ 错误 | Wrong — single string is not an array
python -m src.main mcp add my-server stdio '{"command": "python", "args": "-m my_mcp_server"}'
```

#### 各类 MCP 的完整参数 | Full Parameters by MCP Type

**stdio 类型**（通过子进程启动的 MCP 服务器）：

| 参数 Param | 是否必填 Require | 说明 Description |
|------------|-----------------|------------------|
| `command`  | **是 Yes** | 可执行文件路径或命令名 / Executable path or command name |
| `args`     | **是 Yes** | 命令行参数数组（JSON 字符串数组） / Command-line arguments (JSON array of strings) |
| `env`      | 否 No | 环境变量字典，默认 `null` / Environment variables dict, default `null` |
| `cwd`      | 否 No | 工作目录，默认 `null` / Working directory, default `null` |
| `keep_alive` | 否 No | 是否保持连接，默认 `true` / Keep alive, default `true` |
| `log_file` | 否 No | 日志文件路径，默认 `null` / Log file path, default `null` |

**http/sse 类型**（远程 HTTP 或 SSE 服务器）：

| 参数 Param | 是否必填 Require | 说明 Description |
|-------------|-----------------|------------------|
| `url` | **是 Yes** | 服务器 URL / Server URL |
| `headers` | 否 No | 自定义 HTTP 头字典，默认 `null` / Custom HTTP headers dict, default `null` |
| `auth` | 否 No | 认证信息，默认 `null` / Auth info, default `null` |
| `sse_read_timeout` | 否 No | SSE 读取超时，默认 `null` / SSE read timeout, default `null` |
| `verify` | 否 No | SSL 证书验证，默认 `null` / SSL verification, default `null` |

#### MCP 源文件存放位置 | MCP Source Files Location

MCP 服务器的原始脚本、二进制文件推荐统一存放在 `./mcps/sources/` 目录下，每个 MCP 单独一个子文件夹：

```
mcps/
├── mcps_configs.json          # MCP 配置文件 | MCP config file
├── sources/                   # MCP 源文件存放目录 | MCP source files directory
│   ├── my-python-mcp/
│   │   └── server.py
│   ├── my-node-mcp/
│   │   ├── package.json
│   │   └── server.js
│   └── matlab-mcp/
│       └── matlab-mcp-core-server-win64.exe    # 二进制文件 | Binary executable
```

这样做的好处：统一管理、便于版本控制、避免路径混乱。
Benefits: centralized management, easier version control, and avoiding path confusion.

#### 手动编辑配置文件 | Manual Config File Editing

当命令行安装受限时（如需要复杂嵌套结构），可直接编辑 `./mcps/mcps_configs.json`：
When CLI installation is limited (e.g., complex nested structures needed), you can directly edit `./mcps/mcps_configs.json`:

```json
[
  {
    "name": "my-python-mcp",
    "type": "stdio",
    "if_disabled": false,
    "command": "python",
    "args": ["-m", "my_mcp_server"],
    "env": {"PYTHONPATH": "./mcps/sources/my-python-mcp"},
    "cwd": "./mcps/sources/my-python-mcp",
    "keep_alive": true,
    "log_file": null
  },
  {
    "name": "my-http-mcp",
    "type": "http",
    "if_disabled": false,
    "url": "http://localhost:8080/mcp",
    "headers": {"Authorization": "Bearer token123"},
    "auth": null,
    "sse_read_timeout": null,
    "httpx_client_factory": null,
    "verify": null
  }
]
```

> **提示**: 编辑配置文件后，需要重启 Agent 或通过命令行 `toggle` 后再 `toggle` 来重新加载。
> **Tip**: After editing the config file, restart the Agent or use the CLI `toggle` then `toggle` again to reload.

---

## 配置文件 | Configuration Files

配置文件位于 `./config/` 目录下：
Configuration files are located in the `./config/` directory:

### `api_configs.json` — API 连接配置 | API Connection Configuration

| 参数 Param | 说明 Description |
|------|--------------------|
| `API_URL` | API 请求地址 / API request base URL |
| `API_KEY` | API 密钥 / API authentication key |
| `MAIN_MODEL_NAME` | 主模型名称 / Primary model name |
| `MAIN_MODEL_TEMPERATURE` | 主模型温度参数 / Primary model temperature |
| `MAIN_MODEL_MAX_TOKENS` | 主模型最大输出 Token 数 / Primary model max output tokens |
| `MAIN_MODEL_STREAM` | 主模型是否启用流式输出 / Enable streaming for primary model |
| `MAIN_MODEL_CONTEXT` | 主模型上下文窗口大小 / Primary model context window size |
| `MAIN_MODEL_ENABLE_REASONING` | 主模型是否启用推理 / Enable reasoning for primary model |
| `MAIN_MODEL_REASONING_EFFORT` | 主模型推理强度（low/medium/high）/ Primary model reasoning effort |
| `FAST_MODEL_NAME` | 快速模型名称 / Fast model name |
| `FAST_MODEL_TEMPERATURE` | 快速模型温度参数 / Fast model temperature |
| `FAST_MODEL_MAX_TOKENS` | 快速模型最大输出 Token 数 / Fast model max output tokens |
| `FAST_MODEL_ENABLE_REASONING` | 快速模型是否启用推理 / Enable reasoning for fast model |
| `FAST_MODEL_REASONING_EFFORT` | 快速模型推理强度（low/medium/high）/ Fast model reasoning effort |
| `TIMEOUT_MS` | LLM 请求超时时间（毫秒）/ LLM request timeout (milliseconds) |

### `agent_configs.json` — Agent 运行参数配置 | Agent Runtime Configuration

| 参数 Param | 说明 Description |
|------|--------------------|
| `SIMULATOR_PATH` | TECoSim 仿真器路径 / Path to TECoSim simulator |
| `SIMULATOR_TIMEOUT_S` | 仿真超时时间（秒）/ Simulation timeout (seconds) |
| `MERGE_SYSTEM_PROMPTS` | 是否合并系统提示词 / Whether to merge system prompts |
| `CONTEXT_THRESHOLD` | 上下文阈值比例 / Context threshold ratio |
| `AUTO_SUMMARY_TRIGGER` | 自动摘要触发次数 / Auto summary trigger count |
| `FLATTEN_BEFORE_SUMMARY` | 摘要前是否扁平化消息 / Flatten messages before summary |
| `RANDOM_PROGRESS_TITLE` | 随机进度标题 / Random progress title |
| `RENDER_RESPONSE_AS_MD` | 是否以 Markdown 渲染响应 / Render response as Markdown |
| `RENDER_BASH_AS_MD` | 是否以 Markdown 渲染 Bash 命令输出 / Render bash command output as Markdown |
| `DEEPSEEK_SUPPORT` | 是否启用 DeepSeek 格式支持 / Enable DeepSeek format support |
| `READ_FILE_MB_LIMIT` | 文件读取大小限制（MB）/ File read size limit (MB) |
| `READ_FILE_LLM_KB_LIMIT` | 文件读取 LLM 上下文限制（KB）/ File read LLM context limit (KB) |
| `URL_TIMEOUT_S` | 网页获取超时（秒）/ Web fetch timeout (seconds) |
| `URL_CACHE_TIME_S` | URL 缓存时间（秒）/ URL cache time (seconds) |
| `WEB_SEARCH_BACKEND` | 网络搜索后端 / Web search backend |
| `WEB_SEARCH_API_KEY` | 网络搜索 API Key / Web search API key |
| `WEB_SEARCH_TIMEOUT_S` | 网络搜索超时（秒）/ Web search timeout (seconds) |
| `GREP_FILE_TIMEOUT_S` | 文件搜索超时（秒）/ File search timeout (seconds) |
| `MCP_INIT_TIMEOUT_S` | MCP 初始化超时（秒）/ MCP init timeout (seconds) |
| `MCP_TIMEOUT_S` | MCP 调用超时（秒）/ MCP call timeout (seconds) |

---

## `constants.py` 说明 | About `constants.py`

`src/constants.py` 集中管理所有全局常量与默认参数。**所有 Agent 工具名称均在此集中定义**，便于统一调整命名与重构。文件按功能划分为以下类别：

`src/constants.py` centralizes all global constants and default parameters. **All agent tool names are defined centrally here** for unified naming adjustments and refactoring. The file is organized into the following categories:

### 概览 | Overview

| 类别 Category | 说明 Description |
|---------------|------------------|
| 版本号 Version | Agent 当前版本号 / Current agent version |
| 基础路径 Base Paths | 日志、会话、配置、技能、MCP、cron 等路径 / Paths for logs, sessions, configs, skills, MCPs, crons |
| 文件命名规范 File Naming | 会话目录下的子文件命名 / File names under session directories |
| 状态标签 Status Labels | 工具/操作返回的状态标签（失败、成功、超时、禁用等）及任务状态（pending/in_progress/completed/deleted）/ Status labels for tool/operation returns and task statuses |
| **工具名称 Tool Names** | **所有 Agent 工具的字符串名称（可统一修改）/ All tool string names (centrally managed)** |
| 工具参数 Tool Params | 各工具的默认参数与行为限制 / Default params and limits for tools |
| Bash 风险等级 Bash Risk | Bash 命令的风险分类标签 / Risk classification labels for bash commands |
| UI 配置 UI Configs | 颜色、图标、进度条、提示词列表 / Colors, icons, progress bars, prompt lists |
| 任务看板 Task Board | Scoreboard 任务系统的图标、颜色、状态显示参数 / Task display params for Scoreboard |
| 监听 TUI Listen TUI | Agent 监听模式的渐变色彩与动画参数 / Listen TUI gradient color and animation params |
| 流式显示 Streaming | LLM 流式响应与 TUI 的显示参数 / Display params for streaming LLM responses |
| 编辑视图 Edit View | 文件编辑 TUI 的 diff 视图参数 / Diff view params for file edit TUI |
| Bash 视图 Bash View | Bash 命令输出的行号视图参数 / Line number view params for bash output |
| URL 缓存 URL Cache | URL 缓存显示参数 / URL cache display params |
| MCP 参数 MCP Params | MCP 工具描述显示限制 / MCP tool description limit |

### 工具名称列表 | Tool Names List

所有工具名称集中定义在 `TOOL_NAME_*` 常量中。如需修改某个工具的名称（例如避免与 MCP 工具重名），只需在此修改一处即可全局生效：

All tool names are defined in `TOOL_NAME_*` constants. To rename a tool (e.g., to avoid conflicts with MCP tools), change it here — it takes effect everywhere:

| 常量 Constant | 默认名称 Default Name | 用途 Purpose |
|---------------|----------------------|---------------|
| `TOOL_NAME_VERSION` | `agent_version` | 获取 Agent 版本 / Get agent version |
| `TOOL_NAME_ASK_QUESTION` | `ask_user_question` | 向用户提问 / Ask user structured questions |
| `TOOL_NAME_CREATE_CRON` | `create_cron` | 创建定时任务 / Create a cron task |
| `TOOL_NAME_QUERY_CRON` | `query_cron` | 查询定时任务列表 / Query cron task list |
| `TOOL_NAME_REMOVE_CRON` | `remove_cron` | 删除定时任务 / Remove a cron task |
| `TOOL_NAME_CREATE_TASK` | `create_task` | 创建任务 / Create a task |
| `TOOL_NAME_UPDATE_TASK` | `update_task` | 更新任务 / Update a task |
| `TOOL_NAME_GET_TASK` | `get_task` | 获取任务详情 / Get task details |
| `TOOL_NAME_LIST_TASK` | `list_task` | 列出任务 / List tasks |
| `TOOL_NAME_BASH` | `bash` | 执行 Shell 命令 / Execute bash commands |
| `TOOL_NAME_GLOB_FILE` | `glob_file` | 文件通配匹配 / Glob file patterns |
| `TOOL_NAME_GREP_FILE` | `grep_file` | 文件内容搜索 / Search file contents |
| `TOOL_NAME_READ_FILE` | `read_file` | 读取文件 / Read file |
| `TOOL_NAME_WRITE_FILE` | `write_file` | 写入文件 / Write file |
| `TOOL_NAME_EDIT_FILE` | `edit_file` | 编辑文件 / Edit file |
| `TOOL_NAME_SKILL` | `skill` | 调用技能 / Invoke a skill |
| `TOOL_NAME_WEB_FETCH` | `web_fetch` | 获取网页内容 / Fetch web content |
| `TOOL_NAME_WEB_SEARCH` | `web_search` | 网络搜索 / Search the web |
| `TOOL_NAME_CALL_MCP` | `call_mcp` | 调用 MCP 工具 / Call an MCP tool |
| `TOOL_NAME_CHECK_SIMULATOR` | `check_simulator` | 检查仿真器可用性 / Check simulator availability |
| `TOOL_NAME_INIT_DESIGN` | `init_design` | 创建设计 / Initialize a design |
| `TOOL_NAME_COPY_DESIGN` | `copy_design` | 复制设计 / Copy a design |
| `TOOL_NAME_QUERY_DESIGN` | `query_design` | 查询设计列表 / Query design list |
| `TOOL_NAME_LAUNCH_SIM` | `launch_sim` | 启动仿真 / Launch a simulation |
| `TOOL_NAME_QUERY_RUN` | `query_run` | 查询运行次数 / Query run count |
| `TOOL_NAME_READ_LOG` | `read_log` | 读取仿真日志 / Read simulation logs |

### Bash 风险等级 | Bash Risk Levels

| 常量 Constant | 风险等级 Risk | 说明 Description |
|---------------|---------------|------------------|
| `BASH_HIGH_RISK_LABEL` | 高风险 High (0) | sudo、dd、iptables、防火墙等 / sudo, dd, iptables, firewall, etc. |
| `BASH_PACKAGE_LABEL` | 高风险 High (0) | 包管理器修改系统 / Package manager modifies system |
| `BASH_NETWORK_LABEL` | 高风险 High (0) | 网络命令（curl, wget, ssh 等）/ Network commands |
| `BASH_REMOVAL_RF_LABEL` | 中风险 Med (1) | 递归强制删除 `rm -rf` / Recursive forced removal |
| `BASH_REMOVAL_R_LABEL` | 中风险 Med (2) | 递归删除 `rm -r` / Recursive removal |
| `BASH_REMOVAL_F_LABEL` | 中风险 Med (2) | 强制删除 `rm -f` / Forced removal |
| `BASH_REMOVAL_LABEL` | 中风险 Med (3) | 普通删除 `rm` / Normal removal |
| `BASH_CHMOD_LABEL` | 低风险 Low (4) | 修改文件权限 / Change file permissions |
| `BASH_CHOWN_LABEL` | 低风险 Low (4) | 修改文件所有者 / Change file owner |
| `BASH_FILE_LABEL` | 低风险 Low (4) | 文件操作（cp, mv, mkdir 等）/ File operations |
| `BASH_INLINE_SCRIPT_LABEL` | 低风险 Low (4) | 内联脚本（python -c, node -e 等）/ Inline script execution |
| `BASH_REPOSITORY_MODIFY_LABEL` | 中风险 Med (5) | Git 修改仓库历史 / Git modifies repo history |
| `BASH_STAGE_CHANGE_LABEL` | 中风险 Med (6) | Git 暂存更改 / Git stages changes |
| `BASH_UNKNOWN_LABEL` | 未知 Unknown (7) | 未分类命令 / Unclassified command |
| `BASH_SAFE_LABEL` | 无风险 Safe (8) | 安全命令（ls, cat, grep 等）/ Safe commands |
| `BASH_EMPTY_LABEL` | 无风险 Safe (9) | 空命令 / Empty command |

### UI 配置 | UI Configs

#### 主题色 | Theme Colors

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `MAJOR_COLOR1` | `#FF9FF3`（亮粉 / bright pink） | 强调色、内容图标、进度条终点 / Accent, content icon, progress bar end |
| `MAJOR_COLOR2` | `#54A0FF`（蓝 / blue） | 主色调、命令名称、进度条起点 / Primary color, command names, progress bar start |
| `REASONING_COLOR` | `#54A0FF` | 推理文本颜色 / Reasoning text color |
| `EDIT_VIEW_RMV_BG` | `#5F0000`（暗红 / dark red） | 文件编辑 diff 删除行背景 / Removed line background in edit diff |
| `EDIT_VIEW_ADD_BG` | `#005F00`（暗绿 / dark green） | 文件编辑 diff 新增行背景 / Added line background in edit diff |

#### 图标与符号 | Icons & Symbols

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `AGENT_CONSOLE_ICON` | `✦` | 控制台输入提示符 / Console input prompt marker |
| `REASON_ICON` | `⟡` | 推理内容标记 / Reasoning content marker |
| `CONTENT_ICON` | `●` | 普通内容标记 / Regular content marker |
| `PROGRESS_BAR_FULL` | `█` | 进度条填充字符 / Progress bar filled block |
| `PROGRESS_BAR_EMPTY` | `░` | 进度条空白字符 / Progress bar empty block |
| `OPTIONS_TO_SELECT_PREFIX` | `❯ ` | TUI 选项中当前聚焦项的前缀 / Focused option prefix in TUI |
| `OPTIONS_UN_SELECT_PREFIX` | `  ` | TUI 选项中未聚焦项的前缀 / Unfocused option prefix in TUI |
| `OPTIONS_SELECTED_PREFIX` | ` ✓` | TUI 选项中已选择项的标记 / Selected option suffix in TUI |
| `SELECTED_QUESTION_OPTION_COLOR` | `#A6CEFF` | TUI 中已选择的选项颜色 / Color for selected option |
| `TUI_USER_COMMENT_COLOR` | `#A6CEEF` | 用户注释文本颜色 / Color for user comment text |

#### 样式与格式 | Styles & Formatting

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `REASON_ICON_SYLTE` | `bold #54A0FF` | 推理图标样式 / Reasoning icon style |
| `CONTENT_ICON_SYLTE` | `bold #FF9FF3` | 内容图标样式 / Content icon style |
| `REASON_STYLE` | `italic #54A0FF` | 推理文本样式 / Reasoning text style |
| `CONTENT_STYLE` | `none` | 内容文本样式 / Content text style |
| `BASH_STYLE` | `none` | Bash 命令输出样式 / Bash output style |
| `MESSAGE_PRINT_MARGIN` | `4` | 消息打印左侧缩进宽度 / Left margin width for message printing |

#### 任务看板 | Task Board

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `TASK_DISPLAYS_BEFORE_ARCHIVED` | `3` | 已解决任务归档前的显示次数 / Displays before archiving resolved tasks |
| `MUTE_TASK_OP_INFO` | `true` | 是否在控制台静默任务操作日志 / Mute task operation logs in console |
| `TASK_VIEW_LEFT_MARGIN` | `6` | 任务列表状态图标左侧缩进 / Left margin for task status icons |
| `TASK_VIEW_RIGHT_MARGIN` | `1` | 任务列表状态图标右侧缩进 / Right margin for task status icons |
| `TASK_COLOR_GRADIENT` | `128` | 任务动画渐变阶数 / Gradient color steps for task animation |
| `TASK_COLOR_PERIOD` | `2.0` | 任务动画周期（秒）/ Task animation period (seconds) |
| `TASK_PENDING_WITHOUT_OWNER_ICON` | `○` | 无归属待处理任务图标 / Icon for pending task without owner |
| `TASK_PENDING_WITH_OWNER_ICON` | `●` | 有归属待处理/进行中任务图标 / Icon for pending/in-progress task with owner |
| `TASK_COMPLETED_ICON` | `✓` | 已完成任务图标 / Icon for completed task |
| `TASK_DELETED_ICON` | `✗` | 已删除任务图标 / Icon for deleted task |
| `TASK_PENDING_COLOR_START` | `#545454` | 待处理任务渐变起始色 / Gradient start for pending tasks |
| `TASK_PENDING_COLOR_END` | `#DBDBDB` | 待处理任务渐变终止色 / Gradient end for pending tasks |
| `TASK_IN_PROGRESS_COLOR_START` | `#FF9FF3`（亮粉） | 进行中任务渐变起始色 / Gradient start for in-progress tasks |
| `TASK_IN_PROGRESS_COLOR_END` | `#54A0FF`（蓝） | 进行中任务渐变终止色 / Gradient end for in-progress tasks |
| `TASK_COMPLETED_COLOR` | `#8CDCA0`（绿） | 已完成任务颜色 / Color for completed tasks |
| `TASK_DELETED_COLOR` | `#767676`（灰） | 已删除任务颜色 / Color for deleted tasks |

#### 监听 TUI | Listen TUI

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `LISTEN_TUI_COLOR_START` | `#FF9FF3`（亮粉） | 监听 TUI 标题渐变起始色 / Listen TUI gradient start |
| `LISTEN_TUI_COLOR_END` | `#54A0FF`（蓝） | 监听 TUI 标题渐变终止色 / Listen TUI gradient end |
| `LISTEN_TUI_COLOR_GRADIENT` | `128` | 监听 TUI 渐变色阶数 / Listen TUI gradient steps |
| `LISTEN_TUI_COLOR_PERIOD` | `2.0` | 监听 TUI 动画周期（秒）/ Listen TUI animation period (seconds) |
| `CRON_LISTEN_COLOR_START` | `#FF9FF3`（亮粉） | Cron 监听渐变起始色 / Cron listen gradient start |
| `CRON_LISTEN_COLOR_END` | `#54A0FF`（蓝） | Cron 监听渐变终止色 / Cron listen gradient end |
| `CRON_LISTEN_COLOR_GRADIENT` | `128` | Cron 监听渐变色阶数 / Cron listen gradient steps |
| `CRON_LISTEN_COLOR_PERIOD` | `2.0` | Cron 监听动画周期（秒）/ Cron listen animation period (seconds) |

#### 会话标题 | Session Titles

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `DEFAULT_SESSION_TITLE` | `(Empty session)` | 空会话的默认标题 / Default title for empty session |
| `UNKNOWN_SESSION_TITLE` | `(Unknown session)` | 无法识别会话的标题 / Title for unrecognizable session |
| `ERROR_SESSION_TITLE` | `(Summarize fail, try manually)` | 摘要失败时的回退标题 / Fallback title when summarization fails |

#### 进度与 Spinner | Progress & Spinners

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
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

#### 随机进度标题 | Random Progress Titles

**LLM 请求时循环显示**（`LLM_REQUEST_TITLE_LIST`，7+条）：
Displayed cyclically during LLM requests (7+ entries):
> `"Brain (but not mine) using ..."`  默认第一条 / Default first entry 

**工具执行时循环显示**（`TOOLS_EXECUTION_TITLE_LIST`，23+ 条）：
Displayed cyclically during tool execution (23+ entries):

> `"Reaching into the toolbox ..."`  默认第一条 / Default first entry

**用户输入框前的随机标语**（`USER_PROMPT_PREFIX_LIST` 7+ 条）：
Random slogans before user input (7+ entries):

> `"Type, and behold the breath of silica"`  默认第一条 / Default first entry

All these lists can be customized in `constants.py`

#### 流式显示 | Streaming Display

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `STREAM_DISPLAY_REFRESH_RATE` | `20` | 流式响应 TUI 刷新率（次/秒）/ Stream response TUI refresh rate (fps) |
| `STREAM_DISPLAY_MAX_REASON_LINE` | `10` | 推理内容显示截断行数 / Max reasoning lines before truncation |
| `STREAM_DISPLAY_MAX_CONTENT_LINE` | `20` | 内容显示截断行数 / Max content lines before truncation |

#### 用户提示词 | User Prompt

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `USER_PROMPT_FIXED_PREFIX` | `(Shift+Tab: New line, Enter: Submit)` | 输入框固定提示文字 / Fixed hint text at prompt input |
| `KEY_LISTEN_SLEEP_TIME_MS` | `100` | TUI 键盘轮询间隔（毫秒）/ TUI keyboard poll interval (ms) |

#### 编辑视图 | Edit View

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `EDIT_VIEW_LINE_MARGIN_SINGLE` | `3` | 单次编辑预览上下文行数 / Context lines for single edit preview |
| `EDIT_VIEW_LINE_MARGIN_MULTI` | `2` | 多次编辑预览上下文行数 / Context lines for multi edit preview |
| `EDIT_VIEW_LEFT_SPACE_MARGIN` | `5` | 行号左侧空格数 / Left space margin before line numbers |
| `EDIT_VIEW_LINE_SPACE_MARGIN` | `1` | 行号与内容间空格数 / Space margin between line number and content |

#### Bash 视图 | Bash View

| 常量 Constant | 默认值 Default | 用途 Purpose |
|---------------|----------------|--------------|
| `BASH_VIEW_LEFT_SPACE_MARGIN` | `5` | 行号左侧空格数 / Left space margin before line numbers |
| `BASH_VIEW_LINE_NUM_MARGIN` | `1` | 行号与内容间空格数 / Space margin between line number and content |

### 其他关键常量 | Other Key Constants

| 常量 Constant | 默认值 Default | 说明 Description |
|---------------|----------------|------------------|
| `TECOSIM_AGENT_MAJOR_VERSION` | `0` | Agent 主版本号 / Agent major version |
| `TECOSIM_AGENT_MINOR_VERSION` | `1` | Agent 次版本号 / Agent minor version |
| `TECOSIM_AGENT_UPDATE_VERSION` | `0` | Agent 更新版本号 / Agent update version |
| `MAIN_AGENT_ID` | `"main"` | 主 Agent 标识 ID / Main agent identifier |
| `TASKS_NAME` | `"tasks.json"` | Scoreboard 任务持久化文件名 / Scoreboard task persistence file name |
| `LOG_PATH` | `"./log"` | 日志文件输出目录 / Log file output directory |
| `SESSION_PATH` | `"./session"` | 会话持久化目录 / Session persistence directory |
| `CRON_CONFIGS_PATH` | `"./cron/cron_configs.json"` | 持久化定时任务配置文件 / Durable cron config file path |
| `BASH_TIMEOUT_MS_DEFAULT` | `120000` (2 min) | Bash 命令默认超时 / Default bash command timeout |
| `BASH_TIMEOUT_MS_MAX` | `600000` (10 min) | Bash 命令最大超时 / Max bash command timeout |
| `READ_FILE_MAX_LINE` | `10000` | 单次读取文件最大行数 / Max lines per file read |
| `READ_LOG_MAX_LINE` | `10000` | 单次读取日志最大行数 / Max lines per log read |
| `PERMISSION_REQUEST_DSEC_CHAR_MAX` | `500` | 权限请求描述最大字符数 / Max chars for permission request description |

> **⚠️ 警告 | WARNING**
>
> `constants.py` 中的参数直接影响 Agent 的运行行为与安全策略。除非您完全理解每个参数的作用，**请勿随意修改**。错误修改可能导致：
> - Agent 行为异常或崩溃
> - 安全策略失效，使敏感操作绕过权限控制
> - 文件 I/O、网络请求等工具功能异常
>
> 如需调整行为，建议优先通过 `agent_configs.json` 或 `api_configs.json` 配置。如需重命名工具，仅需修改 `TOOL_NAME_*` 常量。

> **⚠️ WARNING**
>
> Parameters in `constants.py` directly affect the agent's runtime behavior and security policies. **Do not modify them unless you fully understand each parameter's purpose**. Incorrect modifications may lead to:
> - Agent malfunction or crashes
> - Security policy bypass, allowing sensitive operations without permission control
> - Tool malfunctions (file I/O, network requests, etc.)
>
> If you need to adjust behavior, prefer using `agent_configs.json` or `api_configs.json` instead. If you need to rename a tool, simply modify the corresponding `TOOL_NAME_*` constant.
