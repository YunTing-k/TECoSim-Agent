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

Details:
Argument definitions of the TECoSim agent
------------------------------------------------------------------------------------------------------------------------
"""
import argparse
from argparse import Namespace


def tecosim_agent_args() -> Namespace:
    parser = argparse.ArgumentParser(description='Thermo-Electric Coupling Cross-level Display Simulator (TECoSim) Agent')
    parser.add_argument('-l', '--log', help='To enable dev logger', action='store_true')
    parser.add_argument('-r', '--resume', type=str, help='Resume with session UUID', metavar='<UUID>')
    return parser.parse_args()
