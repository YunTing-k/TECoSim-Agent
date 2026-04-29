import shlex
import re

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

BASH_HIGH_RISK_LABEL = "BASH_HIGH_RISK"  # high-risk (0)
BASH_PACKAGE_LABEL = "BASH_PACKAGE"  # high-risk (0)
BASH_NETWORK_LABEL = "BASH_NETWORK"  # high-risk (0)
BASH_RMRF_LABEL = "BASH_RECURSIVE_FORCED_REMOVAL"  # medium-risk (1)
BASH_RMR_LABEL = "BASH_RECURSIVE_REMOVAL"  # medium-risk (2)
BASH_RMF_LABEL = "BASH_FORCED_REMOVAL"  # medium-risk (2)
BASH_RM_LABEL = "BASH_REMOVAL"  # medium-risk (3)
BASH_CHMD_LABEL = "BASH_LOW_RISK_CHMD_OPERATION"  # low-risk (4)
BASH_FILE_LABEL = "BASH_LOW_RISK_FILE_OPERATION"  # low-risk (4)
BASH_REPOSITORY_MODIFY_LABEL = "BASH_REPOSITORY_MODIFY"  # medium-risk (5)
BASH_STAGE_CHANGE_LABEL = "BASH_STAGE_CHANGE"  # medium-risk (6)
BASH_UNKNOWN_LABEL = "BASH_UNKNOWN"  # unknown (7)
BASH_SAFE_LABEL = "BASH_SAFE" # no-risk (8)
BASH_EMPTY_LABEL = "BASH_EMPTY" # no-risk (9)

def get_bash_risk(cmd: str) -> tuple[str, str, int]:
    """Assess the risk level of a single bash command string"""
    if cmd is None or cmd.strip() == "":
        return BASH_EMPTY_LABEL, "Empty command", 9
    """high risk commands handling"""
    high_risk_patterns = [
        (r'sudo\s+', "Uses sudo – privilege escalation"),
        (r'rm\s+-rf\s+/?', "Destructive recursive removal"),
        (r'chmod\s+7{3,4}', "Overly permissive chmod"),
        (r'chown\s+7{3,4}', "Overly permissive chown"),
        (r'dd\s+if=', "Raw disk operation"),
        (r'mkfs', "Filesystem creation"),
        (r'curl.*\|\s*(sh|bash)', "Download and execute pattern (curl … | sh)"),
        (r'wget.*-O-.*\|.*sh', "Download and execute pattern (wget … | sh)"),
        (r'>\s*/dev/|dd\s+of=|\|sh\b|\|bash\b', "Pipeline to shell or raw write"),
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
    package_commands = ["apt", "apt-get", "yum", "dnf", "pacman", "brew", "pip", "npm", "yarn"]
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
                    risk = BASH_RMRF_LABEL
                    reason = "Recursive forced removal (rm/rmdir -rf)"
                    level = 1
                elif has_recursive:
                    risk = BASH_RMR_LABEL
                    reason = "Recursive removal (rm/rmdir -r)"
                    level = 2
                elif has_force:
                    risk = BASH_RMF_LABEL
                    reason = "Forced removal (rm/rmdir -f)"
                    level = 2
                else:
                    risk = BASH_RM_LABEL
                    reason = "Low-risk file removal"
                    level = 3
            elif "chmod" in cmd or "chown" in cmd:
                risk = BASH_CHMD_LABEL
                reason = f"Low-risk {cmd} operation"
                level = 4
            else:
                # mkdir, touch, cp, mv, etc.
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
        "date", "cal", "yes", "true", "false", "test", "[", "printf"
    }

    for op in safe_commands:
        if op in cmd:
            risk = BASH_SAFE_LABEL
            reason = f"Safe command: {cmd}"
            return risk, reason, 8

    """un classified commands handling"""
    return BASH_UNKNOWN_LABEL, f"Command not classified: {cmd}", 7


def evaluate_bash_risk(commands: str):
    """evaluate the risk of given bash commands"""
    cmd_list = split_commands(commands)
    if len(cmd_list) == 0:
        return BASH_EMPTY_LABEL, "Empty command", 9
    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []
    for idx, cmd in enumerate(cmd_list):
        risk, reason, level = get_bash_risk(cmd)
        cmd_risk_list.append(risk)
        cmd_reason_list.append(reason)
        cmd_level_list.append(level)
    idx = min(range(len(cmd_level_list)), key=lambda i: cmd_level_list[i])
    return cmd_risk_list[idx], cmd_reason_list[idx], cmd_level_list[idx]

cmd = 'echo "hello | world" > out.txt | grep foo'
print(evaluate_bash_risk(cmd))

cmd = 'cat file.txt | sort > sorted.txt && uniq'
print(evaluate_bash_risk(cmd))

cmd = 'grep error < log.txt >> errors.log ; echo done'
print(evaluate_bash_risk(cmd))

cmd = '  '
print(evaluate_bash_risk(cmd))

cmd = '14aav 111'
print(evaluate_bash_risk(cmd))

cmd = 'rm -rf'
print(evaluate_bash_risk(cmd))

cmd = 'chmod 676'
print(evaluate_bash_risk(cmd))

cmd = 'chmod 777'
print(evaluate_bash_risk(cmd))

cmd = 'chown 7777'
print(evaluate_bash_risk(cmd))

cmd = 'chmod7777'
print(evaluate_bash_risk(cmd))

cmd = 'dir'
print(evaluate_bash_risk(cmd))