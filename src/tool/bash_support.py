# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.5.12
Description: Bash command execution support

Revision:
---------
2026.5.12      Yu Huang      1.0      Separate from tool_def.py
2026.5.28      Yu Huang      1.1      Revise the bash risk evaluate
2026.6.5       Yu Huang      1.2      Render bash command as Markdown via rich-markdown
2026.6.11      Yu Huang      1.3      Unify as edit-view style: line-number gutter + pygments highlight-then-wrap (preserves
                                      token boundaries across continuation) + dual-BG padding with $bash/$out labels & truncation
2026.6.13      Yu Huang      1.4      Add more safe bash commands
2026.6.14      Yu Huang      1.5      Fix: skip flags in cmd extraction, reclassify kill/sed, git/docker option parsing, guard max_width
2026.6.29      Yu Huang      1.6      Output redirect detection, tee reclassification, SAFE-branch redirect bypass fix;
                                      inline-script raised to level 3; +40 commands (pkg mgrs, build, kubectl, compression)
2026.6.29      Yu Huang      1.7      Fix split_commands (newline/>&/>&/<> merges). Fix sed redirect, /dev/null|stderr|
                                      stdout|tty regex. Add $()/`` eval, find/xargs/awk reclassify, systemctl start,
                                      sysctl -w, ip link set, service start, chmod setuid. +45 cmds, 324 tests.
2026.6.29      Yu Huang      1.8      Mask quoted strings before high-risk regex to eliminate false positives (echo "kill")
2026.6.29      Yu Huang      1.9      Process-sub detection, substitution checks in all safe branches, Docker/kubectl
                                      multi-word subs, pacman flags, eval/to/pkexec/doas detection, >&/>>& redirect,
                                      bare sh→INLINE_SCRIPT, timeout in prefixes, kill/reboot→base_cmd, +18 pkgs/cmds
2026.6.29      Yu Huang      2.0      here-doc detection, eval chain substitution, pkg-mgr substitution checks, remove
                                      export/umask/ulimit/stty from safe, fix 3<>file/&>> redirect detection. 408 tests.
2026.7.3       Yu Huang      2.1      Fix of special Unicode render for bash, bash out, edit, write tool
2026.7.17      Yu Huang      2.2      Fix: qutoed conetent in bash command is completely replaced in _mask_quoted
2026.8.4       Yu Huang      2.3      Fix TUI text preview of NBSP mismatched VS16/ZWJ emoji

