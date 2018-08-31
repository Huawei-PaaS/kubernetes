from common.constants import consts
from oslo_log import log as logging

LOG = logging.getLogger(__name__, 'fuxi')


def create_volume_attach_success_response(dev_path):
    message = "{\"status\": \"Success\", \"device\":\"%s\",\"magiccode\":\"%s\"}" % (dev_path, consts.MAGIC_CODE)
    LOG.info(message)
    return message


def create_volume_success_response(volume_info):
    message = "{\"status\": \"Success\", \"volume\":%s,\"magiccode\":\"%s\"}" % (volume_info, consts.MAGIC_CODE)
    LOG.info(message)
    return message


def create_error_response(message, message_code):
    message = "{\"status\": \"Failed\", \"message\": \"%s\",\"messagecode\":\"%s\",\"magiccode\":\"%s\"}" % (
        message, message_code, consts.MAGIC_CODE)
    LOG.info(message)
    return message


def create_success_response():
    message = "{\"status\": \"Success\",\"magiccode\":\"%s\"}" % consts.MAGIC_CODE
    LOG.info(message)
    return message


def create_init_success_response():
    message = "{\"status\": \"Success\",\"capabilities\":{\"attach\": %s, \"expandvolume\": true , " \
              "\"requiresFSResize\": false, \"supportsMetrics\": true},\"magiccode\":\"%s\"}" % ("false", consts.MAGIC_CODE)
    LOG.info(message)
    return message


def create_not_found_response(message, message_code):
    message = "{\"status\": \"Not found\", \"message\": \"%s\",\"messagecode\":\"%s\",\"magiccode\":\"%s\"}" % (
        message, message_code, consts.MAGIC_CODE)
    LOG.info(message)
    return message


def common_error_response(message, message_code):
    message = "{\"status\": \"Failed\", \"message\": \"%s\",\"messagecode\":\"%s\",\"magiccode\":\"%s\"}" % (
        message, message_code, consts.MAGIC_CODE)
    LOG.info(message)
    return message


def not_support_response():
    message = "{\"status\": \"Not supported\",\"magiccode\":\"%s\"}" % (
        consts.MAGIC_CODE)
    LOG.info(message)
    return message
