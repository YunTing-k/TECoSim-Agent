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

O(n) 逐字符样式提取开销对 Bash 命令（通常 < 500 字符）可忽略。编辑视图的 `render_preview_*` 尚未应用此优化（单行通常 < 120 字符，影响较小）。
The O(n) per-character style extraction cost is negligible for Bash commands (typically < 500 chars). Edit view `render_preview_*` has not yet applied this optimization (lines typically < 120 chars).

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
| Bash 结果 / Result | `#282828` | `#1C1C1C` |

---

## 12. 终端宽度兼容 | Terminal Width Compatibility

`os.get_terminal_size()` 在非 TTY 环境（CI、管道）会抛出 `OSError`，测试时需 `patch`。所有宽度计算应使用 display width（支持 CJK），非 `len()`。建议预留 1 列安全边距防止边界换行异常。
`os.get_terminal_size()` raises `OSError` in non-TTY environments (CI, pipes); use `patch` when testing. All width calculations should use display width (CJK-aware), not `len()`. A 1-column safety margin is recommended to prevent boundary wrapping issues.
