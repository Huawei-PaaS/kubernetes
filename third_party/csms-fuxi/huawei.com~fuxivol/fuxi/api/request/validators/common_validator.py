import os

from api.response import response
from common.config import CONF
from common.constants import consts
from common.i18n import _LE, _LI
from oslo_log import log as logging

LOG = logging.getLogger(__name__, 'fuxi')


def validate_namespace(params):
    if CONF.provider_type == 'storage_manager':
        namespace = params.get('kubernetes.io/namespace', CONF.storage_manager.namespace)
        if not namespace:
            return log_error("Params name_space is none.")
    else:
        namespace = None
    return True, namespace


def validate_manage_namespace(params):
    namespace = params.get('kubernetes.io/namespace', None)
    if not namespace:
        return log_error("Params name_space is none.")
    return True, namespace


def validate_pod_namespace(params):
    pod_namespace = params.get('kubernetes.io/pod.namespace', None)
    if not pod_namespace:
        return log_error("Params pod_name_space is none.")
    return True, pod_namespace


def validate_device_path(device_path):
    if not os.path.exists(device_path):
        return log_error("Device path {0} is not exists.".format(device_path))
    return True, device_path


def validate_mount_device(params):
    mount_device = params.get('kubernetes.io/mountdevicePath', None)
    if not os.path.exists(mount_device):
        return log_error("Mount device {0} is not exists.".format(mount_device))
    return True, mount_device


def validate_mount_path(mount_path):
    if not os.path.exists(mount_path):
        LOG.info(_LI("Mount path {0} is not exists!").format(mount_path))
        return False, response.create_success_response()
    if not os.path.ismount(mount_path):
        LOG.info(_LI("Mount path {0} is not a mount path.").format(mount_path))
        return False, response.create_success_response()
    return True, mount_path


def validate_time_out(params):
    time_out = params.get('kubernetes.io/timeout', None)
    if not time_out:
        time_out = CONF.monitor_state_timeout
    try:
        int(time_out)
        return True, time_out
    except ValueError as e:
        LOG.exception(e.message)
        return log_error("Time out can not covert to int type!")


def log_error(msg):
    message = _LE(msg)
    return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
