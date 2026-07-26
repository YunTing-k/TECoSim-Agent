# Rich 开发注意事项 | Rich Development Pitfalls

TECoSim Agent 在使用 Python Rich 库开发终端 TUI 预览功能时遇到的关键问题与解决方案，供后续开发者参考。

---

## 1. Text 拼接与样式保持 | Text Concatenation & Style Preservation

`Text` 对象使用 `+` 运算符拼接时，左操作数的样式会丢失。
When using the `+` operator on `Text` objects, the left operand's style is lost.

```python
# 错误 / Bad — gutter style lost
prefix = Text(" " * 8, style=Style(bgcolor="#222"))
chunk = Text("hello", style=Style(bgcolor="#141"))
result = prefix + chunk
# result.spans 中缺少 gutter 的样式 / gutter style missing from result.spans
```

**解决方案 / Solution:** 使用 `Text.assemble()` 或 `Text.append()`。Use `Text.assemble()` or `Text.append()`.

```python
result = Text.assemble((" " * 8, gutter_style), (chunk,))
# 或者 / or
result = Text()
result.append(" " * 8, style=gutter_style)
result.append("hello", style=content_style)
```

原因：Rich 的 `Text.__add__` 在合并时应用左操作数的默认样式而非各 span 的独立样式。`Text.assemble` 和 `Text.append` 正确保留了每个 span 的样式。
Reason: Rich's `Text.__add__` applies the left operand's default style, not per-span styles. `Text.assemble` and `Text.append` correctly preserve each span's individual style.

---

## 2. `.stylize()` 与 span 样式覆盖 | .stylize() Overrides Span Styles

`Text.stylize()` 会在整个文本上添加一个全局 overlay span，该 span 会覆盖已有的 per-token span 样式。当逐字符提取样式时，最后一个 span 的样式会胜出（last-write-wins）。
`Text.stylize()` adds a global overlay span that overrides existing per-token span styles. When extracting styles character-by-character, the last span wins (last-write-wins).

```python
hl = _highlight_fragment(text, lexer)
# spans: [('ls', #E5C07B), (' -la', #ABB2BF)]
hl.stylize(Style(bgcolor="#141414"))  # adds full-text bg span — overwrites char_styles
```

**解决方案 / Solution:** 先提取样式，再对切分后的每个 chunk 单独调用 `.stylize()`。
Extract styles first, then call `.stylize()` on each split chunk individually.

```python
hl = _highlight_fragment(text, lexer, strip_bg=True)
# extract spans to char_styles ...
# after splitting, apply bg to each chunk
for chunk in chunks:
    chunk.stylize(Style(bgcolor="#141414"))
```

注意：`_highlight_fragment` 的 `strip_bg=True` 参数会在保持前景色的前提下剥离 pygments 主题背景色。diff 块必须传 `True`，normal 块传 `False` 可保留主题背景。
Note: `_highlight_fragment(strip_bg=True)` strips pygments theme backgrounds while preserving foreground colors. Diff blocks must pass `True`; normal blocks pass `False` to keep the theme background.

---

## 3. CJK/宽字符显示宽度 | CJK/Wide Character Display Width

Python 的 `len(s)` 返回字符数而非终端显示列数。中文等 CJK 字符占据 2 列，直接用 `len()` 计算宽度会导致换行错乱。
Python's `len(s)` counts characters, not terminal display columns. CJK characters occupy 2 columns; using `len()` directly causes incorrect line wrapping.

```python
from unicodedata import east_asian_width
def _display_width(s):
    return sum(2 if east_asian_width(c) in ('F', 'W') else 1 for c in s)
```

该函数用于 `fill_str_line()` 和 `_highlight_and_wrap()` 中的所有续行计算。注意 `\u00A0`（NBSP）的 display width = 1（非 CJK），用 NBSP 填充背景时无需特殊处理。
Used in all continuation line calculations in `fill_str_line()` and `_highlight_and_wrap()`. Note: `\u00A0` (NBSP) has display width = 1 (non-CJK), no special handling needed.

---

