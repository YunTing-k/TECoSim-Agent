# -*- coding: utf-8 -*-
"""
Smoke test for Markdown render visual inspection.

Renders ReasonMD + ContentMD with various Markdown elements using the
same Table layout as get_block_render() in src/context/prompt.py.

Run:  python test/markdown_render_smoke_test.py
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging

logging.basicConfig(level=logging.CRITICAL)

import rich.box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.style import Style
from rich.table import Table as RichTable
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme
from rich.markdown import TableElement, HorizontalRule, ImageItem
from src.utility.basic_utils import ReasonMD, ContentMD
from src.constants import (
    REASON_ICON, REASON_ICON_SYLTE,
    CONTENT_ICON, CONTENT_ICON_SYLTE,
    MESSAGE_PRINT_MARGIN, REASON_STYLE,
    AGENT_CONSOLE_ICON,
    MARKDOWN_TABLE_COLOR, MARKDOWN_TABLE_HEADER_STYLE,
    MARKDOWN_LIST_BULLET_COLOR, MARKDOWN_LIST_NUMBER_COLOR,
    MARKDOWN_INLINE_CODE_COLOR, MARKDOWN_BLOCKQUOTE_STYLE,
    MARKDOWN_LINK_COLOR, MARKDOWN_HR_COLOR,
    MARKDOWN_IMAGE_STYLE,
    MARKDOWN_H1_STYLE, MARKDOWN_H2_STYLE,
    MARKDOWN_H3_STYLE, MARKDOWN_H4_STYLE, MARKDOWN_H5_STYLE, MARKDOWN_H6_STYLE,
)

console = Console(theme=Theme({
    "markdown.h1": MARKDOWN_H1_STYLE,
    "markdown.h2": MARKDOWN_H2_STYLE,
    "markdown.h3": MARKDOWN_H3_STYLE,
    "markdown.h4": MARKDOWN_H4_STYLE,
    "markdown.h5": MARKDOWN_H5_STYLE,
    "markdown.h6": MARKDOWN_H6_STYLE,
    "markdown.table.header": MARKDOWN_TABLE_HEADER_STYLE,
    "markdown.item.bullet": MARKDOWN_LIST_BULLET_COLOR,
    "markdown.item.number": MARKDOWN_LIST_NUMBER_COLOR,
    "markdown.code": MARKDOWN_INLINE_CODE_COLOR,
    "markdown.block_quote": MARKDOWN_BLOCKQUOTE_STYLE,
    "markdown.link_url": MARKDOWN_LINK_COLOR,
    "markdown.hr": MARKDOWN_HR_COLOR,
    "markdown.image": MARKDOWN_IMAGE_STYLE,
}))


# --- custom table element with rounded borders ---

class _RoundedTableElement(TableElement):
    """Same as Rich's TableElement but with box.ROUNDED borders."""

    def __rich_console__(
        self, _console: Console, options: ConsoleOptions
    ) -> RenderResult:
        table = RichTable(
            box=rich.box.ROUNDED,
            pad_edge=False,
            padding=(0, 2),
            border_style=MARKDOWN_TABLE_COLOR,
            style="markdown.table.border",
            show_edge=True,
            show_lines=True,
            collapse_padding=True,
        )

        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                table.add_column(heading)

        if self.body is not None:
            for row in self.body.rows:
                row_content = [element.content for element in row.cells]
                table.add_row(*row_content)

        yield table


# --- custom horizontal rule: continuous line with center dot ---

class _StyledHorizontalRule(HorizontalRule):
    """Horizontal rule with ─ continuous line and · center decoration."""

    def __rich_console__(
        self, _console: Console, options: ConsoleOptions
    ) -> RenderResult:
        style = _console.get_style("markdown.hr", default="none")
        yield Rule(title=Text(f" {AGENT_CONSOLE_ICON} ", style="#696969"), characters="─", style=style, align="center")
        yield Text()


# --- custom image placeholder with themed color ---

class _StyledImageItem(ImageItem):
    """ImageItem that uses markdown.image theme style for placeholder color."""

    def __rich_console__(
        self, _console: Console, options: ConsoleOptions
    ) -> RenderResult:
        link_style = Style(link=self.link or self.destination or None)
        title = self.text or Text(self.destination.strip("/").rsplit("/", 1)[-1])
        if self.hyperlinks:
            title.stylize(link_style)
        text = Text.assemble("🌆 ", title, " ")
        style = _console.get_style("markdown.image", default="none")
        text.stylize(style)
        yield text


# --- local Markdown subclasses with rounded tables ---

