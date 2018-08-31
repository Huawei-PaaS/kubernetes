import os

from api.response import response
from common.config import CONF
from common.constants import consts
from common.i18n import _LE, _LI
from oslo_log import log as logging

LOG = logging.getLogger(__name__, 'fuxi')
STALE_FILE_HANDLE_ERROR_CODE = 116


def validate_namespace(params):
    if CONF.provider_type == 'storage_manager':
        namespace = params.get('kubernetes.io/namespace', CONF.storage_manager.namespace)
        if not namespace:
            message = _LE("Params name_space is none.")
            return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    else:
        namespace = None
    return True, namespace


def validate_manage_namespace(params):
    namespace = params.get('kubernetes.io/namespace', None)
    if not namespace:
        message = _LE("Params name_space is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, namespace


def validate_mount_path(mount_path):
    try:
        os.stat(mount_path)
    except os.error as err:
        if err[0] == STALE_FILE_HANDLE_ERROR_CODE:
            return True, mount_path
        else:
            message = _LE("Mount path {0} is not exists.").format(mount_path)
            return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    if not os.path.ismount(mount_path):
        LOG.info(_LI("Mount path {0} is not a mount path.").format(mount_path))
        return False, response.create_success_response()
    return True, mount_path


def validate_mount(mount_path):
    if os.path.ismount(mount_path):
        LOG.info(_LI("Mount path {0} is already mounted").format(mount_path))
        return False, response.create_success_response()
    return True, mount_path


def validate_mount_device(params):
    mount_device = params.get('kubernetes.io/mountdevicePath', None)
    if not os.path.exists(mount_device):
        return log_error("Mount device {0} is not exists.".format(mount_device))
    return True, mount_device


def log_error(msg):
    message = _LE(msg)
    return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