## 4. Rich 多 span 终端边界换行 | Multi-Span Terminal Boundary Wrapping

当 gutter 使用多个独立 span（margin / line-number-area / content 各有不同的 bg），且内容恰好填满终端宽度时，Rich 会在边界处错误地提前换行。Normal 块使用单 span gutter 不受影响。
When the gutter spans multiple independent spans (margin, line-number area, and content each with different backgrounds), and the content exactly fills the terminal width, Rich incorrectly wraps early at the boundary. Normal blocks with a single-span gutter are unaffected.

**解决方案 / Solution:** 在 `fill_str_line` 中将内容宽度缩小 1。Reduce content width by 1 in `fill_str_line`.

```python
width = os.get_terminal_size().columns - offset - 1  # -1 prevents boundary condition
```

---

## 5. fill_str_line 返回值结构 | Return Value Structure

```python
first, cont_lines = fill_str_line(line, offset)
# 返回结构 / return structure:
# first:     content[:width].ljust(width, NBSP) + "\n"
# cont_lines: [" " * offset + chunk + NBSP_padding, ...]  (不含 "\n" / no "\n")
```

续行 `cont_lines` 不包含换行符，调用方需自行添加。续行以 `" " * offset` 开头，保证了与首行的 gutter 对齐。
Continuation lines in `cont_lines` do not contain newline characters; the caller must add them. Continuation lines start with `" " * offset`, ensuring alignment with the first line's gutter.

---

## 6. Pygments TextLexer 多余换行 | TextLexer Extra Newline

对 `.txt` 等无匹配 lexer 的文件类型，pygments 回退到 `TextLexer`，该 lexer 在输入不以 `\n` 结尾时会自动追加一个 `\n`，导致行数比预期多 1。
For file types without a matching lexer (e.g. `.txt`), pygments falls back to `TextLexer`, which silently appends a trailing `\n` when the input does not end with one — causing one extra line in the output.

**解决方案 / Solution:** 在 `_highlight_fragment` 中切除多余换行。Strip the extra newline in `_highlight_fragment`.

```python
tokens = list(lex(text, lexer))
if tokens and not text.endswith('\n'):
    last_type, last_text = tokens[-1]
    if last_text.endswith('\n'):
        tokens[-1] = (last_type, last_text[:-1])
```

---

## 7. `Style` 对象 vs 样式字符串 | Style Objects vs Style Strings

`.stylize()` 使用字符串时某些场景下背景色渲染不可靠，应始终使用 `Style` 对象。
String-based `.stylize()` may render backgrounds unreliably in some scenarios. Always use `Style` objects.

```python
# 不可靠 / unreliable
text.stylize("on #141414")
# 可靠 / reliable
text.stylize(Style(bgcolor="#141414"))
text.stylize(Style(color="bright_black", bgcolor="#1a1a1a"))
```

注意：`Style(color="bold white", ...)` 不合法——`color` 参数只接受纯颜色名称或 hex 值，粗体等属性需通过 `bold=True` 单独设置。
Note: `Style(color="bold white", ...)` is invalid. The `color` parameter only accepts plain color names or hex values. Use `bold=True` for bold text.

---

## 8. Windows 终端编码 | Windows Terminal Encoding

PowerShell 中测试 Rich 输出时，GBK 编码无法处理 `\xa0`（NBSP）字符。测试时需设置环境变量。生产环境不需要此设置（Rich 正常使用 UTF-8 终端）。
When testing Rich output in PowerShell, GBK encoding cannot handle `\xa0` (NBSP) characters. Set the environment variable for testing. Production does not require this (Rich uses UTF-8 terminals normally).

---

## 9. NBSP 填充与全宽背景 | NBSP Fill for Full-Width Background

使用 `\u00A0`（Non-Breaking Space）而非普通空格进行背景填充。部分终端不渲染尾部空格的背景色，而 NBSP 无可见字形且终端会渲染其背景色，display width 与普通空格一致。
Use `\u00A0` (NBSP) instead of regular spaces for background fill. Some terminals don't render background colors for trailing spaces, while NBSP has no visible glyph yet renders its background color and has the same display width as a regular space.