class LocalReasonMD(ReasonMD):
    elements = dict(ReasonMD.elements)
    elements["table_open"] = _RoundedTableElement
    elements["hr"] = _StyledHorizontalRule
    elements["image"] = _StyledImageItem

    def __init__(self, markup: str):
        super().__init__(markup)  # code_theme/hyperlinks/h1=left inherited
        self.style = REASON_STYLE


class LocalContentMD(ContentMD):
    elements = dict(ContentMD.elements)
    elements["table_open"] = _RoundedTableElement
    elements["hr"] = _StyledHorizontalRule
    elements["image"] = _StyledImageItem

    def __init__(self, markup: str):
        super().__init__(markup)  # code_theme/hyperlinks/h1=left inherited
        self.style = "none"


# --- sample markdown content (realistic docs with h1-h4 + all elements) ---

REASONING = (
    "# Task Analysis\n\n"
    "The user asked to inspect the `project` directory and report its structure.\n"
    "This is a common **exploratory** task that requires listing files, checking\n"
    "permissions, and identifying potential issues before taking any action.\n\n"
    "## Observations\n\n"
    "After reviewing the request, here are the key observations:\n\n"
    "- The path `~/project` *might* contain nested subdirectories\n"
    "- There could be hidden files (`.env`, `.gitignore`) that need `-a` flag\n"
    "- Some items might be ~~temporary~~ symlinks requiring special handling\n"
    "- The output size could be **large** — need to consider `head` or `wc`\n\n"
    "We should also verify the current working directory with `pwd` first\n"
    "to make sure we are operating in the right context. A simple `whoami`\n"
    "check confirms the running user before looking at `chmod` or ownership.\n\n"
    "### Risk Assessment\n\n"
    "| Operation | Risk Level | Reversible |\n"
    "|---|---|---|\n"
    "| `ls` | **None** — pure read | N/A |\n"
    "| `find` | *Low* — read-only if no `-exec` | N/A |\n"
    "| `rm -rf` | **Critical** — irreversible | No |\n"
    "| `chmod` | *Medium* — affects permissions | Manual |\n\n"
    "The table above summarizes the safety profile. Read-only commands like\n"
    "`ls` and `stat` are completely safe and should be preferred whenever possible.\n\n"
    "#### Sample Code\n\n"
    "Here is a quick shell one-liner to get started:\n\n"
    "```bash\n"
    "cd ~/project && ls -laR | head -50\n"
    "```\n\n"
    "If we need to process the output programmatically, Python works too:\n\n"
    "```python\n"
    "import os\n"
    "from pathlib import Path\n\n"
    "root = Path.home() / \"project\"\n"
    "for entry in sorted(root.rglob(\"*\")):\n"
    "    kind = \"DIR\" if entry.is_dir() else \"FILE\"\n"
    "    size = entry.stat().st_size\n"
    "    print(f\"{kind:4s} {size:10d}  {entry.relative_to(root)}\")\n"
    "```\n\n"
    "### Summary\n\n"
    "> **Rule of thumb:** Always start with `ls` before `find`,\n"
    "> and never use `rm -rf` without explicit user confirmation.\n"
    "> This applies especially to ~~production~~ development environments.\n\n"
    "---\n\n"
    "#### Action Plan\n\n"
    "1. Run `pwd` and `whoami` to confirm context\n"
    "2. Execute `ls -la` to see immediate content\n"
    "3. Use `find . -maxdepth 2` for deeper scan\n"
    "4. Report findings with clear visual formatting\n"
    "5. Ask user before any destructive operations\n\n"
    "For reference see the [GNU ls manual](https://man7.org/linux/man-pages/man1/ls.1.html)\n"
    "and the [Python pathlib docs](https://docs.python.org/3/library/pathlib.html)."
)

