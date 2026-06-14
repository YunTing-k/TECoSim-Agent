# 四款 Agent 项目 Bash/Shell 命令实现对比分析
# Bash/Shell Command Implementation: A Cross-Project Comparison

> 对比项目 | Projects：Claude Code · CodeWhale · Codex (OpenAI) · OpenCode  
> 分析日期 | Date：2026-06-14

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

| 维度 / Dimension | Claude Code | CodeWhale | Codex (OpenAI) | OpenCode |
|-----------------|:--:|:--:|:--:|:--:|
| **主语言** / Language | TypeScript (Bun) | Rust | Rust | TypeScript (Effect-TS) |
| **核心文件数** / Core files | ~15 | ~6 | ~10+ crates | ~10 |
| **核心代码量** / Code volume | ~15000 行 | ~6700 行 | ~4000+ 行 | ~2500+ 行 |
| **项目路径** / Path | `D:\Claude Code\claude-code-rev` | `D:\CodeWhale` | `D:\codex` | `D:\opencode` |

---

## 2. 语言与运行时 | Language & Runtime

| | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **主语言** Language | TypeScript，运行于 Bun | Rust，tokio 异步运行时 | Rust，tokio 异步运行时 | TypeScript，Effect-TS 效应系统 |
| **进程 API** Process API | `child_process.spawn()` + `execa` | `std::process::Command` | `tokio::process::Command` | `cross-spawn` (npm 库) |
| **JS 侧补充** JS glue | — | `child_process.spawnSync`（npm wrapper） | TypeScript SDK 封装 CLI 二进制 | — |
| **源码目录** Source dirs | `src/tools/BashTool/` `src/utils/bash/` `src/utils/shell/` | `crates/tui/src/tools/shell.rs` `crates/tui/src/shell_dispatcher.rs` | `codex-rs/core/src/exec.rs` `codex-rs/shell-command/` `codex-rs/exec-server/` | `packages/core/src/tool/bash.ts` `packages/opencode/src/tool/shell.ts` `packages/core/src/cross-spawn-spawner.ts` |

### 关键差异 | Key Differences

- **Rust 系**（CodeWhale、Codex）：性能和内存安全占优，编译期即排除数据竞争，适合大规模部署和高并发场景。
  **Rust-based** (CodeWhale, Codex): Better performance and memory safety — data races ruled out at compile time, well-suited for large-scale deployment and high-concurrency scenarios.
- **TypeScript 系**（Claude Code、OpenCode）：迭代速度快，npm 生态丰富，适合快速原型和频繁变更。
  **TypeScript-based** (Claude Code, OpenCode): Faster iteration with rich npm ecosystem, ideal for rapid prototyping and frequent change cycles.

---

## 3. Shell 检测与抽象 | Shell Detection & Abstraction

### 3.1 抽象方式对比 | Abstraction Approach

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **抽象方式** Approach | `ShellProvider` 接口 | `ShellKind` 枚举 | `ShellType` 枚举 | `META` 元数据对象 |
| **关键文件** Key file | `src/utils/shell/shellProvider.ts` | `crates/tui/src/shell_dispatcher.rs` | `codex-rs/shell-command/src/shell_detect.rs` | `packages/opencode/src/shell/shell.ts` |
| **代码行数** Lines | 33（接口）+ 255（bash）+ 123（pwsh） | 565 | ~100 | 215 |

### 3.2 支持的 Shell 类型 | Supported Shell Types

| Shell | Claude Code | CodeWhale | Codex | OpenCode |
|-------|:--:|:--:|:--:|:--:|
| bash | ✅ | ✅ | ✅ | ✅ |
| zsh | ✅ | ❌ | ✅ | ✅ |
| sh | ✅ | ✅ | ✅ | ✅ |
| PowerShell (pwsh) | ✅ | ✅ | ✅ | ✅ |
| Windows PowerShell | ❌ | ✅ | ❌ | ❌ |
| cmd | ❌ | ✅ | ✅ | ✅ |
| fish | ❌ | ❌ | ❌ | ✅ (标记 deny) |
| dash | ❌ | ❌ | ❌ | ✅ |
| ksh | ❌ | ❌ | ❌ | ✅ |
| nu (nushell) | ❌ | ❌ | ❌ | ✅ (标记 deny) |
| Custom（用户自定义） | ❌ | ✅ | ❌ | ❌ |