| 字符 / Char | 优点 / Pros | 缺点 / Cons |
|------|------|------|
| `" "` 普通空格 / regular space | 简单 / simple | 终端可能不渲染尾部 bg / trailing bg may not render |
| `"\u00A0"` NBSP | 可靠渲染 bg / reliable bg rendering | 终端需 UTF-8 / requires UTF-8 terminal |
| `"█"` 全角块 / fullwidth block | 一定可见 / always visible | 遮挡 bg，不适合背景填充 / covers background |

---

## 10. 高亮-后-切分 vs 切分-后-高亮 | Highlight-Then-Split vs Split-Then-Highlight

`fill_str_line` 先切分返回纯文本再逐段高亮——跨切分边界的 token（如字符串、注释）会被打断，丢失跨行状态。
`fill_str_line` splits first then highlights per-segment — tokens that span the split boundary (e.g. strings, comments) are broken, losing cross-line state.

**解决方案 / Solution:** 先高亮整行生成 Rich Text，再按 display width 切分。
Highlight the entire line first, then split by display width.

```python
hl = _highlight_fragment(line, lexer, strip_bg=True)
char_styles = extract_styles(hl)        # per-character style extraction
chunks = split_by_width(hl, max_width)  # split by display width
for chunk in chunks:
    chunk.stylize(content_bg)           # apply background to each chunk
```

O(n) 逐字符样式提取开销对 Bash 命令（通常 < 500 字符）和编辑视图单行（通常 < 120 字符）均可忽略。`_highlight_and_wrap_edit`（编辑视图用）与 bash 侧 `_highlight_and_wrap` 结构一致，区别为：
- 返回值纯内容（无 gutter），由调用方 `_render_normal_block`/`_render_diff_block` 负责拼接 gutter 和 NBSP padding
- `_render_normal_block` 续行 gutter 用 `Text.assemble((" " * offset, gutter_style), chunk)` 单 span
- `_render_diff_block` 续行 gutter 用 `Text.assemble((margin, style), (line_gutter, style), chunk)` 三 span
The O(n) per-character style extraction cost is negligible for Bash commands (typically < 500 chars) and edit view lines (typically < 120 chars). `_highlight_and_wrap_edit` (edit view) shares the same structure as the bash-side `_highlight_and_wrap`, with these differences:
- Returns pure content (no gutter); callers `_render_normal_block`/`_render_diff_block` handle gutter assembly and NBSP padding
- `_render_normal_block` continuation gutter uses `Text.assemble((" " * offset, gutter_style), chunk)` (single span)
- `_render_diff_block` continuation gutter uses `Text.assemble((margin, style), (line_gutter, style), chunk)` (three spans)

---

## 11. 颜色与样式常量管理 | Color & Style Constant Management

所有可配置颜色/样式定义在 `constants.py` 中，避免硬编码。使用语义化命名：`EDIT_VIEW_*`、`BASH_VIEW_*`、`BASH_RESULT_*`。
Define all configurable colors/styles in `constants.py` to avoid hardcoding. Use semantic naming: `EDIT_VIEW_*`, `BASH_VIEW_*`, `BASH_RESULT_*`.

| 区域 / Area | Gutter BG | Content BG |
|------|-----------|------------|
| 编辑 Normal | `#141414` | `#141414` |
| 编辑 Remove | `#2D1F26` | `#37222C` |
| 编辑 Add | `#1B2B34` | `#20303B` |
| Bash 命令 / Command | `#222222` | `#141414` |
| Bash 结果 / Result | `#222222` | `#141414` |

---

## 12. 终端宽度兼容 | Terminal Width Compatibility

`os.get_terminal_size()` 在非 TTY 环境（CI、管道）会抛出 `OSError`，测试时需 `patch`。所有宽度计算应使用 display width（支持 CJK），非 `len()`。建议预留 1 列安全边距防止边界换行异常。
`os.get_terminal_size()` raises `OSError` in non-TTY environments (CI, pipes); use `patch` when testing. All width calculations should use display width (CJK-aware), not `len()`. A 1-column safety margin is recommended to prevent boundary wrapping issues.

