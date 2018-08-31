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
from oslo_concurrency import processutils
from oslo_utils import excutils

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Controller(object):
    def __init__(self):
        pass

    @abc.abstractmethod
    def mount(self, mount_path, dm_dev, option_key_mount_options):
        pass

    @abc.abstractmethod
    def unmount(self, mount_path):
        pass

def create_mount_point_if_not_exist(mount_path):
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

def change_mount_point_owner(mount_point, option_key_mount_options):
    dir_mode, uid, gid = resovle_mount_options(option_key_mount_options)
    change_owner(mount_point, uid, gid)
    change_dir_mode(mount_point, dir_mode)
    LOG.info("change the mount point owner and dir_mode finished")


def resovle_mount_options(option_key_mount_options):
    mount_option_value = option_key_mount_options.split(",")
    dic = {}
    for tmp in mount_option_value:
        key, value = tmp.split("=")
        dic.update({key.strip(): value.strip()})
    LOG.info(dic)

    return dic["dir_mode"], dic["uid"], dic["gid"]


def change_owner(mount_point, uid, gid):
    try:
        owner = uid + ":" + gid
        processutils.execute('chown', '-R', owner, mount_point, run_as_root=True)
        msg = _LI("Succeed to chown {0} mount_point as {1}").format(mount_point, uid)
        LOG.info(msg)
    except processutils.ProcessExecutionError as e:
        LOG.exception(e.message)
        with excutils.save_and_reraise_exception():
            msg = _LE("Unexpected error while chown mount_point. "
                      "uid: {0}, "
                      "mount_point: {1}"
                      "Error: {2}").format(uid, mount_point, e)
            LOG.error(msg)


def change_dir_mode(mount_point, dir_mode):
    try:
        processutils.execute('chmod', '-R', dir_mode, mount_point, run_as_root=True)
        msg = _LI("Succeed to chmod {0} fs type as {1}").format(mount_point, dir_mode)
        LOG.info(msg)
    except processutils.ProcessExecutionError as e:
        LOG.exception(e.message)
        with excutils.save_and_reraise_exception():
            msg = _LE("Unexpected error while make filesystem. "
                      "Devpath: {0}, "
                      "Fstype: {1}"
                      "Error: {2}").format(mount_point, dir_mode, e)
            LOG.error(msg)