### 3.3 检测策略 | Detection Strategy

#### Claude Code —— 多级回退 | Multi-level Fallback

```
CLAUDE_CODE_SHELL 环境变量
  → $SHELL 环境变量（限定为 bash 或 zsh）
    → which bash / which zsh
      → 常见路径：/bin, /usr/bin, /usr/local/bin, /opt/homebrew/bin
        → 默认偏好：zsh > bash（当 $SHELL 含 'bash' 时反转）
```

#### CodeWhale —— 启动时自动检测 | Auto-Detect on Startup

```rust
pub enum ShellKind {
    Pwsh,                   // PowerShell Core
    WindowsPowerShell,      // 旧版 Windows PowerShell
    Cmd,                    // Windows cmd
    Sh,                     // POSIX sh
    Bash,                   // 通过 $SHELL 或 WSL/Git Bash 检测
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
// 通过 detect_shell_type(PathBuf) 匹配 shell 二进制名称
```

#### OpenCode —— 元数据驱动 | Metadata-Driven（覆盖面最广）

```typescript
const META = {
  bash:   { login: true, posix: true },
  dash:   { login: true, posix: true },
  fish:   { deny: true,  login: true },   // 禁止使用但可检测
  ksh:    { login: true, posix: true },
  nu:     { deny: true },                  // 禁止使用但可检测
  powershell: { ps: true },
  pwsh:   { ps: true },
  sh:     { login: true, posix: true },
  zsh:    { login: true, posix: true },
}
```

### 小结 | Summary

| 项目 | 优势 | 劣势 |
|------|------|------|
| Claude Code | 接口设计清晰，Provider 模式易于扩展 | 仅支持 bash/zsh/pwsh |
| CodeWhale | 支持自定义 Shell，检测逻辑集中 | 不支持 zsh |
| Codex | 简洁高效 | Shell 种类偏少 |
| **OpenCode** | **支持 10 种 Shell，覆盖面最广** | deny 标记的 shell 实际不可用 |

---

## 4. 命令解析 | Command Parsing

### 4.1 总览 | Overview

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **解析方式** Approach | **纯 TypeScript 手写解析器** | 正则匹配（无 AST） | `tree-sitter-bash` Rust crate | `web-tree-sitter` + WASM |
| **关键文件** Key file | `src/utils/bash/bashParser.ts` (4436行) | `crates/tui/src/command_safety.rs` (1468行) | `codex-rs/shell-command/src/bash.rs` | `packages/opencode/src/tool/shell.ts` |
| **解析目标** Goal | 生成 tree-sitter 兼容 AST | 检测危险模式 | 提取命令结构 | 提取命令用于权限判定 |
| **安全防护** Safeguard | 50ms 解析超时 + 50000 节点预算 | 无解析层 | tree-sitter 原生保护 | WASM 异步加载 |
| **PowerShell 解析** | 独立 PowerShellTool | ❌ | 计划中 | `tree-sitter-powershell.wasm` |

### 4.2 各项目详解 | Details

#### Claude Code —— 手写 Parser | Handwritten Parser（4436 行）

四个项目中投入最大、实现最深的方案。完全用 TypeScript 手写了 bash 解析器，包含：

- **完整 Tokenizer**：词法分析，覆盖所有 bash 词法规则
- **完整 Parser**：语法分析，生成与 tree-sitter-bash 兼容的 AST
- **两重安全防护**：
  - 50ms 解析超时（防止对抗性输入导致 hang）
  - 50,000 节点预算（防止深层嵌套导致 OOM）
- **用途**：驱动安全/权限管线，检测危险命令模式