Details:
---------
Bash risk evaluation engine. `split_commands()` tokenizes complex multi-pipe commands via shlex. `get_bash_risk()` classifies
each fragment (high-risk: sudo, dd, iptables, etc.; package mgmt; network; file ops; git; docker; build/script; safe commands).
`evaluate_bash_risk()` returns highest risk across all fragments, respecting user-granted permission tokens. `get_bash_render()`
renders commands with edit-view gutter, pygments syntax highlighting, and visual padding for permission preview.
`get_bash_result_render()` shows command output with line numbers, configurable truncation, and visual padding.
"""
import logging
import re
import shlex
import math
import os

from rich.text import Text
from rich.style import Style
from src.tool.file_io_support import NoJoinText
from src.context.agent_context import AgentContext
from src.tool.file_io_support import _highlight_fragment, _get_lexer, get_line_prefix, fill_str_line
from src.tool.file_io_support import _sanitize_control, _display_width, _slice_by_width
from src.constants import *

sys_log = logging.getLogger('logger')


def _split_single(command: str) -> list[str]:
    """Split a single-line command into fragments (pipe/sequence separators)."""
    separators = frozenset({'|', '||', '&', '&&', ';'})

    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split = False
    lex.quotes = '"\''
    lex.commenters = ''
    lex.wordchars += './-=:'

    tokens: list[str] = []
    while True:
        token = lex.get_token()
        if not token:
            break
        tokens.append(token)

    merged: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            combined = tokens[i] + tokens[i + 1]
            if combined in {'&&', '||', '>>', '<<', '>|', '>&', '>>&', '<&', '<>', '|&', '&>', '&>>'}:
                merged.append(combined)
                i += 2
                continue
        merged.append(tokens[i])
        i += 1

    fragments: list[str] = []
    current: list[str] = []
    for token in merged:
        if token in separators:
            if current:
                fragments.append(' '.join(current))
                current = []
        else:
            current.append(token)

    if current:
        fragments.append(' '.join(current))

    return [f for f in fragments if f]


def split_commands(command: str) -> list[str]:
    """Split a bash command string into individual pipeline/sequence fragments.

    Separators: ``|`` ``||`` ``&&`` ``;`` ``&`` ``newline``.
    Each physical line is treated as a separate command group.

    Multi-character operators (``>|``, ``>>``, ``<<``, ``&&``, ``||``) are
    kept inside each fragment; ``>&`` / ``>>&`` are re-merged after ``&``
    separation.
    """
    all_fragments: list[str] = []
    for raw_line in command.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        all_fragments.extend(_split_single(line))
    return all_fragments


def tokens_from_cmd(cmd: str) -> list[str]:
    """Split a command into tokens via shlex (safe fallback to str.split)."""
    try:
        return shlex.split(cmd)
    except Exception as e:
        sys_log.debug(f"shlex.split failed, falling back to str.split: {e}")
        return cmd.split()


def extract_base_cmd(cmd: str) -> str | None:
    """Extract the real command name from a command string.

    Handles leading env vars (``FOO=bar``), absolute/relative paths,
    and ``sudo`` / ``command`` prefixes.
    """
    tokens = tokens_from_cmd(cmd)
    if not tokens:
        return None

    # Skip leading env var assignments and sudo / command / nohup / time …
    skip_prefixes = frozenset({
        'sudo', 'command', 'nohup', 'time', 'watch', 'env',
        'nice', 'stdbuf', 'setsid', 'chrt', 'ionice',
        'exec', 'chroot', 'pkexec', 'doas', 'runuser', 'busybox',
        'timeout',
    })
    for tok in tokens:
        # Skip flags
        if tok.startswith('-'):
            continue
        # Skip numeric arguments (e.g. timeout duration)
        if tok.replace('.', '', 1).isdigit():
            continue
        # Skip FOO=bar assignments
        if '=' in tok and not tok.startswith('-'):
            continue
        # Skip known prefixes
        base = tok.rstrip('/').split('/')[-1]  # handle /usr/bin/cmd -> cmd
        if base in skip_prefixes:
            continue
        return base
    return tokens[-1].rstrip('/').split('/')[-1]


def _check_output_redirect(cmd: str):
    """Return (BASH_FILE_LABEL, reason, 4) if cmd has an output redirect to a file, else None."""
    tokens = tokens_from_cmd(cmd)
    for i, tok in enumerate(tokens):
        if i + 1 >= len(tokens):
            # Check for no-space redirects like '2>file', '3<>file' embedded in token
            m = re.match(r'^(\d+|&)(>>?|<>|><)(.+)$', tok)
            if m:
                target = m.group(3)
                if not target.startswith('&') and not target.isdigit() and target not in ('/dev/null', '/dev/stderr', '/dev/stdout', '/dev/tty'):
                    return BASH_FILE_LABEL, f"File write via redirect to '{target}'", 4
            continue
        if tok in ('>', '>>', '>|', '&>', '<>', '&>>', '>&', '>>&') or re.match(r'^\d+>>?$', tok):
            if i > 0 and tokens[i - 1].startswith('>('):
                continue
            target = tokens[i + 1]
            if target.startswith('&') or target.startswith('(') or target.startswith('>('):
                continue
            if target.isdigit():
                continue
            if target in ('/dev/null', '/dev/stderr', '/dev/stdout', '/dev/tty'):
                continue
            return BASH_FILE_LABEL, f"File write via redirect to '{target}'", 4
    return None


def _extract_substitutions(cmd: str) -> list[str]:
    """Extract inner commands from ``$()`` and backtick command substitutions."""
    inner: list[str] = []
    # $() style — skip backslash-escaped \$(
    for m in re.finditer(r'(?<!\\)\$\(', cmd):
        depth = 0
        start = m.end()
        for i in range(start, len(cmd)):
            if cmd[i] == '(':
                depth += 1
            elif cmd[i] == ')':
                if depth == 0:
                    inner.append(cmd[start:i])
                    break
                depth -= 1
    # backtick style — skip escape \`
    for m in re.finditer(r'(?<!\\)`([^`]+)`', cmd):
        inner.append(m.group(1))
    return inner


def _extract_process_substitutions(cmd: str) -> list[str]:
    """Extract inner commands from ``<()`` and ``>()`` process substitutions."""
    inner: list[str] = []
    for opener in ('<(', '>('):
        pos = 0
        while True:
            idx = cmd.find(opener, pos)
            if idx == -1:
                break
            start = idx + 2  # after <( or >(
            depth = 1
            i = start
            for i in range(start, len(cmd)):
                if cmd[i] == '(':
                    depth += 1
                elif cmd[i] == ')':
                    depth -= 1
                    if depth == 0:
                        inner.append(cmd[start:i])
                        break
            pos = i + 1
    return inner


def _check_all_substitutions(cmd: str, outer_level: int) -> tuple[str, str, int] | None:
    """Evaluate `$()` , backtick, AND `<() / >()` substitutions.

    Returns the risk of the most dangerous substitution if it is riskier
    (lower level) than *outer_level*, otherwise ``None``.
    """
    subs = _extract_substitutions(cmd) + _extract_process_substitutions(cmd)
    if not subs:
        return None
    best: tuple[str, str, int] | None = None
    for s in subs:
        risk, reason, level = get_bash_risk(s)
        if level < outer_level:
            if best is None:
                best = (risk, f"Command substitution '{s}' → {reason}", level)
            elif level < best[2]:
                best = (risk, f"Command substitution '{s}' → {reason}", level)
    return best


def _check_command_substitution(cmd: str, outer_level: int) -> tuple[str, str, int] | None:
    """Evaluate ``$()`` or backtick substitutions inside *cmd*.

    Returns the risk of the innermost dangerous substitution if it is riskier
    (lower level) than *outer_level*, otherwise ``None``.
    """
    return _check_all_substitutions(cmd, outer_level)


def _mask_quoted(cmd: str) -> str:
    """Replace text inside single and double quotes with spaces.

    This prevents the high-risk regex stage from matching keywords that
    appear only inside quoted strings (e.g. ``echo "kill 1234"``).
    Handles backslash-escaped quotes inside double quotes.
    """
    out = list(cmd)
    in_single = False
    in_double = False
    escape = False
    for i, ch in enumerate(cmd):
        if escape:
            escape = False
            out[i] = ' '
            continue
        if ch == '\\' and in_double:
            escape = True
            out[i] = ' '
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out[i] = ' '
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out[i] = ' '
            continue
        if in_single or in_double:
            out[i] = ' '
    return ''.join(out)


def get_bash_risk(cmd: str) -> tuple[str, str, int]:
    """Assess the risk level of a single bash command fragment.

    Returns (risk_label, reason, level) where *lower* level = *higher* risk.
    """
    if cmd is None or cmd.strip() == "":
        return BASH_EMPTY_LABEL, "Empty command", 9

    # High-risk patterns (regex on the *full* raw command)
    high_risk_patterns: list[tuple[str, str]] = [
        (r'sudo\s+',                           'Uses sudo – privilege escalation'),
        (r'chmod\s+(?:0?777|666|4777|2777|6777|1777)\b', 'Overly permissive chmod (world-writable/setuid)'),
        (r'dd\s+if=',                          'Raw disk read operation (dd if=)'),
        (r'dd\s+of=',                          'Raw disk write operation (dd of=)'),
        (r'\bmkfs\b',                          'Filesystem creation'),
        (r'\bmkswap\b',                        'Swap creation'),
        (r'\bdd\b.*\bof=',                     'Raw disk write via dd'),
        (r'>\s*/dev/(?!null|stderr|stdout|tty|zero|full|random|urandom)', 'Write directly to a device'),
        (r'\|\s*(sh|bash|zsh|fish|dash)\b',    'Pipeline to shell interpreter'),
        (r'\|\s*sudo\s+',                      'Pipeline with sudo'),
        (r'\bssh-keygen\b',                    'SSH key manipulation'),
        (r'^(?:sudo\s+)?passwd(?:\s|$)',       'Password modification command'),
        (r'\bchpasswd\b',                      'Batch password modification command'),
        (r'\bufw\s+(allow|deny|reject|enable|disable)\b', 'Firewall changes (ufw)'),
        (r'\bfirewall-cmd\b',                  'Firewall changes (firewalld)'),
        (r'systemctl\s+(stop|disable|mask|enable|kill)\b', 'Service control changes'),
        (r'service\s+\w+\s+(stop|kill)\b',     'Service stop/kill'),
        (r'docker\s+(rm|system\s+prune|rmi|volume\s+rm|network\s+rm)\b',
                                               'Docker destructive operations'),
        (r'\binit\s+[06]\b',                   'Runlevel change to halt/reboot'),
        (r'\bwget\s+-O\s+/',                   'wget writing to root path'),
        (r'\bcurl\s+.*(-o|--output)\s+/',      'curl writing to root path'),
        (r'>\s*/etc/',                         'Writing to /etc/'),
        (r'>\s*/usr/',                         'Writing to /usr/'),
        (r'>\s*/boot/',                        'Writing to /boot/'),
        (r'\bmknod\b',                         'Creating device nodes'),
        (r'\blosetup\b',                       'Loop device setup'),
        (r'\bmount\b',                         'Mount operation'),
        (r'\bumount\b',                        'Unmount operation'),
        (r'\bparted\b',                        'Partition manipulation'),
        (r'\bfdisk\b',                         'Partition manipulation'),
        (r'\bgrub-install\b',                  'Bootloader install'),
        (r'\bupdate-grub\b',                   'Bootloader update'),
        (r'\bexportfs\b',                      'NFS export manipulation'),
        (r'\bswapon\b',                        'Swap activation'),
        (r'\bswapoff\b',                       'Swap deactivation'),
        (r'\bkexec\b',                         'Kernel execution'),
        (r'\binsmod\b',                        'Kernel module insert'),
        (r'\bmodprobe\b',                      'Kernel module management'),
        (r'\brmmod\b',                         'Kernel module removal'),
        (r'\buseradd\b',                       'Create system user'),
        (r'\badduser\b',                       'Create system user'),
        (r'\busermod\b',                       'Modify user account'),
        (r'\buserdel\b',                       'Delete system user'),
        (r'\bgroupadd\b',                      'Create system group'),
        (r'\bgroupmod\b',                      'Modify system group'),
        (r'\bgroupdel\b',                      'Delete system group'),
        (r'\bcrontab\b',                       'Edit/remove cron jobs'),
        (r'\bat\b',                            'Schedule one-time task'),
        (r'\bbatch\b',                         'Schedule batch task'),
        (r'\bssh-add\b',                       'Add SSH key to agent'),
        (r'chmod\s+[ugoa]*[+-=][rwxXstugo]*[st]\b', 'Setuid/setgid/sticky bit via chmod'),
        (r'systemctl\s+(start|restart|reload|daemon-reload|edit|set-property|isolate|set-default)\b', 'Systemd service modification'),
        (r'sysctl\s+-w\b',                     'Kernel parameter write'),
        (r'ip\s+(link set|addr add|addr del|route add|route del)', 'IP/network configuration change'),
        (r'service\s+\w+\s+(start|restart|reload)', 'Service start/restart'),
        (r'nmcli\s+connection\s+(modify|up|down)', 'NetworkManager connection modification'),
        (r'\broute\s+(add|del)',               'Route table modification'),
        (r'\bnmap\b',                          'Network scanner (active probe)'),
        (r'\bshred\b',                         'Secure file deletion'),
        (r'\bchroot\b',                        'Change root directory'),
        (r'\bnsenter\b',                       'Enter process namespace'),
        (r'\bunshare\b',                       'Unshare process namespace'),
        (r'\bcryptsetup\b',                    'Disk encryption'),
        (r'\bfsck\b',                          'Filesystem check/repair'),
        (r'\b(mdadm|lvcreate|lvremove|lvextend|lvreduce|vgcreate|vgremove|pvcreate|pvremove)\b', 'LVM/RAID block device management'),
        (r'\bhdparm\b',                        'ATA disk parameter tool'),
        (r'\b(gdb|strace|ltrace|perf)\b',      'Process tracing/debugging'),
        (r'\btelinit\b',                       'System V runlevel change'),
        (r'\b(ebtables|arptables|nft|nftables)\b', 'Firewall changes'),
        (r'\btc\s+qdisc\b',                    'Traffic control modification'),
        (r'\bvirsh\b',                         'Libvirt VM management'),
        (r'\b(chsh|chfn|gpasswd|newgrp|vipw|vigr)\b', 'User/group database modification'),
        (r'\bldconfig\b',                      'Dynamic linker cache manipulation'),
        (r'\b(systemd-run|busctl)\b',          'Systemd transient unit / D-Bus control'),
        (r'\b(update-initramfs|dracut)\b',     'Initramfs update'),
        (r'\bhelm\s+(install|upgrade|uninstall|delete)\b', 'Helm chart modification'),
        (r'\bterraform\s+(apply|destroy)\b',   'Terraform infrastructure modification'),
        (r'\bansible-playbook\b',              'Ansible playbook execution'),
        (r'\b(pkexec|doas|runuser)\b',         'Privilege escalation'),
    ]

    # Patterns that inspect *quoted* content — check raw cmd before masking
    for pattern, reason in _RAW_INSPECT_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return BASH_HIGH_RISK_LABEL, reason, 0

    masked = _mask_quoted(cmd)
    for pattern, reason in high_risk_patterns:
        if re.search(pattern, masked, re.IGNORECASE):
            return BASH_HIGH_RISK_LABEL, reason, 0

    # Extract the base command for token-level checks
    base_cmd = extract_base_cmd(cmd)
    if base_cmd is None:
        return BASH_EMPTY_LABEL, "Empty command after tokenization", 9

    # Commands that are dangerous only when they ARE the base command
    # (regex moved here to avoid false positives like `echo kill`)
    if base_cmd in ('kill', 'pkill', 'killall', 'reboot', 'shutdown', 'poweroff', 'su'):
        return BASH_HIGH_RISK_LABEL, f"High-risk command: {base_cmd}", 0

    # iptables -L / -S / --list* are read-only
    if base_cmd == 'iptables':
        for t in tokens_from_cmd(cmd)[1:]:
            if t in ('-L', '-S', '--list') or t.startswith('--list'):
                return BASH_SAFE_LABEL, f"Firewall listing (read-only): {cmd}", 8
        return BASH_HIGH_RISK_LABEL, f"Firewall modification (iptables): {cmd}", 0

    # Package management
    package_managers: dict[str, dict[str, tuple[str, ...]]] = {
        'apt':     {'modify': ('install', 'uninstall', 'remove', 'purge', 'update', 'upgrade'),
                    'check':  ('list', 'search', 'show', 'policy', 'cache')},
        'apt-get': {'modify': ('install', 'uninstall', 'remove', 'purge', 'update', 'upgrade'),
                    'check':  ('check', 'download', 'source')},
        'yum':     {'modify': ('install', 'remove', 'erase', 'update', 'upgrade', 'downgrade', 'reinstall', 'autoremove'),
                    'check':  ('list', 'search', 'info', 'provides', 'deplist')},
        'dnf':     {'modify': ('install', 'remove', 'erase', 'update', 'upgrade', 'downgrade', 'reinstall', 'autoremove'),
                    'check':  ('list', 'search', 'info', 'provides')},
        'pacman':  {'modify': ('-S', '-Sy', '-Syu', '-R', '-Rsn', '-U', 'install', 'remove', 'sync'),
                    'check':  ('-Q', '-Qs', '-Qi', '-Si', '-Ss', 'query', 'info')},
        'brew':    {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade', 'reinstall', 'pin', 'unpin'),
                    'check':  ('list', 'search', 'info', 'outdated', 'desc')},
        'pip':     {'modify': ('install', 'uninstall', 'download'),
                    'check':  ('list', 'show', 'search', 'check', 'freeze')},
        'pip3':    {'modify': ('install', 'uninstall', 'download'),
                    'check':  ('list', 'show', 'search', 'check', 'freeze')},
        'conda':   {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade'),
                    'check':  ('list', 'search', 'info')},
        'npm':     {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade'),
                    'check':  ('list', 'search', 'view', 'outdated', 'pack')},
        'bun':     {'modify': ('install', 'add', 'remove', 'update', 'upgrade'),
                    'check':  ('list', 'outdated')},
        'yarn':    {'modify': ('add', 'remove', 'upgrade', 'install'),
                    'check':  ('list', 'search', 'info', 'outdated')},
        'cargo':   {'modify': ('install', 'uninstall', 'update'),
                    'check':  ('search', 'info')},
        'gem':     {'modify': ('install', 'uninstall', 'update'),
                    'check':  ('list', 'search', 'info', 'outdated')},
        'go':      {'modify': ('install', 'get'),
                    'check':  ('list', 'search', 'env', 'version')},
        'apk':     {'modify': ('add', 'del', 'upgrade', 'update'),
                    'check':  ('list', 'search', 'info', 'policy')},
        'dpkg':    {'modify': ('-i', '--install', 'install', '-r', '--remove', 'remove',
                              '-P', '--purge', 'purge', '--configure', 'configure'),
                    'check':  ('-l', '--list', 'list', '-s', '--status', 'status',
                              '-L', '--listfiles', 'search', 'info')},
        'rpm':     {'modify': ('-i', '--install', 'install', '-e', '--erase', 'erase',
                              '-U', '--upgrade', 'upgrade', '-F', '--freshen', 'freshen'),
                    'check':  ('-q', '--query', 'query', '-V', '--verify', 'verify',
                              'list', 'info')},
        'snap':    {'modify': ('install', 'remove', 'revert', 'refresh'),
                    'check':  ('list', 'find', 'info', 'version')},
        'flatpak': {'modify': ('install', 'uninstall', 'update', 'override'),
                    'check':  ('list', 'search', 'info', 'remotes')},
        'choco':   {'modify': ('install', 'uninstall', 'upgrade', 'pin'),
                    'check':  ('list', 'search', 'info', 'outdated')},
        'winget':  {'modify': ('install', 'uninstall', 'upgrade'),
                    'check':  ('list', 'search', 'show')},
        'port':    {'modify': ('install', 'uninstall', 'upgrade', 'deactivate'),
                    'check':  ('list', 'search', 'info', 'installed')},
        'pipenv':  {'modify': ('install', 'uninstall', 'update', 'lock'),
                    'check':  ('graph', 'check', 'verify')},
        'poetry':  {'modify': ('add', 'remove', 'update', 'install'),
                    'check':  ('show', 'search', 'lock', 'check')},
        'pnpm':    {'modify': ('add', 'remove', 'install', 'update'),
                    'check':  ('list', 'search', 'outdated')},
        'composer':{'modify': ('require', 'remove', 'update', 'install'),
                    'check':  ('show', 'search', 'outdated', 'info')},
        'zypper':  {'modify': ('install', 'remove', 'update', 'upgrade', 'dist-upgrade'),
                    'check':  ('search', 'info', 'list-updates', 'info')},
        'emerge':  {'modify': ('', 'install', 'uninstall', 'update', 'sync', 'search'),
                    'check':  ('info', 'list')},
        'pkg':     {'modify': ('install', 'remove', 'update', 'upgrade', 'delete'),
                    'check':  ('info', 'search', 'query', 'list')},
        'nix-env': {'modify': ('-i', '--install', 'install', '-e', '--uninstall', 'uninstall', '-u', '--upgrade'),
                    'check':  ('-q', '--query', 'query', 'list')},
        'pipx':    {'modify': ('install', 'uninstall', 'upgrade', 'reinstall'),
                    'check':  ('list', 'info')},
    }

    if base_cmd in package_managers:
        ops = package_managers[base_cmd]
        for subcmd in tokens_from_cmd(cmd):
            if subcmd in ops['modify']:
                sub_risk = _check_all_substitutions(cmd, 0)
                if sub_risk is not None:
                    return sub_risk
                return BASH_PACKAGE_LABEL, f"Package management '{cmd}' modifies system", 0
            if subcmd in ops['check']:
                redirect_result = _check_output_redirect(cmd)
                if redirect_result is not None:
                    return redirect_result
                sub_risk = _check_all_substitutions(cmd, 8)
                if sub_risk is not None:
                    return sub_risk
                return BASH_SAFE_LABEL, f"Safe package query '{cmd}'", 8
        if base_cmd == 'emerge':
            return BASH_PACKAGE_LABEL, f"Package management '{cmd}' modifies system", 0
        return BASH_FILE_LABEL, f"Package manager '{cmd}' (unrecognized subcommand, treat as file op)", 4

    #Network commands
    network_commands: dict[str, str] = {
        'curl':   'Network data transfer',
        'wget':   'Network download',
        'nc':     'Netcat network utility',
        'ncat':   'Ncat network utility',
        'telnet': 'Telnet remote access',
        'ssh':    'SSH remote access',
        'scp':    'Secure copy over SSH',
        'sftp':   'SSH file transfer',
        'rsync':  'Remote sync',
        'ftp':    'FTP file transfer',
        'tcpdump':'Packet capture',
        'tshark': 'Packet capture (CLI)',
        'socat':  'Multipurpose relay',
        'hping3': 'Packet crafting tool',
        'nping':  'Packet generation tool',
        'mysql':  'MySQL database client',
        'psql':   'PostgreSQL database client',
        'redis-cli':'Redis database client',
        'aws':    'AWS cloud CLI',
        'gcloud': 'Google Cloud CLI',
        'az':     'Azure cloud CLI',
        'kafkacat':'Kafka CLI client',
        'kcat':   'Kafka CLI client',
    }
    if base_cmd in network_commands:
        return BASH_NETWORK_LABEL, f"Network command '{base_cmd}' may access remote resources", 0

    # File-system / medium-risk commands
    if base_cmd in ('rm', 'rmdir'):
        # Check for -rf / -r / -f flags
        # Re-parse tokens to find flags
        r_tokens = tokens_from_cmd(cmd)
        has_recursive = any(t in ('-r', '-R', '--recursive') or re.match(r'^-.*[rR]', t) for t in r_tokens[1:])
        has_force = any(t in ('-f', '--force') or re.match(r'^-.*f', t) for t in r_tokens[1:])
        if has_recursive and has_force:
            return BASH_REMOVAL_RF_LABEL, "Recursive forced removal (rm -rf)", 1
        elif has_recursive:
            return BASH_REMOVAL_R_LABEL, "Recursive removal (rm -r)", 2
        elif has_force:
            return BASH_REMOVAL_F_LABEL, "Forced removal (rm -f)", 2
        else:
            return BASH_REMOVAL_LABEL, "Low-risk file removal", 3

    if base_cmd == 'chmod':
        return BASH_CHMOD_LABEL, f"File permission change: {cmd}", 4

    if base_cmd == 'chown':
        return BASH_CHOWN_LABEL, f"File ownership change: {cmd}", 4

    file_ops = {'mkdir', 'touch', 'cp', 'mv', 'ln', 'rmdir', 'install', 'truncate',
                 'zip', '7z', '7za', 'rar',
                 'gpg', 'gpg2', 'openssl', 'keytool',
                 'gzip', 'gunzip', 'bzip2', 'bunzip2', 'xz', 'unxz', 'zstd', 'unzstd',
                 'tar', 'unzip', 'unrar', 'lz4', 'compress', 'uncompress',
                 'chgrp', 'setcap', 'setfattr', 'chattr', 'chcon',
                 'fallocate', 'mkfifo', 'sqlite3', 'logrotate',
                 'xargs', 'awk'}
    if base_cmd in file_ops:
        return BASH_FILE_LABEL, f"File operation: {cmd}", 4

    # Git operations
    if base_cmd == 'git':
        g_tokens = tokens_from_cmd(cmd)
        sub = None
        i = 1
        while i < len(g_tokens):
            t = g_tokens[i]
            if t.startswith('-'):
                if t.startswith(('-C', '-c', '--git')):
                    i += 1
                i += 1
                continue
            sub = t
            break
        if sub is not None:
            if sub in ('push', 'pull', 'commit', 'merge', 'rebase', 'checkout', 'reset', 'cherry-pick', 'tag'):
                return BASH_REPOSITORY_MODIFY_LABEL, f"Git operation '{sub}' modifies repository history/remote", 5
            if sub in ('add', 'rm', 'mv', 'restore', 'stash'):
                return BASH_STAGE_CHANGE_LABEL, f"Git operation '{sub}' stages changes", 6
            # git branch -D / -d / --delete is destructive
            if sub == 'branch' and any(t in ('-D', '-d', '--delete') for t in g_tokens):
                return BASH_STAGE_CHANGE_LABEL, f"Git branch deletion: {cmd}", 6
            redirect_result = _check_output_redirect(cmd)
            if redirect_result is not None:
                return redirect_result
            sub_risk = _check_all_substitutions(cmd, 8)
            if sub_risk is not None:
                return sub_risk
            return BASH_SAFE_LABEL, f"Git operation '{sub}' (read-only)", 8
        redirect_result = _check_output_redirect(cmd)
        if redirect_result is not None:
            return redirect_result
        sub_risk = _check_all_substitutions(cmd, 8)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, f"Git command (read-only)", 8

    # Docker / Podman
    docker_read = frozenset({'ps', 'images', 'logs', 'info', 'version', 'inspect',
                                'stats', 'top', 'port', 'history', 'events', 'system df',
                                'system info', 'system events', 'ls'})
    docker_modify = frozenset({'build', 'run', 'pull', 'push', 'start', 'stop', 'restart',
                                 'exec', 'create', 'tag', 'login', 'logout', 'cp',
                                 'export', 'import', 'save', 'load', 'commit', 'update',
                                 'rename', 'wait', 'kill', 'pause', 'unpause',
                                 'network create', 'volume create', 'container create',
                                 'container run', 'container start', 'container stop',
                                 'swarm init', 'swarm join', 'swarm leave',
                                 'stack deploy', 'stack rm', 'compose up', 'compose down',
                                 'compose build', 'service create', 'service update',
                                 'secret create', 'config create', 'plugin install'})
    if base_cmd in ('docker', 'podman'):
        d_tokens = tokens_from_cmd(cmd)
        sub = None
        i = 1
        while i < len(d_tokens):
            t = d_tokens[i]
            if t.startswith('-'):
                if t.startswith(('-H', '--config', '--context', '--host', '--tls')):
                    i += 1
                i += 1
                continue
            if sub is None:
                sub = t
            elif sub in ('volume', 'network', 'container', 'system', 'swarm', 'stack',
                         'service', 'secret', 'config', 'plugin', 'trust', 'buildx',
                         'builder', 'image', 'compose'):
                sub = f"{sub} {t}"
            i += 1
        if sub is not None:
            if sub in docker_read:
                redirect_result = _check_output_redirect(cmd)
                if redirect_result is not None:
                    return redirect_result
                sub_risk = _check_all_substitutions(cmd, 8)
                if sub_risk is not None:
                    return sub_risk
                return BASH_SAFE_LABEL, f"Container read-only command: {cmd}", 8
            if sub in docker_modify:
                return BASH_FILE_LABEL, f"Container modification command: {cmd}", 4
        redirect_result = _check_output_redirect(cmd)
        if redirect_result is not None:
            return redirect_result
        sub_risk = _check_all_substitutions(cmd, 8)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, f"Container command (read-only): {cmd}", 8

    # kubectl
    kubectl_read = frozenset({'get', 'describe', 'logs', 'explain', 'config view',
                               'cluster-info', 'api-resources', 'api-versions',
                               'top', 'events', 'version', 'auth can-i',
                               'certificate', 'rollout history', 'rollout status',
                               'config current-context', 'config get-contexts'})
    kubectl_modify = frozenset({'apply', 'create', 'delete', 'replace', 'patch',
                                 'edit', 'scale', 'rollout', 'expose', 'run',
                                 'cordon', 'uncordon', 'drain', 'taint', 'label',
                                 'annotate', 'set', 'wait', 'port-forward', 'exec',
                                 'cp', 'attach', 'debug', 'proxy',
                                 'certificate', 'cluster-info', 'config'})
    if base_cmd == 'kubectl':
        k_tokens = tokens_from_cmd(cmd)
        sub = None
        i = 1
        while i < len(k_tokens):
            t = k_tokens[i]
            if t.startswith('-'):
                i += 2 if t in ('--kubeconfig', '--context', '--namespace', '-n', '--server') else 1
                continue
            if sub is None:
                sub = t
            elif sub in ('config', 'auth', 'rollout', 'certificate', 'set', 'cluster-info'):
                sub = f"{sub} {t}"
            i += 1
        if sub is not None:
            if sub in kubectl_read:
                redirect_result = _check_output_redirect(cmd)
                if redirect_result is not None:
                    return redirect_result
                sub_risk = _check_all_substitutions(cmd, 8)
                if sub_risk is not None:
                    return sub_risk
                return BASH_SAFE_LABEL, f"K8s read-only command: {cmd}", 8
            if sub in kubectl_modify:
                return BASH_FILE_LABEL, f"K8s modification command: {cmd}", 4
            # Compound sub not directly matched — check fallback by first word
            first_word = sub.split(' ', 1)[0]
            if first_word in kubectl_modify:
                return BASH_FILE_LABEL, f"K8s modification command: {cmd}", 4
        redirect_result = _check_output_redirect(cmd)
        if redirect_result is not None:
            return redirect_result
        sub_risk = _check_all_substitutions(cmd, 8)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, f"K8s command (read-only default): {cmd}", 8

    # Make / build systems
    build_cmds = {'make', 'cmake', 'ninja', 'meson', 'gcc', 'g++', 'clang', 'clang++',
                   'rustc', 'nvcc', 'xmake',
                   'ld', 'as', 'strip', 'ar', 'pkg-config',
                   'autoconf', 'automake', 'autoreconf', 'libtool',
                   'scons', 'bazel', 'bazelisk', 'gradle', 'gradlew',
                   'mvn', 'mvnw', 'ant', 'dotnet', 'msbuild', 'tsc',
                   'npx', 'vite', 'webpack', 'esbuild',
                   'rake', 'mix', 'rebar3', 'zig', 'dub', 'crystal', 'swiftc',
                   'ghc', 'ghci', 'ocamlc', 'ocamlopt', 'sbt', 'nmake', 'qmake'}
    if base_cmd in build_cmds:
        return BASH_FILE_LABEL, f"Build command: {cmd}", 4

    # Python / scripting
    script_cmds = {'python', 'python3', 'node', 'deno', 'ruby', 'perl', 'lua', 'php',
                   'bash', 'sh', 'zsh', 'dash', 'fish', 'source', '.', 'eval'}
    if base_cmd in script_cmds:
        s_tokens = tokens_from_cmd(cmd)
        for t in s_tokens[1:]:
            if t in ('-c', '-e', '-p', '-r', 'eval'):
                return BASH_INLINE_SCRIPT_LABEL, f"Inline script execution: {cmd}", 3
        # Shell interpreters with no args read from stdin (pipe) → inline risk
        # eval always executes inline code
        shell_cmds = {'bash', 'sh', 'zsh', 'dash', 'fish', '.', 'eval'}
        if base_cmd in shell_cmds and len(s_tokens) == 1:
            return BASH_INLINE_SCRIPT_LABEL, f"Shell accepting piped stdin: {cmd}", 3
        # Here-string / here-doc to a shell interpreter → inline code
        for t in s_tokens[1:]:
            if t in ('<<<', '<<') and base_cmd in {'bash', 'sh', 'zsh', 'dash', 'fish', '.'}:
                return BASH_INLINE_SCRIPT_LABEL, f"Shell executing here-doc code: {cmd}", 3
        if base_cmd == 'eval':
            sub_risk = _check_all_substitutions(cmd, 3)
            if sub_risk is not None:
                return sub_risk
            return BASH_INLINE_SCRIPT_LABEL, f"Inline code evaluation (eval): {cmd}", 3
        sub_risk = _check_all_substitutions(cmd, 4)
        if sub_risk is not None:
            return sub_risk
        return BASH_FILE_LABEL, f"Script execution: {cmd}", 4

    # Safe commands (read-only / informational)
    safe_commands: dict[str, str] = {
        # File listing / navigation
        'ls':      'List directory contents',
        'dir':     'List directory contents',
        'exa':     'List directory contents',
        'eza':     'List directory contents',
        'tree':    'Display directory tree',
        'find':    'Find files',
        'fd':      'Find files (modern)',
        'locate':  'Find files (db)',
        'pwd':     'Print working directory',
        'cd':      'Change directory',
        'pushd':   'Push directory to stack',
        'popd':    'Pop directory from stack',
        'dirs':    'Display directory stack',
        'realpath':'Resolve path',
        'basename':'Strip directory from path',
        'dirname': 'Strip filename from path',
        'readlink':'Read symlink target',
        # File info
        'stat':    'File status info',
        'file':    'Determine file type',
        # File content viewing
        'cat':     'Concatenate/display files',
        'bat':     'Cat with syntax highlighting',
        'head':    'Display first lines',
        'tail':    'Display last lines',
        'less':    'Pager',
        'more':    'Pager',
        'wc':      'Word/line/byte count',
        'nl':      'Number lines',
        'od':      'Octal dump',
        'xxd':     'Hex dump',
        'hexdump': 'Hex dump',
        'strings': 'Extract printable strings',
        # Checksums
        'md5sum':  'MD5 checksum',
        'sha1sum': 'SHA1 checksum',
        'sha256sum':'SHA256 checksum',
        'sha512sum':'SHA512 checksum',
        'cksum':   'CRC checksum',
        'cut':     'Cut columns',
        'paste':   'Paste columns',
        'join':    'Join lines',
        'expand':  'Convert tabs to spaces',
        'unexpand':'Convert spaces to tabs',
        'pr':      'Paginate files',
        'fold':    'Wrap lines',
        # Searching
        'grep':    'Search with patterns',
        'egrep':   'Extended grep',
        'fgrep':   'Fixed-string grep',
        'rg':      'ripgrep',
        'ag':      'The Silver Searcher',
        'ack':     'ack grep',
        'diff':    'Compare files',
        'cmp':     'Byte comparison',
        'sdiff':   'Side-by-side diff',
        'comm':    'Compare sorted files',
        # System info
        'uname':   'System info',
        'arch':    'Architecture info',
        'nproc':   'CPU count',
        'hostname':'Host name',
        'whoami':  'Current user',
        'id':      'User ID info',
        'logname': 'Login name',
        'uptime':  'System uptime',
        'date':    'Date/time',
        'cal':     'Calendar',
        'df':      'Disk free',
        'du':      'Disk usage',
        'free':    'Memory usage',
        'lscpu':   'CPU info',
        'lsblk':   'Block device info',
        'lspci':   'PCI device info',
        'lsusb':   'USB device info',
        'lsmod':   'Loaded modules',
        'lsof':    'List open files',
        'lshw':    'Hardware info',
        'dmidecode':'DMI/BIOS info',
        'dmesg':   'Kernel ring buffer',
        'env':     'Environment variables',
        'printenv':'Print environment',
        'getconf': 'System configuration values',
        'sysctl':  'Kernel parameters (read)',
        'journalctl':'Systemd journal viewer',
        'systemctl':'Systemd service manager (read-only default)',
        'service': 'Service control (read-only default)',
        'nvm':     'Node version manager',
        # Process info
        'ps':      'Process snapshot',
        'top':     'Process monitor',
        'htop':    'Interactive process viewer',
        'btm':     'Bottom process viewer',
        'pidof':   'Find PID',
        'pgrep':   'Find process',
        'nice':    'Run with priority',
        'nohup':   'Run immune to hup',
        # Text processing
        'sort':    'Sort lines',
        'uniq':    'Unique lines',
        'shuf':    'Shuffle lines',
        'tr':      'Translate characters',
        'jq':      'JSON processor',
        'yq':      'YAML/JSON processor',
        'tee':     'Duplicate stream',
        'tsort':   'Topological sort',
        'rev':     'Reverse lines',
        'tac':     'Reverse concatenate',
        'column':  'Columnate text',
        'fmt':     'Text formatter',
        'iconv':   'Character set conversion',
        # Compression (read-only)
        'zcat':    'Read compressed',
        'bzcat':   'Read compressed',
        'xzcat':   'Read compressed',
        'zipinfo': 'ZIP info',
        # Network info (read-only)
        'ping':    'Network reachability test',
        'traceroute':'Network route trace',
        'tracepath':'Network route trace',
        'nslookup':'DNS lookup',
        'dig':     'DNS lookup',
        'host':    'DNS lookup',
        'whois':   'WHOIS lookup',
        'ip':      'IP configuration (read)',
        'ifconfig':'Network interface config',
        'ss':      'Socket statistics',
        'netstat': 'Network statistics',
        'route':   'Routing table',
        'arp':     'ARP cache',
        'mtr':     'My traceroute (read-only)',
        'blkid':   'Block device attribute print',
        'loginctl':'Systemd login manager (read-only)',
        'timedatectl':'Systemd time/date info (read-only)',
        'hostnamectl':'Systemd hostname info (read-only)',
        'localectl':'Systemd locale info (read-only)',
        'getfacl': 'Read file ACL',
        'lsattr':  'List file attributes',
        'disown':  'Disown shell job',
        # Misc utils
        'echo':    'Print text',
        'printf':  'Formatted print',
        'which':   'Locate a command',
        'type':    'Describe a command',
        'whereis': 'Locate binary/man/source',
        'command': 'Run a command',
        'test':    'Evaluate expression',
        '[':       'Test builtin',
        'true':    'Return true',
        'false':   'Return false',
        'yes':     'Repeatedly output',
        'seq':     'Print sequences',
        'factor':  'Factor numbers',
        'time':    'Time command execution',
        'watch':   'Execute periodically',
        'clear':   'Clear terminal',
        'tput':    'Terminal capabilities',
        'bc':      'Calculator',
        'expr':    'Evaluate expression',
        'stdbuf':  'Buffer control',
        'sleep':   'Pause execution',
        # Terminal / shell builtins
        'tmux':    'Terminal multiplexer',
        'screen':  'Terminal multiplexer',
        'unalias': 'Remove alias',
        'ssh-agent':'SSH agent',
        # Help / documentation
        'man':     'Manual pages',
        'help':    'Shell help',
        'info':    'Info pages',
        'whatis':  'One-line manual',
        'apropos': 'Search manual',
    }

    # sed -- in-place editing is a file operation
    if base_cmd == 'sed':
        s_tokens = tokens_from_cmd(cmd)
        if any(t.startswith('-i') or t.startswith('--in-place') for t in s_tokens[1:]):
            return BASH_FILE_LABEL, "In-place file modification (sed -i)", 4
        redirect_result = _check_output_redirect(cmd)
        if redirect_result is not None:
            return redirect_result
        sub_risk = _check_all_substitutions(cmd, 8)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, "Stream editing without file modification", 8

    # Detect output redirect (> / >> / n> / >|) to a file path
    redirect_result = _check_output_redirect(cmd)
    if redirect_result is not None:
        return redirect_result

    # tee writes to files by default — only safe if all targets are discard destinations
    if base_cmd == 'tee':
        t_tokens = tokens_from_cmd(cmd)
        has_file_target = False
        i = 1
        while i < len(t_tokens):
            t = t_tokens[i]
            if t.startswith('-') or t.startswith('>(') or t.startswith('<('):
                i += 1
                continue
            if t.isdigit() and i + 1 < len(t_tokens) and t_tokens[i+1] in ('<', '>'):
                i += 1  # skip fd number, handle redirect op below
                continue
            # Merge consecutive '<' and '>' from shlex.split
            if t in ('<', '>'):
                j = i
                while j < len(t_tokens) and t_tokens[j] == t:
                    j += 1
                count = j - i
                combined = t * count
                if combined in ('<<<',):
                    i = j + 1  # skip operator + heredoc content
                else:
                    i = j
                continue
            if t in ('>>', '>|', '&>', '<<<') or re.match(r'^\d+>>?$', t):
                if t == '<<<':
                    i += 2
                else:
                    i += 1
                continue
            if t not in ('/dev/null', '/dev/stderr', '/dev/stdout', '/dev/tty'):
                has_file_target = True
                break
            i += 1
        if has_file_target:
            return BASH_FILE_LABEL, f"File write via tee", 4
        sub_risk = _check_all_substitutions(cmd, 4)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, "Tee to safe destination", 8

    if base_cmd in safe_commands:
        sub_risk = _check_all_substitutions(cmd, 8)
        if sub_risk is not None:
            return sub_risk
        return BASH_SAFE_LABEL, f"Safe command: {safe_commands[base_cmd]}", 8

    # Fallback: unclassified
    return BASH_UNKNOWN_LABEL, f"Command not classified: {cmd}", 7


_RAW_INSPECT_PATTERNS: list[tuple[str, str]] = [
    (r'\bawk\b.*system\s*\(',              'awk with system() call'),
    (r'\bfind\b.*-(exec|execdir|ok|okdir|delete)\b', 'find with command execution or file deletion'),
]


def evaluate_bash_risk(commands: str, ctx: AgentContext) -> tuple[str, str, int]:
    """Evaluate the overall risk of a bash command string (may contain pipes/sequences).

    Returns the *highest* risk (lowest level) found among all fragments.
    """
    # Pre-check raw-inspect patterns on original command (before shlex strips quotes)
    for pattern, reason in _RAW_INSPECT_PATTERNS:
        if re.search(pattern, commands, re.IGNORECASE):
            return BASH_HIGH_RISK_LABEL, reason, 0

    # Extract and evaluate $( ) and backtick substitutions BEFORE masking —
    # $() inside double quotes is valid shell expansion and must not be ignored.
    subs = _extract_substitutions(commands)
    best_sub = None
    for s in subs:
        risk, reason, level = get_bash_risk(s)
        if best_sub is None or level < best_sub[2]:
            best_sub = (risk, f"Command substitution '{s}' → {reason}", level)
    if best_sub is not None:
        return best_sub

    # Mask quoted content BEFORE splitting — prevents shlex quote-stripping from
    # exposing keywords inside quotes to the high-risk regex pass.
    masked = _mask_quoted(commands)
    cmd_list = split_commands(masked)
    if not cmd_list:
        return BASH_EMPTY_LABEL, "Empty command", 9

    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []

    for fragment in cmd_list:
        risk, reason, level = get_bash_risk(fragment)
        # Check permission: skip if the user has already allowed this risk class
        if risk in ctx.permissions:
            if ctx.permissions[risk]:
                continue
        else:
            sys_log.warning(f"Unknown bash command risk: {risk}, reason: {reason}, level: {level}")

        cmd_risk_list.append(risk)
        cmd_reason_list.append(reason)
        cmd_level_list.append(level)

    # If ALL fragments are covered by existing permissions, treat as fully allowed
    if not cmd_level_list:
        return BASH_SAFE_LABEL, "All commands covered by existing permissions", 9

    # Pick the fragment with the *lowest* level (= highest risk)
    idx = min(range(len(cmd_level_list)), key=lambda i: cmd_level_list[i])
    return cmd_risk_list[idx], cmd_reason_list[idx], cmd_level_list[idx]


def _highlight_and_wrap(line: str, lexer, content_style: Style, gutter_style: Style, max_width: int, gutter_width: int):
    """highlight then split by display width — preserves token boundaries across continuation lines."""
    line = line.expandtabs(EDIT_VIEW_TAB_WIDTH)
    line = _sanitize_control(line)
    hl = _highlight_fragment(line, lexer, strip_bg=True)
    plain = str(hl)

    char_styles = [None] * len(plain)
    for span in hl.spans:
        for i in range(span.start, span.end):
            if char_styles[i] is None:
                char_styles[i] = span.style

    lines = []
    pos = 0
    total = len(plain)
    while pos < total:
        head, _ = _slice_by_width(plain[pos:], max_width)
        if not head:
            break
        end = pos + len(head)
        chunk = Text()
        i = pos
        while i < end:
            j = i + 1
            sty = char_styles[i]
            while j < end and char_styles[j] == sty:
                j += 1
            chunk.append(plain[i:j], style=sty)
            i = j
        chunk.stylize(content_style)
        if lines:
            chunk = Text.assemble((" " * gutter_width, gutter_style), chunk)
        else:
            _pad = max_width - _display_width(str(chunk))
            if _pad > 0:
                chunk.append("\u00a0" * _pad, style=content_style)
        lines.append(chunk)
        pos = end

    if len(lines) > 1:
        last = lines[-1]
        _pad = gutter_width + max_width - _display_width(str(last))
        if _pad > 0:
            last.append("\u00a0" * _pad, style=content_style)
    return lines[0] if lines else Text(), lines[1:]


def get_bash_render(commands: str) -> NoJoinText:
    """render bash command with line-number gutter, pygments syntax highlighting, and visual padding."""
    lexer = _get_lexer('script.sh')
    content_style = Style(bgcolor=EDIT_VIEW_NORMAL_BG)
    gutter_style = Style(color="bright_black", bgcolor=BASH_VIEW_GUTTER_BG)

    lines = commands.strip('\n').split('\n')
    budget = math.floor(math.log10(max(len(lines), 1))) + 1
    gutter_width = EDIT_VIEW_LEFT_SPACE_MARGIN + budget + EDIT_VIEW_LINE_SPACE_MARGIN + 1
    max_width = os.get_terminal_size().columns - gutter_width - 1
    if max_width < 1:
        max_width = 1
    _pad_label = lambda txt: " " * (gutter_width - len(txt)) + txt
    gutter_nbsp = "\u00a0" * gutter_width

    body = Text(no_wrap=True)
    for i in range(BASH_VIEW_PADDING_LINES):
        if i == 0:
            lbl = _pad_label("$in")
            body.append(lbl, style=f"bright_black on {BASH_VIEW_GUTTER_BG}")
            first, _ = fill_str_line("", offset=len(lbl))
            body.append(first, style=content_style)
        else:
            first, _ = fill_str_line("", offset=gutter_width)
            body.append(gutter_nbsp, style=f"bright_black on {BASH_VIEW_GUTTER_BG}")
            body.append(first, style=content_style)

    for idx, line in enumerate(lines):
        prefix1, prefix2, _ = get_line_prefix(idx + 1, budget)
        body.append(prefix1 + prefix2 + " ", style=f"bright_black on {BASH_VIEW_GUTTER_BG}")
        first, cont_lines = _highlight_and_wrap(line, lexer, content_style, gutter_style,
                                                 max_width, gutter_width)
        if not line and not cont_lines:
            first.append("\u00a0" * max_width, style=content_style)
        body.append(first)
        if cont_lines:
            for cl in cont_lines:
                body.append("\n")
                body.append(cl)
            body.append("\n")
        else:
            body.append("\n")

    for _ in range(BASH_VIEW_PADDING_LINES):
        first, _ = fill_str_line("", offset=gutter_width)
        body.append(gutter_nbsp, style=f"bright_black on {BASH_VIEW_GUTTER_BG}")
        body.append(first, style=content_style)
    # NoJoinText wrapper: console.print() joins bare Text objects and drops no_wrap, letting rich's rstrip_end()
    # (char-count based) strip NBSP fill from lines with ZWJ/VS16 emoji sequences. Non-Text wrapper keeps no_wrap.
    return NoJoinText(body)


def get_bash_result_render(stdout: str, stderr: str = "") -> NoJoinText:
    """render bash execution output with line numbers, configurable truncation, and visual padding."""
    output = stdout.rstrip('\n')
    if stderr and stderr.strip():
        if output:
            output += "\n"
        output += stderr.rstrip('\n')

    if not output:
        return Text("(empty output)", style="bright_black")

    truncated = False
    truncated_lines = 0
    raw_lines = output.split('\n')
    if 0 < BASH_RESULT_MAX_CHARS < len(output):
        output = output[:BASH_RESULT_MAX_CHARS]
        truncated = True
        lines = output.split('\n')
        lines[-1] = lines[-1] + " ... (truncated)"
        if len(lines) < len(raw_lines):
            truncated_lines = len(raw_lines) - len(lines)
    elif 0 < BASH_RESULT_MAX_LINES < len(raw_lines):
        truncated_lines = len(raw_lines) - BASH_RESULT_MAX_LINES
        lines = raw_lines[:BASH_RESULT_MAX_LINES]
        lines[-1] = lines[-1] + " ... (truncated)"
        truncated = True
    else:
        lines = raw_lines

    budget = math.floor(math.log10(max(len(lines), 1))) + 1
    gutter_width = EDIT_VIEW_LEFT_SPACE_MARGIN + budget + EDIT_VIEW_LINE_SPACE_MARGIN + 1
    _pad_label = lambda txt: " " * (gutter_width - len(txt)) + txt
    content_style = Style(bgcolor=BASH_RESULT_CONTENT_BG)

    body = Text(no_wrap=True)
    for i in range(BASH_RESULT_PADDING_LINES):
        if i == 0:
            lbl = _pad_label("$ out")
            body.append(lbl, style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
            first, _ = fill_str_line("", offset=len(lbl))
            body.append(first, style=content_style)
        else:
            gutter_nbsp = "\u00a0" * gutter_width
            first, _ = fill_str_line("", offset=len(gutter_nbsp))
            body.append(gutter_nbsp, style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
            body.append(first, style=content_style)

    for idx, line in enumerate(lines):
        prefix1, prefix2, _ = get_line_prefix(idx + 1, budget)
        body.append(prefix1, style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
        body.append(prefix2 + " ", style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
        first, cont_lines = fill_str_line(line, offset=len(prefix1) + len(prefix2) + 1)
        body.append(first, style=content_style)
        p = len(prefix1) + len(prefix2) + 1
        for cl in cont_lines:
            body.append(cl[:p], style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
            body.append(cl[p:] + "\n", style=f"bold white on {BASH_RESULT_CONTENT_BG}")

    if truncated:
        info = f"({truncated_lines} lines not shown)" if (truncated_lines > 0) else "(output truncated)"
        prefix1, prefix2, _ = get_line_prefix(len(lines) + 1, budget)
        body.append(prefix1, style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
        body.append(prefix2 + " ", style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
        info_first, info_cont = fill_str_line(info, offset=len(prefix1) + len(prefix2) + 1)
        body.append(info_first, style=Style(color="bright_black", bgcolor=BASH_RESULT_CONTENT_BG))
        p = len(prefix1) + len(prefix2) + 1
        for cl in info_cont:
            body.append(cl[:p], style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
            body.append(cl[p:] + "\n", style=f"bright_black on {BASH_RESULT_CONTENT_BG}")

    for _ in range(BASH_RESULT_PADDING_LINES):
        gutter_nbsp = "\u00a0" * gutter_width
        first, _ = fill_str_line("", offset=len(gutter_nbsp))
        body.append(gutter_nbsp, style=f"bright_black on {BASH_RESULT_GUTTER_BG}")
        body.append(first, style=content_style)
    # NoJoinText wrapper: see get_bash_render — keeps no_wrap through console.print().
    return NoJoinText(body)
