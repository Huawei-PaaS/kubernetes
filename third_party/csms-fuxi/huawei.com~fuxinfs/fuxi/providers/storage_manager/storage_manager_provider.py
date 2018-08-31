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

    def delete(self, namespace, volume_id, storage_type, params):
        return self.manager.delete(namespace, volume_id, storage_type, params)

    def mount(self, mount_path, dm_dev, option_key_mount_options):
        return self.controller.mount(mount_path, dm_dev, option_key_mount_options)

    def unmount(self, mount_path):
        return self.controller.unmount(mount_path)

    def expand(self, namespace, volume_id, size):
        return self.manager.expand(namespace, volume_id, size)