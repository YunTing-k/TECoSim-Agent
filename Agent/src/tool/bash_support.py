# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.5.12\n
Description: Bash command support

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.5.12      Yu Huang     1.0               Separate from tool_def.py\n

Details:
Support of bash command with risk detection
------------------------------------------------------------------------------------------------------------------------
"""
import logging
import re
import shlex

from src.constants import *
from src.context.agent_context import AgentContext

sys_log = logging.getLogger('logger')


def split_commands(command: str) -> list[str]:
    """split a bash command using separators (| & ; && ||) as delimiters,
    discarding the separators while preserving the original whitespace
    inside each fragment. Redirections (>, >>, <, <<) are kept"""
    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split = False
    lex.quotes = '"\''
    lex.commenters = ''
    lex.wordchars += './'      # ensure ./path stays as one token

    # Get tokens together with their original positions
    tokens_with_pos = []
    while True:
        pos = lex.instream.tell() if hasattr(lex.instream, 'tell') else None
        token = lex.get_token()
        if token == '' or token is None:
            break
        # approximate start position (shlex doesn't give exact positions easily)
        # For accuracy we need to scan, but this works for most cases
        start = command.find(token, pos if pos else 0)
        end = start + len(token) if start != -1 else -1
        tokens_with_pos.append((token, start, end))

    # Merge multi-character operators
    merged_tokens = []
    i = 0
    while i < len(tokens_with_pos):
        tok, s, e = tokens_with_pos[i]
        if i + 1 < len(tokens_with_pos):
            next_tok = tokens_with_pos[i+1][0]
            if tok + next_tok in {'>>', '<<', '&&', '||'}:
                merged_tokens.append((tok+next_tok, s, tokens_with_pos[i+1][2]))
                i += 2
                continue
        merged_tokens.append((tok, s, e))
        i += 1

    sep_operators = {'|', '&', ';', '&&', '||'}
    fragments = []
    current_start = 0
    in_fragment = False

    for tok, s, e in merged_tokens:
        if tok in sep_operators:
            if in_fragment:
                # End fragment at the character before the separator
                fragments.append(command[current_start:s].strip())
                in_fragment = False
        else:
            if not in_fragment:
                current_start = s
                in_fragment = True

    if in_fragment:
        fragments.append(command[current_start:].strip())

    # Remove empty fragments
    fragments = [f for f in fragments if f]
    return fragments


def get_bash_risk(cmd: str) -> tuple[str, str, int]:
    """Assess the risk level of a single bash command string"""
    if cmd is None or cmd.strip() == "":
        return BASH_EMPTY_LABEL, "Empty command", 9
    """high risk commands handling"""
    high_risk_patterns = [
        (r'sudo\s+', "Uses sudo – privilege escalation"),
        (r'chmod\s+7{3,4}', "Overly permissive chmod"),
        (r'chown\s+7{3,4}', "Overly permissive chown"),
        (r'dd\s+if=', "Raw disk operation"),
        (r'mkfs', "Filesystem creation"),
        (r'>\s*/dev/|dd\s+of=|\|sh\b|\|bash\b', "Pipeline to sensitive dir"),
        (r'\|\s*sudo\s+', "Pipeline with sudo"),
        (r'ssh-keygen', "SSH key manipulation"),
        (r'passwd|chpasswd', "Password modification"),
        (r'iptables|ufw\s+(allow|deny)', "Firewall changes"),
        (r'systemctl\s+(stop|disable|mask|enable)', "Service control"),
        (r'docker\s+(rm|system\s+prune)', "Docker destructive operations"),
    ]
    for pattern, reason in high_risk_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            risk = BASH_HIGH_RISK_LABEL
            full_reason = reason
            return risk, full_reason, 0

    # package management commands handling
    package_commands = ["apt", "apt-get", "yum", "dnf", "pacman", "brew", "pip", "conda", "npm", "yarn"]
    package_modify_operations = ("install", "uninstall", "remove", "purge", "update", "upgrade")
    package_check_operations = ("list", "search", "show", "outdated", "info")
    if any(cmd.startswith(cmd_name + " ") or cmd == cmd_name for cmd_name in package_commands):
        for op in package_modify_operations:
            if op in cmd:
                risk = BASH_PACKAGE_LABEL
                reason = f"Package management operation '{cmd}' affects system"
                return risk, reason, 0
        for op in package_check_operations:
            if op in cmd:
                risk = BASH_SAFE_LABEL
                reason = f"Safe package check operation '{cmd}'"
                return risk, reason, 8

    # network commands handling
    network_commands = ("curl", "wget", "nc", "telnet", "ssh")
    for op in network_commands:
        if op in cmd:
            return BASH_NETWORK_LABEL, f"Network command '{cmd}' in pipeline/chain may execute remote content", 0

    """medium risk commands handling"""
    # other risk commands handling
    other_risk_commands = {
        "mkdir", "touch", "cp", "rm", "mv", "ln", "chmod", "chown",
        "rmdir", "nano", "vim", "code"
    }

    for op in other_risk_commands:
        if op in cmd:
            if re.search(r'(^|\s)rm(\s|$)', cmd):
                has_recursive = bool(re.search(r'(^|\s)(-r|-R|--recursive)(\s|$)', cmd))
                has_force = bool(re.search(r'(^|\s)(-f|--force)(\s|$)', cmd))
                if has_recursive and has_force:
                    risk = BASH_REMOVAL_RF_LABEL
                    reason = "Recursive forced removal (rm/rmdir -rf)"
                    level = 1
                elif has_recursive:
                    risk = BASH_REMOVAL_R_LABEL
                    reason = "Recursive removal (rm/rmdir -r)"
                    level = 2
                elif has_force:
                    risk = BASH_REMOVAL_F_LABEL
                    reason = "Forced removal (rm/rmdir -f)"
                    level = 2
                else:
                    risk = BASH_REMOVAL_LABEL
                    reason = "Low-risk file removal"
                    level = 3
            elif "chmod" in cmd:
                risk = BASH_CHMOD_LABEL
                reason = f"Low-risk chmod {cmd} operation"
                level = 4
            elif "chown" in cmd:
                risk = BASH_CHOWN_LABEL
                reason = f"Low-risk chown {cmd} operation"
                level = 4
            else:
                risk = BASH_FILE_LABEL
                reason = f"Low-risk file operation: {cmd}"
                level = 4
            return risk, reason, level

    # git commands handling
    medium_risk_git_command = ("push", "pull", "commit", "merge", "rebase", "checkout", "reset")
    low_risk_git_command = ("add", "rm", "mv")
    if "git" in cmd:
        for op in medium_risk_git_command:
            if op in cmd:
                risk = BASH_REPOSITORY_MODIFY_LABEL
                reason = f"Git operation '{op}' modifies repository history/remote"
                return risk, reason, 5
        for op in low_risk_git_command:
            if op in cmd:
                risk = BASH_STAGE_CHANGE_LABEL
                reason = f"Git operation '{op}' stages changes"
                return risk, reason, 6
        risk = BASH_SAFE_LABEL
        reason = f"Safe git operation '{cmd}'"
        return risk, reason, 8

    """safe commands handling"""
    safe_commands = {
        "ls", "dir", "pwd", "echo", "printf", "cat", "head", "tail", "wc",
        "uname", "grep", "egrep", "fgrep", "find", "diff", "cmp", "df",
        "which", "type", "realpath", "basename", "dirname",
        "date", "cal", "yes", "true", "false", "test", "[", "printf",
        "sort", "uniq"
    }

    for op in safe_commands:
        if op in cmd:
            risk = BASH_SAFE_LABEL
            reason = f"Safe command: {cmd}"
            return risk, reason, 8

    """un classified commands handling"""
    return BASH_UNKNOWN_LABEL, f"Command not classified: {cmd}", 7


def evaluate_bash_risk(commands: str, ctx: AgentContext):
    """evaluate the risk of given bash commands"""
    cmd_list = split_commands(commands)
    if len(cmd_list) == 0:
        return BASH_EMPTY_LABEL, "Empty command", 9
    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []
    for idx, cmd in enumerate(cmd_list):
        risk, reason, level = get_bash_risk(cmd)
        if risk in ctx.permissions:
            if ctx.permissions[risk]:
                continue
            cmd_risk_list.append(risk)
            cmd_reason_list.append(reason)
            cmd_level_list.append(level)
        else:
            raise RuntimeError(f"Unknown bash command risk: {risk}")
    idx = min(range(len(cmd_level_list)), key=lambda i: cmd_level_list[i])
    return cmd_risk_list[idx], cmd_reason_list[idx], cmd_level_list[idx]
