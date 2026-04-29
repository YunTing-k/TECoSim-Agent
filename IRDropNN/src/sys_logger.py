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

Details:
------------------------------------------------------------------------------------------------------------------------
Colorful logger, output the logging information to the console and the file, the logging levels are defined as:\n
'DEBUG': 'white'\n
'PARAM': 'blue'\n
'INFO': 'green'\n
'WARNING': 'yellow'\n
'ERROR': 'red'\n
'CRITICAL': 'bold_red'
"""
import io
import logging
import datetime
import colorlog

LOG_LEVEL_PARAM = 25
logging.addLevelName(LOG_LEVEL_PARAM, "PARAM")  # 设置自定义日志级别


class Logger:
    def __init__(self, name: str = 'log'):
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.DEBUG)
        self.config = {
            'DEBUG': 'white',
            'PARAM': 'blue',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
        self.name = name
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        current_time = datetime.datetime.now()
        time_format = current_time.strftime("%Y-%m-%d %H_%M_%S")
        fh = logging.FileHandler(filename='../log/' + self.name + '_' + time_format + '.txt', mode='w')
        fh.setLevel(logging.DEBUG)
        log_format = colorlog.ColoredFormatter(
            fmt='%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s -> [%(levelname)s] : %(message)s',
            datefmt='%H:%M:%S',
            log_colors=self.config
        )
        sh.setFormatter(log_format)
        fh.setFormatter(log_format)
        self.logger.addHandler(sh)
        self.logger.addHandler(fh)

    def param(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'PARAM'."""
        if self.isEnabledFor(LOG_LEVEL_PARAM):
            self.log(LOG_LEVEL_PARAM, msg, *args, **kwargs)

    logging.Logger.param = param


class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of the StdOut.
    """
    logger = None
    level = None
    buf = ''

    def __init__(self, logger, level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf):
        self.buf = buf.strip('\r\n\t ')

    def flush(self):
        self.logger.log(self.level, self.buf)
