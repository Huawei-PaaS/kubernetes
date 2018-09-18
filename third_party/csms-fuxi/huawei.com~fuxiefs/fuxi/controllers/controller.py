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

import os
import abc
import six

from common.i18n import _LI, _LE
from common.constants import consts
from clients import utils
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Controller(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def mount(self, mount_path, dm_dev, share_proto):
        pass

    @abc.abstractmethod
    def unmount(self, mount_path):
        pass

    def create_mount_point_if_not_exist(self, mount_path):
        if not os.path.exists(mount_path):
            msg = _LI("The mount path not exists and create it.")
            LOG.info(msg)

        mount_point = mount_path
        if not os.path.exists(mount_point) or not os.path.isdir(mount_point):
            try:
                utils.execute('mkdir', '-p', '-m=755', mount_point,
                              run_as_root=True)
            except Exception as ex:
                LOG.exception(ex.message)
                msg = _LE("Failed to create mount path {0}.ex: {1}").format(mount_point, ex)
                LOG.error(msg)
                return None, msg, consts.MOUNT_ERROR
        return mount_point, None, consts.VOLUME_NO_STATUS
