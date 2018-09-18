from clients.storage_manager import storage_manager_client
from common.constants import consts
from controllers import controller, efsdevice
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StorageManagerVMController(controller.Controller):
    def __init__(self):
        super(StorageManagerVMController, self).__init__()
        self.storage_manager_client = storage_manager_client.StorageManagerClient()
        pass

    def mount(self, mount_path, dm_dev, share_proto):
        mount_point, msg, ret_code = self.create_mount_point_if_not_exist(mount_path)
        if not mount_point:
            return mount_point, msg, ret_code

        mount_point, message = efsdevice.do_mount(dm_dev, mount_point, share_proto)
        if mount_point is not None:
            return mount_point, message, consts.MOUNT_OK
        else:
            return mount_point, message, consts.MOUNT_ERROR

    def unmount(self, mount_path):
        return efsdevice.do_unmount(mount_path)
