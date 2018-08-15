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
import json
import six
import os

from clients import utils
from oslo_log import log as logging
from common.constants import consts
from common.constants import volume_status
from common.i18n import _LE, _LI, _LW
from common.config import CONF
from common import config
from common.utils import exec_cmd
from controllers import blockdevice
from oslo_concurrency import processutils
from oslo_utils import excutils

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Controller(object):
    def __init__(self):
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
    def getvolumelimitinfo(self):
        pass

    def getvolumelimitkey(self, disk_mode, volume_name):
        volume_limit_key, err = self._get_volumelimitkey_with_diskmode(disk_mode)
        if err != None:
            LOG.info("Failed to get volume limit key with disk_mode {0}, then try with volume_name".format(err))
            return self._get_volumelimitkey_with_volumename(volume_name)
        return volume_limit_key, None

    """
        _get_host_disk_limit get the disk limit specifications for current host.
        If there is '../../etc/fuxi.conf' with well-defined key-value pairs, just reads and returns:
            a dict with the corresponding contents of section 'host_disk_limit' in it, and None indicating no error message
        If the key-value pairs in '../../etc/fuxi.conf' are not valid or haven't been refreshed, it will: 
            * call 'servers/' + server_id + '/block_device?host_src=$host_src' to get the latest block device status;
            * parse the information of max_total_disk_num, max_vbd_disk_num and max_scsi_disk_num
            * construct a dict to hold the corresponding key-value pairs
            * rewrite the dict into '../../etc/fuxi.conf' 
            a dict with the corresponding refreshed contents of section 'host_disk_limit' will be returned, as well as 
                None indicating no error message. 
            None and a string error message if error occurs in the above steps.
    """

    def _get_host_disk_limit_spec(self, host_src):
        if not os.path.exists(config.CONF_FILE):
            return None, "Can't find %s" % (config.CONF_FILE)

        is_initialized = config.get(config.HOST_DISK_LIMIT_SECTION, config.IS_INITIALIZED_KEY, default=None)
        if is_initialized == 'False':
            try:
                server_id = utils.get_server_id()
                if not server_id:
                    err_msg = "Fail to get server id for current host"
                    LOG.error(err_msg)
                    return None, err_msg
                else:
                    attached_volume_spec = self.storage_manager_client.get_attached_volume_spec_from_host(
                        server_id,
                        host_src)
                    LOG.info(
                        "Get attached disk info for host (service_id={0}): {1}".format(server_id, attached_volume_spec))
                    max_total_disk_num, max_vbd_disk_num, max_scsi_disk_num = self._parse_host_attached_disk_spec(
                        attached_volume_spec)
                    config.modify(config.HOST_DISK_LIMIT_SECTION, config.IS_INITIALIZED_KEY, 'True')
                    config.modify(config.HOST_DISK_LIMIT_SECTION, config.MAX_TOTAL_DISK_NUM_KEY, max_total_disk_num)
                    config.modify(config.HOST_DISK_LIMIT_SECTION, config.MAX_VBD_DISK_NUM_KEY, max_vbd_disk_num)
                    config.modify(config.HOST_DISK_LIMIT_SECTION, config.MAX_SCSI_DISK_NUM_KEY, max_scsi_disk_num)
                    updated_options = {
                        config.MAX_TOTAL_DISK_NUM_KEY: max_total_disk_num,
                        config.MAX_VBD_DISK_NUM_KEY: max_vbd_disk_num,
                        config.MAX_SCSI_DISK_NUM_KEY: max_scsi_disk_num
                    }
                    return updated_options, None
            except Exception as e:
                err_msg = ("Get attached disk info for host failed: {0}").format(e)
                LOG.error(err_msg)
                return None, err_msg
        else:
            options = {
                config.MAX_TOTAL_DISK_NUM_KEY: int(CONF.host_disk_limit.max_total_disk_num),
                config.MAX_VBD_DISK_NUM_KEY: int(CONF.host_disk_limit.max_vbd_disk_num),
                config.MAX_SCSI_DISK_NUM_KEY: int(CONF.host_disk_limit.max_scsi_disk_num),
            }
            LOG.debug("Get volume limit spec from config :{0}".format(options))
            return options, None

    def _parse_host_attached_disk_spec(self, host_attached_disk_spec):
        origin_total_disk = host_attached_disk_spec["total_disk_num"]
        origin_total_vbd = host_attached_disk_spec["total_vbd_num"]
        origin_total_scsi = host_attached_disk_spec["total_scsi_num"]
        return origin_total_disk, origin_total_vbd, origin_total_scsi

    def _get_volumelimitkey_with_volumename(self, volume_name):
        fuxivol_pv_disk, err_msg = self._query_mounted_fuxivol_pv_disk(volume_name, consts.SCSI_DISK_DEVICE_NAME_PREFIX)
        if err_msg != None:
            if self._supports_vbd():
                fuxivol_pv_disk, err_msg = self._query_mounted_fuxivol_pv_disk(volume_name,
                                                                               consts.VBD_DISK_DEVICE_NAME_PREFIX)
                if err_msg != None:
                    LOG.info("volume {0} is not VBD: {1}".format(volume_name, err_msg))
                    return None, err_msg
                return consts.HC_VBD_MODE_DISK_VOLUME_LIMIT_KEY, None
            else:
                return None, err_msg
        return consts.HC_SCSI_MODE_DISK_VOLUME_LIMIT_KEY, None

    @abc.abstractmethod
    def _supports_vbd(self):
        pass

    def _get_volumelimitkey_with_diskmode(self, disk_mode):
        disk_mode = str(disk_mode).upper()
        if disk_mode == consts.HC_DISK_MODE_VBD:
            return consts.HC_VBD_MODE_DISK_VOLUME_LIMIT_KEY, None
        elif disk_mode == consts.HC_DISK_MODE_SCSI:
            return consts.HC_SCSI_MODE_DISK_VOLUME_LIMIT_KEY, None
        else:
            error = _LE("Unknown disk_mode: {0}").format(disk_mode)
            LOG.error(error)
            return None, error

    """
    The kubelet supporting volumelimit of flexvolume will call getvolumelimitinfo() to get the attached disk limit information
    in the view of k8s.
    The default periodic calling time of kubelet is 20s, so the logging points should be less as much as possible to avoid logging flood for fuxivol.

    Maximum HC disk volumes in HC CCE ECS VM node used as attachable disk PV for Pods, its value is fixed to maximum disks number of the vm minus two
    (one for system, one for docker).
    ECS VM used in CCE can be divided into two types according to support/none-support six-volumes feature:
        * ECS X86 VM
            - none-support-six-volumes ECS VM:
                * default_max_hc_disk_volumes (22):  vbd&scsi_total(24)-os&docker_vbd(2)
                * default_max_hc_vbd_disk_volumes (22): vbd_total(24)-os&docker_vbd(2)
                * default_max_hc_scsi_disk_volumes (22): min{vbd&scsi_total(24)-os&docker_vbd(2), scsi_total(23)}
            - support-six-volumes ECS VM:
                * default_max_hc_disk_volumes (58):  vbd&scsi_total(60)-os&docker_vbd(2)
                * default_max_hc_vbd_disk_volumes (22): vbd_total(24)-os&docker_vbd(2)
                * default_max_hc_scsi_disk_volumes (58): min{vbd&scsi_total(60)-os&docker_vbd(2), scsi_total(59)}
        * ECS ARM VM (rc3/rc6/rm6)
            * default_max_hc_disk_volumes (22):  vbd&scsi_total(24)-os&docker_vbd(2)
            * default_max_hc_vbd_disk_volumes (22): vbd_total(24)-os&docker_vbd(2)
            * default_max_hc_scsi_disk_volumes (22): min{vbd&scsi_total(24)-os&docker_vbd(2), scsi_total(23)}

    Currently not all the ECS VM in all regions support six-volumes feature, and ECS has no explicit api to query the maximum disks specification.
    ECS only provides 'GET /v2.1/servers/{server_id}/block_device' api to present currently disk attachments and remaining total/vbd/scsi disks number,
    and this api may not be provided in all regions.

    So do the following steps to get the volume limit information response:
        1. Use the corresponding values for none-support-six-volumes scene as defaults.
        2. Query to get the latest maximum disk specification of hosted vm if needed and refresh if successful,
            if calling of this method is failed, and just logs and goes through to step3.
        3. Scan device names for vbd&scsi locally, identify the disks not used by fuxivol pv and minus the numbers from default_max_hc_vbd/scsi_disk_volumes
        4. Construct and return the volume limit info for the hosted vm.
    """

    def _get_volumelimitinfo_for_vm(self):
        # Step 1. Set default disk maximum number of ECS VM for flavours of KVM excluding D2/D3/I3
        max_total_disk_num = consts.DEFAULT_MAX_TOTAL_DISK_NUM_OF_ECS_VM
        max_vbd_disk_num = consts.DEFAULT_MAX_VBD_DISK_NUM_OF_ECS_VM
        max_scsi_disk_num = consts.DEFAULT_MAX_SCSI_DISK_NUM_OF_ECS_VM

        # Step 2. Query to get the latest maximum disk specification of hosted vm if needed and refresh if successful
        host_disk_limit_info, err_msg = self._get_host_disk_limit_spec(consts.HOST_SOURCE_ECS)
        if err_msg is None:
            max_total_disk_num = host_disk_limit_info[config.MAX_TOTAL_DISK_NUM_KEY]
            max_vbd_disk_num = host_disk_limit_info[config.MAX_VBD_DISK_NUM_KEY]
            max_scsi_disk_num = host_disk_limit_info[config.MAX_SCSI_DISK_NUM_KEY]
        else:
            LOG.error(
                "Failed to get disk specification of current host %s, so still use the default values for ecs vm" % (
                err_msg))

        total_fuxivolpv_used_vbd_num = 0
        total_fuxivolpv_used_scsi_num = 0
        total_used_vbd_num = 0
        total_used_scsi_num = 0

        # Step 3.1 Scan device names for vbd locally
        if max_vbd_disk_num != 0:
            LOG.debug("Start to scan vbd disks")
            total_fuxivolpv_used_vbd_vdx_num, total_used_vbd_vdx_num, find_vdx_block_err_msg = self._find_disk_num_info_for_target_prefix(
                consts.VBD_DISK_DEVICE_NAME_PREFIX, consts.VBD_DISK_BUS_NAME)
            if find_vdx_block_err_msg is None:
                LOG.debug("Find vbd disks numbers with device prefix %s: fuxivolpv used(%d), total used(%d)" % (
                    consts.VBD_DISK_DEVICE_NAME_PREFIX, total_fuxivolpv_used_vbd_vdx_num, total_used_vbd_vdx_num))
                total_fuxivolpv_used_vbd_num += total_fuxivolpv_used_vbd_vdx_num
                total_used_vbd_num += total_used_vbd_vdx_num
            else:
                LOG.error("Failed to get numbers of vbd disks with prefix %s: %s" % (
                    consts.VBD_DISK_DEVICE_NAME_PREFIX, find_vdx_block_err_msg))

            total_fuxivolpv_used_vbd_xvdx_num, total_used_vbd_xvdx_num, find_xvdx_block_err_msg = self._find_disk_num_info_for_target_prefix(
                consts.VBD_DISK_DEVICE_NAME_PREFIX_IN_XEN, None)
            if find_xvdx_block_err_msg is None:
                LOG.debug("Find vbd disks numbers with device prefix %s: fuxivolpv used(%d), total used(%d)" % (
                    consts.VBD_DISK_DEVICE_NAME_PREFIX_IN_XEN, total_fuxivolpv_used_vbd_xvdx_num,
                    total_used_vbd_xvdx_num))
                total_fuxivolpv_used_vbd_num += total_fuxivolpv_used_vbd_xvdx_num
                total_used_vbd_num += total_used_vbd_xvdx_num
            else:
                LOG.error("Failed to get number of vbd disks with prefix %s: %s" % (
                    consts.VBD_DISK_DEVICE_NAME_PREFIX_IN_XEN, find_xvdx_block_err_msg))

            if find_vdx_block_err_msg != None and find_xvdx_block_err_msg != None:
                LOG.info("Failed to get number of vbd disks and just count two vbd disk number for os & docker")
                total_used_vbd_num += consts.OS_DOCKER_USED_HC_DISK_NUM

        # Step 3.2 Scan device names for scsi locally
        if max_scsi_disk_num != 0:
            LOG.debug("Start to scan scsi disks")
            total_fuxivolpv_used_scsi_num, total_used_scsi_num, err_msg = self._find_disk_num_info_for_target_prefix(
                consts.SCSI_DISK_DEVICE_NAME_PREFIX, consts.SCSI_DISK_BUS_NAME)
            if err_msg is None:
                LOG.debug("Find scsi disks numbers with device prefix %s: fuxivolpv used(%d), total used(%d)" % (
                    consts.SCSI_DISK_DEVICE_NAME_PREFIX, total_fuxivolpv_used_scsi_num, total_used_scsi_num))
            else:
                LOG.error(
                    "Failed to get number of scsi disks with prefix %s: %s" % (consts.SCSI_DISK_BUS_NAME, err_msg))

        # Step 3.3 Calculate and prepare numbers for report
        total_used_disk_num = total_used_scsi_num + total_used_vbd_num
        total_unused_disk_num = max_total_disk_num - total_used_disk_num

        total_unused_vbd_num = min(max_vbd_disk_num - total_used_vbd_num, total_unused_disk_num)
        remain_vbd_disk_num_for_pod = total_fuxivolpv_used_vbd_num + total_unused_vbd_num

        total_unused_scsi_num = min(max_scsi_disk_num - total_used_scsi_num, total_unused_disk_num)
        remain_scsi_disk_num_for_pod = total_fuxivolpv_used_scsi_num + total_unused_scsi_num

        remain_total_disk_num_for_pod = total_fuxivolpv_used_scsi_num + total_fuxivolpv_used_vbd_num + total_unused_disk_num

        # Step 4.
        volume_limit_result = self._make_volume_limit_info(remain_total_disk_num_for_pod, remain_vbd_disk_num_for_pod,
                                                           remain_scsi_disk_num_for_pod)
        LOG.debug("Prepare volume limit info: {0}".format(volume_limit_result))
        return json.dumps(volume_limit_result)

    """
    The kubelet supporting volumelimit of flexvolume will call getvolumelimitinfo() to get the attached disk limit information
    in the view of k8s.
    The default periodic calling time of kubelet is 20s, so the logging points should be less as much as possible to avoid logging flood for fuxivol.

    Maximum HC disk volumes in HC CCE BMS PM node used as attachable disk PV for Pods, its value is fixed to maximum disks number of the PM minus two
    (one for system, one for docker).
    BMS PM used in CCE can be divided into two types according to the its CPU architecture:
        * BMS X86 PM
            - with SDI (now):
                * default_max_hc_disk_volumes (58):  scsi_total(60)-os&docker_scsi_most(2)
                * default_max_hc_scsi_disk_volumes (58): scsi_total(60)-os&docker_scsi_most(2)
            - without SDI (now):
                * default_max_hc_disk_volumes (0)
                * default_max_hc_scsi_disk_volumes (0)
        * BMS ARM PM:
            - with SDI (future): TODO make sure the specification
                * default_max_hc_disk_volumes (58):  scsi_total(60)-os&docker_scsi_most(2)
                * default_max_hc_scsi_disk_volumes (58): scsi_total(60)-os&docker_scsi_most(2)
            - without SDI (now):
                * default_max_hc_disk_volumes (0)
                * default_max_hc_scsi_disk_volumes (0)

    Currently not all the BMS PM in all regions support HC Disks, and BMS has no explicit api to query the maximum disks specification.
    The above specification of BMS X86 PM is just documented online, and there is no api to judge the given BMS PM has SDI or not.

    So do the following steps to get the volume limit information response:
        1. Use the corresponding values of BMS X86 PM with SDI as defaults.
        2. Query to get the latest maximum disk specification of hosted pm if needed and refresh if successful,
            if calling of this method is failed, and just logs and goes through to step3.
        3. Check the SDI driver locally according to the os release.
            * If there is no SDI driver so just set all the volume limits to 0 for now to return.
            * If SDI driver exists, then goes on
        4. Scan device names for scsi locally, identify the disks not used by fuxivol pv and minus the numbers from scsi_disk_volumes
        5. Construct and return the volume limit info for the hosted PM.
    """

    def _get_volumelimitinfo_for_bms(self):
        # Step 1. Set default disk maximum number of BMS X86 PM with SDI
        max_total_disk_num = consts.DEFAULT_MAX_TOTAL_DISK_NUM_OF_BMS_PM
        max_scsi_disk_num = consts.DEFAULT_MAX_SCSI_DISK_NUM_OF_BMS_PM

        # Step 2. Query to get the latest maximum disk specification of hosted pm if needed and refresh if successful
        host_disk_limit_info, err_msg = self._get_host_disk_limit_spec(consts.HOST_SOURCE_BMS)
        if err_msg is None:
            max_total_disk_num = host_disk_limit_info[config.MAX_TOTAL_DISK_NUM_KEY]
            max_scsi_disk_num = host_disk_limit_info[config.MAX_SCSI_DISK_NUM_KEY]
        else:
            LOG.error(
                "Failed to get disk specification of current host %s, so still use the default values for bms pm" % (
                err_msg))

        remain_total_disk_num_for_pod = consts.DEFAULT_ZERO_DISK_OF_BMS_PM
        remain_vbd_disk_num_for_pod = consts.DEFAULT_ZERO_DISK_OF_BMS_PM
        remain_scsi_disk_num_for_pod = consts.DEFAULT_ZERO_DISK_OF_BMS_PM

        if max_total_disk_num != 0:
            # Step 3. Check the SDI driver locally according to the os release
            is_sdi_driver_installed = self._check_installation_of_sdi_driver()
            if is_sdi_driver_installed:
                total_fuxivolpv_used_scsi_num = 0
                total_used_scsi_num = 0

                # Step 4.1 Scan device names for scsi locally
                LOG.debug("Start to scan scsi disks")
                total_fuxivolpv_used_scsi_num, total_used_scsi_num, err_msg = self._find_disk_num_info_for_target_prefix(
                    consts.SCSI_DISK_DEVICE_NAME_PREFIX, consts.SCSI_DISK_BUS_NAME)
                if err_msg is None:
                    LOG.info("Find scsi disks numbers with device prefix %s: fuxivolpv used(%d), total used(%d)" % (
                        consts.SCSI_DISK_DEVICE_NAME_PREFIX, total_fuxivolpv_used_scsi_num, total_used_scsi_num))
                else:
                    LOG.info(
                        "Failed to get number of vbd disks and just count two vbd disk number for os & docker: %s" % err_msg)
                    total_used_scsi_num += consts.OS_DOCKER_USED_HC_DISK_NUM

                # Step 4.2 Calculate and prepare numbers for report
                total_used_disk_num = total_used_scsi_num
                total_unused_disk_num = max_total_disk_num - total_used_disk_num
                total_unused_scsi_num = max_scsi_disk_num - total_used_scsi_num
                remain_scsi_disk_num_for_pod = total_fuxivolpv_used_scsi_num + total_unused_scsi_num
                remain_total_disk_num_for_pod = total_fuxivolpv_used_scsi_num + total_unused_disk_num
            else:
                LOG.info(
                    "The sdi driver has not been installed, set remain_scsi_disk_num_for_pod&remain_total_disk_num_for_pod to 0: {0}".format(
                        err_msg))
                remain_scsi_disk_num_for_pod = consts.DEFAULT_ZERO_DISK_OF_BMS_PM
                remain_total_disk_num_for_pod = consts.DEFAULT_ZERO_DISK_OF_BMS_PM

        # Step 5.
        volume_limit_result = self._make_volume_limit_info(remain_total_disk_num_for_pod, remain_vbd_disk_num_for_pod,
                                                           remain_scsi_disk_num_for_pod)
        LOG.debug("Prepare volume limit info: {0}".format(volume_limit_result))
        return json.dumps(volume_limit_result)

    def _check_installation_of_sdi_driver(self):
        # Check is EulerOS and checkout installation of scsi_ep_front
        if os.path.exists("/etc/euleros-release"):
            cmd = "rpm -qa | grep scsi_ep_front"
            sdi_driver, err_msg = exec_cmd.exec_shell_cmd(cmd, 5)
            if err_msg != None:
                LOG.error("Failed to query sdi driver {0}".format(err_msg))
                return False
            if len(sdi_driver) == 0 or sdi_driver[0] == "":
                LOG.info("There is no sdi driver")
                return False
            return True
        else:
            LOG.debug("Currently, CCE BMS PM node only supports EulerOS")
            return False

    def _check_before_attach(self, volume_id, volume, shareable, volume_attachment_state):
        state = volume_attachment_state
        if state in [volume_status.UNKNOWN, volume_status.WRONG_STATUS]:
            msg = "Volume state is in unknown or wrong status."
            LOG.error(msg)
            return volume_status.NOT_READY_TO_ATTACH, msg, consts.ATTACH_ERROR
        if state == volume_status.ALREADY_ATTACHED_TO_THIS_HOST:
            msg = "Volume is already attach to this host."
            LOG.info(msg)
            return volume_status.ALREADY_ATTACHED, msg, consts.ATTACH_OK
        if state == volume_status.ALREADY_ATTACHED_TO_OTHER_HOST and not shareable:
            msg = _LE(
                "The volume {0} is un_shareable and already attached to another server, begin to force attach").format(
                volume_id)
            LOG.info(msg)
            return volume_status.READY_TO_FORCE_ATTACH, msg, consts.VOLUME_IS_UNSHAREABLE
        # volume state :not attach ,attach other volume shareable. we need to attach volume
        if state == volume_status.NOT_ATTACH:
            msg = _LE("The volume {0} existed and not attached").format(volume_id)
            LOG.info(msg)
            return volume_status.READY_TO_ATTACH, msg, consts.VOLUME_NO_STATUS
        elif state == volume_status.ALREADY_ATTACHED_TO_OTHER_HOST and shareable:
            msg = _LI("The volume is shareable and continue to attach")
            LOG.info(msg)
            return volume_status.READY_TO_ATTACH, msg, consts.VOLUME_NO_STATUS

    def _check_before_detach(self, volume_id, volume, volume_attachment_state, dm_dev):

        state = volume_attachment_state
        mountpoints = blockdevice.get_dev_mountpoints(dm_dev)
        if len(mountpoints) > 0:
            msg = _LI("The volume have mount path,can't to detach!")
            LOG.info(msg)
            return volume_status.NOT_READY_TO_DETACH, msg, consts.VOLUME_STATE_IS_INCORRECT
        if state == volume_status.ALREADY_ATTACHED_TO_THIS_HOST:
            msg = _LI("The volume is attached to current host!")
            LOG.info(msg)
            return volume_status.READY_TO_DETACH, msg, consts.VOLUME_NO_STATUS
        elif state == volume_status.ALREADY_ATTACHED_TO_OTHER_HOST:
            msg = _LI("The volume is attached to other host!")
            LOG.info(msg)
            return volume_status.NOT_ATTACH, msg, consts.VOLUME_NO_STATUS
        elif state == volume_status.NOT_ATTACH:
            msg = _LI("The volume is not attached to current host!")
            LOG.info(msg)
            return volume_status.NOT_ATTACH, msg, consts.VOLUME_NO_STATUS
        else:
            msg = _LI("The volume is not attached to current host!")
            LOG.info(msg)
            return volume_status.NOT_READY_TO_DETACH, msg, consts.VOLUME_STATE_IS_INCORRECT

    def _create_mount_point_if_not_exist(self, mount_path):
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

    def change_mount_point_owner(self, mount_point, option_key_mount_options):
        dir_mode, uid, gid = resovle_mount_options(option_key_mount_options)
        change_owner(mount_point, uid, gid)
        change_dir_mode(mount_point, dir_mode)
        LOG.info("change the mount point owner and dir_mode finished")

    def change_monit_point_dir_mode(self, mount_point):
        try:
            processutils.execute('chmod', '777', mount_point, run_as_root=True)
            msg = _LI("Succeed to chmod {0} mount_point as all open dir_mode").format(mount_point)
            LOG.info(msg)
            return mount_point
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            with excutils.save_and_reraise_exception():
                msg = _LE("Unexpected error while chmod dir_mode. "
                          "mount_point: {0}, "
                          "Error: {1}").format(mount_point, e)
                LOG.error(msg)
            return None

    """
        Get the number of disks which are not used by fuxivol pv with specific mode in the hosted vm,
        the valid parameter pairs of device_prefix and disk_mode are as follows:
        * For VBD Disks: consts.VBD_DISK_DEVICE_NAME_PREFIX, consts.VBD_DISK_BUS_NAME
        * For SCSI Disks: consts.SCSI_DISK_DEVICE_NAME_PREFIX, consts.SCSI_DISK_BUS_NAME
    """

    def _find_disk_num_info_for_target_prefix(self, device_prefix, disk_mode):
        fuxivolpv_used_disks_num, err_msg = self._query_fuxivol_pv_disks_num(device_prefix)
        if err_msg != None:
            error = _LE("Failed to query {0} disks using device prefix {1} for fuxivol pv: {2}").format(disk_mode,
                                                                                                        device_prefix,
                                                                                                        err_msg)
            LOG.error(error)
            return 0, 0, error

        total_disks_num, err_msg = self._query_total_disks_num(device_prefix, disk_mode)
        if err_msg != None:
            error = _LE("Failed to query total {0} disks using device prefix {1} in the hosted vm: {2}").format(
                disk_mode, device_prefix, err_msg)
            LOG.error(error)
            return 0, 0, error

        return fuxivolpv_used_disks_num, total_disks_num, None

    """
        Get number of all the simple disk nams (such as 'vda' or 'sda') in the hosted vm using the pairs of deivce_prefix an disk_mode:
        * For VBD Disks: consts.VBD_DISK_DEVICE_NAME_PREFIX, consts.VBD_DISK_BUS_NAME
        * For SCSI Disks: consts.SCSI_DISK_DEVICE_NAME_PREFIX, consts.SCSI_DISK_BUS_NAME
    """

    def _query_total_disks_num(self, device_prefix, disk_mode):
        target_disk_num, err_msg = self._query_disks_num_with_device_prefix(device_prefix)
        if err_msg == None:
            return target_disk_num, None
        if disk_mode == None:
            return target_disk_num, err_msg
        else:
            LOG.info("Failed to query disks number with device prefix %s, so use disk mode %s to query." % (
            err_msg, disk_mode))
            target_disk_num, err_msg = self._query_disks_num_with_bus_name(disk_mode)
            if err_msg != None:
                LOG.info("Failed to query disks with disk mode %s: %s" % (disk_mode, err_msg))
            return target_disk_num, err_msg

    """
        Get number of all the simple disk names (such as 'vda' or 'sda') in the hosted vm through 'fdisk' with device_prefix:
        * consts.VBD_DISK_DEVICE_NAME_PREFIX:  "/dev/vd"
        * consts.SCSI_DISK_DEVICE_NAME_PREFIX: "/dev/sd"
    """

    def _query_disks_num_with_device_prefix(self, device_prefix):
        cmd = "fdisk -l | grep 'Disk %s' | awk '{print $2}' | cut -d \":\" -f 1 | cut -c 6- | wc -l" % (device_prefix)
        outputs, err = exec_cmd.exec_shell_cmd(cmd, 5)
        if err is None:
            outputs_lines = outputs.splitlines()
            for line in outputs_lines:
                try:
                    number_in_int = int(line)
                    return number_in_int, None
                except ValueError:
                    LOG.debug("unexpected non-number response line: %s" % line)
            return 0, "no valid disk number result by lines: %s" % (outputs_lines)
        return 0, err

    """
        Get number of all the simple disk names (such as 'vda' or 'sda') i_find_non_fuxivol_pv_disk_numn the hosted vm through listing /dev/disk/by-id/ with disk_bus_name:
        * consts.VBD_DISK_BUS_NAME:  "virtio" for VBD mode
        * consts.SCSI_DISK_BUS_NAME: "scsi" for SCSI mode
    """

    def _query_disks_num_with_bus_name(self, disk_bus_name):
        cmd = "ls -l /dev/disk/by-id/ | grep %s | grep -v part | awk '{print $11}' | cut -c 7- | wc -l" % (
        disk_bus_name)
        num, err = exec_cmd.exec_shell_cmd(cmd, 5)
        if err is None:
            return int(num), None
        return 0, err

    """
        Get number of the simple names (such as 'vda' or 'sda') of disks used by fuxivol pv in the hosted vm with device_prefix:
        * consts.VBD_DISK_DEVICE_NAME_PREFIX:  "/dev/vd"
        * consts.SCSI_DISK_DEVICE_NAME_PREFIX: "/dev/sd"
    """

    def _query_fuxivol_pv_disks_num(self, device_prefix):
        cmd = "mount | grep 'huawei.com/fuxivol' | grep '%s' | awk '{print $1}' | cut -c 6- | wc -l" % (device_prefix)
        num, err = exec_cmd.exec_shell_cmd(cmd, 5)
        if err is None:
            return int(num), None
        return 0, err

    def _make_volume_limit_info(self, max_total_disk_num, max_vbd_disk_num, max_scsi_disk_num):
        volume_limit_info = {}
        if max_total_disk_num >= 0:
            volume_limit_info[consts.HC_ALL_MODE_DISK_VOLUME_LIMIT_KEY] = max_total_disk_num
        if max_vbd_disk_num >= 0:
            volume_limit_info[consts.HC_VBD_MODE_DISK_VOLUME_LIMIT_KEY] = max_vbd_disk_num
        if max_scsi_disk_num >= 0:
            volume_limit_info[consts.HC_SCSI_MODE_DISK_VOLUME_LIMIT_KEY] = max_scsi_disk_num
        return volume_limit_info

    def _get_num_of_non_fuxivol_pv_disks(self, total_disks_with_mode, fuxi_pv_disks_with_mode):
        total_disk_with_mode_set = set(total_disks_with_mode)
        fuxi_pv_disks_with_mode_set = set(fuxi_pv_disks_with_mode)
        return len(total_disk_with_mode_set.difference(fuxi_pv_disks_with_mode_set))

    """
        Get the simple names (such as 'vda' or 'sda') of disk used by fuxivol pv in the hosted vm with volume_name and target_device_prefix:
        * consts.VBD_DISK_DEVICE_NAME_PREFIX:  "/dev/vd"
        * consts.SCSI_DISK_DEVICE_NAME_PREFIX: "/dev/sd"
    """

    def _query_mounted_fuxivol_pv_disk(self, volume_name, target_device_prefix):
        cmd = "mount | grep 'huawei.com/fuxivol' | grep '%s' | grep '%s' | awk '{print $1}' | cut -c 6-" % (
        volume_name, target_device_prefix)
        results, err_msg = exec_cmd.exec_shell_cmd(cmd, 5)
        if err_msg != None:
            return None, err_msg
        if results != None and len(results) == 0:
            return None, "The device name prefix of volume %{0} is not %{1}".format(volume_name, target_device_prefix)


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
        msg = _LI("Succeed to chmod {0} mount_point as {1}").format(mount_point, dir_mode)
        LOG.info(msg)
    except processutils.ProcessExecutionError as e:
        LOG.exception(e.message)
        with excutils.save_and_reraise_exception():
            msg = _LE("Unexpected error while chmod dir_mode. "
                      "mount_point: {0}, "
                      "dir_mode: {1}"
                      "Error: {2}").format(mount_point, dir_mode, e)
            LOG.error(msg)


def _check_before_get_dev_by_link_path(link_path):
    try:
        dev_path = os.path.realpath(link_path)
        return dev_path
    except OSError as ex:
        LOG.exception(ex.message)
        msg = "Failed to get device path by link path. Error: {0}".format(ex)
        LOG.error(_LE(msg))
        return None


def _check_before_get_link_path_by_volume(volume_id):
    try:
        link_path = os.path.join(consts.VOLUME_LINK_DIR, volume_id)
        return link_path
    except OSError as e:
        LOG.exception(e.message)
        msg = "Failed to get link path by volume id. Error: {0}".format(e)
        LOG.error(_LE(msg))
        return None


def _check_before_get_mount_point_by_link_path(link_path):
    try:
        dev_path = os.path.realpath(link_path)
        mount_point = blockdevice.get_dev_mountpoints(dev_path)
        return mount_point
    except OSError as e:
        LOG.exception(e.message)
        msg = "Failed to get mount point by link path. Error: {0}".format(e)
        LOG.error(_LE(msg))
        return None
