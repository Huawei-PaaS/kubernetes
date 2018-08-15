import os
import stat
from vm_volume_util import search_dir, get_device, get_real_path
from common.constants import consts
from common.i18n import _LW, _LE

from oslo_log import log as logging
from controllers import controller, blockdevice

LOG = logging.getLogger(__name__)


def get_dev_by_volume(volume_id):
    devices = os.listdir(consts.VOLUME_LINK_DIR)
    virtual_path = None
    for dev in devices:
        if (volume_id[0:20] in dev) and (volume_id not in dev):
            virtual_path = consts.VOLUME_LINK_DIR + dev
            msg = "Find matched device {0}".format(virtual_path)
            LOG.info(msg)
            break
    if not virtual_path:
        LOG.warning(_LW("Could not find matched device."))
        return None
    dev_path = os.path.realpath(virtual_path)
    return dev_path


def get_device_path(volume_id):
    dm_dev = os.path.realpath(consts.VOLUME_LINK_DIR + volume_id)
    try:
        if stat.S_ISBLK(os.stat(dm_dev)[stat.ST_MODE]):
            return dm_dev
        else:
            return None
    except OSError as e:
        msg = "Failed to get device path. message: {0}".format(e)
        LOG.info(msg)
        return None


def get_xendev_by_vloume(volume, server_id):
    temp_dev_lst = []
    try:
        dev_lst = get_device(volume, server_id)
        for item in dev_lst:
            temp_dev_lst.extend(search_dir(item))
        real_path = get_real_path(temp_dev_lst)
        msg = "Find matched device {0}".format(real_path)
        LOG.info(msg)
        if real_path is not None and real_path.find("xvd") == -1:
            return None
        return real_path
    except OSError as ex:
        LOG.exception(ex.message)
        msg = "Failed to get device path. Error: {0}".format(ex)
        LOG.error(_LE(msg))
        return None


def get_dev_by_link_path(link_path):
    return controller._check_before_get_dev_by_link_path(link_path)


def get_link_path_by_volume(volume_id):
    return controller._check_before_get_link_path_by_volume(volume_id)


def get_mount_point_by_link_path(link_path):
    return controller._check_before_get_mount_point_by_link_path(link_path)
