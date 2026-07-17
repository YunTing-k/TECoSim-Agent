# MCP 与 Skills 设置指南 | MCP & Skills Setup Guide

---

## 技能 | Skills

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

---

## MCP（模型上下文协议）| Model Context Protocol

MCP 配置文件路径为 `./mcps/mcps_configs.json`，支持三种传输类型。
MCP config file is located at `./mcps/mcps_configs.json`, supporting three transport types.

### CLI 管理（推荐）| CLI Management (Recommended)

优先使用命令行管理 MCP，命令行无法满足需求时再手动编辑配置文件。
Prefer using the CLI to manage MCPs. Only manually edit the config file when the CLI cannot meet your needs.

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

> **⚠️ Windows 引号问题**：cmd.exe 不识别单引号，必须用双引号包裹 JSON，内部双引号用 `\"` 转义。PowerShell 支持单引号，可直接使用。
>
> **⚠️ Windows Quoting Issue**: cmd.exe does not recognize single quotes — use double quotes with escaped inner quotes (`\"`). PowerShell supports single quotes directly.

### 关于 `args` 参数 | About the `args` Parameter

`args` 必须是一个 **JSON 字符串数组**，而非单个字符串：
`args` must be **a JSON array of strings**, not a single string:

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

### 各类 MCP 的完整参数 | Full Parameters by MCP Type

#### stdio 类型（通过子进程启动的 MCP 服务器）| stdio type (MCP server launched as subprocess)

| 参数 Parameter | 是否必填 Required | 说明 Description |
|-----------|----------|-------------|
| `command` | **是 Yes** | 可执行文件路径或命令名 / Executable path or command name |
| `args` | **是 Yes** | 命令行参数数组（JSON 字符串数组）/ Command-line arguments (JSON array of strings) |
| `env` | 否 No | 环境变量字典，默认 `null` / Environment variables dict, default `null` |
| `cwd` | 否 No | 工作目录，默认 `null` / Working directory, default `null` |
| `keep_alive` | 否 No | 是否保持连接，默认 `true` / Keep alive, default `true` |
| `log_file` | 否 No | 日志文件路径，默认 `null` / Log file path, default `null` |

#### http/sse 类型（远程 HTTP 或 SSE 服务器）| http/sse type (Remote HTTP or SSE server)

| 参数 Parameter | 是否必填 Required | 说明 Description |
|-----------|----------|-------------|
| `url` | **是 Yes** | 服务器 URL / Server URL |
| `headers` | 否 No | 自定义 HTTP 头字典，默认 `null` / Custom HTTP headers dict, default `null` |
| `auth` | 否 No | 认证信息，默认 `null` / Auth info, default `null` |
| `sse_read_timeout` | 否 No | SSE 读取超时，默认 `null` / SSE read timeout, default `null` |
| `verify` | 否 No | SSL 证书验证，默认 `null` / SSL verification, default `null` |

### MCP 源文件存放位置 | MCP Source Files Location

MCP 服务器的原始脚本、二进制文件推荐统一存放在 `./mcps/sources/` 目录下，每个 MCP 单独一个子文件夹：
MCP server source scripts/binaries should be stored in `./mcps/sources/`, each in its own subfolder:

```
mcps/
├── mcps_configs.json          # MCP 配置文件 / MCP config file
├── sources/                   # MCP 源文件存放目录 / MCP source files directory
│   ├── my-python-mcp/
│   │   └── server.py
│   ├── my-node-mcp/
│   │   ├── package.json
│   │   └── server.js
│   └── matlab-mcp/
│       └── matlab-mcp-core-server-win64.exe    # 二进制文件 / Binary executable
```

这样做的好处：统一管理、便于版本控制、避免路径混乱。
Benefits: centralized management, easier version control, and avoiding path confusion.

### 手动编辑配置文件 | Manual Config File Editing

当命令行安装受限时（如需要复杂嵌套结构），可直接编辑 `./mcps/mcps_configs.json`：
When CLI installation is limited (e.g., complex nested structures needed), directly edit `./mcps/mcps_configs.json`:

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

> **提示 | Tip**: 
> 
> 编辑配置文件后，需要重启 Agent 或通过命令行 `toggle` 后再重启 Agent 来重新加载。
> After editing the config file, restart the Agent or use the CLI `toggle` then restart the Agent to reload.
