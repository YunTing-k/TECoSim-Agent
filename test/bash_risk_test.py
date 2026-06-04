from src.constants import *
from src.tool.bash_support import split_commands, get_bash_risk

def evaluate_bash_risk(commands: str):
    """evaluate the risk of given bash commands"""
    cmd_list = split_commands(commands)
    if not cmd_list:
        return BASH_EMPTY_LABEL, "Empty command", 9

    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []

    for fragment in cmd_list:
        risk, reason, level = get_bash_risk(fragment)
        cmd_risk_list.append(risk)
        cmd_reason_list.append(reason)
        cmd_level_list.append(level)

    # If ALL fragments are covered by existing permissions, treat as fully allowed
    if not cmd_level_list:
        return BASH_SAFE_LABEL, "All commands covered by existing permissions", 9

    # Pick the fragment with the *lowest* level (= highest risk)
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

cmd = 'rm -rf /'
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

cmd = 'curl 123.com'
print(evaluate_bash_risk(cmd))

cmd = 'sort > /dev/1.txt'
print(evaluate_bash_risk(cmd))

cmd = 'sort > /1.txt'
print(evaluate_bash_risk(cmd))

cmd = 'docker list'
print(evaluate_bash_risk(cmd))

cmd = 'docker rm'
print(evaluate_bash_risk(cmd))