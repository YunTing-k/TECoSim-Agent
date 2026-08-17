# 五款 Agent 项目 Bash/Shell 命令实现对比分析
# Bash/Shell Command Implementation: A Five-Project Comparison

> 对比项目 | Projects：Claude Code · CodeWhale · Codex (OpenAI) · OpenCode · deepseek-harness  
> 分析日期 | Date：2026-06-14（deepseek-harness 补充于 2026-08-17）

## 目录 | Table of Contents

1. [总览 | Overview](#1-总览--overview)
2. [语言与运行时 | Language & Runtime](#2-语言与运行时--language--runtime)
3. [Shell 检测与抽象 | Shell Detection & Abstraction](#3-shell-检测与抽象--shell-detection--abstraction)
4. [命令解析 | Command Parsing](#4-命令解析--command-parsing)
5. [安全与沙箱机制 | Security & Sandbox](#5-安全与沙箱机制--security--sandbox)
6. [进程生成 | Process Spawning](#6-进程生成--process-spawning)
7. [进程终止 | Process Termination](#7-进程终止--process-termination)
8. [输出处理 | Output Handling](#8-输出处理--output-handling)
9. [超时机制 | Timeout](#9-超时机制--timeout)
10. [各项目架构详解 | Architecture Details](#10-各项目架构详解--architecture-details)
11. [总结评价 | Summary & Evaluation](#11-总结评价--summary--evaluation)

---

## 1. 总览 | Overview

| 维度 / Dimension | Claude Code | CodeWhale | Codex (OpenAI) | OpenCode | deepseek-harness |
|-----------------|:--:|:--:|:--:|:--:|:--:|
| **主语言** / Language | TypeScript (Bun) | Rust | Rust | TypeScript (Effect-TS) | TypeScript (Node.js + Cordis) |
| **核心文件数** / Core files | ~15 | ~6 | ~10+ crates | ~10 | ~30（4 分组 / 4 groups） |
| **核心代码量** / Code volume | ~15000 行 / lines | ~6700 行 / lines | ~4000+ 行 / lines | ~2500+ 行 / lines | ~11300 行 / lines |

---

## 2. 语言与运行时 | Language & Runtime

| | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **主语言** Language | TypeScript，运行于 Bun / TypeScript, runs on Bun | Rust，tokio 异步运行时 / Rust, tokio async runtime | Rust，tokio 异步运行时 / Rust, tokio async runtime | TypeScript，Effect-TS 效应系统 / TypeScript, Effect-TS effect system | TypeScript，Node.js + Cordis 插件框架（全 ESM / fully ESM） |
| **进程 API** Process API | `child_process.spawn()` + `execa` | `std::process::Command` | `tokio::process::Command` | `cross-spawn` (npm 库 / npm library) | `node:child_process.spawn()` + `node-pty`（运行时唯一第三方进程库 / the only third-party process library at runtime） |
| **JS 侧补充** JS glue | — | `child_process.spawnSync`（npm wrapper） | TypeScript SDK 封装 CLI 二进制 / TypeScript SDK wrapping the CLI binary | — | 自研原生层 / Self-built native layer：C11 Landlock addon（`native/landlock-run`）+ Windows ACL 受限令牌 runner（FFI） |
| **源码目录** Source dirs | `src/tools/BashTool/` `src/utils/bash/` `src/utils/shell/` | `crates/tui/src/tools/shell.rs` `crates/tui/src/shell_dispatcher.rs` | `codex-rs/core/src/exec.rs` `codex-rs/shell-command/` `codex-rs/exec-server/` | `packages/core/src/tool/bash.ts` `packages/opencode/src/tool/shell.ts` `packages/core/src/cross-spawn-spawner.ts` | `packages/subprocess/subprocess-local/src/` `packages/shell/{bash-local,bash-sandbox,tool-bash}/` `packages/terminal/terminal-bash/` `packages/sandbox/{sandbox-local,sandbox-windows-acl}/` |

### 关键差异 | Key Differences

- **Rust 系**（CodeWhale、Codex）：性能和内存安全占优，编译期即排除数据竞争，适合大规模部署和高并发场景。
  **Rust-based** (CodeWhale, Codex): Better performance and memory safety — data races ruled out at compile time, well-suited for large-scale deployment and high-concurrency scenarios.
- **TypeScript 系**（Claude Code、OpenCode）：迭代速度快，npm 生态丰富，适合快速原型和频繁变更。
  **TypeScript-based** (Claude Code, OpenCode): Faster iteration with rich npm ecosystem, ideal for rapid prototyping and frequent change cycles.
- **Node.js 系**（deepseek-harness）：「一切皆插件」（Cordis 驱动），抽象缝与实现分离最彻底；运行时零第三方进程库——进程树管理、环境擦洗、沙箱 runner 全部自研。
  **Node.js-based** (deepseek-harness): "Everything is a plugin" (powered by Cordis) — cleanest separation between abstract seams and implementations; zero third-party process libraries at runtime — process-tree management, env scrubbing, and sandbox runners are all self-built.

---

## 3. Shell 检测与抽象 | Shell Detection & Abstraction

### 3.1 抽象方式对比 | Abstraction Approach

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **抽象方式** Approach | `ShellProvider` 接口 / interface | `ShellKind` 枚举 / enum | `ShellType` 枚举 / enum | `META` 元数据对象 / metadata object | `ShellExecutor` 抽象服务（能力缝 / capability seam） |
| **关键文件** Key file | `src/utils/shell/shellProvider.ts` | `crates/tui/src/shell_dispatcher.rs` | `codex-rs/shell-command/src/shell_detect.rs` | `packages/opencode/src/shell/shell.ts` | `packages/shell/shell/src/index.ts`（缝 / seam 103 行 / lines）`bash-local`（333）`bash-sandbox`（182） |
| **代码行数** Lines | 33（接口 / interface）+ 255（bash）+ 123（pwsh） | 565 | ~100 | 215 | 103（缝 / seam）+ 各实现 100~450 / 100~450 per implementation |

### 3.2 支持的 Shell 类型 | Supported Shell Types

| Shell | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|-------|:--:|:--:|:--:|:--:|:--:|
| bash | ✅ | ✅ | ✅ | ✅ | ✅ |
| zsh | ✅ | ❌ | ✅ | ✅ | ❌ |
| sh | ✅ | ✅ | ✅ | ✅ | ❌（仅 bash / bash only） |
| PowerShell (pwsh) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Windows PowerShell | ❌ | ✅ | ❌ | ❌ | ✅（编码前导兼容 5.1 / encoding preamble for 5.1 compat） |
| cmd | ❌ | ✅ | ✅ | ✅ | ❌ |
| fish | ❌ | ❌ | ❌ | ✅ (标记 deny / marked deny) | ❌ |
| dash | ❌ | ❌ | ❌ | ✅ | ❌ |
| ksh | ❌ | ❌ | ❌ | ✅ | ❌ |
| nu (nushell) | ❌ | ❌ | ❌ | ✅ (标记 deny / marked deny) | ❌ |
| Custom（用户自定义 / user-defined） | ❌ | ✅ | ❌ | ❌ | ❌ |

### 3.3 检测策略 | Detection Strategy

#### Claude Code —— 多级回退 | Multi-level Fallback

```
CLAUDE_CODE_SHELL 环境变量 / env var
  → $SHELL 环境变量 / env var（限定为 bash 或 zsh / restricted to bash or zsh）
    → which bash / which zsh
      → 常见路径 / common paths：/bin, /usr/bin, /usr/local/bin, /opt/homebrew/bin
        → 默认偏好 / default preference：zsh > bash（当 $SHELL 含 'bash' 时反转 / reversed when $SHELL contains 'bash'）
```

#### CodeWhale —— 启动时自动检测 | Auto-Detect on Startup

```rust
pub enum ShellKind {
    Pwsh,                   // PowerShell Core
    WindowsPowerShell,      // 旧版 Windows PowerShell / legacy Windows PowerShell
    Cmd,                    // Windows cmd
    Sh,                     // POSIX sh
    Bash,                   // 通过 $SHELL 或 WSL/Git Bash 检测 / detected via $SHELL or WSL/Git Bash
    Custom { binary: String, flag: String },
}
```

#### Codex —— 路径名匹配 | Path Name Matching

```rust
pub enum ShellType {
    Zsh,
    Bash,
    PowerShell,
    Sh,
    Cmd,
}
// 通过 detect_shell_type(PathBuf) 匹配 shell 二进制名称 / matches the shell binary name via detect_shell_type(PathBuf)
```

#### OpenCode —— 元数据驱动 | Metadata-Driven（覆盖面最广）

```typescript
const META = {
  bash:   { login: true, posix: true },
  dash:   { login: true, posix: true },
  fish:   { deny: true,  login: true },   // 禁止使用但可检测 / denied but detectable
  ksh:    { login: true, posix: true },
  nu:     { deny: true },                  // 禁止使用但可检测 / denied but detectable
  powershell: { ps: true },
  pwsh:   { ps: true },
  sh:     { login: true, posix: true },
  zsh:    { login: true, posix: true },
}
```

#### deepseek-harness —— 无检测，执行器挂载 | No Detection, Executor Mounting

不检测当前 shell（无 `$SHELL` 读取、无路径探测、无 ShellType 枚举）；「shell 类型」由挂载哪个执行器插件决定：
No current-shell detection (no `$SHELL` read, no path probing, no ShellType enum); the "shell type" is determined by which executor plugin is mounted:

```
平台分支在组合层 | Platform branch at composition layer
  ├─ POSIX → bash 执行器 | win32 → pwsh 执行器（二选一挂载，重复挂载报错 / mount one of the two; duplicate mounting errors）
  ├─ 调用方式硬编码 argv / hardcoded invocation argv：bash -c <command> / pwsh -NoLogo -NoProfile -NonInteractive -Command
  └─ shell-env 不是"检测器" / not a "detector"，而是受信 DSH_* 环境变量注册表 / but a trusted DSH_* environment-variable registry
      （DSH_HOME / DSH_SHELL=1 / DSH_SESSION_ID，插件可注册额外变量 / plugins may register extra variables）
```

### 小结 | Summary

| 项目 / Project | 优势 / Pros | 劣势 / Cons |
|------|------|------|
| Claude Code | 接口设计清晰，Provider 模式易于扩展 / Clear interface design; Provider pattern is easy to extend | 仅支持 bash/zsh/pwsh / supports only bash/zsh/pwsh |
| CodeWhale | 支持自定义 Shell，检测逻辑集中 / Supports custom shells; detection logic centralized | 不支持 zsh / no zsh support |
| Codex | 简洁高效 / Simple and efficient | Shell 种类偏少 / fewer shell types |
| OpenCode | 支持 10 种 Shell，覆盖面最广 / Supports 10 shell types — the widest coverage | deny 标记的 shell 实际不可用 / deny-marked shells are unusable |
| deepseek-harness | 能力缝设计最彻底，实现可整体替换（本地/沙箱/远程）/ Most thorough seam design; implementations fully swappable (local/sandbox/remote) | 仅 bash/pwsh 两种，无检测机制 / only bash/pwsh; no detection mechanism |

---

## 4. 命令解析 | Command Parsing

### 4.1 总览 | Overview

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **解析方式** Approach | **纯 TypeScript 手写解析器 / Handwritten pure-TypeScript parser** | 正则匹配（无 AST）/ Regex matching (no AST) | `tree-sitter-bash` Rust crate | `web-tree-sitter` + WASM | **无解析 / No parsing**（命令作为单个 argv 元素直传 `bash -c` / command passed as a single argv element to `bash -c`） |
| **关键文件** Key file | `src/utils/bash/bashParser.ts` (4436 行 / lines) | `crates/tui/src/command_safety.rs` (1468 行 / lines) | `codex-rs/shell-command/src/bash.rs` | `packages/opencode/src/tool/shell.ts` | `packages/shell/bash-local/src/index.ts` |
| **解析目标** Goal | 生成 tree-sitter 兼容 AST / Generate tree-sitter-compatible AST | 检测危险模式 / Detect dangerous patterns | 提取命令结构 / Extract command structure | 提取命令用于权限判定 / Extract commands for permission decisions | 无（安全由沙箱层承担 / security delegated to the sandbox layer） |
| **安全防护** Safeguard | 50ms 解析超时 + 50000 节点预算 / 50ms parse timeout + 50,000 node budget | 无解析层 / No parsing layer | tree-sitter 原生保护 / Native tree-sitter protection | WASM 异步加载 / WASM async loading | fail-closed 沙箱（不可用即拒绝执行 / refuses to run when unavailable） |
| **PowerShell 解析** | 独立 PowerShellTool / Dedicated PowerShellTool | ❌ | 计划中 / Planned | `tree-sitter-powershell.wasm` | ❌ |

### 4.2 各项目详解 | Details

#### Claude Code —— 手写 Parser | Handwritten Parser（4436 行）

五个项目中投入最大、实现最深的方案。完全用 TypeScript 手写了 bash 解析器，包含：
The largest and deepest implementation among the five projects — a complete bash parser handwritten in TypeScript, including:

- **完整 Tokenizer / Full tokenizer**：词法分析，覆盖所有 bash 词法规则 / lexing that covers all bash lexical rules
- **完整 Parser / Full parser**：语法分析，生成与 tree-sitter-bash 兼容的 AST / parsing that produces a tree-sitter-bash-compatible AST
- **两重安全防护 / Two-fold safeguards**：
  - 50ms 解析超时（防止对抗性输入导致 hang）/ 50ms parse timeout (prevents hangs on adversarial input)
  - 50,000 节点预算（防止深层嵌套导致 OOM）/ 50,000 node budget (prevents OOM on deep nesting)
- **用途 / Use**：驱动安全/权限管线，检测危险命令模式 / drives the security/permission pipeline and detects dangerous command patterns

```typescript
// 关键代码路径 / key code paths
src/utils/bash/bashParser.ts      // 主解析器 (4436 行 / lines) / main parser
src/utils/bash/bashPipeCommand.ts // 管道命令重排 / pipe command rearrangement
src/utils/bash/shellCompletion.ts // Shell 补全 / shell completion
src/utils/bash/shellQuote.ts      // Shell 引用工具 / shell quoting utilities
src/utils/bash/shellQuoting.ts    // 额外引用处理 / extra quoting handling
src/utils/bash/ShellSnapshot.ts   // Shell 环境快照 (582 行 / lines) / shell environment snapshot
```

#### Codex —— tree-sitter-bash Rust 原生绑定 | Native Rust Binding

使用 Rust 原生 `tree-sitter-bash` crate，编译期链接 C 解析器，解析性能最优：
Uses the native Rust `tree-sitter-bash` crate, linking the C parser at compile time for optimal parsing performance:

```rust
use tree_sitter_bash::LANGUAGE as BASH;

pub fn try_parse_shell(shell_lc_arg: &str) -> Option<Tree> {
    let lang = BASH.into();
    let mut parser = Parser::new();
    parser.set_language(&lang).expect("load bash grammar");
    parser.parse(shell_lc_arg, None)
}

pub fn extract_bash_command(command: &[String]) -> Option<(&str, &str)> {
    let [shell, flag, script] = command else { return None; };
    if !matches!(flag.as_str(), "-lc" | "-c") { return None; }
    Some((shell, script))
}
```

#### OpenCode —— tree-sitter WASM 异步加载 | WASM Async Loading

通过 `web-tree-sitter` 加载 WASM 编译的 bash 和 PowerShell 语法，支持运行时动态加载：
Loads WASM-compiled bash and PowerShell grammars via `web-tree-sitter`, with runtime dynamic loading:

```typescript
const parser = lazy(async () => {
  const { Parser } = await import("web-tree-sitter")
  const bash = new Parser()
  bash.setLanguage(bashLanguage)   // tree-sitter-bash.wasm
  const ps = new Parser()
  ps.setLanguage(psLanguage)       // tree-sitter-powershell.wasm
  return { bash, ps }
})
```

#### CodeWhale —— 正则匹配 | Regex Matching（最轻量）

不使用 AST，直接以正则做模式匹配：
No AST — pattern matching directly with regexes:

```rust
// 检测 curl/wget 管道到 shell 的危险模式 / detect curl|wget piped to a shell
if (command_lower.contains("curl") || command_lower.contains("wget"))
    && (command_lower.contains("| sh")
        || command_lower.contains("| bash")
        || command_lower.contains("| zsh"))
{
    // 标记为危险 / mark as dangerous
}
```

#### deepseek-harness —— 零解析 + 沙箱兜底 | No Parsing, Sandbox Backstop

完全不解析命令——命令不经任何 AST/正则/转义层，作为**单个 argv 元素**传给 `bash -c`（无中间 shell 引用层，也就无注入面）：
No parsing at all — the command bypasses any AST/regex/quoting layer and is passed to `bash -c` as a **single argv element** (no intermediate shell-quoting layer, hence no injection surface):

```typescript
// bash-local: 命令直传，无 -l/-i、无 login shell、不 source rc 文件、不 eval
// command passed straight through; no -l/-i, no login shell, no rc sourcing, no eval
runArgv(spec, ['bash', '-c', spec.command])

// 安全不靠解析：沙箱 confine 包装整条 argv（bwrap/landlock/seatbelt/Windows ACL）
// security does not rely on parsing: sandbox confine wraps the whole argv (bwrap/landlock/seatbelt/Windows ACL)
confine(['bash', '-c', command], policy)   // bash-sandbox

// 终端层只做"输出净化"：sanitize.ts 流式剥离 OSC/CSI 转义序列，无命令黑名单
// the terminal layer only sanitizes output: sanitize.ts strips OSC/CSI escape sequences; no command blacklist
// （防终端注入攻击；命令安全完全由 ctx.sandbox.confine() 承担）
// (prevents terminal injection; command safety is fully delegated to ctx.sandbox.confine())
```

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 / Notes |
|----------------------|:--:|------|
| 解析深度 / Depth | **Claude Code** | 手写 4436 行 parser，投入最大 / handwritten 4436-line parser; largest investment |
| 解析性能 / Performance | **Codex** | Rust 原生 tree-sitter，编译期链接 / native Rust tree-sitter, compile-time linking |
| 工程简洁 / Simplicity | **CodeWhale** | 正则匹配，零外部依赖 / regex matching, zero external dependencies |
| Shell 覆盖面 / Coverage | **OpenCode** | 同时解析 bash 和 PowerShell / parses both bash and PowerShell |
| 零解析设计 / No parsing | **deepseek-harness** | 不解析命令，安全完全由沙箱 + fail-closed 承担 / no command parsing; security fully handled by sandbox + fail-closed |

---

## 5. 安全与沙箱机制 | Security & Sandbox

### 5.1 安全代码量 | Security Code Volume

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **安全策略代码** Policy code | `bashSecurity.ts` (2592 行 / lines) + `bashPermissions.ts` (2621 行 / lines) = **5213 行 / lines** | `command_safety.rs` (1468 行 / lines) | `execpolicy` crate (~600 行 / lines) | bash tool 内联 / inline (~200 行 / lines) | sandbox 组 / sandbox group ~6200 行 / lines（sandbox-local 567 + windows-acl ~2480 + landlock-run C 298 + policy 267） |
| **沙箱代码** Sandbox code | 文件输出层 / file-output layer O_NOFOLLOW | `sandbox/mod.rs` | `sandboxing` crate + `shell-escalation` crate | 路径白名单 / path whitelist | bwrap / Landlock / Seatbelt SBPL / Windows ACL 受限令牌 / restricted token（4 后端 / 4 backends） |

### 5.2 拦截的危险模式 | Dangerous Pattern Detection

#### Claude Code（覆盖面最广 | Widest Coverage）

- **命令替换 / Command substitution**：`$()`、`${}`、`$[]`
- **进程替换 / Process substitution**：`<()`、`>()`、`=()`
- **Zsh 危险命令 / Dangerous zsh commands**：`zmodload`、`emulate`、`sysopen`、`zpty`、`ztcp`
- **jq 代码执行 / jq code execution**：`jq` 的 `system()` 函数 / the `system()` function of `jq`
- **跨操作符传播检测 / Cross-operator propagation detection**：`&&`、`||`、`|`、`;` 后的危险命令 / dangerous commands after `&&`, `||`, `|`, `;`
- **不完整命令检测 / Incomplete command detection**：heredoc 未闭合等 / unclosed heredocs, etc.
- 所有检查项带有**数字 ID / numeric IDs**，用于遥测追踪 / for telemetry tracking

#### CodeWhale

- `curl`/`wget` 管道到 `sh`/`bash`/`zsh` / piping curl/wget to sh/bash/zsh
- 各类危险命令关键词匹配 / keyword matching for various dangerous commands
- `execpolicy` 引擎的 allow/deny/ask 策略匹配 / allow/deny/ask policy matching in the execpolicy engine
- `bash_arity.rs`（579 行 / lines）：命令前缀 + 参数数量的白名单匹配 / whitelist matching on command prefix + argument count

#### Codex

- **前缀规则匹配 / Prefix rule matching**：`PrefixRule` 基于命令前缀做 allow/deny / allow/deny decisions based on the command prefix
- **网络规则 / Network rules**：`NetworkRuleProtocol` 控制网络访问 / controls network access
- **execve 拦截 / execve interception**（独有 | Unique）：Unix 上拦截所有 `exec()` 调用，shell 内部子进程也必经策略引擎 / intercepts all `exec()` calls on Unix; even shell-internal child processes pass through the policy engine

```rust
// shell-escalation/src/unix/execve_wrapper.rs
// 拦截 execve 调用并路由到策略服务器 / intercepts execve calls and routes them to the policy server
pub struct EscalateRequest {
    pub program: String,
    pub args: Vec<String>,
    pub env: HashMap<String, String>,
}
```

#### OpenCode

- 外部目录访问控制 / external directory access control
- 危险命令模式检测 / dangerous command pattern detection
- tree-sitter 解析辅助权限判断 / tree-sitter parsing assists permission decisions

#### deepseek-harness —— 无黑名单，全沙箱 | No Blacklist, Sandbox-Only

没有任何危险命令关键词/正则黑名单（无 curl|sh 检测、无命令替换检测）；安全模型是**「进程沙箱 + 输出净化 + 环境擦洗」三层**：
No dangerous-command keyword/regex blacklist (no curl|sh detection, no command-substitution detection); the security model is a **three-layer stack of "process sandbox + output sanitization + environment scrubbing"**:

- **三档文件策略 / Three-tier file policy**：`read-only` / `workspace-write` / `danger-full-access`，纯文件效应策略 / a pure file-effect policy——注释明确 / comments explicitly state "Network and process visibility are outside this vocabulary"（不管网络与进程可见性 / network and process visibility are not covered）
- **fail-closed**：沙箱不可用抛 `SandboxUnavailableError` 拒绝执行 / throws `SandboxUnavailableError` and refuses to run when the sandbox is unavailable（"silent unconfined passthrough is forbidden"）；landlock-run 失败退出码 125，绝不 exec / exits 125 on failure and never execs；Windows "a child is NEVER spawned unrestricted"
- **升级审批 / Escalation approval**：`approveEscalation` + `ESCALATION_TARGETS`（工具层 `sandbox_permissions` + `justification` 参数 / tool-level `sandbox_permissions` + `justification` parameters），会话模式经 session 日志事件 `sandbox/mode` 持久化 / session mode persisted via the `sandbox/mode` session log event
- **凭证环境擦除 / Credential env scrubbing**（subprocess 层 / layer）：`SENSITIVE_ENV_PATTERN = /KEY|PASSWORD|SECRET|TOKEN/i` 命名的环境变量及 `DSH_*` 前缀默认不传给子进程 / env vars matching the pattern and the `DSH_*` prefix are not passed to children by default，防 `DEEPSEEK_API_KEY` 隐式泄漏 / preventing implicit leakage of `DEEPSEEK_API_KEY`（显式指定则合并回去 / explicitly provided ones are merged back）
- **终端注入防护 / Terminal injection protection**：`sanitize.ts` 流式剥离 OSC/CSI 转义序列（防终端控制字符注入 / prevents terminal control-character injection），识别 iTerm2 `133;D;` 提示符标记 / recognizes iTerm2 `133;D;` prompt markers

### 5.3 沙箱层对比 | Sandbox Layer Comparison

| 特性 / Feature | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|----------------|:--:|:--:|:--:|:--:|:--:|
| 文件系统隔离 / FS isolation | `O_NOFOLLOW` 防符号链接攻击 / against symlink attacks | sandbox 模块识别 shell 程序 / sandbox module identifies shell programs | sandboxing crate | 路径白名单 / path whitelist | bwrap `--ro-bind / /` / Landlock ruleset（跨 execve 继承 / inherited across execve）/ Seatbelt SBPL / Windows ACL `WRITE_RESTRICTED` 令牌 + SID ACE / restricted token + SID ACE |
| 网络隔离 / Network isolation | — | — | NetworkProxy | — | —（策略词汇明确排除网络 / network explicitly outside the policy vocabulary） |
| exec 拦截 / exec interception | — | — | ✅ shell-escalation | — | —（Landlock 规则集随 execve 继承，等效自限 / Landlock ruleset inherited across execve — equivalent self-restriction） |
| 进程清理 / Process cleanup | tree-kill | PDEATHSIG + Job Objects | kill_on_drop | taskkill + SIGKILL | 进程组 SIGTERM→SIGKILL + taskkill /T + PID+started 双因子身份 / two-factor identity |

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 / Notes |
|----------------------|:--:|------|
| 安全覆盖广度 / Coverage | **Claude Code** | 5000+ 行安全代码，覆盖数十种攻击模式 / 5000+ lines of security code covering dozens of attack patterns |
| 沙箱隔离深度 / Isolation | **Codex** | execve 拦截为独有特性，从内核层面拦截 / execve interception is unique — interception at the kernel level |
| 可配置性 / Configurability | **Codex** | execpolicy 引擎支持灵活的规则配置 / execpolicy engine supports flexible rule configuration |
| 沙箱后端广度 / Backends | **deepseek-harness** | 3 平台 4 后端（bwrap→landlock 探测链 / probe chain / seatbelt / windows-acl），全 fail-closed / all fail-closed |

---

## 6. 进程生成 | Process Spawning

### 6.1 核心 API 对比 | API Comparison

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **底层 API** Underlying API | `child_process.spawn()` | `std::process::Command` | `tokio::process::Command` | `cross-spawn` → Node `spawn` | `node:child_process.spawn()` + `node-pty` |
| **关键文件** Key file | `src/utils/Shell.ts` (474 行 / lines) + `src/utils/ShellCommand.ts` (465 行 / lines) | `crates/tui/src/tools/shell.rs` (3071 行 / lines) | `codex-rs/core/src/spawn.rs` + `codex-rs/core/src/exec.rs` (1570 行 / lines) | `packages/core/src/cross-spawn-spawner.ts` (508 行 / lines) | `packages/subprocess/subprocess-local/src/spawn.ts` (543 行 / lines) + `terminal.ts` (249 行 / lines) |
| **跨平台** Cross-platform | `execa` 处理 .bat/.cmd (Win) / handles .bat/.cmd on Windows | Rust 原生跨平台 / natively cross-platform | Rust 原生跨平台 / natively cross-platform | `cross-spawn` 库自动适配 / automatic adaptation via cross-spawn | 显式平台分支 / explicit platform branching：POSIX `detached` 进程组 / process groups / Windows taskkill；env 大小写不敏感合并 / case-insensitive env merging |
| **PTY 支持** PTY support | ❌（管道 / pipes） | ✅（后台任务 PTY / background-task PTY） | ✅（`codex_utils_pty`） | ✅（`pty.node.ts` / `pty.bun.ts`） | ✅（`node-pty`，TERM=dumb） |

### 6.2 Shell 传参方式 | Shell Argument Construction

#### Claude Code

```typescript
// bashProvider.ts - 完整的 shell 环境初始化 / full shell environment initialization
const commandString = [
  sourceSnapshot,              // 加载环境快照（别名、函数、环境变量）/ load environment snapshot (aliases, functions, env vars)
  sessionEnvScripts,           // 会话环境脚本 / session environment scripts
  disableExtendedGlob,         // 禁用扩展 glob（安全）/ disable extended glob (security)
  `eval ${JSON.stringify(pipeRearrangedCommand)}`,  // 通过 eval 执行 / execute via eval
  `pwd -P`,                    // 追踪 CWD 变更 / track CWD changes
].join('\n')

// 最终执行 / final execution
spawn('/bin/bash', ['-c', commandString], { ... })
```

#### OpenCode

```typescript
// shell.ts - 根据 shell 类型构造参数 / build arguments per shell type
export function args(file: string, command: string, cwd: string) {
  if (n === "bash") {
    return ["-l", "-c",
      `shopt -s expand_aliases; source ~/.bashrc; cd -- "$1"; eval ${JSON.stringify(command)}`,
      "opencode", cwd]
  }
  if (n === "zsh") {
    return ["-l", "-c",
      `source ~/.zshenv; source ~/.zshrc; cd -- "$1"; eval ${JSON.stringify(command)}`,
      "opencode", cwd]
  }
  if (n === "cmd") return ["/c", command]
  if (ps(file)) return ["-NoProfile", "-Command", command]
  return ["-c", command]
}
```

#### Codex

```rust
// shell.rs - 简洁的参数构造 / concise argument construction
pub fn derive_exec_args(&self, command: &str, use_login_shell: bool) -> Vec<String> {
    match self.shell_type {
        ShellType::Zsh | ShellType::Bash | ShellType::Sh => {
            let arg = if use_login_shell { "-lc" } else { "-c" };
            vec![self.shell_path.to_string_lossy().to_string(), arg.to_string(), command.to_string()]
        }
        ShellType::PowerShell => {
            let mut args = vec![self.shell_path.to_string_lossy().to_string()];
            if !use_login_shell { args.push("-NoProfile".to_string()); }
            args.push("-Command".to_string()); args.push(command.to_string()); args
        }
        ShellType::Cmd => {
            vec![self.shell_path.to_string_lossy().to_string(), "/c".to_string(), command.to_string()]
        }
    }
}
```

#### deepseek-harness

```typescript
// bash-local - 单 argv 直传：无 -l/-i、不 source rc、不 eval（与 OpenCode 的
// "source ~/.bashrc + eval" 形成对照：deepseek-harness 放弃环境保真换取纯净与可预测）
// single-argv passthrough: no -l/-i, no rc sourcing, no eval — in contrast to OpenCode's
// "source ~/.bashrc + eval": deepseek-harness trades environment fidelity for purity and predictability
runArgv(spec, ['bash', '-c', spec.command])

// 环境合并：覆盖项 → 调用方 env → 受信 dshEnv（最后合并，托管变量不可被顶替）
// env merge: overrides → caller env → trusted dshEnv (merged last; managed variables cannot be overridden)
env: { ...ENV_OVERRIDES, ...spec.env, ...spec.dshEnv }
// ENV_OVERRIDES = { NO_COLOR:'1', TERM:'dumb', PAGER:'cat', GIT_PAGER:'cat' }

// pwsh-local：-NoProfile 不加载 profile；ENCODING_PREAMBLE 钉死 UTF-8 输出
// -NoProfile skips the profile; ENCODING_PREAMBLE pins UTF-8 output encoding
[this.pwshPath, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', `${ENCODING_PREAMBLE}${spec.command}`]

// subprocess 层：凭证形态环境变量名默认擦除（防 DEEPSEEK_API_KEY 隐式泄漏）
// subprocess layer: credential-shaped env var names are scrubbed by default (prevent implicit DEEPSEEK_API_KEY leakage)
const SENSITIVE_ENV_PATTERN = /KEY|PASSWORD|SECRET|TOKEN/i
```

### 6.3 后台任务支持 | Background Task Support

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **后台任务** Background tasks | `LocalShellTask` (523 行 / lines) | async background spawn | exec-server 进程管理 / process management | Effect forkScoped | `ShellProcess` 句柄 / handle + `ctx.jobs.start()`（返回 jobId / returns a jobId） |
| **输出监控** Output monitoring | 文件大小看门狗（5s 轮询）/ file-size watchdog (5s polling) | tokio 异步 / tokio async | exec-server 事件流 / event stream | Stream.runForEach | `readOutput()` 基于 `readFrom(offset)` 偏移量增量读取（合并 `[stderr]` 段 / merging `[stderr]` segments） |
| **任务终止** Task termination | `killShellTasks.ts` | — | exec-server 信号 / signals | killTree | `kill()` → `terminate()` 进程组 SIGTERM→SIGKILL / process-group SIGTERM→SIGKILL；后台忽略 timeoutMs / background ignores timeoutMs |

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 / Notes |
|----------------------|:--:|------|
| Shell 环境完整性 / Environment fidelity | **Claude Code** | 快照、别名、函数、CWD 追踪，考虑最周全 / snapshots, aliases, functions, CWD tracking — the most thorough |
| PTY 支持 / PTY support | **Codex / CodeWhale** | 原生 PTY，适合交互式命令 / native PTY, suitable for interactive commands |
| 参数构造灵活性 / Argument flexibility | **OpenCode** | 每种 shell 独立参数模板 / per-shell argument templates |
| 环境变量卫生 / Env hygiene | **deepseek-harness** | 凭证形态 env 名自动擦除 + 受信 `DSH_*` 变量注入，防密钥隐式泄漏 / credential-shaped env names auto-scrubbed + trusted `DSH_*` variable injection, preventing implicit key leakage |

---

## 7. 进程终止 | Process Termination

### 7.1 对比 | Comparison

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **实现方式** Approach | `tree-kill` npm 包 / npm package | Linux: `PR_SET_PDEATHSIG`<br>Win: `CreateJobObjectW` + `KILL_ON_JOB_CLOSE` | `kill_on_drop(true)` | Win: `taskkill /T /F`<br>POSIX: `process.kill(-pid)` | POSIX: `process.kill(-pid)` 进程组 / process group<br>Win: `taskkill /PID /T /F`<br>两阶段 / two-phase SIGTERM → graceMs(3s) → SIGKILL |
| **进程树清理** Tree cleanup | tree-kill 递归遍历 / recursive traversal | **内核级自动回收 / kernel-level automatic reclamation** | Tokio 自动管理 / Tokio auto-management | 手动 SIGTERM → 延迟 → SIGKILL 级联 / manual SIGTERM → delay → SIGKILL cascade | kill 前 `treeAlive()` 重探测防 PID 复用 / re-probe `treeAlive()` before each kill against PID reuse；PTY 会话级清理（先杀后代再杀 shell）/ PTY session-level cleanup (descendants first, then the shell)；Linux `/proc` 组存活探测 / group liveness probing |
| **异常退出保护** Crash safety | 依赖包实现 / relies on the package | ✅ 父进程死亡 → 子进程自动终止 / parent death → children auto-terminated | ✅ tokio drop 保证 / guaranteed by tokio drop | ❌ 需手动处理 / manual handling required | ✅ host `exit` 事件同步 SIGKILL 兜底 / synchronous SIGKILL fallback on host exit（`terminateForHostExit`） |

### 7.2 详细对比 | Details

#### CodeWhale —— 最可靠的方案 | Most Robust Approach

```rust
// Linux: 使用内核特性，父进程死亡时子进程自动收到信号
// kernel feature: children receive the signal automatically when the parent dies
#[cfg(target_os = "linux")]
unsafe {
    libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL, 0, 0, 0);
}

// Windows: 使用 Job Objects，父进程退出时子进程被强制终止
// Job Objects: children are forcibly terminated when the parent exits
#[cfg(windows)]
unsafe {
    let job = CreateJobObjectW(null(), null());
    let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    SetInformationJobObject(job, ...);
    AssignProcessToJobObject(job, child_process_handle);
}
```

#### OpenCode —— 两阶段终止 | Two-Phase Termination

```typescript
export async function killTree(proc: ChildProcess, opts?: { exited?: () => boolean }) {
  if (process.platform === "win32") {
    // Windows: 使用 taskkill 强制终止进程树 / force-terminate the process tree via taskkill
    const killer = spawn("taskkill", ["/pid", String(pid), "/f", "/t"], { ... })
  } else {
    // POSIX: SIGTERM → 等待 3s → SIGKILL / wait 3s → SIGKILL
    process.kill(-pid, "SIGTERM")
    await sleep(3000)
    if (!opts?.exited?.()) process.kill(-pid, "SIGKILL")
  }
}
```

#### Claude Code

```typescript
import treeKill from 'tree-kill'

#doKill(code?: number): void {
  this.#status = 'killed'
  if (this.#childProcess.pid) {
    treeKill(this.#childProcess.pid, 'SIGKILL')
  }
  this.#resolveExitCode(code ?? SIGKILL)
}
```

#### deepseek-harness —— 树级两阶段升级 + PID 复用防护 | Tree-Scoped Two-Phase Escalation

```typescript
// spawn.ts - 唯一对外终止动词 terminate()：SIGTERM → graceMs → SIGKILL 升级
// the only external termination verb: SIGTERM → graceMs → SIGKILL escalation
const terminate = (): void => {
  if (treeExitObserved || graceTimer !== undefined) return   // 幂等 / idempotent
  kill('SIGTERM')
  graceTimer = setTimeout(() => { kill('SIGKILL') }, spec.graceMs)  // 默认 3s / default 3s
}
// 每次 kill 前都重探测"树是否还活着"（treeAlive()），防 PID 复用误杀无关进程
// re-probe tree liveness (treeAlive()) before each kill, so PID reuse never kills unrelated processes

// 平台分派：POSIX 负 pid 发整个进程组；Windows taskkill /T /F
// platform dispatch: negative pid signals the whole group on POSIX; taskkill /T /F on Windows
function signalTree(platform, pid, sig, child, taskkill): void {
  if (platform === 'win32') { taskkill(pid); return }
  try { process.kill(-pid, sig) }            // 进程组 / process group
  catch { try { child.kill(sig) } catch {} } // 组已消失 → 回退直接子进程 / group gone → fall back to the direct child
}

// PTY 会话级清理（terminal.ts）：先杀后代（TERM→grace→KILL），再杀 shell，
// PTY session-level cleanup (terminal.ts): descendants first (TERM→grace→KILL), then the shell,
// 拒绝向前台组 = shell 自身（pgid === this.pid）发 SIGKILL
// refuses to SIGKILL the foreground group when it is the shell itself (pgid === this.pid)
```

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 / Notes |
|----------------------|:--:|------|
| 可靠性 / Reliability | **CodeWhale** | PDEATHSIG + Job Objects 是内核级保证，即使进程 panic 也不会泄漏 / kernel-level guarantee; no leaks even if the process panics |
| 简洁性 / Simplicity | **Codex** | `kill_on_drop(true)` 一行搞定 / one line |
| 跨平台兼容 / Cross-platform | **OpenCode** | 明确区分 Win/POSIX，逻辑清晰 / clear Win/POSIX distinction, clean logic |
| PID 复用防护 / PID-reuse guard | **deepseek-harness** | kill 前重探测进程树 + PID+started 双因子身份，防止误杀无关进程 / re-probe before kill + PID+started two-factor identity, preventing kills of unrelated processes |

---

## 8. 输出处理 | Output Handling

### 8.1 总览 | Overview

| | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **方式** Strategy | **文件描述符输出 / File-descriptor output** | 内存 Buffer / in-memory buffer | PTY/Pipe 流式 / streaming | 流式 + 溢出写文件 / streaming + overflow to file | **内存尾窗 + spill 文件 / In-memory tail + spill file**（tail-keep） |
| **stdout/stderr** | 同一文件按时间交错 / same file, interleaved by time（O_APPEND） | 分开收集 / collected separately | 分开收集 / collected separately | 合并收集 / merged（all stream） | 分开收集 / collected separately |
| **截断策略** Truncation | 大输出落盘，返回 `outputFilePath` / large output goes to disk, returns `outputFilePath` | `shell_output.rs` 截断 + 摘要 / truncation + summary | `FullBuffer` vs `ShellTool` | 1MB 上限 / 1MB cap（`MAX_CAPTURE_BYTES`） | 每流 / per-stream 64KB 内存尾窗 / in-memory tail + 64MiB spill 上限 / cap（超限删 spill 文件 / spill deleted on overflow）；终端 / terminal scrollback 4MiB / 视口 / viewport 256KiB |
| **后台监控** BG monitoring | 文件大小看门狗（5s 轮询）/ file-size watchdog (5s polling) | async 流处理 / stream handling | exec-server 事件流 / event stream | `Effect.forkScoped` + `Stream.runForEach` | `readFrom(offset)` 偏移量增量读取（多读者安全，不消费 / multi-reader safe, non-consuming） |
| **关键文件** Key file | `src/utils/Shell.ts` `src/utils/ShellCommand.ts` | `crates/tui/src/tools/shell_output.rs` (299 行 / lines) | `codex-rs/exec-server/src/local_process.rs` | `packages/opencode/src/tool/shell.ts` | `packages/subprocess/subprocess-local/src/spawn.ts`（`OutputCollector` 104-251 行 / lines） |

### 8.2 四种典型策略 | Four Output Strategies

#### 策略 A：文件描述符 | Strategy A: File Descriptor（Claude Code 独有）

```
spawn shell → stdout/stderr → 同一文件 fd / same file fd (O_APPEND)
                              ├─ 按时间交错写入（保持时序）/ interleaved writes by time (timing preserved)
                              ├─ O_NOFOLLOW 防符号链接攻击 / against symlink attacks
                              ├─ 小输出：内存读取 / small output: read in memory
                              └─ 大输出：返回 outputFilePath 引用 / large output: return an outputFilePath reference
```

**优势 / Pros**：
- 不阻塞管道，适合长时间运行的命令 / non-blocking pipes, good for long-running commands
- 原子写入（POSIX O_APPEND 保证）/ atomic writes (guaranteed by POSIX O_APPEND)
- 安全（O_NOFOLLOW 防止沙箱逃逸）/ secure (O_NOFOLLOW prevents sandbox escape)
- 大输出不占用内存 / large output does not consume memory

**劣势 / Cons**：
- Windows 兼容性需要特殊处理（MSYS2）/ Windows compatibility needs special handling (MSYS2)
- 需要额外的文件管理逻辑 / extra file-management logic required

#### 策略 B：PTY/Pipe 流式 | Strategy B: PTY/Pipe Streaming（Codex、OpenCode）

```
spawn shell → PTY/Pipe → 流式读取 / streaming reads
              ├─ 逐 chunk 收集 / collect chunk by chunk
              ├─ 超限时截断 / truncate on overflow
              └─ 溢出部分写入文件 / overflow written to a file
```

#### 策略 C：内存 Buffer | Strategy C: In-Memory Buffer（CodeWhale）

```
spawn shell → 完整收集 / full collection → 截断 + 摘要 / truncate + summarize
```

#### 策略 D：内存尾窗 + spill 文件 | Strategy D: Tail + Spill（deepseek-harness）

```
spawn shell → 流式收集 / streaming collection（OutputCollector）
              ├─ 内存只保留"最后 maxBytes 字节"（尾部；错误与最终结果集中在输出末尾）
              │  memory keeps only the "last maxBytes bytes" (the tail; errors and final results cluster at the end)
              ├─ 首次溢出 → 创建 spill 文件（随机后缀 + wx 防符号链接植入 + 0600 仅 owner）
              │  first overflow → create a spill file (random suffix + wx against symlink planting + 0600 owner-only)
              │    └─ 完整流（含已收集 chunk）落盘 → 头部可从 spill 恢复
              │       full stream (incl. collected chunks) to disk → the head is recoverable from the spill
              ├─ 超过 spill 上限（64MiB）→ 删除 spill 文件，仅留内存尾窗
              │  beyond the spill cap (64MiB) → delete the spill file, keep the in-memory tail only
              └─ 返回 { text, truncated, spillPath? }，模型可见 / model-visible [output truncated; full output: <path>]
```

**优势 / Pros**：
- 头尾兼顾：spill 文件承载完整流（头部），内存尾窗覆盖尾部（错误/结果）/ head+tail: the spill holds the full stream (head), the in-memory tail covers the end (errors/results)
- 偏移量读取 `readFrom(offset)` 不消费流，多读者安全（后台增量读取的基础）/ offset reads via `readFrom(offset)` do not consume the stream — multi-reader safe (the basis of background incremental reads)
- 文件安全：随机后缀 + `wx` 标志 + 私有目录（0700），防共享 tmp 目录攻击 / file safety: random suffix + `wx` flag + private directory (0700), against shared-tmp-dir attacks
- 管道排水超时：子进程 exit 后幸存后代继承管道 fd 时，用同一 graceMs 限制 `close` 等待 / pipe-drain timeout: when surviving descendants inherit pipe fds after child exit, the same graceMs bounds the `close` wait

**劣势 / Cons**：
- truncated 时模型需额外读 spill 文件 / the model must read the spill file when truncated
- 需要临时文件生命周期管理（超限即删）/ temp-file lifecycle management required (deleted on overflow)

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 / Notes |
|----------------------|:--:|------|
| 大输出处理 / Large output | **Claude Code** | 文件描述符方案不占用内存 / the fd scheme uses no memory |
| 时序保真度 / Timing fidelity | **Claude Code** | stdout/stderr 按时间交错 / stdout/stderr interleaved by time |
| 实现简洁 / Simplicity | **CodeWhale** | 直接内存收集 / direct in-memory collection |
| 头尾兼顾 / Head+tail | **deepseek-harness** | spill 文件承载完整流，内存尾窗覆盖尾部，偏移读取不消费 / the spill holds the full stream, the in-memory tail covers the end, offset reads are non-consuming |

---

## 9. 超时机制 | Timeout

| | Claude Code | CodeWhale | Codex | OpenCode | deepseek-harness |
|---|---|---|---|---|---|
| **实现** Implementation | `AbortSignal` + 命令级超时 / command-level timeout | `wait_timeout` crate | `ExecExpiration` 结构体 / struct | `Duration` + `forceKillAfter` | `deadline()`（dsh-timeout）融合超时与取消 / merges timeout and cancellation + guard 插件 / guard plugin `tool-call-timeout-policy`（TOOL_TIMEOUT） |
| **默认值** Default | 可配置 / configurable | 可配置 / configurable | 可配置 / configurable | 2 分钟 / 2 min（`DEFAULT_TIMEOUT_MS`） | 120s（前台 bash / foreground bash）；终端 / terminal send 等待 / waits 30s（仅 settle 不杀 shell / settles only, never kills the shell） |
| **最大值** Maximum | 可配置 / configurable | 可配置 / configurable | 可配置 / configurable | 10 分钟 / 10 min（`MAX_TIMEOUT_MS`） | 600s（单次覆盖上限 / per-call override cap clampTimeout）；后台任务忽略 timeoutMs / background tasks ignore timeoutMs |
| **输出上限** Output cap | 文件大小 + 行数 / file size + line count | Buffer 大小 / buffer size | Buffer 大小 / buffer size | 1MB（`MAX_CAPTURE_BYTES`） | 64KB/流内存 / 64KB per-stream memory + 64MiB spill |

---

## 10. 各项目架构详解 | Architecture Details

### 10.1 Claude Code

```
用户命令 | User command "!ls"
  │
  ├─ processBashCommand.tsx         ← 入口 | Entry：判断 Shell 类型 / resolve the shell type
  │   ├─ isPowerShellToolEnabled()  
  │   └─ resolveDefaultShell()      
  │
  ├─ BashTool.tsx (1144 行 / lines) ← Bash 工具主逻辑 | Tool logic
  │   ├─ bashSecurity.ts (2592 行 / lines)   ← 安全校验 | Security（50+ 检查项 / checks）
  │   ├─ bashPermissions.ts (2621 行 / lines)← 权限系统 | Permissions
  │   └─ bashCommandHelpers.ts      ← 复合命令处理 | Compound commands
  │
  ├─ bashParser.ts (4436 行 / lines)← 纯 TS 手写 Parser | Handwritten parser
  │   ├─ Tokenizer（词法分析 / lexing）
  │   ├─ Parser（语法分析 / parsing → tree-sitter 兼容 AST / compatible AST）
  │   └─ 安全限制 | Safeguards（50ms 超时 / 50000 节点预算）
  │
  ├─ ShellProvider                  ← Shell 抽象层 | Abstraction layer
  │   ├─ bashProvider.ts (255 行 / lines)    ← bash 环境初始化 / env initialization
  │   └─ powershellProvider.ts      ← pwsh 环境初始化 / env initialization
  │
  ├─ Shell.ts (474 行 / lines)               ← exec() 入口 | Entry：spawn 进程 / spawn the process
  │   └─ ShellCommand.ts (465 行 / lines)    ← wrapSpawn：状态追踪、超时、后台 / status tracking, timeout, background
  │
  └─ 输出层 | Output
      ├─ 文件描述符 / file descriptors (O_APPEND/O_NOFOLLOW)
      ├─ 后台看门狗 | BG watchdog (5s 轮询 / polling)
      └─ outputFilePath 引用返回 / returns an outputFilePath reference
```

### 10.2 CodeWhale

```
用户命令 | User command
  │
  ├─ tool_catalog.rs                ← exec_shell 注册为默认工具 / registered as the default tool
  │
  ├─ shell_dispatcher.rs (565 行 / lines)    ← Shell 检测 & 命令构建 / shell detection & command construction
  │   ├─ ShellKind 枚举检测 / enum detection
  │   └─ build_command() → std::process::Command
  │
  ├─ command_safety.rs (1468 行 / lines)     ← 安全分析 | Safety（正则匹配 / regex matching）
  │
  ├─ execpolicy/lib.rs (853 行 / lines)      ← 策略引擎 | Policy engine
  │   ├─ ToolAskRule: allow/deny/ask
  │   └─ bash_arity.rs (579 行 / lines)      ← 命令前缀参数数量白名单 / whitelist of command-prefix argument counts
  │
  ├─ shell.rs (3071 行 / lines)              ← 核心执行引擎 | Core engine
  │   ├─ execute()                  ← 命令解析与执行 / command parsing & execution
  │   ├─ execute_sync_sandboxed()   ← 同步 + 沙箱 / synchronous + sandbox
  │   ├─ spawn_background_sandboxed()← 后台 + PTY / background + PTY
  │   └─ ShellResult { exit_code, stdout, stderr, ... }
  │
  ├─ sandbox/mod.rs                 ← 沙箱模块 | Sandbox
  │
  └─ 进程管理 | Process management
      ├─ PR_SET_PDEATHSIG (Linux)
      └─ CreateJobObjectW (Windows)
```

### 10.3 Codex (OpenAI)

```
用户命令 | User command
  │
  ├─ shell_detect.rs                ← Shell 类型检测 / shell type detection
  │
  ├─ bash.rs                        ← tree-sitter-bash 解析 / parsing
  │   └─ extract_bash_command()
  │
  ├─ shell.rs                       ← Shell 抽象 / shell abstraction
  │   └─ derive_exec_args()
  │
  ├─ execpolicy crate               ← 策略引擎 | Policy engine
  │   ├─ PrefixRule: 前缀匹配 / prefix matching
  │   └─ NetworkRuleProtocol: 网络控制 / network control
  │
  ├─ exec.rs (1570 行 / lines)               ← 核心执行引擎 | Core engine
  │   ├─ ExecParams { command, cwd, expiration, sandbox, ... }
  │   ├─ ExecExpiration: 超时/取消 / timeout/cancellation
  │   └─ ExecCapturePolicy: ShellTool | FullBuffer
  │
  ├─ spawn.rs                       ← 进程生成 | Process spawn
  │   └─ spawn_child_async() → tokio::process::Command
  │
  ├─ exec-server/                   ← 执行后端 | Execution backend
  │   ├─ local_process.rs           ← PTY/Pipe 生成 / PTY/pipe spawning
  │   ├─ remote_process.rs          ← 远程执行 / remote execution
  │   └─ process.rs                 ← 事件类型 & 日志 / event types & logging
  │
  ├─ shell-escalation/ (Unix only)  ← execve 拦截 | Interception
  │   ├─ execve_wrapper.rs          ← 拦截入口 / interception entry
  │   ├─ escalate_client.rs         ← 调用 libc::execv() / calls libc::execv()
  │   ├─ escalate_server.rs         ← 策略路由 / policy routing
  │   └─ escalation_policy.rs       ← 决策 trait / decision trait
  │
  └─ sandboxing crate               ← 沙箱抽象 | Sandbox abstraction
```

### 10.4 OpenCode

```
用户命令 | User command
  │
  ├─ tool/bash.ts (V2)              ← Bash 工具定义 | Tool definition
  │   ├─ Input: { command, workdir, timeout, description }
  │   ├─ Output: { exitCode, output, truncated, timedOut }
  │   └─ 权限检查 & 路径验证 / permission checks & path validation
  │
  ├─ tool/shell.ts (657 行 / lines)          ← OpenCode Shell 工具 / the OpenCode shell tool
  │   ├─ tree-sitter 解析 (bash + pwsh WASM) / tree-sitter parsing (bash + pwsh WASM)
  │   ├─ 权限审批（命令模式匹配）/ permission approval (command-pattern matching)
  │   ├─ 流式输出收集 / streaming output collection
  │   └─ 溢出写文件截断 / overflow-to-file truncation
  │
  ├─ shell/shell.ts (215 行 / lines)         ← Shell 运行时 | Runtime
  │   ├─ META: 10 种 Shell 元数据 / metadata for 10 shells
  │   ├─ args(): 每种 Shell 独立参数模板 / per-shell argument templates
  │   └─ killTree(): 两阶段终止 / two-phase termination
  │
  ├─ cross-spawn-spawner.ts (508 行 / lines) ← 进程生成器 | Spawner
  │   ├─ spawn(): cross-spawn → Node spawn
  │   ├─ killGroup(): Win taskkill / POSIX process.kill(-pid)
  │   └─ 流式 stdout/stderr 收集 / streaming stdout/stderr collection
  │
  ├─ process.ts                     ← AppProcess 抽象 / abstraction
  │   ├─ run(): 完整执行 + 超时 / full execution + timeout
  │   └─ runStream(): 流式执行 / streaming execution
  │
  └─ 辅助模块 | Auxiliary
      ├─ pty.ts / pty.node.ts / pty.bun.ts  ← PTY 支持 / PTY support
      ├─ desktop/shell-env.ts                ← Shell 环境探测 / shell env probing
      └─ plugin/shell.ts                     ← 插件 Shell 类型 / plugin shell types
```

### 10.5 deepseek-harness

```
模型工具 | Model tools（tool-bash / tool-pwsh / tool-bash-persistent / tool-terminal）
  │  schema: command/description/timeoutMs/workdir/run_in_background/sandbox_permissions
  │  └─ execute(): 沙箱升级审批 / sandbox escalation approval → shellEnv.collect(DSH_*) → 后台 / background ctx.jobs.start() / 前台 / foreground ctx.shell.run()
  │
  ├─ shell 能力缝 | Seam: ShellExecutor (resolve/run/start)   ← packages/shell/shell/
  │   ├─ bash-local (333 行 / lines)      ← bash -c <command> 单 argv 直传 / single-argv passthrough（无 login/rc/eval）
  │   ├─ bash-sandbox (182 行 / lines)    ← confine(argv, policy) 整条 argv 沙箱包装 / wraps the whole argv in a sandbox（继承本地执行器 / inherits the local executor）
  │   ├─ pwsh-local (363 行 / lines)      ← pwsh -NoLogo -NoProfile -NonInteractive -Command
  │   └─ pwsh-sandbox (189 行 / lines)    ← 同上 / same as above + Windows ACL confine
  │
  ├─ subprocess 能力缝 | Seam: SubprocessRuntime (spawn/spawnTerminal)  ← packages/subprocess/
  │   ├─ spawn.ts (543 行 / lines)        ← node:child_process.spawn + detached 进程组 / process group
  │   │   ├─ OutputCollector     ← 内存尾窗 64KB + spill 文件 64MiB / in-memory 64KB tail + 64MiB spill file（wx/0600/随机后缀 / random suffix）
  │   │   ├─ signalTree          ← POSIX kill(-pid) / Win taskkill /PID /T /F
  │   │   └─ terminate()         ← SIGTERM → graceMs(3s) → SIGKILL（kill 前重探测树存活 / re-probes tree liveness before killing）
  │   ├─ terminal.ts (249 行 / lines)     ← node-pty PTY 会话 / PTY session（TERM=dumb，会话级清理 / session-level cleanup）
  │   └─ process-inspector.ts (374 行 / lines) ← /proc + ps 进程表 / process table：树遍历 / tree traversal / 前台组 tpgid / foreground tpgid / stdin 等待 syscall / stdin-waiting syscalls
  │
  ├─ sandbox 能力缝 | Seam: SandboxProvider (confine)   ← packages/sandbox/
  │   ├─ sandbox-local (567 行 / lines)   ← 平台链 / platform chain：linux [bwrap→landlock 探测 / probing] / darwin [seatbelt] / win32 [windows-acl]
  │   ├─ sandbox-policy (154 行 / lines)  ← 三档模式 + 会话覆盖 / three-tier modes + session override（session 日志事件 / log event sandbox/mode）
  │   ├─ windows-acl (~2480 行 / lines)   ← WRITE_RESTRICTED 受限令牌 / restricted token + SID 白名单 ACE / whitelist ACE（只限写 / write-only）
  │   └─ native landlock-run     ← C11 原生 addon / native C11 addon（~300 行 / lines main.c），fail-closed 退出码 / exit code 125
  │
  ├─ terminal 能力缝 | Seam: TerminalSessionService（持久 PTY 会话 / persistent PTY sessions）   ← packages/terminal/
  │   ├─ session.ts (565 行 / lines)      ← 单飞 send / single-flight send + 4 种就绪判定 / readiness verdicts（stdin_read/精确探针 / exact probe/inferred_idle/session_exit）+ 30s 超时 / timeout
  │   └─ sanitize.ts (188 行 / lines)     ← 流式转义序列剥离 / streaming escape-sequence stripping（OSC/CSI），识别 / recognizes 133;D 提示符标记 / prompt markers
  │
  └─ guard 插件 | Guard plugins（packages/guard/）
      ├─ tool-call-timeout-policy ← 工具级超时包装 / per-tool timeout wrapper（TOOL_TIMEOUT）
      └─ repeat-tool-reminder     ← 重复工具调用提醒 / repeated-tool-call reminders
```

---

## 11. 总结评价 | Summary & Evaluation

### 各维度最佳 | Best by Dimension

| 维度 / Dimension | 最佳项目 / Best | 说明 / Notes |
|------------------|:--:|------|
| **命令解析深度** / Parsing depth | **Claude Code** | 手写 4436 行 bash parser + 50ms 超时 + 节点限制 / handwritten 4436-line bash parser + 50ms timeout + node budget |
| **安全防护广度** / Security breadth | **Claude Code** | 5000+ 行安全代码，覆盖数十种攻击模式 / 5000+ lines of security code covering dozens of attack patterns |
| **沙箱隔离深度** / Sandbox depth | **Codex** | `execve` 拦截为独有特性，从系统调用层面控制 / execve interception is unique — control at the syscall level |
| **沙箱后端多样性** / Sandbox backends | **deepseek-harness** | 3 平台 4 后端（bwrap→landlock 探测链 / probe chain / seatbelt / windows-acl），全 fail-closed / all fail-closed |
| **进程生命周期可靠性** / Process reliability | **CodeWhale** | PDEATHSIG + Job Objects 内核级保证 / kernel-level guarantee |
| **Shell 种类覆盖** / Shell coverage | **OpenCode** | 10 种 shell（含 fish/nu/dash），元数据驱动 / 10 shells (incl. fish/nu/dash), metadata-driven |
| **大输出处理** / Large output | **Claude Code** | 文件描述符方案：不占内存、时序保真 / fd scheme: no memory, timing-faithful |
| **输出头尾兼顾** / Head+tail output | **deepseek-harness** | spill 文件承载完整流 + 内存尾窗，偏移读取不消费 / the spill holds the full stream + in-memory tail; offset reads are non-consuming |
| **环境变量安全** / Env safety | **deepseek-harness** | 凭证形态 env 名自动擦除（KEY/PASSWORD/SECRET/TOKEN + DSH_*）/ credential-shaped env names auto-scrubbed (…) |
| **工程架构清晰度** / Architecture | **Codex** | 多 crate 分层，关注点分离最好 / multi-crate layering, best separation of concerns |
| **抽象缝设计** / Seam design | **deepseek-harness** | seam 与实现彻底分离，本地/沙箱/远程可整体替换 / seams fully separated from implementations; local/sandbox/remote fully swappable |
| **代码简洁性** / Code brevity | **CodeWhale** | 单文件 `shell.rs` 3071 行集中管理 / single-file `shell.rs` (3071 lines) centralized management |
| **跨平台兼容性** / Cross-platform | **OpenCode** | `cross-spawn` + 明确的 Win/POSIX 分支 / explicit Win/POSIX branches |
| **PTY 支持** / PTY support | **Codex / CodeWhale** | 原生 PTY 支持交互式命令 / native PTY for interactive commands |

### 各项目定位 | Project Positioning

| 项目 / Project | 定位 / Positioning | 定位（英）/ Positioning (EN) | 核心设计理念 / Design Philosophy |
|-------------|-------------|------|------|
| **Claude Code** | 面向外部用户的商业产品 | External-facing product | 安全第一 / Security first：解析器和安全层投入巨大，适合不可信输入 / heavy investment in parser and security layers, suited to untrusted input |
| **Codex** | 多场景部署平台 | Multi-scenario platform | 架构优先 / Architecture first：分层清晰，支持本地/远程执行，沙箱隔离最深 / clear layering, local/remote execution, deepest sandbox isolation |
| **CodeWhale** | 实用主义工具 | Pragmatic tooling | 简洁高效 / Pragmatic：最少代码解决核心问题，进程管理最可靠 / minimal code for core problems, most reliable process management |
| **OpenCode** | 开发者工具 | Developer tool | 兼容性优先 / Compatibility first：支持最多 shell 类型，streaming 体验好 / most shell types, great streaming experience |
| **deepseek-harness** | DeepSeek 开源 Agent 框架 | Open-source agent framework | 插件化 + fail-closed / Plugin-first + fail-closed：一切皆插件（Cordis），安全靠沙箱兜底而非命令解析 / everything is a plugin (Cordis); security backed by the sandbox rather than command parsing |

### 可借鉴的设计模式 | Design Patterns Worth Adopting

1. **Shell Provider 模式**（Claude Code / Codex）：接口抽象 + 多实现，便于扩展新 Shell
   **Shell Provider pattern**: Interface abstraction with multiple implementations for easy shell extension.
2. **PDEATHSIG + Job Objects**（CodeWhale）：最可靠的进程生命周期管理
   **PDEATHSIG + Job Objects**: Most reliable process lifecycle management.
3. **文件描述符输出**（Claude Code）：解决大输出和时序保真问题
   **File descriptor output**: Solves large output and timing fidelity issues.
4. **execve 拦截**（Codex）：最深层的沙箱隔离
   **execve interception**: Deepest sandbox isolation layer.
5. **META 元数据驱动**（OpenCode）：声明式管理多种 Shell 差异
   **META metadata-driven**: Declarative management of cross-shell differences.
6. **两阶段终止**（OpenCode）：SIGTERM 优雅退出 → SIGKILL 兜底
   **Two-phase termination**: SIGTERM graceful shutdown → SIGKILL as fallback.
7. **tree-sitter WASM 异步加载**（OpenCode）：零安装依赖的语法解析
   **tree-sitter WASM async loading**: Zero-install dependency for syntax parsing.
8. **能力缝（Seam）模式**（deepseek-harness）：抽象服务接口与本地实现分离，为远程/沙箱实现预留
   **Capability seam**: Abstract service interface separated from local implementation, reserved for remote/sandbox variants.
9. **内存尾窗 + spill 文件**（deepseek-harness）：完整流落盘、内存只留尾部，头尾兼顾
   **Tail-keep + spill file**: Full stream spilled to disk while memory keeps only the tail.
10. **fail-closed 沙箱**（deepseek-harness）：沙箱不可用即拒绝执行，绝不无限制 spawn
    **Fail-closed sandbox**: Refuse to execute when sandbox is unavailable; never spawn unrestricted.
