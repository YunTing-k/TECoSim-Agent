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

Details:
---------
Bash risk evaluation engine. `split_commands()` tokenizes complex multi-pipe commands via shlex. `get_bash_risk()` classifies
each fragment (high-risk: sudo, dd, iptables, etc.; package mgmt; network; file ops; git; docker; build/script; safe commands).
`evaluate_bash_risk()` returns highest risk across all fragments, respecting user-granted permission tokens.
"""
import logging
import re
import shlex

from src.constants import *
from src.context.agent_context import AgentContext

sys_log = logging.getLogger('logger')


def split_commands(command: str) -> list[str]:
    """Split a bash command string into individual pipeline/sequence fragments.

    Separators: ``|`` ``||`` ``&&`` ``;`` ``&``  (but NOT ``>&`` or ``>>&``).
    Redirections (``>``, ``>>``, ``<``, ``<<``, ``<<<``, ``>&``, ``>>&``,
    ``<&``, ``<>``) are kept inside each fragment.

    The implementation uses `shlex` to tokenize so that quoted strings are
    handled correctly, and then re-assembles fragments from non-separator
    tokens.
    """
    separators = frozenset({'|', '||', '&', '&&', ';'})

    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split = False
    lex.quotes = '"\''
    lex.commenters = ''
    # Keep hyphens (flags like -rf), equals signs (env vars like FOO=bar)
    # and colons (PATH=/usr/bin) as part of word tokens.
    lex.wordchars += './-=:'

    tokens: list[str] = []
    while True:
        token = lex.get_token()
        if not token:
            break
        tokens.append(token)

    # Merge adjacent tokens that form multi-character operators
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            combined = tokens[i] + tokens[i + 1]
            if combined in {'&&', '||', '>>', '<<'}:
                merged.append(combined)
                i += 2
                continue
        merged.append(tokens[i])
        i += 1

    # Build fragments: everything between separators belongs to one fragment
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


def tokens_from_cmd(cmd: str) -> list[str]:
    """Split a command into tokens via shlex (safe fallback to str.split)."""
    try:
        return shlex.split(cmd)
    except Exception:
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
    })
    for tok in tokens:
        # Skip FOO=bar assignments
        if '=' in tok and not tok.startswith('-'):
            continue
        # Skip known prefixes
        base = tok.rstrip('/').split('/')[-1]  # handle /usr/bin/cmd -> cmd
        if base in skip_prefixes:
            continue
        return base
    return tokens[-1].rstrip('/').split('/')[-1]


def get_bash_risk(cmd: str) -> tuple[str, str, int]:
    """Assess the risk level of a single bash command fragment.

    Returns (risk_label, reason, level) where *lower* level = *higher* risk.
    """
    if cmd is None or cmd.strip() == "":
        return BASH_EMPTY_LABEL, "Empty command", 9

    # High-risk patterns (regex on the *full* raw command)
    high_risk_patterns: list[tuple[str, str]] = [
        (r'sudo\s+',                           'Uses sudo – privilege escalation'),
        (r'chmod\s+[0-7]{3,4}\b',              'Overly permissive chmod (octal)'),
        (r'chmod\s+\+?[augo]*=?\s*rwx\b',      'Overly permissive chmod (symbolic)'),
        (r'dd\s+if=',                          'Raw disk read operation (dd if=)'),
        (r'dd\s+of=',                          'Raw disk write operation (dd of=)'),
        (r'\bmkfs\b',                          'Filesystem creation'),
        (r'\bmkswap\b',                        'Swap creation'),
        (r'\bdd\b.*\bof=',                     'Raw disk write via dd'),
        (r'>\s*/dev/',                         'Write directly to a device'),
        (r'\|\s*(sh|bash|zsh|fish|dash)\b',    'Pipeline to shell interpreter'),
        (r'\|\s*sudo\s+',                      'Pipeline with sudo'),
        (r'\bssh-keygen\b',                    'SSH key manipulation'),
        (r'^(?:sudo\s+)?passwd(?:\s|$)',       'Password modification command'),
        (r'\bchpasswd\b',                      'Batch password modification command'),
        (r'\biptables\b',                      'Firewall changes (iptables)'),
        (r'\bufw\s+(allow|deny|reject|enable|disable)\b', 'Firewall changes (ufw)'),
        (r'\bfirewall-cmd\b',                  'Firewall changes (firewalld)'),
        (r'systemctl\s+(stop|disable|mask|enable|kill)\b', 'Service control changes'),
        (r'service\s+\w+\s+(stop|kill)\b',     'Service stop/kill'),
        (r'docker\s+(rm|system\s+prune|rmi|volume\s+rm|network\s+rm)\b',
                                               'Docker destructive operations'),
        (r'\bpoweroff\b',                      'System poweroff'),
        (r'\breboot\b',                        'System reboot'),
        (r'\bshutdown\b',                      'System shutdown'),
        (r'\binit\s+[06]\b',                   'Runlevel change to halt/reboot'),
        (r'\bwget\s+-O\s+/',                   'wget writing to root path'),
        (r'\bcurl\s+.*(-o|--output)\s+/',      'curl writing to root path'),
        (r'\btee\s+/',                         'tee writing to root path'),
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
    ]

    for pattern, reason in high_risk_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            return BASH_HIGH_RISK_LABEL, reason, 0

    # Extract the base command for token-level checks
    base_cmd = extract_base_cmd(cmd)
    if base_cmd is None:
        return BASH_EMPTY_LABEL, "Empty command after tokenization", 9

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
        'pacman':  {'modify': ('install', 'remove', 'uninstall', 'upgrade', 'sync'),
                    'check':  ('query', 'search', 'info', 'list')},
        'brew':    {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade', 'reinstall', 'pin', 'unpin'),
                    'check':  ('list', 'search', 'info', 'outdated', 'desc')},
        'pip':     {'modify': ('install', 'uninstall', 'download'),
                    'check':  ('list', 'show', 'search', 'check', 'freeze')},
        'pip3':    {'modify': ('install', 'uninstall', 'download'),
                    'check':  ('list', 'show', 'search', 'check', 'freeze')},
        'conda':   {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade'),
                    'check':  ('list', 'search', 'info')},
        'npm':     {'modify': ('install', 'uninstall', 'remove', 'update', 'upgrade', 'audit', 'fund'),
                    'check':  ('list', 'search', 'view', 'outdated', 'pack')},
        'bun':     {'modify': ('install', 'add', 'remove', 'update', 'upgrade', 'unlink', 'link'),
                    'check': ('pm ls', 'pm cache', 'list', 'outdated')},
        'yarn':    {'modify': ('add', 'remove', 'upgrade', 'install'),
                    'check':  ('list', 'search', 'info', 'outdated')},
        'cargo':   {'modify': ('install', 'uninstall', 'update'),
                    'check':  ('search', 'info')},
        'gem':     {'modify': ('install', 'uninstall', 'update'),
                    'check':  ('list', 'search', 'info', 'outdated')},
        'go':      {'modify': ('install', 'download'),
                    'check':  ('list', 'search')},
    }

    if base_cmd in package_managers:
        ops = package_managers[base_cmd]
        for subcmd in tokens_from_cmd(cmd):
            if subcmd in ops['modify']:
                return BASH_PACKAGE_LABEL, f"Package management '{cmd}' modifies system", 0
            if subcmd in ops['check']:
                return BASH_SAFE_LABEL, f"Safe package query '{cmd}'", 8

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

    file_ops = {'mkdir', 'touch', 'cp', 'mv', 'ln', 'rmdir', 'install', 'truncate'}
    if base_cmd in file_ops:
        return BASH_FILE_LABEL, f"File operation: {cmd}", 4

    # Git operations
    if base_cmd == 'git':
        # Extract git subcommand
        g_tokens = tokens_from_cmd(cmd)
        if len(g_tokens) >= 2:
            sub = g_tokens[1]
            if sub in ('push', 'pull', 'commit', 'merge', 'rebase', 'checkout', 'reset', 'fetch', 'cherry-pick', 'tag'):
                return BASH_REPOSITORY_MODIFY_LABEL, f"Git operation '{sub}' modifies repository history/remote", 5
            if sub in ('add', 'rm', 'mv', 'restore', 'stash'):
                return BASH_STAGE_CHANGE_LABEL, f"Git operation '{sub}' stages changes", 6
            # Other git commands are "safe"
            return BASH_SAFE_LABEL, f"Git operation '{sub}' (read-only)", 8

    # Docker / Podman
    docker_read = frozenset({'ps', 'images', 'logs', 'info', 'version', 'inspect',
                                'stats', 'top', 'port', 'history', 'events', 'system df',
                                'system info', 'system events', 'ls'})
    docker_modify = frozenset({'build', 'run', 'pull', 'push', 'start', 'stop', 'restart',
                                'exec', 'create', 'tag', 'login', 'logout', 'cp',
                                'export', 'import', 'save', 'load', 'commit', 'update',
                                'rename', 'wait', 'kill', 'pause', 'unpause',
                                'network create', 'volume create', 'container create',
                                'container run', 'container start', 'container stop'})
    if base_cmd in ('docker', 'podman'):
        d_tokens = tokens_from_cmd(cmd)
        if len(d_tokens) >= 2:
            sub = d_tokens[1]
            if sub in docker_read:
                return BASH_SAFE_LABEL, f"Container read-only command: {cmd}", 8
            if sub in docker_modify:
                return BASH_FILE_LABEL, f"Container modification command: {cmd}", 4

    # Make / build systems
    build_cmds = {'make', 'cmake', 'ninja', 'meson', 'gcc', 'g++', 'clang', 'clang++',
                   'rustc', 'go-build', 'cargo-build', 'nvcc', 'xmake'}
    if base_cmd in build_cmds:
        return BASH_FILE_LABEL, f"Build command: {cmd}", 4

    # Python / scripting
    script_cmds = {'python', 'python3', 'node', 'deno', 'ruby', 'perl', 'lua', 'php'}
    if base_cmd in script_cmds:
        s_tokens = tokens_from_cmd(cmd)
        # If running with a script file, treat as file operation
        # If -c or -e (inline script), treat as unknown / higher risk
        for t in s_tokens[1:]:
            if t in ('-c', '-e'):
                return BASH_UNKNOWN_LABEL, f"Inline script execution: {cmd}", 7
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
        'realpath':'Resolve path',
        'basename':'Strip directory from path',
        'dirname': 'Strip filename from path',
        'readlink':'Read symlink target',
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
        # Process info
        'ps':      'Process snapshot',
        'top':     'Process monitor',
        'htop':    'Interactive process viewer',
        'btm':     'Bottom process viewer',
        'pidof':   'Find PID',
        'pgrep':   'Find process',
        'pkill':   'Signal process',
        'kill':    'Send signal',
        'killall': 'Kill processes by name',
        'nice':    'Run with priority',
        'renice':  'Change priority',
        'nohup':   'Run immune to hup',
        # Text processing
        'sort':    'Sort lines',
        'uniq':    'Unique lines',
        'shuf':    'Shuffle lines',
        'tr':      'Translate characters',
        'sed':     'Stream editor',
        'awk':     'Pattern scanning',
        'jq':      'JSON processor',
        'yq':      'YAML/JSON processor',
        'xargs':   'Build and execute commands',
        'tee':     'Duplicate stream',
        'tsort':   'Topological sort',
        'rev':     'Reverse lines',
        # Compression (read-only)
        'gzip':    'Compress/decompress',
        'gunzip':  'Decompress',
        'zcat':    'Read compressed',
        'bzip2':   'Compress/decompress',
        'bunzip2': 'Decompress',
        'bzcat':   'Read compressed',
        'xz':      'Compress/decompress',
        'unxz':    'Decompress',
        'xzcat':   'Read compressed',
        'zstd':    'Compress/decompress',
        'unzstd':  'Decompress',
        'tar':     'Archive tool',
        'unzip':   'Extract ZIP',
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
        'nmcli':   'NetworkManager CLI',
        'nmap':    'Network scanner',
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
        'stty':    'Terminal settings',
        'bc':      'Calculator',
        'expr':    'Evaluate expression',
        'stdbuf':  'Buffer control',
        'timeout': 'Run with time limit',
        'git':     'Git operations (default read)',
        # Help / documentation
        'man':     'Manual pages',
        'help':    'Shell help',
        'info':    'Info pages',
        'whatis':  'One-line manual',
        'apropos': 'Search manual',
    }

    if base_cmd in safe_commands:
        return BASH_SAFE_LABEL, f"Safe command: {safe_commands[base_cmd]}", 8

    # Fallback: unclassified
    return BASH_UNKNOWN_LABEL, f"Command not classified: {cmd}", 7


def evaluate_bash_risk(commands: str, ctx: AgentContext) -> tuple[str, str, int]:
    """Evaluate the overall risk of a bash command string (may contain pipes/sequences).

    Returns the *highest* risk (lowest level) found among all fragments.
    """
    cmd_list = split_commands(commands)
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
            raise RuntimeError(f"Unknown bash command risk: {risk}")

        cmd_risk_list.append(risk)
        cmd_reason_list.append(reason)
        cmd_level_list.append(level)

    # If ALL fragments are covered by existing permissions, treat as fully allowed
    if not cmd_level_list:
        return BASH_SAFE_LABEL, "All commands covered by existing permissions", 9

    # Pick the fragment with the *lowest* level (= highest risk)
    idx = min(range(len(cmd_level_list)), key=lambda i: cmd_level_list[i])
    return cmd_risk_list[idx], cmd_reason_list[idx], cmd_level_list[idx]
