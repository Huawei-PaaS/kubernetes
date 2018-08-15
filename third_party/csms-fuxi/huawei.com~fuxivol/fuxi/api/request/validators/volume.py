from common_validator import validate_manage_namespace, log_error

from oslo_log import log as logging
from common.constants.consts import AM_RWO, AM_ROX, AM_RWX

LOG = logging.getLogger(__name__, 'fuxi')
WHITE_SPACE = ' '


def validate_create_volume_params(params):
    ok, result = validate_manage_namespace(params)
    if not ok:
        return ok, result

    ok, result = validate_volume_name(params)
    if not ok:
        return ok, result

    ok, result = validate_volume_size(params)
    if not ok:
        return ok, result
    return True, None


def validate_volume_size(params):
    volume_size = params.get('kubernetes.io/size', None)
    if not volume_size:
        return log_error("volume_size is none.")
    try:
        int(volume_size)
        return True, volume_size
    except ValueError as e:
        LOG.exception(e.message)
        return log_error("Volume size can not covert to int type!")


def validate_size(size):
    try:
        int(size)
        return True, size
    except ValueError as e:
        LOG.exception(e.message)
        return log_error("Volume size can not covert to int type!")


def validate_volume_name(params):
    volume_name = params.get('kubernetes.io/name', None)
    if not volume_name:
        return log_error("volume_name is none.")
    if volume_name.isspace():
        return log_error("volume_name is Invalid")
    if volume_name.strip().find(WHITE_SPACE) != -1:
        return log_error("volume_name can not contain white space ")
    return True, volume_name.strip()


def validate_volume_id(params):
    volume_id = params.get('volumeID', None)
    if not volume_id:
        return log_error("volume_id is not given.")
    return True, volume_id


def validate_file_system_type(params):
    file_system_type = params.get('kubernetes.io/fsType', None)
    if not file_system_type:
        return log_error("File system type is not given.")
    if file_system_type not in ["ext3", "ext4"]:
        return log_error("File system type {0} is not support".format(file_system_type))
    return True, file_system_type


def validate_access_mode(params):
    access_mode = params.get('kubernetes.io/accessmode', None)

    if access_mode and access_mode not in [AM_RWO, AM_ROX, AM_RWX]:
        return log_error("Access mode  {0} is not support".format(access_mode))
    return True, access_mode


def validate_passthrough(params):
    metadata = params.get('kubernetes.io/hw:passthrough', None)
    if metadata is None:
        params.update({'kubernetes.io/hw:passthrough': 'false'})
        return True, None
    return True, None


def validate_readwrite_mode(params):
    readwrite_mode = params.get('kubernetes.io/readwrite', None)
    if not readwrite_mode:
        return log_error("Readwrite mode  is not given.")
    if readwrite_mode not in ["rw", "ro"]:
        return log_error("Readwrite mode  {0} is not support".format(readwrite_mode))
    return True, readwrite_mode


def validate_volume_pod_uid(params):
    volume_pod_uid = params.get('kubernetes.io/pod.uid', None)
    if not volume_pod_uid:
        return log_error("volume_pod_uid is not given.")
    return True, volume_pod_uid


def validate_mount_options(params):
    option_key_mount_options = params.get('kubernetes.io/mountoptions', None)
    return True, option_key_mount_options


def validate_volume_name_for_volumelimit(params):
    volume_name = params.get('kubernetes.io/pvOrVolumeName', None)
    if not volume_name:
        return log_error("Params kubernetes.io/pvOrVolumeName is none.")
    return True, volume_name


def validate_disk_mode(params):
    disk_mode = params.get('disk-mode', None)
    if not disk_mode:
        return log_error("Params disk-mode is none.")
    return True, disk_mode
