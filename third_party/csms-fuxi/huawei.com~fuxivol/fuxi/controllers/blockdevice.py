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
import fcntl
import psutil

from common.i18n import _LI, _LE
from common.config import CONF
from common.utils import exec_cmd
from oslo_log import log as logging
from oslo_concurrency import processutils
from oslo_utils import excutils

LOG = logging.getLogger(__name__)


class Partition(object):
    def __init__(self, device, mountpoint, fstype, opts):
        self.device = device
        self.mountpoint = mountpoint
        self.fstype = fstype
        self.opts = opts

    def __repr__(self, *args, **kwargs):
        return str(self.__dict__)


class BlockerDeviceManager(object):
    def make_filesystem(self, devpath, fstype):
        try:
            processutils.execute('mkfs', '-t', fstype, '-F', devpath, run_as_root=True)
            msg = _LI("Succeed to mkfs {0} fs type as {1}").format(devpath, fstype)
            LOG.info(msg)
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            with excutils.save_and_reraise_exception():
                msg = _LE("Unexpected error while make filesystem. "
                          "Devpath: {0}, "
                          "Fstype: {1}"
                          "Error: {2}").format(devpath, fstype, e)
                LOG.error(msg)

    def mount_bind(self, mount_point, part_dir, fs_type):
        try:
            processutils.execute('mount', '--bind', mount_point, part_dir, run_as_root=True)
            msg = _LI("Succeed to mount --bind the {0} and {1}").format(part_dir, mount_point)
            LOG.info(msg)
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            with excutils.save_and_reraise_exception():
                msg = _LE("Unexpected error while mount block device. "
                          "part_dir: {0}, "
                          "mount_point: {1} "
                          "fs_type: {2}, "
                          "error: {3}").format(part_dir,
                                               mount_point,
                                               fs_type,
                                               e)
                LOG.error(msg)

    def mount(self, dev_path, mount_point, fs_type, rw_mode):
        try:
            processutils.execute('mount', '-o', rw_mode, dev_path, mount_point, run_as_root=True)
            processutils.execute('resize2fs', dev_path, run_as_root=True)
            msg = _LI("Succeed to mount the {0} to {1} as mode {2}").format(dev_path, mount_point, rw_mode)
            LOG.info(msg)
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            with excutils.save_and_reraise_exception():
                msg = _LE("Unexpected error while mount block device. "
                          "dev_path: {0}, "
                          "mount_point: {1} "
                          "fs_type: {2}, "
                          "error: {3}").format(dev_path,
                                               mount_point,
                                               fs_type,
                                               e)
                LOG.error(msg)

    def unmount(self, mount_point):
        if CONF.provider_type == 'storage_manager':
            lock_file = CONF.storage_manager.lock_path + '.unmount'
            try:
                if not os.path.exists(lock_file):
                    msg = _LE("Unmount lock is not exists!")
                    LOG.error(msg)
                    return
            except Exception as ex:
                msg = _LE("Unexpected err while check unmount lock. "
                          "Error: {0}").format(ex)
                LOG.error(msg)
                return

            with open(lock_file, 'w') as lockfile:
                fcntl.flock(lockfile, fcntl.LOCK_EX)
                try:
                    processutils.execute('umount', mount_point, run_as_root=True)
                except processutils.ProcessExecutionError as e:
                    LOG.exception(e.message)
                    with excutils.save_and_reraise_exception():
                        msg = _LE("Unexpected err while unmount block device. "
                                  "Mount Point: {0}, "
                                  "Error: {1}").format(mount_point, e)
                        LOG.error(msg)
                finally:
                    fcntl.flock(lockfile, fcntl.LOCK_UN)
        else:
            try:
                processutils.execute('umount', mount_point, run_as_root=True)
            except Exception as e:
                with excutils.save_and_reraise_exception():
                    msg = _LE("Unexpected err while unmount block device. "
                              "Mount Point: {0}, "
                              "Error: {1}").format(mount_point, e)
                    LOG.error(msg)

    def get_mounts(self):
        mounts = psutil.disk_partitions()
        return [Partition(mount.device, mount.mountpoint,
                          mount.fstype, mount.opts) for mount in mounts]

    # Detects the fs type and the partition table type of the given block device,
    # returns the fstype or pttype (string), and error message (None | string).
    #
    def get_disk_format(self, devpath):
        cmd = "blkid -p -s TYPE -s PTTYPE -o export %s" % (devpath)
        # the status code will not be 0 (perhaps 512 in python), when the disk is raw without any fs
        # as well as real error occurs, but the output is always meaningful.
        _, outputs = exec_cmd.exec_shell_cmd_with_raw_resp(cmd, 5)
        if len(outputs) == 0:
            LOG.info("Detect %s is raw without any fs" % devpath)
            return "raw", None

        fstype = ""
        pttype = ""
        output_lines = outputs.splitlines()
        for line in output_lines:
            if len(line) <= 0:
                continue
            items = line.split("=")
            if len(items) != 2:
                return "", "blkid returns invalid output: %s" % outputs

            # TYPE is filesystem type, and PTTYPE is partition table type, according
            # to https://www.kernel.org/pub/linux/utils/util-linux/v2.21/libblkid-docs/.
            if items[0] == "TYPE":
                fstype = items[1]
            elif items[0] == "PTTYPE":
                pttype = items[1]

        if len(pttype) > 0:
            msg = "detect %s with partition table type: %s" % (devpath, pttype)
            LOG.info(msg)
            return "partition table type=%s" % pttype, None

        return fstype, None

    # judges the given device has supported fstype, and returns accordingly (bool, detail_msg):
    # * detects supported fstype, returns True, fstype
    # * detects unsupported fstype, returns False, detail message
    #
    def has_supported_fstype(self, devpath):
        fstype, err_msg = self.get_disk_format(devpath)
        if err_msg != None:
            return False, err_msg
        if fstype == "ext4" or fstype == "raw":
            return True, fstype
        else:
            return False, "unsupported fstype: %s" % fstype



def get_dev_mountpoints(devpath):
    partitions = psutil.disk_partitions()
    res = []
    for p in partitions:
        if p.device == devpath:
            res.append(p.mountpoint)
    return res


def _check_already_mount(devpath, mountpoint):
    partitions = BlockerDeviceManager().get_mounts()
    for p in partitions:
        if devpath == p.device and mountpoint == p.mountpoint:
            return True
    return False


def do_mount_bind(mountpoint, fstype, part_dir):
    bdm = BlockerDeviceManager()
    try:
        bdm.mount_bind(mountpoint, part_dir, fstype)
    except processutils.ProcessExecutionError as e:
        LOG.exception(e.message)
    return mountpoint


def do_mount(devpath, mountpoint, fstype, rw_mode):
    if not _check_already_mount(devpath, mountpoint):
        bdm = BlockerDeviceManager()
        try:
            supported_fstype, detailed_msg = bdm.has_supported_fstype(devpath)
            if supported_fstype:
                # Only make fs for raw disk without any fs
                if detailed_msg == "raw":
                    LOG.info("try to mkfs for raw disk %s" % devpath)
                    bdm.make_filesystem(devpath, fstype)
                bdm.mount(devpath, mountpoint, fstype, rw_mode)
            else:
                # Deny to mount for disk with unsupported fstype or partition
                return mountpoint, detailed_msg
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            bdm.mount(devpath, mountpoint, fstype, rw_mode)
    return mountpoint, None


def do_unmount(mount_point):
    BlockerDeviceManager().unmount(mount_point)
