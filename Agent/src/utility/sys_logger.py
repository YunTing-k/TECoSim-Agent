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
2026.6.2       Yu Huang     1.5               Refactor logger with composition + explicit delegation + monkey-patch

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
    """Custom logger wrapper that configures the shared 'logger' singleton and adds param()."""
    def __init__(self, name: str = 'log', dev_log: bool = False):
        # Always use the shared 'logger' singleton so early getLogger('logger') references are preserved
        self._logger = logging.getLogger('logger')
        self._logger.setLevel(logging.DEBUG)
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
            self._logger.addHandler(sh)
        fh = logging.FileHandler(filename=os.path.join(LOG_PATH, self.name + '_' + time_format + '.txt'), mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(log_format)
        self._logger.addHandler(fh)

        # Register under the given name too, so logging.getLogger(name) also returns this instance
        if name != 'logger':
            logging.Logger.manager.loggerDict[name] = self._logger

    # Custom method
    def param(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'PARAM'."""
        if self._logger.isEnabledFor(LOG_LEVEL_PARAM):
            self._logger.log(LOG_LEVEL_PARAM, msg, *args, **kwargs)

    # Delegate standard logging.Logger methods via properties (IDE jump goes to stdlib source)
    @property
    def debug(self):
        """See logging.Logger.debug"""
        return self._logger.debug

    @property
    def info(self):
        """See logging.Logger.info"""
        return self._logger.info

    @property
    def warning(self):
        """See logging.Logger.warning"""
        return self._logger.warning

    @property
    def error(self):
        """See logging.Logger.error"""
        return self._logger.error

    @property
    def critical(self):
        """See logging.Logger.critical"""
        return self._logger.critical

    @property
    def exception(self):
        """See logging.Logger.exception"""
        return self._logger.exception

    @property
    def log(self):
        """See logging.Logger.log"""
        return self._logger.log

    @property
    def isEnabledFor(self):
        """See logging.Logger.isEnabledFor"""
        return self._logger.isEnabledFor

    @property
    def getEffectiveLevel(self):
        """See logging.Logger.getEffectiveLevel"""
        return self._logger.getEffectiveLevel

    @property
    def setLevel(self):
        """See logging.Logger.setLevel"""
        return self._logger.setLevel

    @property
    def addHandler(self):
        """See logging.Logger.addHandler"""
        return self._logger.addHandler

    @property
    def removeHandler(self):
        """See logging.Logger.removeHandler"""
        return self._logger.removeHandler

    @property
    def hasHandlers(self):
        """See logging.Logger.hasHandlers"""
        return self._logger.hasHandlers


# Monkey-patch: make param() available on logging.getLogger('logger') instances
def _param(self: logging.Logger, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'PARAM'."""
    if self.isEnabledFor(LOG_LEVEL_PARAM):
        self.log(LOG_LEVEL_PARAM, msg, *args, **kwargs)

logging.Logger.param = _param