CONTENT = (
    "# Project Structure Report\n\n"
    "This is the inspection result for the requested directory. The analysis\n"
    "covers file types, sizes, permissions, and potential issues discovered\n"
    "during the automated scan.\n\n"
    "## Overview\n\n"
    "The directory contains **42 files** across *8 subdirectories*. Most files\n"
    "are Python source (`.py`) with a few configuration files (`.json`, `.yaml`).\n"
    "No ~~temporary~~ build artifacts were found, which suggests a clean tree.\n\n"
    "Here is the top-level listing:\n\n"
    "```bash\n"
    "$ ls -la ~/project\n"
    "drwxr-xr-x  8 user  staff   256 Jun 29 14:00 .\n"
    "drwxr-xr-x 20 user  staff   640 Jun 28 09:00 ..\n"
    "-rw-r--r--  1 user  staff  1024 Jun 29 13:50 README.md\n"
    "drwxr-xr-x  4 user  staff   128 Jun 29 13:55 src/\n"
    "drwxr-xr-x  3 user  staff    96 Jun 29 13:55 test/\n"
    "-rw-r--r--  1 user  staff   512 Jun 29 13:50 pyproject.toml\n"
    "```\n\n"
    "### File Breakdown\n\n"
    "| Extension | Count | Total Size |\n"
    "|---|---|---|\n"
    "| `.py` | 31 | 245 KB |\n"
    "| `.json` | 4 | 18 KB |\n"
    "| `.yaml` | 3 | 12 KB |\n"
    "| `.md` | 2 | 8 KB |\n"
    "| `.toml` | 1 | 0.5 KB |\n"
    "| `.gitignore` | 1 | 0.2 KB |\n\n"
    "### Permissions Check\n\n"
    "All files are within the expected permission range. A quick scan\n"
    "using `find . -perm /o+w` returned no world-writable files, which\n"
    "is a good security posture for a development repository.\n\n"
    "```python\n"
    "import stat\n"
    "import os\n\n"
    "def check_permissions(root: str):\n"
    "    issues = []\n"
    "    for dirpath, _, filenames in os.walk(root):\n"
    "        for fn in filenames:\n"
    "            path = os.path.join(dirpath, fn)\n"
    "            mode = os.stat(path).st_mode\n"
    "            if mode & stat.S_IWOTH:\n"
    "                issues.append(path)\n"
    "    return issues\n"
    "```\n\n"
    "#### Recommendations\n\n"
    "- **Immediate:** No critical issues found — repo is clean\n"
    "- *Short term:* Add `.editorconfig` for consistent formatting\n"
    "- *Long term:* Consider `pre-commit` hooks for automated checks\n"
    "- Document the CI/CD pipeline in the README\n"
    "- Set up Dependabot for dependency updates\n\n"
    "1. Push the current state to `main` branch\n"
    "2. Create a `dev` branch for new changes\n"
    "3. Open a PR for review before merging\n"
    "4. Tag a release if all tests pass\n\n"
    "> **Note:** This is a living document. The repository structure\n"
    "> may change as the project evolves. Always re-run the inspection\n"
    "> after significant changes to `src/` or configuration files.\n\n"
    "---\n\n"
    "## Dependencies\n\n"
    "The project relies on the following key packages (from `pyproject.toml`):\n\n"
    "| Package | Version | Purpose |\n"
    "|---|---|---|\n"
    "| `openai` | >=1.0 | LLM API client |\n"
    "| `rich` | >=13.0 | Terminal UI rendering |\n"
    "| `pydantic` | >=2.0 | Data validation |\n"
    "| `httpx` | >=0.25 | HTTP client |\n\n"
    "### Next Steps\n\n"
    "The analysis is complete. All findings have been documented above.\n"
    "Refer to the [project README](https://github.com/example/project#readme)\n"
    "for more detailed setup instructions and contribution guidelines.\n\n"
    "![Architecture](https://placehold.co/600x200/1a1a2e/FF9FF3?text=TECoSim+Agent)\n\n"
    "#### Final Checklist\n\n"
    "1. Verify `git status` is clean\n"
    "2. Confirm all tests pass with `pytest`\n"
    "3. Review any unstaged changes\n"
    "4. Commit with a descriptive message\n\n"
    "##### Notes\n\n"
    "Minor observations and caveats about the analysis process.\n\n"
    "###### Footnotes\n\n"
    "All data was collected at the time of the last `git pull`.\n"
    "Timestamps may vary across timezones."
)


def render_block(reasoning: str | None, content: str | None, label: str):
    """Render reasoning + content with the same Table layout as get_block_render()."""
    console.print(Text(f"\n{'=' * 60}\n  {label}\n{'=' * 60}\n", style="bright_black"))

    if reasoning not in (None, ""):
        t_reason = RichTable(show_header=False, show_edge=False, padding=0, box=None, collapse_padding=True)
        t_reason.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t_reason.add_column(vertical="top")
        t_reason.add_row(
            Text(f" {REASON_ICON} ", style=REASON_ICON_SYLTE),
            LocalReasonMD("{Think}: " + reasoning),
        )
        console.print(t_reason)
        console.print()

    if content not in (None, ""):
        t_content = RichTable(show_header=False, show_edge=False, padding=0, box=None, collapse_padding=True)
        t_content.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
        t_content.add_column(vertical="top")
        t_content.add_row(
            Text(f" {CONTENT_ICON} ", style=CONTENT_ICON_SYLTE),
            LocalContentMD(content),
        )
        console.print(t_content)


if __name__ == "__main__":
    render_block(REASONING, CONTENT, "LocalReasonMD + LocalContentMD All MD element types")
