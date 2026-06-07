# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.4.8
Description: Argument of the TECoSim agent

Revision:
---------
2026.4.8       Yu Huang      1.0      First implementation
2026.4.28      Yu Huang      1.1      Dangerously allow all permissions support
2026.5.15      Yu Huang      1.2      Disable all skills support
2026.5.21-22   Yu Huang      1.3      Agent MCPs support
2026.5.31      Yu Huang      1.4      Add CLI session management support
2026.6.2       Yu Huang      1.5      Add CLI command support of skill list
2026.6.3       Yu Huang      1.6      Add cron tasks support
2026.6.5       Yu Huang      1.7      Add --nosystem, --notools, --nocrons support

Details:
---------
CLI argument parser for the agent. Main arguments: `-l` (dev log), `-r <UUID>` (resume session), `--nosystem`, `--notools`,
`--nocrons`, `--noskills`, `--nomcps`, `--dangerously_allow_all`. Sub-commands: `session` (list/remove sessions),
`cron` (list/remove durable cron tasks), `skill` (list skills), `mcp` (list/add/toggle/remove MCP servers).
"""
import argparse
from argparse import Namespace


def tecosim_agent_args() -> Namespace:
    """Arguments of the TECoSim agent"""

    """main command"""
    parser = argparse.ArgumentParser(description='Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent')
    parser.add_argument('-l', '--log', help='To enable dev logger', action='store_true')
    parser.add_argument('-r', '--resume', type=str, help='Resume with session UUID', metavar='<UUID>')
    parser.add_argument('--nosystem', help='To disable main agent\'s system prompts', action='store_true')
    parser.add_argument('--notools', help='To disable main agent\'s tools', action='store_true')
    parser.add_argument('--nocrons', help='To disable all cron tasks in main agent and subagent', action='store_true')
    parser.add_argument('--noskills', help='To disable all skills in main agent and subagent', action='store_true')
    parser.add_argument('--nomcps', help='To disable all MCPs in main agent and subagent', action='store_true')
    parser.add_argument('--dangerously_allow_all', help='Dangerously allow all permissions, this may damage '
                        'your workspace or computer. Think twice before toggle this flag!', action='store_true')

    """root of sub commands"""
    subparsers = parser.add_subparsers(dest='command', help='sub commands')

    """sub command for sessions"""
    session_parser = subparsers.add_parser('session', help='Session operations')
    session_subparsers = session_parser.add_subparsers(dest='session_action', help='Session actions')

    # session list
    session_list = session_subparsers.add_parser('list', help='List all sessions')

    # session remove
    session_remove = session_subparsers.add_parser('remove', help='Remove a session with UUID')
    session_remove.add_argument('uuid', type=str, help='Session\'s UUID to remove')

    """sub command for durable cron tasks"""
    cron_parser = subparsers.add_parser('cron', help='Durable cron tasks operations')
    cron_subparsers = cron_parser.add_subparsers(dest='cron_action', help='Durable cron tasks actions')

    # durable cron task list
    cron_list = cron_subparsers.add_parser('list', help='List all durable cron tasks')

    # cron task remove
    cron_remove = cron_subparsers.add_parser('remove', help='Remove a durable cron task with ID')
    cron_remove.add_argument('id', type=str, help='Durable cron task\'s ID to remove')

    """sub command for skills"""
    skill_parser = subparsers.add_parser('skill', help='Skill operations')
    skill_subparsers = skill_parser.add_subparsers(dest='skill_action', help='Skill actions')

    # skill list
    skill_list = skill_subparsers.add_parser('list', help='List all skills')

    """sub command for MCPs"""
    mcp_parser = subparsers.add_parser('mcp', help='MCP operations')
    mcp_subparsers = mcp_parser.add_subparsers(dest='mcp_action', help='MCP actions')

    # mcp list
    mcp_list = mcp_subparsers.add_parser('list', help='List all MCP servers')

    # mcp add
    mcp_add = mcp_subparsers.add_parser('add', help='Add an MCP server with name')
    mcp_add.add_argument('name', type=str, help='MCP server\'s name to add')
    mcp_add.add_argument('type', type=str, help='MCP server\'s transport type')
    mcp_add.add_argument('params', type=str, help='JSON string of MCP parameters')

    # mcp toggle
    mcp_disable = mcp_subparsers.add_parser('toggle', help='Toggle an MCP server with name from enable/disable to disable/enable')
    mcp_disable.add_argument('name', type=str, help='MCP server\'s name to disable')

    # mcp remove
    mcp_remove = mcp_subparsers.add_parser('remove', help='Remove an MCP server with name')
    mcp_remove.add_argument('name', type=str, help='MCP server\'s name to remove')

    return parser.parse_args()