---

## 13. Windows CMD 滚动条与 Live 光标定位冲突 | Windows CMD Scrollbar & Live Cursor Positioning Conflict

在 Windows CMD 终端中使用 `Live(transient=True, auto_refresh=False)` + `live.refresh()` 循环刷新时，如果用户手动拖动滚动条离开 Live 区域并停留，终端会在数秒后整体**冻结**——画面不刷新，滚动无响应，直至用户拖动回底部或滚动到最底部后才恢复正常。

When using `Live(transient=True, auto_refresh=False)` + `live.refresh()` in a refresh loop on Windows CMD, if the user manually drags the scrollbar away from the Live area and stays there, the entire terminal **freezes** after several seconds — no display refresh, no scroll response — until the user drags back to the bottom or scrolls to the very bottom.

### 原因 / Root Cause

`Live` 的 `transient=True` 刷新机制依赖 ANSI 逃逸序列在终端内部 **保存光标位置→跳回→覆盖内容→恢复光标位置**。Windows CMD 的滚屏 buffer 与光标定位是耦合的——当用户拖动滚动条离开 Live 区域后，终端可视范围与 Rich 保存的光标基准不再一致。每次 `live.refresh()` 发出的光标定位逃逸序列在滚动偏移状态下被 CMD 错误处理，状态累积不一致最终导致终端冻结。拖动回底部后终端重新同步，恢复。

`Live` with `transient=True` relies on ANSI escape sequences to **save cursor position → jump back → overwrite content → restore cursor position**. Windows CMD's scroll buffer is coupled with cursor positioning — when the user drags the scrollbar away from the Live area, the terminal's visible viewport no longer matches the cursor anchor saved by Rich. Every `live.refresh()` emits cursor-positioning escape sequences that CMD mishandles under scroll offset, accumulating state inconsistency until the terminal freezes. Dragging back to the bottom re-synchronizes and restores normal behavior.

### 发生场景 / When It Happens

- `agent_listen.py` 的 `listen_tui()`：`Live(transient=True, auto_refresh=False)` 循环刷新按键监听 TUI
- `prompt.py` 的 LLM stream 显示：`Live(transient=True, refresh_per_second=...)` 持续更新流式输出
- 任何有 `transient=True` + 循环 `refresh()` 且运行时间较长（超过数秒）的 Live 场景
- 在 Windows CMD 和 PowerShell 上均可能重现

- `agent_listen.py` `listen_tui()`: `Live(transient=True, auto_refresh=False)` loop-refreshes the key-listen TUI
- `prompt.py` LLM stream display: `Live(transient=True, refresh_per_second=...)` continuously updates streaming output
- Any scenario with `transient=True` + refresh loop running for more than a few seconds
- Reproducible on Windows Command Prompt (CMD) and PowerShell

---

## 14. Live transient 清理残留 + vertical_overflow `...` 截断 | Live Transient Cleanup Residue & vertical_overflow Ellipsis Truncation

在 LLM 流式输出场景中，`Live` 用于实时显示递增内容。当内容（reasoning/content）行数超过终端可视高度时，会触发两个连锁问题：
1. 流式阶段：Rich `Live` 默认 `vertical_overflow="ellipsis"` 导致超出行被 `...` 截断
2. 退出阶段：`transient=True` 的 `restore_cursor()` 只能回溯光标行数，已滚出可视区的行无法清除，残留为"幽灵行"

In LLM streaming output scenarios, `Live` displays incrementally growing content. When the content (reasoning/content) line count exceeds the terminal's visible height, two cascading issues occur:
1. Streaming phase: Rich `Live` defaults to `vertical_overflow="ellipsis"`, causing excess lines to be truncated with `...`
2. Exit phase: `transient=True`'s `restore_cursor()` can only backtrack cursor lines — lines already scrolled out of the visible viewport cannot be cleared, leaving "ghost" residual lines

### 残留复现 / Reproduction

