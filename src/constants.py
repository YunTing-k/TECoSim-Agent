# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.14
Description: Global constants and default parameters for TECoSim agent

Revision:
---------
2026.4.14      Yu Huang      1.0      First implementation
2026.6.13      Yu Huang      1.1      Subagent support: types, status, icons, colors, tool result limits & Add header
2026.6.14      Yu Huang      1.2      Add: simulator timeout default, agent label renames, subagent step/warn defaults
2026.6.29      Yu Huang      1.3      Add: QUESTION_NO_CHOICE_LABEL, SUBAGENT_SUMMARIES_NAME
2026.7.15-16   Yu Huang      1.4      Add WeChat bot interaction support

Details:
---------
All global constants, default parameters, and tool name strings. Divided into: version, basic file paths,
subagent constants, system labels, major colors, bash risk levels, UI display params, task management,
MCP params, and more.
"""
"""TECoSim Agent constants"""
"""TECoSim Agent version"""
TECOSIM_AGENT_MAJOR_VERSION: int = 0
TECOSIM_AGENT_MINOR_VERSION: int = 3
TECOSIM_AGENT_UPDATE_VERSION: int = 0
"""Basic configs"""
# basic files/dirs
LOG_PATH: str = "./log"
API_CONFIGS_PATH: str = "./config/api_configs.json"
AGENT_CONFIGS_PATH: str = "./config/agent_configs.json"
MCPS_PATH: str = "./mcps"
SKILLS_PATH: str = "./skills"
MCPS_CONFIGS_PATH: str = MCPS_PATH + "/mcps_configs.json"
SESSION_PATH: str = "./session"
CRON_CONFIGS_PATH: str = "./cron/cron_configs.json"
CRON_TASK_ID_LEN: int = 8
WECHAT_CRED_PATH: str = "./config/wechat_bot_cred.json"
# files/dirs under session:
USER_HISTORY_NAME: str = "user_history"
MESSAGES_NAME: str = "messages.json"
CONTEXT_NAME: str = "context.json"
CRON_NAME: str = "cron_configs.json"
TASKS_NAME: str = "tasks.json"
RUNS_NAME: str = "runs.json"
DESIGNS_NAME: str = "designs.json"
WECHAT_MEDIA_CACHE_DIR: str = "wechat_cache"
WECHAT_MEDIA_CACHE_NAME: str = "cdn_cache.json"
WECHAT_HISTORY_NAME: str = "msg_history.json"
# WeChat bot
WECHAT_BOT_LOGIN_DEFAULT_TIMEOUT_S: float = 120
WECHAT_BOT_STOP_DEFAULT_TIMEOUT_S: float = 10
WECHAT_BOT_HEAD_CDN_DEFAULT_TIMEOUT_S: float = 10
WECHAT_BOT_TEXT_REPLY_DEFAULT_TIMEOUT_S: float = 30
WECHAT_BOT_MEDIA_REPLY_DEFAULT_TIMEOUT_S: float = 60
WECHAT_BOT_MUTE_NONFATAL_ERROR_DEFAULT: bool = False
WECHAT_BOT_MSG_SUMMARY_CHAR_MAX: int = 100
WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB_DEFAULT: int = 100
WECHAT_MEDIA_CACHE_KEY_MAX_LEN: int = 8
WECHAT_BOT_QUOTED_CHAR_MAX: int = 1000
WECHAT_BOT_LOCKED_LIST: list[str] = [
    "✅ Session has been locked. You have exclusive access. Other users will be denied until this session ends.",
    "✅ Exclusive session initiated. All other incoming requests will be rejected for the duration of this conversation.",
    "✅ You now hold the session lock. No other users will be admitted until you disconnect.",
    "✅ Session secured. External access has been disabled for the remainder of this interaction.",
    "✅ Lock acquired. This session is now single-user. Concurrent requests will be blocked.",
]
WECHAT_BOT_BLOCK_REPLY_LIST: list[str] = [
    "❌ Sorry, I'm currently serving another user. This session won't be available until it ends.",
    "❌ I'm in a private session right now. No queue, no waiting — please don't hold your breath.",
    "❌ Occupied. There's no line to wait in — this conversation is exclusive until it's over.",
    "❌ Another user has locked this session. You won't get through until they're done.",
    "❌ Currently in an exclusive chat. Don't wait around — this won't open up mid-session.",
    "❌ I'm a one-person-at-a-time kind of bot. No queue, no waiting list, just come back... eventually.",
    "❌ Someone else has my full attention right now. I don't do reservations — try again only if you're feeling lucky.",
    "❌ I'm not ignoring you, but I kind of am. This session is locked, and there's no ETA.",
    "❌ Session locked. No waitlist. Try again only after the current chat ends.",
    "❌ Exclusive session in progress. Door's closed, no peeking.",
    "❌ Occupied. No queue. Come back when it's quiet.",
    "❌ I'm with someone else and can't switch mid-conversation. There's no waitlist — you'll just have to catch me when I'm free.",
    "❌ This is a strictly one-on-one session. No interruptions allowed, no line forming. Please don't wait on me.",
]
# subagent
MAIN_AGENT_ID: str = "main"
AGENT_ID_LEN: int = 8
EXPLORER_AGENT_LABEL: str = "explorer"
WORKER_AGENT_LABEL: str = "worker"
SCHEDULER_AGENT_LABEL: str = "scheduler"
AGENT_PENDING_LABEL: str = "pending"
AGENT_RUNNING_LABEL: str = "running"
AGENT_TIMEOUT_LABEL: str = "timeout"
AGENT_ERROR_LABEL: str = "error"
AGENT_DONE_LABEL: str = "done"
AGENT_UNKNOWN_LABEL: str = "unknown"  # defensive-only: never set at runtime, used as fallback on resume deserialization
SUBAGENT_DUMP_DIR: str = "agents"
SUBAGENT_SUMMARIES_NAME: str = "summaries.json"
SUBAGENT_DEFAULT_MAX_STEPS: int = 30
SUBAGENT_DEFAULT_WARN_STEPS: int = 2
SUBAGENT_DEFAULT_TIMEOUT_S: int = 600
SUBAGENT_DEFAULT_MODEL_TYPE: str = "fast"
SUBAGENT_RESULT_LOG_CHAR_LIMIT: int = 200
SUBAGENT_TOOL_DISPLAY_MAX_LEN: int = 120
SUBAGENT_PROMPT_LOG_CHAR_LEN: int = 200
SUBAGENT_SUBJECT_CHAR_LIMIT: int = 40
SUBAGENT_TOOL_RESULT_DEFAULT_CHAR_LIMIT: int = 50000
MAIN_TOOL_RESULT_DEFAULT_CHAR_LIMIT: int = 20000
TOOL_RESULT_TRUNCATION_ROUNDS: int = 6  # max rounds for iterative field-level truncation before fallback hard cut
TOOL_RESULT_TRUNCATION_MIN_BUDGET: int = 1024  # floor budget for truncated field content, prevents near-empty truncation
TOOL_RESULT_TRUNCATION_MARKER_RESERVE: int = 60  # char reserve for truncation marker overhead
TOOL_RESULT_TRUNCATION_START_LABEL: str = "<truncated>"
TOOL_RESULT_TRUNCATION_END_LABEL: str = "</truncated>"
SUBAGENT_PENDING_ICON: str = "○"
SUBAGENT_IN_PROGRESS_ICON: str = "♦"
SUBAGENT_DONE_ICON: str = "✓"
SUBAGENT_ERROR_ICON: str = "✗"
SUBAGENT_COLOR_START: str = "#202020"
SUBAGENT_COLOR_END: str = "#808080"
SUBAGENT_COLOR_GRADIENT: int = 128
SUBAGENT_COLOR_PERIOD: float = 4
# others
DEFAULT_TIMEOUT_MS: int = 1000000
WECHAT_PROMPT_START_LABEL: str = "<wechat_bot>"
WECHAT_PROMPT_END_LABEL: str = "</wechat_bot>"
WECHAT_PROMPT_ICON: str = "▶"
SYS_REMINDER_START_LABEL: str = "<system_reminder>"
SYS_REMINDER_END_LABEL: str = "</system_reminder>"
SYS_REMINDER_ICON: str = "⚑"
SUBAGENT_START_LABEL: str = "<subagent>"
SUBAGENT_END_LABEL: str = "</subagent>"
SUBAGENT_ICON: str = "▲"
SKILL_START_LABEL: str = "<skill_content>"
SKILL_END_LABEL: str = "</skill_content>"
SKILL_ICON: str = "❖"
CRON_START_LABEL: str = "<cron_tasks>"
CRON_END_LABEL: str = "</cron_tasks>"
CRON_ICON: str = "⬟"
CRON_PROMPT_DISPLAY_CHAR_MAX: int = 200
SIM_DESIGN_NAME: str = "design"
SIM_RUN_NAME: str = "run"
FAIL_LABEL: str = "FAIL"
UNKNOWN_LABEL: str = "UNKNOWN"
FALLBACK_LABEL: str = "FALLBACK"
SUCCESS_LABEL: str = "SUCCESS"
DONE_LABEL: str = "DONE"
TIMEOUT_LABEL: str = "TIMEOUT"
CANCELLED_LABEL: str = "CANCELLED"
DENIED_LABEL: str = "DENIED"
MUTE_PERMISSION_DENIED_INFO: str = "Permission request denied, you don't have access to this tool"
MAINAGENT_PERMISSION_DENIED_INFO: str = "Permission request denied by user"
MAINAGENT_PERMISSION_DENIED_PREFIX_INFO: str = "Permission request denied by user with comment:"
DISABLED_LABEL: str = "DISABLED"
TRUNCATED_LABEL: str = "TRUNCATED"
TASK_PENDING_LABEL: str = "pending"
TASK_IN_PROGRESS_LABEL: str = "in_progress"
TASK_COMPLETED_LABEL: str = "completed"
TASK_DELETED_LABEL: str = "deleted"
TASK_DISPLAYS_BEFORE_ARCHIVED: int = 6
MUTE_TASK_OP_INFO: bool = True
RUN_PENDING_LABEL: str = "PENDING"
RUN_CANCELLED_LABEL: str = "CANCELLED"
RUN_TIMEOUT_LABEL: str = "TIMEOUT"
RUN_RUNTIME_ERROR_LABEL: str = "RUNTIME_ERROR"
RUN_DONE_LABEL: str = "DONE"
"""Tool names"""
# basic tools
TOOL_NAME_VERSION: str = "agent_version"
TOOL_NAME_SPAWN_AGENT: str = "spawn_agent"
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
TOOL_NAME_WECHAT_SEND_MEDIA: str = "wechat_send_media"
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
QUESTION_NO_CHOICE_LABEL = "(User didn't choose any option)"
BASH_TIMEOUT_MS_MAX: int = 600000
BASH_TIMEOUT_MS_DEFAULT: int = 120000
SIMULATOR_TIMEOUT_DEFAULT_S: int = 3600
GLOB_FILE_ENTRIES_DEFAULT: int = 250
GREP_FILE_HEAD_LIMIT_DEFAULT: int = 250
READ_FILE_MAX_LINE: int = 10000
READ_FILE_ENCODING_DEFAULT: str = "utf-8"
READ_FILE_LINE_CHAR_LIMIT: int = 2000  # max chars per line before truncation (LLM-facing output)
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
BASH_INLINE_SCRIPT_LABEL = "BASH_LOW_RISK_INLINE_SCRIPT_OPERATION"  # medium-risk (3)
BASH_REPOSITORY_MODIFY_LABEL = "BASH_REPOSITORY_MODIFY"  # medium-risk (5)
BASH_STAGE_CHANGE_LABEL = "BASH_STAGE_CHANGE"  # medium-risk (6)
BASH_UNKNOWN_LABEL = "BASH_UNKNOWN"  # unknown (7)
BASH_SAFE_LABEL = "BASH_SAFE" # no-risk (8)
BASH_EMPTY_LABEL = "BASH_EMPTY" # no-risk (9)
"""UI"""
MAJOR_COLOR1: str = "#FF9FF3"  # bright major color
MAJOR_COLOR2: str = "#54A0FF"  # common major color
REASONING_COLOR: str = MAJOR_COLOR2
REASON_STYLE: str = f"italic {REASONING_COLOR}"
CONTENT_STYLE: str = "none"
MARKDOWN_TABLE_COLOR: str = MAJOR_COLOR2
MARKDOWN_TABLE_HEADER_STYLE: str = f"bold {MAJOR_COLOR2}"
MARKDOWN_LIST_BULLET_COLOR: str = "#FF9FF3"
MARKDOWN_LIST_NUMBER_COLOR: str = "#FF9FF3"
MARKDOWN_INLINE_CODE_COLOR: str = "#61D6D6"
MARKDOWN_BLOCKQUOTE_STYLE: str = "italic #696969"
MARKDOWN_LINK_COLOR: str = "#F5A742"
MARKDOWN_HR_COLOR: str = "#696969"
MARKDOWN_IMAGE_STYLE: str = "#F5A742"
MARKDOWN_H1_STYLE: str = f"bold underline #FF9FF3"
MARKDOWN_H2_STYLE: str = f"bold #FF9FF3"
MARKDOWN_H3_STYLE: str = f"#FF9FF3"
MARKDOWN_H4_STYLE: str = f"italic #FFBCF7"
MARKDOWN_H5_STYLE: str = f"italic #FFCAF8"
MARKDOWN_H6_STYLE: str = f"italic #FFD9FA"
EDIT_FUZZY_WARN_COLOR: str = MAJOR_COLOR1  # fuzzy match warning
EDIT_SUBTLE_COLOR: str = "bright_black"  # exact-family subtle label
AGENT_CONSOLE_ICON: str = "✦"
REASON_ICON: str = "⟡"
REASON_ICON_SYLTE: str = f"bold {MAJOR_COLOR2}"
CONTENT_ICON: str = "●"
CONTENT_ICON_SYLTE: str = f"bold {MAJOR_COLOR1}"
MESSAGE_PRINT_MARGIN: int = 4
MESSAGE_COLOR_GRADIENT: int = 128
MESSAGE_COLOR_PERIOD: float = 1.75
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
LISTEN_TUI_COLOR_PERIOD: float = 1.75
TASK_EMPTY_TITLE: str = ""
TASK_VIEW_LEFT_MARGIN: int = 6
TASK_VIEW_RIGHT_MARGIN: int = 1
TASK_COLOR_GRADIENT: int = 128
TASK_COLOR_PERIOD: float = 1.75
TASK_PENDING_WITHOUT_OWNER_ICON: str = "○"
TASK_PENDING_WITHOUT_OWNER_ICON_STYLE: str = "bright_black"
TASK_PENDING_WITHOUT_OWNER_STYLE: str = "bright_black"
TASK_PENDING_WITH_OWNER_ICON: str = "●"
TASK_PENDING_COLOR_START: str = "#202020"
TASK_PENDING_COLOR_END: str = "#808080"
TASK_IN_PROGRESS_COLOR_START: str = MAJOR_COLOR1
TASK_IN_PROGRESS_COLOR_END: str = MAJOR_COLOR2
TASK_COMPLETED_ICON: str = "✓"
TASK_COMPLETED_COLOR: str = "#8CDCA0"
TASK_DELETED_ICON: str = "✗"
TASK_DELETED_COLOR: str = "#767676"
CRON_LISTEN_COLOR_START: str = MAJOR_COLOR1
CRON_LISTEN_COLOR_END: str = MAJOR_COLOR2
CRON_LISTEN_COLOR_GRADIENT: int = 128
CRON_LISTEN_COLOR_PERIOD: float = 1.75
OPTIONS_TO_SELECT_PREFIX: str = "❯ "
OPTIONS_UN_SELECT_PREFIX: str = "  "
OPTIONS_SELECTED_PREFIX: str = " ✓"
OPTIONS_UNSELECTED_PREFIX: str = ""
KEY_LISTEN_SLEEP_TIME_MS: int = 30
SPINNER_LIVE_CHECK_GAP_MS: int = 200
SPINNER_TERMINATE_WAIT_S: int = 10
USER_PROMPT_FIXED_PREFIX: str = "(Shift+Tab: New line, Enter: Submit)"
WECHAT_VERIFY_CODE_PREFIX1: str = "Please input the verify code on you phone"
WECHAT_VERIFY_CODE_PREFIX2: str = "Wrong verify code, please input the correct verify code on you phone"
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
EDIT_VIEW_RMV_BG: str = "#37222C"  # remove line content bg color
EDIT_VIEW_ADD_BG: str =  "#20303B" # add line content bg color
EDIT_VIEW_NORMAL_BG: str = "#141414"  # normal/context line bg color
EDIT_VIEW_RMV_LINE_BG: str = "#2D1F26"  # remove line number darker bg color
EDIT_VIEW_ADD_LINE_BG: str = "#1B2B34"  # add line number darker bg color
EDIT_VIEW_RMV_SYMBOL_COLOR: str = "#E26A75"  # remove '-' symbol color
EDIT_VIEW_ADD_SYMBOL_COLOR: str = "#B8DB87"  # add '+' symbol color
EDIT_VIEW_LINE_MARGIN_SINGLE: int = 3
EDIT_VIEW_LINE_MARGIN_MULTI: int = 2
EDIT_VIEW_LEFT_SPACE_MARGIN: int = 5
EDIT_VIEW_LINE_SPACE_MARGIN: int = 1
EDIT_VIEW_TAB_WIDTH: int = 4
EDIT_SYNTAX_THEME: str = "one-dark"
"""Match mode for edit_file fallback chain"""
MATCH_MODE_EXACT: str = "exact"
MATCH_MODE_QUOTE_NORM: str = "quote_norm"
MATCH_MODE_UNICODE_ESCAPE: str = "unicode_escape"
MATCH_MODE_LINE_TRIMMED: str = "line_trimmed"
MATCH_MODE_FLEX_INDENT: str = "flex_indent"
MATCH_MODE_ESCAPE_LITERAL: str = "escape_literal"
MATCH_MODE_TRIMMED_BOUNDARY: str = "trimmed_boundary"
MATCH_MODE_DESC = {
    MATCH_MODE_EXACT: "exact match",
    MATCH_MODE_QUOTE_NORM: "exact (quote normalized)",
    MATCH_MODE_UNICODE_ESCAPE: "exact (unicode decoded)",
    MATCH_MODE_LINE_TRIMMED: "fuzzy match (line trimmed)",
    MATCH_MODE_FLEX_INDENT: "fuzzy match (indentation flexible)",
    MATCH_MODE_ESCAPE_LITERAL: "fuzzy match (escape literal corrected)",
    MATCH_MODE_TRIMMED_BOUNDARY: "fuzzy match (boundary trimmed)",
}
# match modes considered "exact enough" — shown in subtle color, not alarming orange
MATCH_MODE_EXACT_FAMILY = {MATCH_MODE_EXACT, MATCH_MODE_QUOTE_NORM, MATCH_MODE_UNICODE_ESCAPE}
BASH_VIEW_LEFT_SPACE_MARGIN: int = 5
BASH_VIEW_GUTTER_BG: str = "#222222"  # bash gutter (margin + line number) bg color
BASH_VIEW_PADDING_LINES: int = 1  # blank padding lines above and below the command block
BASH_RESULT_GUTTER_BG: str = "#222222"  # bash result output line-number gutter bg
BASH_RESULT_CONTENT_BG: str = "#141414"  # bash result output content bg
BASH_RESULT_MAX_LINES: int = 60  # max lines to display in bash result preview
BASH_RESULT_MAX_CHARS: int = 3000  # max chars to display in bash result preview
BASH_RESULT_PADDING_LINES: int = 1  # blank padding lines above and below the result block
WRITE_VIEW_GUTTER_BG: str = "#222222"  # write file preview gutter bg
WRITE_VIEW_CONTENT_BG: str = "#141414"  # write file preview content bg
WRITE_VIEW_PADDING_LINES: int = 1  # blank padding lines above and below write preview
WRITE_VIEW_MAX_LINES: int = 40  # max lines to display in write file preview
WRITE_VIEW_MAX_CHARS: int = 2000  # max chars to display in write file preview
URL_CACHE_VIEW_MAX: int = 8
URL_CACHE_CONTENT_CHAR_MAX: int = 100
MCP_TOOL_DESC_CHAR_LIMIT: int =  250
