from clients.storage_manager import storage_manager_client
from common.constants import consts
from controllers import controller, efsdevice
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StorageManagerPMController(controller.Controller):
    def __init__(self):
        super(StorageManagerPMController, self).__init__()
        self.host_ip = consts.DEFAULT_ADDRESS
        self.storage_manager_client = storage_manager_client.StorageManagerClient()

    def mount(self, mount_path, dm_dev):
        mount_point, msg, ret_code = self.create_mount_point_if_not_exist(mount_path)
        if not mount_point:
            return None, msg, ret_code

        efsdevice.do_mount(dm_dev, mount_point)

        return mount_point, None, consts.MOUNT_OK

    def unmount(self, mount_path):
        return efsdevice.do_unmount(mount_path)
