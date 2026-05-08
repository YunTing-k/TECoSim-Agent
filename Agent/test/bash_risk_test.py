from src.tool import tool_def

def evaluate_bash_risk(commands: str):
    """evaluate the risk of given bash commands"""
    cmd_list = tool_def.split_commands(commands)
    if len(cmd_list) == 0:
        return "N/A", "Empty command", 9
    cmd_level_list: list[int] = []
    cmd_risk_list: list[str] = []
    cmd_reason_list: list[str] = []
    for idx, cmd_str in enumerate(cmd_list):
        risk, reason, level = tool_def.get_bash_risk(cmd_str)
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