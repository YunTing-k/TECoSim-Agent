# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.14
Description: Agent skills support

Revision:
---------
2026.5.14      Yu Huang      1.0      First implementation
2026.6.2       Yu Huang      1.1      Revise the mark of skill content & Add CLI command support of skill list
2026.6.10      Yu Huang      1.2      Define all inserted message labels in constans.py

Details:
---------
Skill loading system: `load_all_skill_metas()` scans `skills/*/SKILL.md` for YAML front-matter (name, description).
`load_skill_content()` reads and parses skill Markdown body. Supports CLI operations (list) and manual loading via builtin
commands. Skills are injectable into the agent context as system-level instructions.
"""
import os
import logging
import sys
import yaml, glob

from rich.text import Text
from rich.panel import Panel
from argparse import Namespace
from rich.console import Console
from pathlib import Path
from src.constants import *

sys_log = logging.getLogger('logger')


def load_all_skill_metas(skills_root: str, console: Console) -> list[dict[str, str]]:
    """load all skill metas in skills_root"""
    metas: list[dict[str, str]] = []
    for md_file in glob.glob(f"{skills_root}/*/SKILL.md"):
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
            if content.startswith("---"):
                _, fm, _ = content.split("---", 2)
                data = yaml.safe_load(fm)
                name = str(data["name"])
                description = str(data["description"])
                metas.append({
                    "name": name,
                    "description": description,
                })
            else:
                sys_log.warning(f"Fail to load skill {md_file} from {skills_root} with error: No yaml header found")
                console.print(f"Fail to load skill {md_file} from {skills_root} with error: No yaml header found",
                              style="bold yellow")
        except Exception as e:
            sys_log.warning(f"Fail to load skill {md_file} from {skills_root} with error: {e}")
            console.print(f"Fail to load skill {md_file} from {skills_root} with error: {e}", style="bold yellow")
    sys_log.debug(f"{len(metas)} skills loaded from {skills_root}")
    console.print(f"[{MAJOR_COLOR2}]{len(metas)}[/{MAJOR_COLOR2}] skills loaded from [{MAJOR_COLOR2}]{skills_root}[/{MAJOR_COLOR2}]")
    return metas


def get_skill_description(skill_name: str, skills: list[dict[str, str]]) -> str | None:
    """get skill description from skill_name and skills list"""
    for skill in skills:
        if skill["name"] == skill_name:
            return skill["description"]
    return None


def load_skill_content(skills_root: str, skill_name: str, console: Console, manual: bool = False) -> dict[str, str] | None:
    """load content of a skill from skills_root with given `skill_name`"""
    md_file = os.path.join(skills_root, skill_name, "SKILL.md")
    if not os.path.isfile(md_file):
        sys_log.warning(f"Skill file not found: {md_file}")
        console.print(f"Skill file not found: {md_file}", style="bold red")
        return None
    try:
        skill_folder = Path(md_file).parent.absolute().as_posix()
        with open(md_file, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        sys_log.warning(f"Fail to read skill {md_file} with error: {e}")
        console.print(f"Fail to read skill {md_file} with error: {e}", style="bold yellow")
        raise RuntimeError(f"Fail to read skill {md_file} with error: {e}")

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].lstrip("\n")
        else:
            body = content
    else:
        body = content
    sys_log.debug(f"Loaded skill content for {skill_name} with {len(body)} chars")
    console.print(f"Loaded skill content for [{MAJOR_COLOR2}]{skill_name}[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(body)}[/{MAJOR_COLOR2}] chars")
    if not manual:
        return {"skill_directory": skill_folder,
                "content": f"{SKILL_START_LABEL}\n"
                           f"{body}\n"
                           f"{SKILL_END_LABEL}"}
    else:
        return {"status": f"skill manually loaded by user with /{skill_name}",
                "skill_directory": skill_folder,
                "content": f"{SKILL_START_LABEL}\n"
                           f"{body}\n"
                           f"{SKILL_END_LABEL}"}


def skill_entry_cli(args: Namespace, console: Console):
    """skill CLI operations support"""
    if args.command != "skill":
        return

    """skill operations"""
    if args.skill_action == 'list':
        skill_list_cli(console)
    else:
        sys_log.warning(f"Unknown skill action: {args.skill_action}")
        console.print(f"Unknown skill action: {args.skill_action}", style="bold yellow")
        sys.exit(-1)

    """skill action doesn't entry main program"""
    sys.exit(0)


def skill_list_cli(console: Console):
    """query all available skills (no truncate)"""
    skills = load_all_skill_metas(skills_root=SKILLS_PATH, console=console)
    title = f"Available Skills ({len(skills)})"
    cmd_str = Text()
    for skill in skills:
        cmd_str.append(f"{skill["name"]}", style=f"bold {MAJOR_COLOR1}")
        cmd_str.append(f": ", style=f"white")
        cmd_str.append(f"{skill["description"]}\n\n", style=f"white")
    if cmd_str.plain.endswith("\n\n"):
        cmd_str.rstrip()
    console.print(Panel.fit(cmd_str, title=title, title_align="left",
                            padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))
