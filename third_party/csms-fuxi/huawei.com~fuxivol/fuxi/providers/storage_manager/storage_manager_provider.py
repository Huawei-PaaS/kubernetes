# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from common import config
from controllers.storage_manager.physical_machine import sm_pm_controller
from controllers.storage_manager.virtual_machine import sm_vm_controller
from managers.storage_manager import storage_manager
from oslo_log import log as logging
from providers import provider

LOG = logging.getLogger(__name__)


class StorageManagerProvider(provider.Provider):
    def __init__(self):
        super(StorageManagerProvider, self).__init__()
        if "vm" == config.CONF.get("host_machine_type"):
            self.controller = sm_vm_controller.StorageManagerVMController()
        else:
            self.controller = sm_pm_controller.StorageManagerPMController()

        self.manager = storage_manager.StorageManager()

    def create(self, namespace, volume_opts):
        return self.manager.create(namespace, volume_opts)

    def delete(self, namespace, volume_id, params):
        return self.manager.delete(namespace, volume_id, params)

    def attach(self, namespace, volume_id, volume_opts):
        return self.controller.attach(namespace, volume_id, volume_opts)

    def detach(self, namespace, volume_name, node_name, volume_opts):
        return self.controller.detach(namespace, volume_name, node_name, volume_opts)

    def mount_bind(self, namespace, volume_id, mount_path, fs_type, rw_mode, part_dir, option_key_mount_options):
        return self.controller.mount_bind(namespace, volume_id, mount_path, fs_type, rw_mode, part_dir,
                                          option_key_mount_options)

    def mount(self, namespace, volume_id, mount_path, fs_type, rw_mode):
        return self.controller.mount(namespace, volume_id, mount_path, fs_type, rw_mode)

    def unmount(self, namespace, mount_path):
        return self.controller.unmount(namespace, mount_path)

    def unmountdevice(self, deviceMountPath):
        return self.controller.unmountdevice(deviceMountPath)

    def expand(self, namespace, volume_id, size):
        return self.manager.expand(namespace, volume_id, size)

    def getvolumelimitinfo(self):
        return self.controller.getvolumelimitinfo()

    def getvolumelimitkey(self, disk_mode, volume_name):
        return self.controller.getvolumelimitkey(disk_mode, volume_name)