```python
with Live(renderable, refresh_per_second=20, console=console, transient=True) as live:
    for chunk in stream:
        live.update(get_stream_render(content))  # 截断版（indicator + 最后 N 行）/ truncated (indicator + last N lines)

# Live 退出 → restore_cursor() 试图向上回溯清理
# 但当 stream render 行数 > 终端高度时，部分行已滚动溢出
# restore_cursor() 无法回溯到溢出区域的行 → 残留！
# Live exits → restore_cursor() attempts to backtrack and clean up
# But when stream render lines > terminal height, some lines have scrolled out
# restore_cursor() cannot reach overflow lines → residual!
console.print(get_block_render(full_content))  # 完整输出被残留污染 / full output mixed with residue
```

### 根因 / Root Cause

Rich `Live.stop()`：

```python
def stop(self):
    # ...
    self.vertical_overflow = "visible"               # 最后一次刷新允许完整渲染 / allow full render on last refresh
    with self.console:
        try:
            if not self._alt_screen and not self.console.is_jupyter:
                self.refresh()                        # 最后一次刷新 / final refresh
        finally:
            # ...
            if self.transient and not self._alt_screen:
                self.console.control(self._live_render.restore_cursor())  # 光标回溯清理 / cursor backtrack cleanup
```

关键矛盾：`stop()` 先设置 `vertical_overflow = "visible"` 完整渲染最终内容，然后如果 `transient=True` 立即执行 `restore_cursor()` 尝试擦除。`restore_cursor()` 通过 ANSI 逃逸序列回溯光标行数，但**只能定位到终端可视高度内的行**——内容行数超过终端高度时，溢出行已滚出可视区，光标无法回溯到这些行，导致残留。

The critical contradiction: `stop()` first sets `vertical_overflow = "visible"` to fully render the final output, then immediately executes `restore_cursor()` to attempt cleanup if `transient=True`. `restore_cursor()` backtracks the cursor via ANSI escape sequences, but **can only target lines within the terminal's visible height** — when rendered content exceeds the terminal height, overflow lines have scrolled out of the viewport, making them unreachable by cursor backtracking, thus leaving residual lines.

### 解决方案 / Solution

1. **`transient=False`** — 禁用 `restore_cursor()`，避免不完整清理
   Disable `restore_cursor()` to avoid incomplete cleanup.

2. **流式更新保持 `vertical_overflow="ellipsis"`** — 这是 Live 的默认值，流式阶段自动截断超长内容防止屏幕不受控滚动
   Streaming updates keep the default `vertical_overflow="ellipsis"`, auto-truncating overflow content to prevent screen thrashing.

3. **最终完整渲染放到 `with` 块内最后一行** — `with` 退出时 `stop()` 将 `vertical_overflow` 覆盖为 `"visible"` 后才执行最后一次 `refresh()`，此时你的最终 render（完整 `get_block_render()`）被完整渲染，不截断，且无清理残留
   Place the final full render as the last `live.update()` inside the `with` block — on exit, `stop()` overrides `vertical_overflow` to `"visible"` before the final `refresh()`, rendering your full `get_block_render()` completely, without truncation, and without cleanup residue.

```python
with Live(get_stream_render(...), refresh_per_second=20, console=console, transient=False) as live:
    for chunk in response:
        # ... accumulate content ...
        live.update(get_stream_render(...))        # 截断显示 / truncated display

    live.update(get_block_render(...))             # 完整渲染 / full block render
# 退出 → stop(): vertical_overflow="visible" → final refresh → 完整输出保留
# Exit → stop(): vertical_overflow="visible" → final refresh → full output preserved
```

对比原有错误模式 / Contrast with the original wrong pattern:
```python
# 错误 / Wrong
with Live(..., transient=True) as live:
    for chunk in response:
        live.update(get_stream_render(...))

# 退出 → restore_cursor 清理 → 残留 + 丢失最终内容
# Exit → restore_cursor cleanup → residual lines + lost final content
console.print(get_block_render(...))  # 此行的渲染在 cleanup 之后执行，无法清除残留
                                      # This render runs after cleanup — cannot clear residuals
```
