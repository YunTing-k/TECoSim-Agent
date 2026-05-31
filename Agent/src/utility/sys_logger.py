# -*- coding: utf-8 -*-
"""
Header information
------------------------------------------------------------------------------------------------------------------------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab\n
Author: Yu Huang\n
Create Date: 2023.11.20\n
Description: Logger definition

Revision:
------------------------------------------------------------------------------------------------------------------------
[Date]         [By]         [Version]         [Change Log]\n
2023.11.20     Yu Huang     1.0               First implementation\n
2024.4.11      Yu Huang     1.1               Add param level and tqdm to logger\n
2026.1.16      Yu Huang     1.2               Add function of param level logger\n
2026.4.16      Yu Huang     1.3               Bug fix of no file written\n
2026.5.31      Yu Huang     1.4               Define used file/dir. paths in constants.py\n

Details:
------------------------------------------------------------------------------------------------------------------------
Colorful logger, output the logging information to the console and the file, the logging levels are defined as:\n
'DEBUG': 'light_black'\n
'PARAM': 'light_blue'\n
'INFO': 'white'\n
'WARNING': 'light_yellow'\n
'ERROR': 'light_red'\n
'CRITICAL': 'red'
"""
import os
import logging
import datetime
import colorlog

from src.constants import LOG_PATH

LOG_LEVEL_PARAM = 25
logging.addLevelName(LOG_LEVEL_PARAM, "PARAM")


class Logger:
    def __init__(self, name: str = 'log', dev_log: bool = False):
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.DEBUG)
        self.config = {
            'DEBUG': 'light_black',
            'PARAM': 'light_blue',
            'INFO': 'white',
            'WARNING': 'light_yellow',
            'ERROR': 'light_red',
            'CRITICAL': 'red',
        }
        self.name = name
        self.dev_log = dev_log

        current_time = datetime.datetime.now()
        time_format = current_time.strftime("%Y-%m-%d %H_%M_%S")
        log_format = colorlog.ColoredFormatter(
            fmt='%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s -> [%(levelname)s] : %(message)s',
            datefmt='%H:%M:%S',
            log_colors=self.config
        )
        if self.dev_log:
            sh = logging.StreamHandler()
            sh.setLevel(logging.DEBUG)
            sh.setFormatter(log_format)
            self.logger.addHandler(sh)
        # fh = logging.FileHandler(filename=LOG_PATH + self.name + '_' + time_format + '.txt', mode='w')
        fh = logging.FileHandler(filename=os.path.join(LOG_PATH, self.name + '_' + time_format + '.txt'), mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(log_format)
        self.logger.addHandler(fh)

    def param(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'PARAM'."""
        if self.isEnabledFor(LOG_LEVEL_PARAM):
            self.log(LOG_LEVEL_PARAM, msg, *args, **kwargs)

    logging.Logger.param = param