```typescript
// 关键代码路径
src/utils/bash/bashParser.ts      // 主解析器 (4436 行)
src/utils/bash/bashPipeCommand.ts // 管道命令重排
src/utils/bash/shellCompletion.ts // Shell 补全
src/utils/bash/shellQuote.ts      // Shell 引用工具
src/utils/bash/shellQuoting.ts    // 额外引用处理
src/utils/bash/ShellSnapshot.ts   // Shell 环境快照 (582 行)
```

#### Codex —— tree-sitter-bash Rust 原生绑定 | Native Rust Binding

使用 Rust 原生 `tree-sitter-bash` crate，编译期链接 C 解析器，解析性能最优：

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

```rust
// 检测 curl/wget 管道到 shell 的危险模式
if (command_lower.contains("curl") || command_lower.contains("wget"))
    && (command_lower.contains("| sh")
        || command_lower.contains("| bash")
        || command_lower.contains("| zsh"))
{
    // 标记为危险
}
```

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 |
|----------------------|:--:|------|
| 解析深度 / Depth | **Claude Code** | 手写 4436 行 parser，投入最大 |
| 解析性能 / Performance | **Codex** | Rust 原生 tree-sitter，编译期链接 |
| 工程简洁 / Simplicity | **CodeWhale** | 正则匹配，零外部依赖 |
| Shell 覆盖面 / Coverage | **OpenCode** | 同时解析 bash 和 PowerShell |

---

## 5. 安全与沙箱机制 | Security & Sandbox

### 5.1 安全代码量 | Security Code Volume

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **安全策略代码** Policy code | `bashSecurity.ts` (2592行) + `bashPermissions.ts` (2621行) = **5213行** | `command_safety.rs` (1468行) | `execpolicy` crate (~600行) | bash tool 内联 (~200行) |
| **沙箱代码** Sandbox code | 文件输出层 O_NOFOLLOW | `sandbox/mod.rs` | `sandboxing` crate + `shell-escalation` crate | 路径白名单 |

### 5.2 拦截的危险模式 | Dangerous Pattern Detection

#### Claude Code（覆盖面最广 | Widest Coverage）

- **命令替换**：`$()`、`${}`、`$[]`
- **进程替换**：`<()`、`>()`、`=()`
- **Zsh 危险命令**：`zmodload`、`emulate`、`sysopen`、`zpty`、`ztcp`
- **jq 代码执行**：`jq` 的 `system()` 函数
- **跨操作符传播检测**：`&&`、`||`、`|`、`;` 后的危险命令
- **不完整命令检测**：heredoc 未闭合等
- 所有检查项带有**数字 ID**，用于遥测追踪

#### CodeWhale

- `curl`/`wget` 管道到 `sh`/`bash`/`zsh`
- 各类危险命令关键词匹配
- `execpolicy` 引擎的 allow/deny/ask 策略匹配
- `bash_arity.rs`（579行）：命令前缀 + 参数数量的白名单匹配

#### Codex

- **前缀规则匹配**：`PrefixRule` 基于命令前缀做 allow/deny
- **网络规则**：`NetworkRuleProtocol` 控制网络访问
- **execve 拦截**（独有 | Unique）：Unix 上拦截所有 `exec()` 调用，shell 内部子进程也必经策略引擎

```rust
// shell-escalation/src/unix/execve_wrapper.rs
// 拦截 execve 调用并路由到策略服务器
pub struct EscalateRequest {
    pub program: String,
    pub args: Vec<String>,
    pub env: HashMap<String, String>,
}
```

#### OpenCode

- 外部目录访问控制
- 危险命令模式检测
- tree-sitter 解析辅助权限判断

### 5.3 沙箱层对比 | Sandbox Layer Comparison

| 特性 | Feature | Claude Code | CodeWhale | Codex | OpenCode |
|-------|---------|:--:|:--:|:--:|:--:|
| 文件系统隔离 | FS isolation | `O_NOFOLLOW` 防符号链接攻击 | sandbox 模块识别 shell 程序 | sandboxing crate | 路径白名单 |
| 网络隔离 | Network isolation | — | — | NetworkProxy | — |
| exec 拦截 | exec interception | — | — | ✅ shell-escalation | — |
| 进程清理 | Process cleanup | tree-kill | PDEATHSIG + Job Objects | kill_on_drop | taskkill + SIGKILL |

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 |
|----------------------|:--:|------|
| 安全覆盖广度 / Coverage | **Claude Code** | 5000+ 行安全代码，覆盖数十种攻击模式 |
| 沙箱隔离深度 / Isolation | **Codex** | execve 拦截为独有特性，从内核层面拦截 |
| 可配置性 / Configurability | **Codex** | execpolicy 引擎支持灵活的规则配置 |

