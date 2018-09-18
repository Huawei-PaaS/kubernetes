from common_validator import validate_manage_namespace

from api.response import response
from oslo_log import log as logging
from common.constants import consts
from common.i18n import _LE
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
        message = _LE("volume_size is none.")
        response.create_error_response(message, consts.GET_PARAMS_FAILED)
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    try:
        size = int(volume_size)
        if size < 100:
            message = _LE("volume_size is {0}.".format(size))
            response.create_error_response(message, consts.GET_PARAMS_FAILED)
            return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
        return True, volume_size
    except ValueError as e:
        LOG.exception(e.message)
        message = _LE("Volume size can not covert to int type!")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)


def validate_size(size):
    try:
        int(size)
        return True, size
    except ValueError as e:
        LOG.exception(e.message)
        message = _LE("Volume size can not convert to int type!")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)


def validate_volume_name(params):
    volume_name = params.get('kubernetes.io/name', None)
    if not volume_name:
        message = _LE("volume_name is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    if volume_name.isspace():
        message = _LE("volume_name is Invalid")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    if volume_name.strip().find(WHITE_SPACE) != -1:
        message = _LE("volume_name can not contain white space ")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, volume_name.strip()


def validate_volume_id(params):
    volume_id = params.get('volumeID', None)
    if not volume_id:
        message = _LE("volume_id is not given.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, volume_id


def validate_file_system_type(params):
    file_system_type = params.get('kubernetes.io/fsType', None)
    if not file_system_type:
        message = _LE("File system type is not given.")
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    if file_system_type not in ["ext3", "ext4", "efs", "cifs"]:
        message = _LE("File system type {0} is not support").format(file_system_type)
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    return True, file_system_type


def validate_storage_type(params):
    storage_type = params.get("kubernetes.io/storagetype", "EFS")
    if storage_type.strip() not in ('EFS', 'efs'):
        message = _LE("Storage type {0} is not support").format(storage_type)
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    return True, storage_type


def validate_access_mode(params):
    access_mode = params.get('kubernetes.io/accessmode', None)

    if access_mode and access_mode not in [AM_RWO, AM_ROX, AM_RWX]:
        message = _LE("Access mode  {0} is not support").format(access_mode)
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    return True, access_mode


def validate_readwrite_mode(params):
    readwrite_mode = params.get('kubernetes.io/readwrite', None)
    if not readwrite_mode:
        message = _LE("Readwrite mode  is not given.")
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    if readwrite_mode not in ["rw", "ro"]:
        message = _LE("Readwrite mode  {0} is not support").format(readwrite_mode)
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    return True, readwrite_mode


def validate_volume_pod_uid(params):
    volume_pod_uid = params.get('kubernetes.io/pod.uid', None)
    if not volume_pod_uid:
        message = _LE("volume_pod_uid is not given.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, volume_pod_uid


def validate_mount_path(mount_path):
    return True


def validate_fs_type(fs_type):
    return True


def validate_dev_path(dev_path):
    return True


def validate_share_proto(params):
    share_proto = params.get('kubernetes.io/shareproto', None)

    if not share_proto:
        message = _LE("Params shareproto is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, share_proto


def validate_access_to(params):
    access_to = params.get('kubernetes.io/accessto', None)

    if not access_to:
        message = _LE("Params accessto is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, access_to


def validate_access_level(params):
    access_level = params.get('kubernetes.io/accesslevel', None)

    if not access_level:
        message = _LE("Params accesslevel is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    if access_level not in ["rw", "ro"]:
        message = _LE("accesslevel {0} is not support").format(access_level)
        return False, response.common_error_response(message, consts.GET_PARAMS_FAILED)
    return True, access_level


def validate_vpcid(params):
    vpcid = params.get('kubernetes.io/vpcid', None)
    if not vpcid:
        message = _LE("Params vpcid is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, vpcid


def validate_netid(params):
    netid = params.get('kubernetes.io/netid', None)
    if not netid:
        message = _LE("Params netid is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, netid


def validate_securitygroupid(params):
    securitygroupid = params.get('kubernetes.io/securitygroupid', None)
    if not securitygroupid:
        message = _LE("Params securitygroupid is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, securitygroupid


def validate_volume_type(params):
    volumetype = params.get('kubernetes.io/volumetype', None)
    if not volumetype or volumetype not in ("COMMON", "HIGH", "ULTRAHIGH"):
        message = _LE("Params volumetype is not support.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, volumetype


def validate_availability_zone(params):
    zone = params.get('kubernetes.io/zone', None)
    if not zone:
        message = _LE("Params zone is none.")
        return False, response.create_error_response(message, consts.GET_PARAMS_FAILED)
    return True, zone
