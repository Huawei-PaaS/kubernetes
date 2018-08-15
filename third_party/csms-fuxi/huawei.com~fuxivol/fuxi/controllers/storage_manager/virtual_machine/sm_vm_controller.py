import os
import stat

from clients import utils
from clients.storage_manager import storage_manager_client
from common.constants import consts
from common.constants import volume_status
from common.i18n import _LI, _LE, _LW
from controllers import controller, blockdevice, state_monitor
from controllers import volume_device_mapper
from controllers.storage_manager.virtual_machine import vm_volume_device_mapper
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import uuidutils, excutils
from common.fuxi_exceptions.NotFoundException import BlockDeviceAppNotFoundException
from vm_volume_util import get_scsi_device

LOG = logging.getLogger(__name__)


class StorageManagerVMController(controller.Controller):
    def __init__(self):
        super(StorageManagerVMController, self).__init__()
        self.storage_manager_client = storage_manager_client.StorageManagerClient()
        pass

    def attach(self, namespace, volume_id, volume_opts):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Failed to get volume from the volume_id {0}. Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED

        volume_attachment_state = self._get_volume_attachment_state(volume)
        mapped_volume_attach_state, msg, ret_code = self._check_before_attach(
            volume_id, volume, self._is_volume_shareable(volume), volume_attachment_state)

        # Handle volume_status.READY_TO_ATTACH case:
        server_id = utils.get_server_id()
        if not server_id:
            msg = "Fail to get server id"
            LOG.error(msg)
            return None, msg, consts.CONNECT_VOLUME_FAILED

        if mapped_volume_attach_state == volume_status.NOT_READY_TO_ATTACH:
            return None, msg, ret_code
        if mapped_volume_attach_state == volume_status.READY_TO_FORCE_ATTACH:
            return self.force_attach(namespace, volume_id, volume, volume_opts)
        if mapped_volume_attach_state == volume_status.ALREADY_ATTACHED:
            link_path = vm_volume_device_mapper.get_link_path_by_volume(volume_id)
            if link_path is None:
                msg = "Volume is attached to this machine, but can't get link path."
                return None, msg, consts.VOLUME_ATTACHED_THIS_NO_DEV
            if os.path.exists(link_path):
                mount_point = vm_volume_device_mapper.get_mount_point_by_link_path(link_path)
                if len(mount_point) > 0:
                    msg = "Volume is already to this host, the mount point is {0} ".format(mount_point)
                    LOG.info(msg)
                else:
                    msg = "Volume is already to this host, but not get mount point."
                    LOG.info(msg)
                return vm_volume_device_mapper.get_dev_by_link_path(link_path), msg, ret_code
            else:
                msg = "Volume is already to this host, and try to rebuild link path."
                LOG.info(msg)
                dev_path, msg, ret_status = self.rebuild_link_path_by_volume(server_id, namespace, link_path, volume_id)
                return dev_path, msg, ret_status

        LOG.info(_LI("The volume_opts: {0} ").format(volume_opts))
        time_out = volume_opts.get("timeout")
        LOG.info(_LI("The time out time: {0} ").format(time_out))
        before_set = self.get_device()
        _, msg, state = self._attach_volume(namespace, server_id, volume_id, time_out)
        if state != consts.ATTACH_OK:
            return None, msg, state

        dev_path = self.get_node_device_path(server_id, volume_id, namespace)
        after_set = self.get_device()
        diff_path_set = after_set.difference(before_set)
        LOG.info("The diff path set: {0} ".format(diff_path_set))
        if len(diff_path_set) == 1:
            if not dev_path:
                dev_path = diff_path_set.pop()
                LOG.info("The Last dev_path: {0} ".format(dev_path))

        if not dev_path:
            try:
                self.storage_manager_client.disconnect_volume_vir(namespace, server_id, volume_id)
            except Exception as ex:
                LOG.error(ex.message)
            finally:
                msg = "Failed to attach volume to this host. Failed to get block dev path!"
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED

        ok = volume_device_mapper.add_dev_to_volume_mapping(dev_path, volume_id)
        if not ok:
            volume_device_mapper.remove_dev_to_volume_mapping(volume_id)
            try:
                self.storage_manager_client.disconnect_volume_vir(namespace, server_id, volume_id)
            except Exception as ex:
                LOG.error(ex.message)
            finally:
                msg = "Failed to attach volume to this host. Failed to save volume  dev path mapping."
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED

        LOG.info(_LI("Device path: {0}").format(dev_path))
        return dev_path, None, consts.ATTACH_OK

    def _attach_volume(self, namespace, server_id, volume_id, time_out):
        try:
            LOG.info(_LI("Start to attach volume {0} to server {1}").format(volume_id, server_id))
            volume_attachment = self.storage_manager_client.connect_volume_vir(
                namespace=namespace, server_id=server_id, volume_id=volume_id)
            if not volume_attachment:
                msg = "Failed to attach volume to this host."
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED
            LOG.info(_LI("The time out time: {0}").format(time_out))
            volume_monitor = state_monitor.StateMonitor(
                self.storage_manager_client,
                volume_attachment["volumeAttachment"],
                namespace, True, time_out)
            volume_monitor.monitor_attach()
            return None, "", consts.ATTACH_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = "Attaching volume {0} to server {1} failed. Error: {2}".format(volume_id, server_id, ex)
            LOG.error(_LE(msg))
            return None, msg, consts.CONNECT_VOLUME_FAILED

    def force_attach(self, namespace, volume_id, volume, volume_opts):
        try:
            attached_server_id = volume.get("status", None).get('attachments', [])[0].get("server_id", None)
            if attached_server_id is not None:
                self.storage_manager_client.disconnect_volume_vir(namespace=namespace, server_id=attached_server_id,
                                                                  volume_id=volume_id)
                LOG.info(_LI("The volume_opts:{0}").format(volume_opts))
                time_out = volume_opts.get("timeout")
                LOG.info(_LI("The time out time: {0}").format(time_out))
                volume_monitor = state_monitor.StateMonitor(
                    self.storage_manager_client,
                    volume['status'], namespace, False, time_out)
                volume_monitor.monitor_detach()
            else:
                msg = "Fail to get the unshareable volume %s attachment service_id, can not to continue attach!".format(
                    volume_id)
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED
        except Exception as ex:
            LOG.error(ex.message)
            msg = "Fail to detach the unshareable volume %s, can not to continue attach!".format(volume_id)
            LOG.error(msg)
            return None, msg, consts.CONNECT_VOLUME_FAILED

        # Handle volume_status.READY_TO_ATTACH case:
        server_id = utils.get_server_id()
        if not server_id:
            msg = "Fail to get server id"
            LOG.error(msg)
            return None, msg, consts.CONNECT_VOLUME_FAILED
        LOG.info(_LI("The volume_opts: {0}").format(volume_opts))
        time_out = volume_opts.get("timeout")
        LOG.info(_LI("The time out time: {0}").format(time_out))
        before_set = self.get_device()
        _, msg, state = self._attach_volume(namespace, server_id, volume_id, time_out)
        if state != consts.ATTACH_OK:
            return None, msg, state

        dev_path = vm_volume_device_mapper.get_dev_by_volume(volume_id)

        if not dev_path:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
            dev_path = vm_volume_device_mapper.get_xendev_by_vloume(volume, server_id)
            LOG.info("The Xen dev_path: {0}".format(dev_path))
        dev_path = self.get_node_device_path(server_id, volume_id, namespace)
        after_set = self.get_device()
        diff_path_set = after_set.difference(before_set)
        LOG.info("The diff path set: {0}".format(diff_path_set))
        if len(diff_path_set) == 1:
            if not dev_path:
                dev_path = diff_path_set.pop()
                LOG.info("The Last dev_path: {0}".format(dev_path))
        LOG.info("dev_path: {0}".format(dev_path))

        if not dev_path:
            try:
                self.storage_manager_client.disconnect_volume_vir(namespace, server_id, volume_id)
            except Exception as ex:
                LOG.error(ex.message)
            finally:
                msg = "Failed to attach volume to this host. Failed to get block dev path!"
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED

        ok = volume_device_mapper.add_dev_to_volume_mapping(dev_path, volume_id)
        if not ok:
            volume_device_mapper.remove_dev_to_volume_mapping(volume_id)
            try:
                self.storage_manager_client.disconnect_volume_vir(namespace, server_id, volume_id)
            except Exception as ex:
                LOG.error(ex.message)
            finally:
                msg = "Failed to attach volume to this host. Failed to save volume dev path mapping."
                LOG.error(msg)
                return None, msg, consts.CONNECT_VOLUME_FAILED

        LOG.info(_LI("Device path: {0}").format(dev_path))
        return dev_path, None, consts.ATTACH_OK

    def detach(self, namespace, volume_name, node_name, volume_opts):
        volume_id = self.storage_manager_client.get_volume_id_from_pv(volume_name)
        if volume_id is None:
            msg = _LE("Failed to get Volume id from persistent volume name {0}").format(volume_name)
            LOG.error(msg)
            return None, consts.DETACH_OK
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} failed.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord to the volume id."
            LOG.error(msg)
            return msg, consts.GET_VOLUME_RECORD_FAILED
        dm_dev = vm_volume_device_mapper.get_device_path(volume_id)
        volume_attachment_state = self._get_volume_attachment_state(volume)
        detach_status, msg, ret_code = self._check_before_detach(
            volume_id, volume, volume_attachment_state, dm_dev)

        if detach_status == volume_status.NOT_READY_TO_DETACH:
            return msg, ret_code
        elif detach_status == volume_status.NOT_ATTACH:
            return None, consts.DETACH_OK

        try:
            self.storage_manager_client.disconnect_volume_vir(namespace, utils.get_server_id(), volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Detaching volume {0} failed. "
                      "Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return msg, consts.DETACH_ERROR
        try:
            LOG.info(_LI("The volume_opts:{0}").format(volume_opts))
            time_out = volume_opts.get("timeout")
            LOG.info(_LI("The time out time: {0}").format(time_out))
            volume_monitor = state_monitor.StateMonitor(
                self.storage_manager_client,
                volume['status'], namespace, False, time_out)
            volume_device_mapper.remove_dev_to_volume_mapping(volume_id)
            volume_monitor.monitor_detach()
        except Exception as ex:
            LOG.exception(ex.message)
            msg = "disconnect volume {0} failed. Error: {1}".format(volume_id, ex)
            LOG.error(_LE(msg))
            return msg, consts.DETACH_ERROR
        return None, consts.DETACH_OK

    def get_device_path(self, volume):
        return os.path.join(consts.VOLUME_LINK_DIR, volume["status"]["id"])

    def mount_bind(self, namespace, volume_id, mount_path, fs_type, rw_mode, part_dir, option_key_mount_options):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} failed.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Failed get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED

        state = self._get_volume_attachment_state(volume)
        if state != volume_status.ALREADY_ATTACHED_TO_THIS_HOST:
            msg = _LE("Volume {0} is not in correct state, current state "
                      "is {1}").format(volume_id, state)
            LOG.error(msg)
            return None, msg, consts.VOLUME_IS_ATTACHED_TO_OTHERS

        part_dir, msg, ret_code = self._create_mount_point_if_not_exist(part_dir)
        if not part_dir:
            return None, msg, ret_code

        blockdevice.do_mount_bind(mount_path, fs_type, part_dir)
        if option_key_mount_options:
            real_part_dir = os.path.realpath(part_dir)
            self.change_mount_point_owner(real_part_dir, option_key_mount_options)
        return mount_path, None, consts.MOUNT_OK

    def mount(self, namespace, volume_id, mount_path, fs_type, rw_mode):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} from Iaas failed.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED

        state = self._get_volume_attachment_state(volume)
        if state != volume_status.ALREADY_ATTACHED_TO_THIS_HOST:
            msg = _LE("Volume {0} is not in correct state, current state "
                      "is {1}").format(volume_id, state)
            LOG.error(msg)
            return None, msg, consts.VOLUME_IS_ATTACHED_TO_OTHERS

        dev_path, msg, ret_code = self._get_dev_path_by_volume(volume)
        if not dev_path:
            return None, msg, ret_code

        mount_point, msg, ret_code = self._create_mount_point_if_not_exist(mount_path)
        if not mount_point:
            return None, msg, ret_code

        mount_point, msg = blockdevice.do_mount(dev_path, mount_point, fs_type, rw_mode)
        if msg != None:
            return None, msg, consts.VOLUME_MOUNT_DEVICE_FAILED
        mount_point = self.change_monit_point_dir_mode(mount_point)
        if not mount_point:
            msg = "Change the mount point to all open failed."
            LOG.error(msg)
            return None, msg, consts.MOUNT_ERROR

        return mount_point, None, consts.MOUNT_OK

    def _get_dev_path_by_volume(self, volume):
        link_path = self.get_device_path(volume)
        if not os.path.exists(link_path):
            msg = _LE("Could not find device link file.")
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_DEVICE_PATH_FAILED
        dev_path = os.path.realpath(link_path)
        if not dev_path or not os.path.exists(dev_path):
            msg = _LE("Can't find volume device path.")
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_DEVICE_PATH_FAILED
        return dev_path, None, consts.VOLUME_NO_STATUS

    def unmount(self, namespace, mount_path):
        return blockdevice.do_unmount(mount_path)

    def unmountdevice(self, deviceMountPath):
        return blockdevice.do_unmount(deviceMountPath)

    def _get_volume_id_from_dm_dev(self, dm_dev):
        disk_id_list = os.listdir(consts.VOLUME_LINK_DIR)
        for disk_id in disk_id_list:
            if uuidutils.is_uuid_like(disk_id) and dm_dev == os.path.realpath(consts.VOLUME_LINK_DIR + disk_id):
                return disk_id
        return None

    def _get_volume_attachment_state(self, volume):
        if not volume:
            return volume_status.UNKNOWN
        try:
            status = volume["status"]["status"]
            LOG.info(_LI("volume is  {0} status  {1}.").format(volume, status))
            if status not in ['Using', 'Available']:
                LOG.error(_LE("The volume is not in right status for attach, The status is {0}").format(status))
                return volume_status.WRONG_STATUS

            attachments = volume["status"]["attachments"]
            if not attachments:
                return volume_status.NOT_ATTACH
            server_id = utils.get_server_id()
            for attachment in attachments:
                if attachment['server_id'] == server_id:
                    return volume_status.ALREADY_ATTACHED_TO_THIS_HOST
            else:
                return volume_status.ALREADY_ATTACHED_TO_OTHER_HOST

        except Exception as ex:
            LOG.exception(ex.message)
            LOG.error(_LE("Error happened while getting volume list information from cinder. Error: {0}").format(ex))
            return None, volume_status.UNKNOWN

    def _is_volume_shareable(self, volume):
        return volume["spec"].get("multiattach", False)

    def rebuild_link_path_by_volume(self, server_id, namespace, link_path, volume_id):
        dev_path = self.get_node_device_path(server_id, volume_id, namespace)
        if not dev_path:
            message = "Volume is attached to this machine, but can't get device path."
            LOG.info(message)
            return None, message, consts.VOLUME_ATTACHED_THIS_NO_DEV
        else:
            try:
                processutils.execute('rm', '-f', link_path, run_as_root=True)
                processutils.execute('ln', '-s',
                                     dev_path,
                                     link_path,
                                     run_as_root=True)
                msg = "Volume is attached to this machine, and rebuild link path succeed."
                LOG.info(msg)
                return dev_path, msg, consts.ATTACH_OK
            except processutils.ProcessExecutionError as e:
                LOG.exception(e.message)
                msg = _LE("Unexpected error while rebuild link path. "
                          "dev_path: {0}, "
                          "link_path: {1} "
                          "error: {2}").format(dev_path,
                                               link_path,
                                               e)
                LOG.error(msg)
                message = "Volume is attached to this machine, but can't get device path."
                LOG.info(message)
                return None, message, consts.VOLUME_ATTACHED_THIS_NO_DEV

    def get_device(self):
        path_dir = consts.DEV_PATH
        lst = [os.path.join(path_dir, item) for item in os.listdir(path_dir) if
               stat.S_ISBLK(os.stat(os.path.join(path_dir, item))[stat.ST_MODE])]
        return set(lst)

    def get_node_device_path(self, server_id, volume_id, namespace):
        bus, pci_address = self.get_bus_pci_address(server_id, volume_id)
        wwn = self.get_wwn(namespace, volume_id)

        if bus == "virtio" and pci_address != "":
            LOG.info("The pci_address:{0}".format(pci_address))
        if bus == "scsi" and wwn != "":
            return get_scsi_device(wwn)

        dev_path = vm_volume_device_mapper.get_dev_by_volume(volume_id)

        if not dev_path:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
            dev_path = vm_volume_device_mapper.get_xendev_by_vloume(volume, server_id)
            LOG.info("The Xen dev_path:{0}".format(dev_path))

        LOG.info("dev_path:{0}".format(dev_path))

        return dev_path

    def get_bus_pci_address(self, server_id, volume_id):
        try:
            volume_attachment = self.storage_manager_client.get_volume_attachment(server_id, volume_id)
            bus = volume_attachment["volumeAttachment"]["bus"]
            pci_address = volume_attachment["volumeAttachment"]["pciAddress"]
            return bus, pci_address
        except BlockDeviceAppNotFoundException as be:
            LOG.exception(be.message)
            return None, None
        except Exception as e:
            LOG.exception(e.message)
            return None, None

    def get_wwn(self, namaspce, volume_id):
        volume = self.storage_manager_client.get_volume(namaspce, volume_id)
        volume_spec = volume["spec"]
        if "wwn" in volume_spec.keys():
            wwn = volume_spec["wwn"]
        else:
            wwn = ""
        return wwn

    def getvolumelimitinfo(self):
        # Currently in CCE ECS/BMS Nodes are all used sm_vm_controller, so here it needs to handle separately
        if self._is_real_vm():
            return self._get_volumelimitinfo_for_vm()
        else:
            return self._get_volumelimitinfo_for_bms()

    def _supports_vbd(self):
        # Currently in CCE ECS/BMS Nodes are all used sm_vm_controller, so here it needs to handle separately
        if self._is_real_vm():
            return True
        else:
            return False

    def _is_real_vm(self):
        real_host_type = utils.get_real_host_type()
        if real_host_type == consts.HOST_TYPE_VM:
            return True
        elif real_host_type == consts.HOST_TYPE_PM:
            return False
        else:
            LOG.info("Unknown host type %s but assumed as vm" % real_host_type)
            return True
