import os

from clients.storage_manager import storage_manager_client
from common.constants import consts
from controllers import controller, nfsdevice
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StorageManagerVMController(controller.Controller):
    def __init__(self):
        super(StorageManagerVMController, self).__init__()
        self.storage_manager_client = storage_manager_client.StorageManagerClient()
        pass

    def mount(self, mount_path, dm_dev, option_key_mount_options):
        mount_point, msg, ret_code = controller.create_mount_point_if_not_exist(mount_path)
        if not mount_point:
            return mount_point, msg, ret_code

        mount_point, message = nfsdevice.do_mount(dm_dev, mount_point)
        if option_key_mount_options:
            real_mount_point = os.path.realpath(mount_point)
            controller.change_mount_point_owner(real_mount_point, option_key_mount_options)
        if mount_point is not None:
            return mount_point, message, consts.MOUNT_OK
        else:
            return mount_point, message, consts.MOUNT_ERROR

    def unmount(self, mount_path):
        return nfsdevice.do_unmount(mount_path)
