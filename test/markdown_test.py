from rich.text import Text
from rich.table import Table
from rich.console import Group, Console
from rich.markdown import Markdown

TEST_MD = ("# Heading H1\n"
            "## Heading H2\n"
            "### Heading H3\n"
            "#### Heading H4\n"
            "##### Heading H5\n"
            "###### Heading H6\n"
            "\n"
            "---\n"
            "\n"
            "This is a paragraph **strong chars**, *italic chars*, ***strong + italic chars***, and `inline code`\n"
            "\n"
            "> This is a block_quote\n"
            "> with multiline block_quote\n"
            ">\n"
            "> > nested block_quote\n"
            "\n"
            "- item list\n"
            "  - nested item list\n"
            "  - nested item list\n"
            "  - nested item list\n"
            "  - nested item list\n"
            ". order item\n"
            "   1. nested order item\n"
            "   2. nested order item\n"
            "   3. nested order item\n"
            "   4. nested order item\n"
            "\n"
            "- [ ] Todo list1\n"
            "- [ ] Todo list2\n"
            "- [ ] Todo list3\n"
            "- [x] Done list4\n"
            "- [x] Done list5\n"
            "- [x] Done list6\n"
            "\n"
            "---\n"
            "\n"
            "| table key           | table value                |\n"
            "|---------------------|----------------------------|\n"
            "| **Name1**           | Value1                     |\n"
            "| **Name2**           | Value2 + *Value1*          |\n"
            "\n"
            "Link with [what is this?](https://example.com)\n"
            "\n"
            "![image](https://via.placeholder.com/150)\n"
            "\n"
            "```python\n"
            "from collections.abc import Iterator\n"
            "\n"
            "\n"
            "# This is an example\n"
            "class Math:\n"
            "    @staticmethod\n"
            "    def fib(n: int) -> Iterator[int]:\n"
            "        \"\"\"Fibonacci series up to n.\"\"\"\n"
            "        a, b = 0, 1\n"
            "        while a < n:\n"
            "            yield a\n"
            "            a, b = b, a + b\n"
            "\n"
            "\n"
            "result = sum(Math.fib(42))\n"
            "print(f\"The answer is {result}\")\n"
            "```\n")

console = Console()

class ReasonMD(Markdown):
    """TECoSim agent Markdown render for agent reasoning"""
    def __init__(self, markup: str):
        super().__init__(markup)
        # self.style = REASON_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"


class ContentMD(Markdown):
    """TECoSim agent Markdown render for agent content"""
    def __init__(self, markup: str):
        super().__init__(markup)
        # self.style = CONTENT_STYLE
        self.code_theme = "one-dark"
        self.hyperlinks = True
        self.elements["heading_open"].LEVEL_ALIGN["h1"] = "left"

md = ContentMD(TEST_MD)
console.print(md)


def get_block_render(collected_reasoning: str | None, collected_content: str | None, as_md: bool) -> Group:
    """get the render of the non-stream messages"""
    parts = []

    """display reasoning"""
    if collected_reasoning not in (None, ""):
        parts.append(Text("\n"))
        if as_md:
            parts.append(ReasonMD("{Think}: " + collected_reasoning))
        else:
            parts.append(Text("{Think}: " + collected_reasoning))
        parts.append(Text("\n"))

    """display chat"""
    if collected_content not in (None, ""):
        if collected_reasoning in (None, ""):
            parts.append(Text("\n"))
        if as_md:
            parts.append(ContentMD(collected_content))
        else:
            parts.append(Text(collected_content))
        parts.append(Text("\n"))

    return Group(*parts)

console.print("Start ↓")
console.print("")
console.print("")
console.print("")
console.print("End   ↑\n")


console.print("Start ↓")
console.print(get_block_render("# This is a reasoning block\n- list1\n- list2\n\nWhat is the moon tastes like?",
                               "# This is a content block\n1. list1\n2. list2\n\nWhat is the sun tastes like?", True))
console.print("End   ↑\n")

console.print("Start ↓")
console.print(get_block_render(None,
                               "# This is a content block\n1. list1\n2. list2\n\nWhat is the sun tastes like?", True))
console.print("End   ↑\n")

console.print("Start ↓")
console.print(get_block_render("# This is a reasoning block\n- list1\n- list2\n\nWhat is the moon tastes like?",
                               None, True))
console.print("End   ↑\n")

console.print("Start ↓")
console.print(get_block_render("# This is a reasoning block\n- list1\n- list2\n\nWhat is the moon tastes like?",
                               "", True))
console.print("End   ↑\n")

console.print(Markdown("```bash\n"
                       "grep error < log.txt >> errors.log ; echo done\n"
                       "cat file.txt | sort > sorted.txt && uniq\n"
                       "echo \"hello | world\" > out.txt | grep foo\n"
                       "```", code_theme="one-dark"))

def get_bash_render(commands: str, as_md: bool) -> Group:
    """get the renderable of a bash command string"""
    parts = []
    lines = commands.strip('\n').split('\n')
    line_count = len(lines)
    line_num_width = len(str(line_count))

    line_numbers = "\n".join(f"{' ' * 3}{i:>{line_num_width}}{' ' * 1}" for i in range(1, line_count + 1))
    print(repr(line_numbers))
    t = Table(show_header=False, show_edge=False, padding=0,
              box=None, collapse_padding=True)
    t.add_column(no_wrap=True, vertical="middle")
    t.add_column(vertical="middle")
    if as_md:
        bash_content = Markdown("```bash\n" + commands + "\n```", code_theme="one-dark")
        t.add_row(Text(f"{line_numbers}", style=f"bright_black"), bash_content)
    else:
        t.add_row(Text(f"{line_numbers}", style=f"bright_black"), Text(commands.strip('\n')))

    parts.append(t)
    return Group(*parts)

console.print()
console.print(get_bash_render("grep error < log.txt >> errors.log ; echo done\n"
                       "cat file.txt | sort > sorted.txt && uniq\n"
                       "echo \"hello | world\" > out.txt | grep foo\n", True))

console.print(Markdown("```bash linenums=\"1\"\n"
                       "grep error < log.txt >> errors.log ; echo done # [line 1]\n"
                       "[line 2] cat file.txt | sort > sorted.txt && uniq\n"
                       "3 echo \"hello | world\" > out.txt | grep foo\n"
                       "```", code_theme="one-dark"))