---

## 6. 进程生成 | Process Spawning

### 6.1 核心 API 对比 | API Comparison

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **底层 API** Underlying API | `child_process.spawn()` | `std::process::Command` | `tokio::process::Command` | `cross-spawn` → Node `spawn` |
| **关键文件** Key file | `src/utils/Shell.ts` (474行) + `src/utils/ShellCommand.ts` (465行) | `crates/tui/src/tools/shell.rs` (3071行) | `codex-rs/core/src/spawn.rs` + `codex-rs/core/src/exec.rs` (1570行) | `packages/core/src/cross-spawn-spawner.ts` (508行) |
| **跨平台** Cross-platform | `execa` 处理 .bat/.cmd (Win) | Rust 原生跨平台 | Rust 原生跨平台 | `cross-spawn` 库自动适配 |
| **PTY 支持** PTY support | ❌（管道） | ✅（后台任务 PTY） | ✅（`codex_utils_pty`） | ✅（`pty.node.ts` / `pty.bun.ts`） |

### 6.2 Shell 传参方式 | Shell Argument Construction

#### Claude Code

```typescript
// bashProvider.ts - 完整的 shell 环境初始化
const commandString = [
  sourceSnapshot,              // 加载环境快照（别名、函数、环境变量）
  sessionEnvScripts,           // 会话环境脚本
  disableExtendedGlob,         // 禁用扩展 glob（安全）
  `eval ${JSON.stringify(pipeRearrangedCommand)}`,  // 通过 eval 执行
  `pwd -P`,                    // 追踪 CWD 变更
].join('\n')

// 最终执行
spawn('/bin/bash', ['-c', commandString], { ... })
```

#### OpenCode

```typescript
// shell.ts - 根据 shell 类型构造参数
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
// shell.rs - 简洁的参数构造
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

### 6.3 后台任务支持 | Background Task Support

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **后台任务** Background tasks | `LocalShellTask` (523行) | async background spawn | exec-server 进程管理 | Effect forkScoped |
| **输出监控** Output monitoring | 文件大小看门狗（5s 轮询） | tokio 异步 | exec-server 事件流 | Stream.runForEach |
| **任务终止** Task termination | `killShellTasks.ts` | — | exec-server 信号 | killTree |

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 |
|----------------------|:--:|------|
| Shell 环境完整性 / Environment fidelity | **Claude Code** | 快照、别名、函数、CWD 追踪，考虑最周全 |
| PTY 支持 / PTY support | **Codex / CodeWhale** | 原生 PTY，适合交互式命令 |
| 参数构造灵活性 / Argument flexibility | **OpenCode** | 每种 shell 独立参数模板 |

---

## 7. 进程终止 | Process Termination

### 7.1 对比 | Comparison

| 评价维度 / Dimension | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **实现方式** Approach | `tree-kill` npm 包 | Linux: `PR_SET_PDEATHSIG`<br>Win: `CreateJobObjectW` + `KILL_ON_JOB_CLOSE` | `kill_on_drop(true)` | Win: `taskkill /T /F`<br>POSIX: `process.kill(-pid)` |
| **进程树清理** Tree cleanup | tree-kill 递归遍历 | **内核级自动回收** | Tokio 自动管理 | 手动 SIGTERM → 延迟 → SIGKILL 级联 |
| **异常退出保护** Crash safety | 依赖包实现 | ✅ 父进程死亡 → 子进程自动终止 | ✅ tokio drop 保证 | ❌ 需手动处理 |

### 7.2 详细对比 | Details

#### CodeWhale —— 最可靠的方案 | Most Robust Approach

```rust
// Linux: 使用内核特性，父进程死亡时子进程自动收到信号
#[cfg(target_os = "linux")]
unsafe {
    libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL, 0, 0, 0);
}

