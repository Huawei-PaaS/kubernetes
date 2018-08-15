# coding=utf8

import logging
import os
import ConfigParser
import getpass
import socket
import config
import stat


def get_config(file_path=config.CONF_FILE, section='', option=''):
    if os.path.exists(file_path) is False or section is None or option is None:
        return None
    tmp_config = ConfigParser.RawConfigParser()
    if os.path.exists(file_path):
        tmp_config.read(file_path)
    else:
        return None
    if section.lower() == 'default':
        return tmp_config.get(section, option)
    if tmp_config.has_section(section) is False:
        return None
    if tmp_config.has_option(section, option):
        return tmp_config.get(section, option)
    return None


def format_log(mode='DEBUG'):
    log_path = get_config(section="DEFAULT", option="log_audit")
    logger = logging.getLogger("log_audit")

    # set log path
    log_file = logging.FileHandler(log_path)

    # set log level
    if hasattr(logging, mode):
        logger.setLevel(getattr(logging, mode))
        log_file.setLevel(getattr(logging, mode))
    else:
        logger.setLevel(logging.DEBUG)
        log_file.setLevel(logging.DEBUG)

    # set log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(process)d - %(levelname)s - %(message)s"
    )
    log_file.setFormatter(formatter)
    logger.addHandler(log_file)

    return logger


class LoggerAudit(object):
    def __init__(self):
        try:
            self.logger = format_log()
            self.global_info = getpass.getuser() + ' - ' \
                               + socket.gethostbyname(socket.gethostname()) + ';'
        except:
            self.global_info = getpass.getuser() + ' - localhost:'
            return

    def info(self, info=''):
        try:
            self.logger.info(self.global_info + ' ' + info)
        except:
            return

    def error(self, error=''):
        try:
            self.logger.error(self.global_info + ' ' + error)
        except:
            return

    def warn(self, warning=''):
        try:
            self.logger.warning(self.global_info + ' ' + warning)
        except:
            return

    def critical(self, critical=''):
        try:
            self.logger.critical(self.global_info + ' ' + critical)
        except:
            return

    def debug(self, debug=''):
        try:
            self.logger.debug(self.global_info + ' ' + debug)
        except:
            return
