"""TECoSim Agent constants"""
"""TECoSim Agent version"""
TECOSIM_AGENT_MAJOR_VERSION: int = 0
TECOSIM_AGENT_MINOR_VERSION: int = 1
TECOSIM_AGENT_UPDATE_VERSION: int = 1
"""Basic configs"""
# basic files
LOG_PATH: str = "./log"
API_CONFIGS_PATH: str = "./config/api_configs.json"
AGENT_CONFIGS_PATH: str = "./config/agent_configs.json"
MCPS_PATH: str = "./mcps"
SKILLS_PATH: str = "./skills"
MCPS_CONFIGS_PATH: str = MCPS_PATH + "/mcps_configs.json"
SESSION_PATH: str = "./session"
CRON_CONFIGS_PATH: str = "./cron/cron_configs.json"
CRON_TASK_ID_LEN: int = 8
# files under session:
USER_HISTORY_NAME: str = "user_history"
MESSAGES_NAME: str = "messages.json"
CONTEXT_NAME: str = "context.json"
CRON_NAME: str = "cron_configs.json"
TASKS_NAME: str = "tasks.json"
RUNS_NAME: str = "runs.json"
DESIGNS_NAME: str = "designs.json"
# others
MAIN_AGENT_ID: str = "main"
SIM_DESIGN_NAME: str = "design"
SIM_RUN_NAME: str = "run"
FAIL_LABEL: str = "FAIL"
SUCCESS_LABEL: str = "SUCCESS"
DONE_LABEL: str = "DONE"
TIMEOUT_LABEL: str = "TIMEOUT"
CANCELLED_LABEL: str = "CANCELLED"
DENIED_LABEL: str = "DENIED"
DISABLED_LABEL: str = "DISABLED"
TRUNCATED_LABEL: str = "TRUNCATED"
TASK_PENDING_LABEL: str = "pending"
TASK_IN_PROGRESS_LABEL: str = "in_progress"
TASK_COMPLETED_LABEL: str = "completed"
TASK_DELETED_LABEL: str = "deleted"
TASK_DISPLAYS_BEFORE_ARCHIVED: int = 3
MUTE_TASK_OP_INFO: bool = True
RUN_PENDING_LABEL: str = "PENDING"
RUN_CANCELLED_LABEL: str = "CANCELLED"
RUN_TIMEOUT_LABEL: str = "TIMEOUT"
RUN_RUNTIME_ERROR_LABEL: str = "RUNTIME_ERROR"
RUN_DONE_LABEL: str = "DONE"
"""Tool names"""
# basic tools
TOOL_NAME_VERSION: str = "agent_version"
TOOL_NAME_ASK_QUESTION: str = "ask_user_question"
TOOL_NAME_CREATE_CRON: str = "create_cron"
TOOL_NAME_QUERY_CRON: str = "query_cron"
TOOL_NAME_REMOVE_CRON: str = "remove_cron"
TOOL_NAME_CREATE_TASK: str = "create_task"
TOOL_NAME_UPDATE_TASK: str = "update_task"
TOOL_NAME_QUERY_TASK: str = "query_task"
TOOL_NAME_BASH: str = "bash"
TOOL_NAME_GLOB_FILE: str = "glob_file"
TOOL_NAME_GREP_FILE: str = "grep_file"
TOOL_NAME_READ_FILE: str = "read_file"
TOOL_NAME_WRITE_FILE: str = "write_file"
TOOL_NAME_EDIT_FILE: str = "edit_file"
TOOL_NAME_SKILL: str = "skill"
TOOL_NAME_WEB_FETCH: str = "web_fetch"
TOOL_NAME_WEB_SEARCH: str = "web_search"
TOOL_NAME_CALL_MCP: str = "call_mcp"
# simulation tools
TOOL_NAME_CHECK_SIMULATOR: str = "check_simulator"
TOOL_NAME_INIT_DESIGN: str = "init_design"
TOOL_NAME_QUERY_DESIGN: str = "query_design"
TOOL_NAME_LAUNCH_SIM: str = "launch_sim"
TOOL_NAME_QUERY_RUN: str = "query_run"
TOOL_NAME_READ_LOG: str = "read_log"
"""Tool calls params"""
ASK_USER_QUESTION_MAX_QUESTION: int = 4
ASK_USER_QUESTION_MIN_QUESTION: int = 1
ASK_USER_QUESTION_MAX_OPTION: int = 4
ASK_USER_QUESTION_MIN_OPTION: int = 2
QUESTION_OTHER_LABEL = "<Other>"
QUESTION_OTHER_OPTION_DESC = "Type your ideas"
QUESTION_RECOMMEND_LABEL = "Recommended"
BASH_TIMEOUT_MS_MAX: int = 600000
BASH_TIMEOUT_MS_DEFAULT: int = 120000
GLOB_FILE_ENTRIES_DEFAULT: int = 250
GREP_FILE_HEAD_LIMIT_DEFAULT: int = 250
READ_FILE_MAX_LINE: int = 10000
READ_FILE_ENCODING_DEFAULT: str = "utf-8"
WRITE_FILE_MODE_DEFAULT: str = "write"
WRITE_FILE_ENCODING_DEFAULT: str = "utf-8"
EDIT_FILE_ENCODING_DEFAULT: str = "utf-8"
WEB_SEARCH_QUERY_MIN: int = 2
READ_LOG_MAX_LINE: int = 10000
READ_LOG_ENCODING_DEFAULT: str = "utf-8"
"""Bash command risk"""
BASH_HIGH_RISK_LABEL = "BASH_HIGH_RISK"  # high-risk (0)
BASH_PACKAGE_LABEL = "BASH_PACKAGE"  # high-risk (0)
BASH_NETWORK_LABEL = "BASH_NETWORK"  # high-risk (0)
BASH_REMOVAL_RF_LABEL = "BASH_RECURSIVE_FORCED_REMOVAL"  # medium-risk (1)
BASH_REMOVAL_R_LABEL = "BASH_RECURSIVE_REMOVAL"  # medium-risk (2)
BASH_REMOVAL_F_LABEL = "BASH_FORCED_REMOVAL"  # medium-risk (2)
BASH_REMOVAL_LABEL = "BASH_REMOVAL"  # medium-risk (3)
BASH_CHMOD_LABEL = "BASH_LOW_RISK_CHMOD_OPERATION"  # low-risk (4)
BASH_CHOWN_LABEL = "BASH_LOW_RISK_CHOWN_OPERATION"  # low-risk (4)
BASH_FILE_LABEL = "BASH_LOW_RISK_FILE_OPERATION"  # low-risk (4)
BASH_INLINE_SCRIPT_LABEL = "BASH_LOW_RISK_INLINE_SCRIPT_OPERATION"  # low-risk (4)
BASH_REPOSITORY_MODIFY_LABEL = "BASH_REPOSITORY_MODIFY"  # medium-risk (5)
BASH_STAGE_CHANGE_LABEL = "BASH_STAGE_CHANGE"  # medium-risk (6)
BASH_UNKNOWN_LABEL = "BASH_UNKNOWN"  # unknown (7)
BASH_SAFE_LABEL = "BASH_SAFE" # no-risk (8)
BASH_EMPTY_LABEL = "BASH_EMPTY" # no-risk (9)
"""UI"""
MAJOR_COLOR1: str = "#FF9FF3"  # bright major color
MAJOR_COLOR2: str = "#54A0FF"  # common major color
AGENT_CONSOLE_ICON: str = "✦"
REASON_ICON: str = "⟡"
REASON_ICON_SYLTE: str = f"bold {MAJOR_COLOR2}"
CONTENT_ICON: str = "●"
CONTENT_ICON_SYLTE: str = f"bold {MAJOR_COLOR1}"
MESSAGE_PRINT_MARGIN: int = 4
DEFAULT_SESSION_TITLE: str = "(Empty session)"
UNKNOWN_SESSION_TITLE: str = "(Unknown session)"
ERROR_SESSION_TITLE: str = "(Summarize fail, try manually)"
SELECTED_QUESTION_OPTION_COLOR: str = "#A6CEFF"
PROGRESS_BAR_FULL: str = "█"  # █ ■
PROGRESS_BAR_EMPTY: str = "░"  # ░ □
PROGRESS_DISPLAY_REFRESH_RATE: int = 30
TUI_USER_COMMENT_COLOR: str = "#A6CEEF"
LISTEN_TUI_COLOR_START: str = MAJOR_COLOR1
LISTEN_TUI_COLOR_END: str = MAJOR_COLOR2
LISTEN_TUI_COLOR_GRADIENT: int = 128
LISTEN_TUI_COLOR_PERIOD: float = 2.0
TASK_EMPTY_TITLE: str = ""
TASK_VIEW_LEFT_MARGIN: int = 6
TASK_VIEW_RIGHT_MARGIN: int = 1
TASK_COLOR_GRADIENT: int = 128
TASK_COLOR_PERIOD: float = 2.0
TASK_PENDING_WITHOUT_OWNER_ICON: str = "○"
TASK_PENDING_WITHOUT_OWNER_ICON_STYLE: str = "bright_black"
TASK_PENDING_WITHOUT_OWNER_STYLE: str = "bright_black"
TASK_PENDING_WITH_OWNER_ICON: str = "●"
TASK_PENDING_COLOR_START: str = "#545454"
TASK_PENDING_COLOR_END: str = "#DBDBDB"
TASK_IN_PROGRESS_COLOR_START: str = MAJOR_COLOR1
TASK_IN_PROGRESS_COLOR_END: str = MAJOR_COLOR2
TASK_COMPLETED_ICON: str = "✓"
TASK_COMPLETED_COLOR: str = "#8CDCA0"
TASK_DELETED_ICON: str = "✗"
TASK_DELETED_COLOR: str = "#767676"
CRON_LISTEN_COLOR_START: str = MAJOR_COLOR1
CRON_LISTEN_COLOR_END: str = MAJOR_COLOR2
CRON_LISTEN_COLOR_GRADIENT: int = 128
CRON_LISTEN_COLOR_PERIOD: float = 2.0
OPTIONS_TO_SELECT_PREFIX: str = "❯ "
OPTIONS_UN_SELECT_PREFIX: str = "  "
OPTIONS_SELECTED_PREFIX: str = " ✓"
OPTIONS_UNSELECTED_PREFIX: str = ""
KEY_LISTEN_SLEEP_TIME_MS: int = 100
SPINNER_LIVE_CHECK_GAP_MS: int = 200
SPINNER_TERMINATE_WAIT_S: int = 10
REASONING_COLOR: str = "#54A0FF"
REASON_STYLE: str = f"italic {REASONING_COLOR}"
CONTENT_STYLE: str = "none"
BASH_STYLE: str = "none"
USER_PROMPT_FIXED_PREFIX: str = "(Shift+Tab: New line, Enter: Submit)"
USER_PROMPT_PREFIX_LIST: list[str] = [  # toggle in agent_configs -> RANDOM_PROGRESS_TITLE
    "Type, and behold the breath of silica",
    "Whisper your command into the chips",
    "Strike the silica, and watch it dream in text",
    "Breathe syntax into the sleeping sand",
    "Across countless hops and fibers, we hear you",
    "Another prayer to the god of electrons, please type",
    "Your keystroke is the avalanche waiting to happen",
]
LLM_REQUEST_TITLE_LIST: list[str] = [  # toggle in agent_configs -> RANDOM_PROGRESS_TITLE
    "Brain (but not mine) using ...",
    "Staring into the abyss. The abyss is typing ...",
    "Waking up the hamsters in the server room ...",
    "Polishing the magic mirror. It takes time ...",
    "Synapses firing in a data center far, far away ...",
    "Even AI needs a moment to think (or pretend to) ...",
    "Electrons and photons are dancing. Let them waltz ...",
]
LLM_REQUEST_DONE_TITLE: str = "LLM response latency"
LLM_REQUEST_INTRP_TITLE: str = "LLM request interrupted"
LLM_REQUEST_FAIL_TITLE: str = "LLM request failed"
LLM_REQUEST_SPINNER: str = "dots2"
TOOLS_EXECUTION_TITLE_LIST: list[str] = [  # toggle in agent_configs -> RANDOM_PROGRESS_TITLE
    "Reaching into the toolbox ...",
    "Finding the right screwdriver ...",
    "Chopping the local ingredients ...",
    "Firing up the local stove ...",
    "Searching the dusty archives ...",
    "Spinning the wrench ...",
    "Sending a carrier pigeon ...",
    "Stripping the wires ...",
    "Reading the local voltage ...",
    "Grounding to local earth ...",
    "Scanning the shelf ...",
    "Pruning the local branches ...",
    "Harvesting from the home garden ...",
    "Planting a syscall ...",
    "Raking through the local stack ...",
    "Casting a local spell ...",
    "Seasoning to taste, locally ...",
    "Mapping the local terrain ...",
    "Deploying the local appendage ...",
    "Exploring the file system catacombs ...",
    "Brewing a local concoction ...",
    "Summoning the on-device daemon ...",
    "Letting the circuits sweat ...",
    "Deploying the desk minion ...",
]
TOOLS_EXECUTION_DONE_TITLE: str = "Tools execution done"
TOOLS_EXECUTION_INTRP_TITLE: str = "Tools execution interrupted"
TOOLS_EXECUTION_FAIL_TITLE: str = "Tools execution failed"
TOOLS_EXECUTION_SPINNER: str = "bouncingBall"
PERMISSION_REQUEST_DSEC_CHAR_MAX: int = 500
STREAM_DISPLAY_REFRESH_RATE: int = 20
STREAM_DISPLAY_MAX_REASON_LINE: int = 10
STREAM_DISPLAY_MAX_CONTENT_LINE: int = 20
EDIT_VIEW_RMV_BG: str = "#5F0000"  # remove line bg color
EDIT_VIEW_ADD_BG: str = "#005F00"  # add line bg color
EDIT_VIEW_LINE_MARGIN_SINGLE: int = 3
EDIT_VIEW_LINE_MARGIN_MULTI: int = 2
EDIT_VIEW_LEFT_SPACE_MARGIN: int = 5
EDIT_VIEW_LINE_SPACE_MARGIN: int = 1
BASH_VIEW_LEFT_SPACE_MARGIN: int = 5
BASH_VIEW_LINE_NUM_MARGIN: int = 1
URL_CACHE_VIEW_MAX: int = 8
URL_CACHE_CONTENT_CHAR_MAX: int = 100
MCP_TOOL_DESC_CHAR_LIMIT: int =  250
