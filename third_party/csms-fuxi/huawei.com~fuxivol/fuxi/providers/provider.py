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

import abc
import six

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Provider(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def create(self, namespace, volume_opts):
        pass

    @abc.abstractmethod
    def delete(self, namespace, volume_id, params):
        pass

    @abc.abstractmethod
    def attach(self, namespace, volume_id, volume_opts):
        pass

    @abc.abstractmethod
    def detach(self, namespace, volume_name, node_name, volume_opts):
        pass

    @abc.abstractmethod
    def mount_bind(self, namespace, volume_id, mount_path, fs_type, rw_mode, part_dir, option_key_mount_options):
        pass

    @abc.abstractmethod
    def mount(self, namespace, volume_id, mount_path, fs_type, rw_mode):
        pass

    @abc.abstractmethod
    def unmount(self, namespace, mount_path):
        pass

    @abc.abstractmethod
    def unmountdevice(self, deviceMountPath):
        pass

    @abc.abstractmethod
    def expand(self, namespace, volume_id, size):
        pass

    @abc.abstractmethod
    def getvolumelimitinfo(self):
        pass

    @abc.abstractmethod
    def getvolumelimitkey(self, disk_mode, volume_name):
        pass