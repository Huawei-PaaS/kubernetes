import os
from common.constants import consts
from controllers import controller, blockdevice
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def get_dev_by_volume(volume_id):
    link_path = os.path.join(consts.VOLUME_LINK_DIR, volume_id)
    dev_path = os.path.realpath(link_path)
    return dev_path


def get_dev_by_link_path(link_path):
    return controller._check_before_get_dev_by_link_path(link_path)


def get_link_path_by_volume(volume_id):
    return controller._check_before_get_link_path_by_volume(volume_id)


def get_mount_point_by_link_path(link_path):
    return controller._check_before_get_mount_point_by_link_path(link_path)
