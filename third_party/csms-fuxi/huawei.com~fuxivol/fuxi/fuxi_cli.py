import base64
import json
import os
import sys

from common import config
from common.constants import consts
from oslo_log import log as logging

from api import api as storage_api
from api.response import response

LOG = logging.getLogger(__name__, 'fuxi')


def usage():
    LOG.error("Invalid usage. Usage: ")
    LOG.error("\t$0 attach <json params> <nodename>")
    LOG.error("\t$0 isattached <json params> <nodename>")
    LOG.error("\t$0 waitforattach <mount device> <json params>")
    LOG.error("\t$0 detach <mount device>")
    LOG.error("\t$0 mount <mount dir> <mount device> <json params>")
    LOG.error("\t$0 mountdevice <mount dir> <mount device> <json params>")
    LOG.error("\t$0 unmount <mount dir>")
    LOG.error("\t$0 unmountdevice <deviceMountPath> <json params>")
    LOG.error("\t$0 create <json params>")
    LOG.error("\t$0 delete <volume_id> <json params>")
    LOG.error("\t$0 expandvolume <json params>")
    LOG.error("\t$0 getvolumelimitkey <json params>")
    LOG.error("\t$0 getvolumelimitinfo <json params>")
    result = response.create_error_response("Invalid usage", consts.INVALID_USAGE)
    LOG.error(result)
    return result


def dispatch_commands(cmd, args):
    if "attach" == cmd:
        print(api.attach(json.loads(base64.decodestring(args[1]))[0]))
    elif "isattached" == cmd:
        print (api.isattached())
    elif "waitforattach" == cmd:
        print(api.waitforattach(json.loads(base64.decodestring(args[1]))[0]))
    elif "detach" == cmd:
        print(api.detach(args[1], args[2], json.loads(base64.decodestring(args[3]))[0]))
    elif "mount" == cmd:
        print(api.mount(args[1], args[2], json.loads(base64.decodestring(args[3]))[0]))
    elif "mountdevice" == cmd:
        print(api.mount_device(args[1], args[2], json.loads(base64.decodestring(args[3]))[0]))
    elif "unmount" == cmd:
        print(api.unmount(args[1], json.loads(base64.decodestring(args[2]))[0]))
    elif "unmountdevice" == cmd:
        print(api.unmountdevice(args[1], json.loads(base64.decodestring(args[2]))[0]))
    elif "create" == cmd:
        print(api.create(json.loads(base64.decodestring(args[1]))[0]))
    elif "delete" == cmd:
        print(api.delete(args[1], json.loads(base64.decodestring(args[2]))[0]))
    elif "expandvolume" == cmd:
        print(api.expand(args[1], args[2], json.loads(base64.decodestring(args[3]))[0]))
    elif "getvolumelimitkey" == cmd:
        print(api.getvolumelimitkey(json.loads(base64.decodestring(args[1]))[0]))
    elif "getvolumelimitinfo" == cmd:
        print(api.getvolumelimitinfo())
    elif "init" == cmd:
        print(api.init())
    else:
        print(usage())


def get_command_and_argv():
    if len(sys.argv) < 2:
        print(usage())
    ret_command = sys.argv[1]
    ret_argv = sys.argv[1:]
    return ret_command, ret_argv


def init_log():
    log_file = config.get("DEFAULT", "log_file", consts.LOG_FILE)
    logging.tempest_set_log_file(log_file)
    logging.register_options(config.CONF)  # debug opts
    logging.setup(config.CONF, 'fuxi')


def set_environment():
    provider_type = config.get("DEFAULT", "provider_type", None)
    if provider_type == 'storage_manager':
        certificate_path = config.get("STORAGE_MANAGER", "root_key_path", None)
        if certificate_path is None:
            LOG.error("Failed to get environment variable!")
            return False
        try:
            os.environ['CIPHER_ROOT'] = certificate_path
            return True
        except OSError as ex:
            LOG.exception(ex.message)
            LOG.error("Failed to set environment variable! Err: {0}").format(ex.message)
            return False
    else:
        return True


if __name__ == "__main__":

    command, argv = get_command_and_argv()
    command = command.lower()

    sys.argv = sys.argv[0:1]  # in order to avoid oslo.config read sys.argv
    config.init()
    init_log()
    config.enable()
    set_environment()

    LOG.debug("Fuxi volume driver starts to work!")
    LOG.info("command: " + command)
    LOG.info(argv)

    api = storage_api.API()
    if command not in ["create", "delete", "attach", "isattached", "detach", "mount", "unmount", "unmountdevice",
                       "init", "waitforattach", "mountdevice", "expandvolume", "getvolumelimitinfo", "getvolumelimitkey"]:
        print(usage())
    try:
        dispatch_commands(command, argv)
    except Exception as ex:
        LOG.exception(ex.message)
        LOG.error(ex.message)
        result = response.create_error_response(ex.message, consts.GET_PARAMS_FAILED)
        print result
