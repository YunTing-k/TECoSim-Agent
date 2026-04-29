# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2026.4.8\n
Description: Argument of the TECoSim agent

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2026.4.8       Yu Huang     1.0               First implementation\n
2026.4.28      Yu Huang     1.1               Dangerously allow all permissions support\n

Details:
Argument definitions of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import argparse
from argparse import Namespace


def tecosim_agent_args() -> Namespace:
    """Arguments of the TECoSim agent"""
    parser = argparse.ArgumentParser(description='Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent')
    parser.add_argument('-l', '--log', help='To enable dev logger', action='store_true')
    parser.add_argument('-r', '--resume', type=str, help='Resume with session UUID', metavar='<UUID>')
    parser.add_argument('--dangerously_allow_all', help='Dangerously allow all permissions, this may damage '
                                                        'your workspace or computer. Think twice before toggle this flag!',
                        action='store_true')
    return parser.parse_args()