// Windows: 使用 Job Objects，父进程退出时子进程被强制终止
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
    // Windows: 使用 taskkill 强制终止进程树
    const killer = spawn("taskkill", ["/pid", String(pid), "/f", "/t"], { ... })
  } else {
    // POSIX: SIGTERM → 等待 3s → SIGKILL
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

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 |
|----------------------|:--:|------|
| 可靠性 / Reliability | **CodeWhale** | PDEATHSIG + Job Objects 是内核级保证，即使进程 panic 也不会泄漏 |
| 简洁性 / Simplicity | **Codex** | `kill_on_drop(true)` 一行搞定 |
| 跨平台兼容 / Cross-platform | **OpenCode** | 明确区分 Win/POSIX，逻辑清晰 |

---

## 8. 输出处理 | Output Handling

### 8.1 总览 | Overview

| | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **方式** Strategy | **文件描述符输出** | 内存 Buffer | PTY/Pipe 流式 | 流式 + 溢出写文件 |
| **stdout/stderr** | 同一文件按时间交错（O_APPEND） | 分开收集 | 分开收集 | 合并收集（all stream） |
| **截断策略** Truncation | 大输出落盘，返回 `outputFilePath` | `shell_output.rs` 截断 + 摘要 | `FullBuffer` vs `ShellTool` | 1MB 上限（`MAX_CAPTURE_BYTES`） |
| **后台监控** BG monitoring | 文件大小看门狗（5s 轮询） | async 流处理 | exec-server 事件流 | `Effect.forkScoped` + `Stream.runForEach` |
| **关键文件** Key file | `src/utils/Shell.ts` `src/utils/ShellCommand.ts` | `crates/tui/src/tools/shell_output.rs` (299行) | `codex-rs/exec-server/src/local_process.rs` | `packages/opencode/src/tool/shell.ts` |

### 8.2 三种典型策略 | Three Output Strategies

#### 策略 A：文件描述符 | Strategy A: File Descriptor（Claude Code 独有）

```
spawn shell → stdout/stderr → 同一文件 fd (O_APPEND)
                              ├─ 按时间交错写入（保持时序）
                              ├─ O_NOFOLLOW 防符号链接攻击
                              ├─ 小输出：内存读取
                              └─ 大输出：返回 outputFilePath 引用
```

**优势**：
- 不阻塞管道，适合长时间运行的命令
- 原子写入（POSIX O_APPEND 保证）
- 安全（O_NOFOLLOW 防止沙箱逃逸）
- 大输出不占用内存

**劣势**：
- Windows 兼容性需要特殊处理（MSYS2）
- 需要额外的文件管理逻辑

#### 策略 B：PTY/Pipe 流式 | Strategy B: PTY/Pipe Streaming（Codex、OpenCode）

```
spawn shell → PTY/Pipe → 流式读取
              ├─ 逐 chunk 收集
              ├─ 超限时截断
              └─ 溢出部分写入文件
```

#### 策略 C：内存 Buffer | Strategy C: In-Memory Buffer（CodeWhale）

```
spawn shell → 完整收集 → 截断 + 摘要
```

### 小结 | Summary

| 评价维度 / Dimension | 最佳 / Best | 说明 |
|----------------------|:--:|------|
| 大输出处理 / Large output | **Claude Code** | 文件描述符方案不占用内存 |
| 时序保真度 / Timing fidelity | **Claude Code** | stdout/stderr 按时间交错 |
| 实现简洁 / Simplicity | **CodeWhale** | 直接内存收集 |

---

## 9. 超时机制 | Timeout

| | Claude Code | CodeWhale | Codex | OpenCode |
|---|---|---|---|---|
| **实现** Implementation | `AbortSignal` + 命令级超时 | `wait_timeout` crate | `ExecExpiration` 结构体 | `Duration` + `forceKillAfter` |
| **默认值** Default | 可配置 | 可配置 | 可配置 | 2 分钟（`DEFAULT_TIMEOUT_MS`） |
| **最大值** Maximum | 可配置 | 可配置 | 可配置 | 10 分钟（`MAX_TIMEOUT_MS`） |
| **输出上限** Output cap | 文件大小 + 行数 | Buffer 大小 | Buffer 大小 | 1MB（`MAX_CAPTURE_BYTES`） |

---

## 10. 各项目架构详解 | Architecture Details

### 10.1 Claude Code

```
用户命令 | User command "!ls"
  │
  ├─ processBashCommand.tsx         ← 入口 | Entry：判断 Shell 类型
  │   ├─ isPowerShellToolEnabled()  
  │   └─ resolveDefaultShell()      
  │
  ├─ BashTool.tsx (1144行)          ← Bash 工具主逻辑 | Tool logic
  │   ├─ bashSecurity.ts (2592行)   ← 安全校验 | Security（50+ 检查项）
  │   ├─ bashPermissions.ts (2621行)← 权限系统 | Permissions
  │   └─ bashCommandHelpers.ts      ← 复合命令处理 | Compound commands
  │
  ├─ bashParser.ts (4436行)         ← 纯 TS 手写 Parser | Handwritten parser
  │   ├─ Tokenizer（词法分析）
  │   ├─ Parser（语法分析 → tree-sitter 兼容 AST）
  │   └─ 安全限制 | Safeguards（50ms 超时 / 50000 节点预算）
  │
  ├─ ShellProvider                  ← Shell 抽象层 | Abstraction layer
  │   ├─ bashProvider.ts (255行)    ← bash 环境初始化
  │   └─ powershellProvider.ts      ← pwsh 环境初始化
  │
  ├─ Shell.ts (474行)               ← exec() 入口 | Entry：spawn 进程
  │   └─ ShellCommand.ts (465行)    ← wrapSpawn：状态追踪、超时、后台
  │
  └─ 输出层 | Output
      ├─ 文件描述符 (O_APPEND/O_NOFOLLOW)
      ├─ 后台看门狗 | BG watchdog (5s 轮询)
      └─ outputFilePath 引用返回
```

### 10.2 CodeWhale

```
用户命令 | User command
  │
  ├─ tool_catalog.rs                ← exec_shell 注册为默认工具
  │
  ├─ shell_dispatcher.rs (565行)    ← Shell 检测 & 命令构建
  │   ├─ ShellKind 枚举检测
  │   └─ build_command() → std::process::Command
  │
  ├─ command_safety.rs (1468行)     ← 安全分析 | Safety（正则匹配）
  │
  ├─ execpolicy/lib.rs (853行)      ← 策略引擎 | Policy engine
  │   ├─ ToolAskRule: allow/deny/ask
  │   └─ bash_arity.rs (579行)      ← 命令前缀参数数量白名单
  │
  ├─ shell.rs (3071行)              ← 核心执行引擎 | Core engine
  │   ├─ execute()                  ← 命令解析与执行
  │   ├─ execute_sync_sandboxed()   ← 同步 + 沙箱
  │   ├─ spawn_background_sandboxed()← 后台 + PTY
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
  ├─ shell_detect.rs                ← Shell 类型检测
  │
  ├─ bash.rs                        ← tree-sitter-bash 解析
  │   └─ extract_bash_command()
  │
  ├─ shell.rs                       ← Shell 抽象
  │   └─ derive_exec_args()
  │
  ├─ execpolicy crate               ← 策略引擎 | Policy engine
  │   ├─ PrefixRule: 前缀匹配
  │   └─ NetworkRuleProtocol: 网络控制
  │
  ├─ exec.rs (1570行)               ← 核心执行引擎 | Core engine
  │   ├─ ExecParams { command, cwd, expiration, sandbox, ... }
  │   ├─ ExecExpiration: 超时/取消
  │   └─ ExecCapturePolicy: ShellTool | FullBuffer
  │
  ├─ spawn.rs                       ← 进程生成 | Process spawn
  │   └─ spawn_child_async() → tokio::process::Command
  │
  ├─ exec-server/                   ← 执行后端 | Execution backend
  │   ├─ local_process.rs           ← PTY/Pipe 生成
  │   ├─ remote_process.rs          ← 远程执行
  │   └─ process.rs                 ← 事件类型 & 日志
  │
  ├─ shell-escalation/ (Unix only)  ← execve 拦截 | Interception
  │   ├─ execve_wrapper.rs          ← 拦截入口
  │   ├─ escalate_client.rs         ← 调用 libc::execv()
  │   ├─ escalate_server.rs         ← 策略路由
  │   └─ escalation_policy.rs       ← 决策 trait
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
  │   └─ 权限检查 & 路径验证
  │
  ├─ tool/shell.ts (657行)          ← OpenCode Shell 工具
  │   ├─ tree-sitter 解析 (bash + pwsh WASM)
  │   ├─ 权限审批（命令模式匹配）
  │   ├─ 流式输出收集
  │   └─ 溢出写文件截断
  │
  ├─ shell/shell.ts (215行)         ← Shell 运行时 | Runtime
  │   ├─ META: 10 种 Shell 元数据
  │   ├─ args(): 每种 Shell 独立参数模板
  │   └─ killTree(): 两阶段终止
  │
  ├─ cross-spawn-spawner.ts (508行) ← 进程生成器 | Spawner
  │   ├─ spawn(): cross-spawn → Node spawn
  │   ├─ killGroup(): Win taskkill / POSIX process.kill(-pid)
  │   └─ 流式 stdout/stderr 收集
  │
  ├─ process.ts                     ← AppProcess 抽象
  │   ├─ run(): 完整执行 + 超时
  │   └─ runStream(): 流式执行
  │
  └─ 辅助模块 | Auxiliary
      ├─ pty.ts / pty.node.ts / pty.bun.ts  ← PTY 支持
      ├─ desktop/shell-env.ts                ← Shell 环境探测
      └─ plugin/shell.ts                     ← 插件 Shell 类型
```

---

## 11. 总结评价 | Summary & Evaluation

### 各维度最佳 | Best by Dimension

| 维度 / Dimension | 最佳项目 / Best | 说明 |
|------------------|:--:|------|
| **命令解析深度** / Parsing depth | **Claude Code** | 手写 4436 行 bash parser + 50ms 超时 + 节点限制 |
| **安全防护广度** / Security breadth | **Claude Code** | 5000+ 行安全代码，覆盖数十种攻击模式 |
| **沙箱隔离深度** / Sandbox depth | **Codex** | `execve` 拦截为独有特性，从系统调用层面控制 |
| **进程生命周期可靠性** / Process reliability | **CodeWhale** | PDEATHSIG + Job Objects 内核级保证 |
| **Shell 种类覆盖** / Shell coverage | **OpenCode** | 10 种 shell（含 fish/nu/dash），元数据驱动 |
| **大输出处理** / Large output | **Claude Code** | 文件描述符方案：不占内存、时序保真 |
| **工程架构清晰度** / Architecture | **Codex** | 多 crate 分层，关注点分离最好 |
| **代码简洁性** / Code brevity | **CodeWhale** | 单文件 `shell.rs` 3071 行集中管理 |
| **跨平台兼容性** / Cross-platform | **OpenCode** | `cross-spawn` + 明确的 Win/POSIX 分支 |
| **PTY 支持** / PTY support | **Codex / CodeWhale** | 原生 PTY 支持交互式命令 |

### 各项目定位 | Project Positioning

| 项目 / Project | 定位 / Positioning | 核心设计理念 / Design Philosophy |
|-------------|-------------|------|
| **Claude Code** | 面向外部用户的商业产品 | External-facing product | 安全第一：解析器和安全层投入巨大，适合不可信输入 |
| **Codex** | 多场景部署平台 | Multi-scenario platform | 架构优先：分层清晰，支持本地/远程执行，沙箱隔离最深 |
| **CodeWhale** | 实用主义工具 | Pragmatic tooling | 简洁高效：最少代码解决核心问题，进程管理最可靠 |
| **OpenCode** | 开发者工具 | Developer tool | 兼容性优先：支持最多 shell 类型，streaming 体验好 |

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
