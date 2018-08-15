import os
import os.path

from controllers import brickconnector
from clients.storage_manager import storage_manager_client
from common.constants import consts
from common.constants import volume_status
from common.i18n import _LE, _LI
from controllers import controller, blockdevice, volume_device_mapper
from controllers.storage_manager.physical_machine import pm_volume_device_mapper
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import uuidutils
from hw_brick.initiator import connector as hwconnector
from controllers import state_monitor
from clients import utils

LOG = logging.getLogger(__name__)


class StorageManagerPMController(controller.Controller):
    def __init__(self):
        super(StorageManagerPMController, self).__init__()
        self.host_ip = consts.DEFAULT_ADDRESS
        self.storage_manager_client = storage_manager_client.StorageManagerClient()

    def attach(self, namespace, volume_id, volume_opts):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} from Cinder failed.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED

        if not volume:
            msg = "IN the PM model Can not get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED

        volume_attachment_state = self._get_volume_attachment_state(volume)
        mapped_volume_attach_state, msg, ret_code = super(
                StorageManagerPMController, self)._check_before_attach(
                volume_id, volume, self._is_volume_shareable(volume), volume_attachment_state)
        if mapped_volume_attach_state == volume_status.NOT_READY_TO_ATTACH:
            return None, msg, ret_code
        if mapped_volume_attach_state == volume_status.ALREADY_ATTACHED:
            link_path = pm_volume_device_mapper.get_link_path_by_volume(volume_id)
            if link_path is None:
                msg = "Volume is attached to this machine, but can't get link path."
                return None, msg, consts.VOLUME_ATTACHED_THIS_NO_DEV
            if os.path.exists(link_path):
                mount_point = pm_volume_device_mapper.get_mount_point_by_link_path(link_path)
                if len(mount_point) > 0:
                    msg = "Volume is already to this host,the mount point is {0}".format(mount_point)
                    LOG.info(msg)
                else:
                    msg = "Volume is already to this host,but not get mount point."
                    LOG.info(msg)
                return pm_volume_device_mapper.get_dev_by_link_path(link_path), msg, ret_code
            else:
                msg = "Volume is already to this host, and try to rebuild link path."
                LOG.info(msg)
                dev_path, msg, ret_status = self.rebuild_link_path_by_volume(namespace, link_path, volume)
                return dev_path, msg, ret_status

        # Handle volume_status.READY_TO_ATTACH case:
        host_name = utils.get_host_name()
        LOG.info(_LI("The volume_opts:{0}").format(volume_opts))
        time_out = volume_opts.get("timeout")
        LOG.info(_LI("The time out time:{0}").format(time_out))
        dev_path, msg, state = self._attach_volume(namespace, host_name, volume, time_out)
        if state != consts.ATTACH_OK:
            return None, msg, state
        LOG.info(_LI("Device path: {0}").format(dev_path))
        return dev_path, None, consts.ATTACH_OK

    def detach(self, namespace, dm_dev, volume_opts):
        volume_id = self._get_volume_id_from_dm_dev(dm_dev)
        if not volume_id:
            msg = _LE("Failed to get Volume id from device path {0}").format(dm_dev)
            return msg, consts.DETACH_ERROR
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} from Cinder failed.").format(volume_id, e)
            LOG.error(msg)
            return msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord the volume id."
            LOG.error(msg)
            return msg, consts.GET_VOLUME_RECORD_FAILED

        volume_attachment_state = self._get_volume_attachment_state(volume)
        detach_status, msg, ret_code = super(
                StorageManagerPMController, self)._check_before_detach(
                volume_id, volume, volume_attachment_state, dm_dev)

        if detach_status == volume_status.NOT_READY_TO_DETACH:
            return msg, ret_code

        try:
            LOG.info(_LI("The volume_opts:{0}").format(volume_opts))
            time_out = volume_opts.get("timeout")
            LOG.info(_LI("The time out time:{0}").format(time_out))
            msg, detach_state = self._detach_volume(namespace, volume, time_out)
            if detach_state != consts.DETACH_OK:
                return msg, consts.DETACH_ERROR
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Detaching volume {0} failed. "
                      "Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return msg, consts.DETACH_ERROR

        volume_device_mapper.remove_dev_to_volume_mapping(volume_id)
        return None, consts.DETACH_OK

    def mount_bind(self, namespace, volume_id, mount_path, fs_type, rw_mode, part_dir, option_key_mount_options):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} from Cinder failed.Err: {1}").format(volume_id, e)
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

        part_dir, msg, ret_code = super(
            StorageManagerPMController, self)._create_mount_point_if_not_exist(part_dir)
        if not part_dir:
            return None, msg, ret_code

        blockdevice.do_mount_bind(mount_path, fs_type, part_dir)
        return mount_path, None, consts.MOUNT_OK

    def mount(self, namespace, volume_id, mount_path, fs_type, rw_mode):
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get Volume {0} from Cinder failed.Err: {1}").format(volume_id, e)
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

        mount_point, msg, ret_code = super(
                StorageManagerPMController, self)._create_mount_point_if_not_exist(mount_path)
        if not mount_point:
            return None, msg, ret_code

        _, msg = blockdevice.do_mount(dev_path, mount_point, fs_type, rw_mode)
        if msg != None:
            return None, msg, consts.VOLUME_MOUNT_DEVICE_FAILED
        return mount_point, None, consts.MOUNT_OK

    def unmount(self, namespace, mount_path):
        return blockdevice.do_unmount(mount_path)

    def unmountdevice(self, deviceMountPath):
        return blockdevice.do_unmount(deviceMountPath)

    def _get_connection_info(self, namespace, volume_id):
        LOG.info(_LI("Get connection info for osbrick connector and use it to connect to volume"))
        try:
            root_helper = utils.get_root_helper()
            connector_properties = hwconnector.get_connector_properties(root_helper, self.host_ip, None, True)
            LOG.info(_LI("The connector_properties info: {0}").format(connector_properties))
            conn_info = self.storage_manager_client.initialize_connection(namespace, volume_id, connector_properties)
            msg = _LI("Get connection information {0}").format(conn_info)
            LOG.info(msg)
            return conn_info
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Error happened when initialize connection for volume. Error: {0}").format(e)
            LOG.error(msg)
            return None

    def vlun_check(self, conn_info):
        if conn_info is None:
            LOG.error("The conn_info is None when checking vlun!")
            return True
        conn_info = conn_info['connection_info']
        if 'driver_volume_type' in conn_info:
            LOG.info(_LI("Volume type is {0}").format(conn_info['driver_volume_type']))
            if conn_info['driver_volume_type'].lower() == 'fibre_channel':
                try:
                    vlun, space = utils.execute('upadmin', 'show', 'vlun')
                    vlun_number = vlun.count('\n')
                    if vlun_number == 258:
                        LOG.error(_LE("The number of vlun is more than 256, vlun_number is : %d") % vlun_number)
                        return False
                    return True
                except processutils.ProcessExecutionError as e:
                    LOG.exception(e.message)
                    LOG.error(_LE("Error happened when get vlun number. Error: {0}").format(e))
                    return True
            return True
        else:
            LOG.error(_LE("Incorrect conn_info when checking vlun!"))
            return True

    def _connect_volume(self, namespace, volume):
        volume_id = volume["status"]["id"]
        conn_info = self._get_connection_info(namespace, volume_id)
        if not conn_info:
            return True, None
        try:
            brick_connector = self.get_wrapped_brick_connector(conn_info, volume=volume)
            if not brick_connector:
                return True, None

            vlun_valid = self.vlun_check(conn_info)
            if not vlun_valid:
                return False, None

            device_info = brick_connector.connect_volume(conn_info['connection_info']['data'])
            LOG.info(_LI("Get device_info after connect to volume %s") % device_info)
            link_path = os.path.join(consts.VOLUME_LINK_DIR, volume_id)
            utils.execute('ln', '-s',
                          os.path.realpath(device_info['path']),
                          link_path,
                          run_as_root=True)

            return True, {'path': link_path}
        except processutils.ProcessExecutionError as e:
            LOG.exception(e.message)
            LOG.error(_LE("Error happened when connecting to the target volume. Error: {0}").format(e))
            return True, None

    def _attach_volume(self, namespace, server_id, volume, time_out, **connect_opts):
        host_name = server_id
        LOG.info(_LI("Attach volume {0} to this server {1}.").format(volume, host_name))

        volume_id = volume["status"]["id"]
        try:
            self.storage_manager_client.reserve_volume(namespace, volume_id)
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Reserve volume {0} failed,Exception: {1}".format(volume, ex))
            LOG.error(msg)
            return None, msg, consts.ATTACH_ERROR

        try:
            vlun_valid, device_info = self._connect_volume(namespace, volume)
            if not vlun_valid:
                msg = _LE("The number of vlun is more than 256.")
                LOG.error(msg)
                self.on_attach_volume_failed(namespace, volume, volume_id)
                return None, msg, consts.ATTACH_ERROR

            if not device_info:
                msg = _LE("Connect the volume failed and device_info is None.")
                LOG.error(msg)
                self.on_attach_volume_failed(namespace, volume, volume_id, time_out)
                return None, msg, consts.ATTACH_ERROR

            device_path = os.path.realpath(device_info["path"])
            LOG.info(_LI("Begin to Attach volume to this server."))
            self.storage_manager_client.connect_volume_phy(
                    namespace=namespace, host_name=host_name,
                    volume_id=volume_id, device=device_path)
            LOG.info(_LI("The time out time: {0}").format(time_out))
            volume_monitor = state_monitor.StateMonitor(self.storage_manager_client,
                                                        volume["status"],
                                                        namespace, True, time_out)
            volume_monitor.monitor_attach()
            LOG.info(_LI("Attach volume to this server successfully."))
            return device_path, "", consts.ATTACH_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Attach volume {0} to this server failed! Exception: {1}".format(volume, ex))
            LOG.error(_LE(msg))
            self.on_attach_volume_failed(namespace, volume, volume_id, time_out)
            return None, msg, consts.ATTACH_ERROR

    def on_attach_volume_failed(self, namespace, volume, volume_id, time_out):
        try:
            self._detach_volume(namespace, volume, time_out)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Error: {0}").format(e)
            LOG.error(msg)
        finally:
            try:
                self.storage_manager_client.unreserve_volume(namespace, volume_id)
            except Exception as e:
                LOG.exception(e.message)
                msg = _LE("Error: {0}").format(e)
                LOG.error(msg)

    def _detach_volume(self, namespace, volume, time_out, **disconnect_opts):
        LOG.info(_LI("_detach volume {0} to this server .").format(volume))
        volume_id = volume["status"]["id"]
        conn_info = self._get_connection_info(namespace, volume_id)
        try:
            LOG.info(_LI("Get wrapped brick connector, Detach volume ."))
            brick_connector = self.get_wrapped_brick_connector(conn_info, volume=volume)
            if not brick_connector:
                msg = _LE("Get brick connector failed! connection info: {0}").format(volume_id)
                return msg, consts.GET_CONNECTOR_FAILED
            brick_connector.disconnect_volume(conn_info['connection_info']['data'], None)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Error happened when disconnect volume {0} {1} from "
                      "this server. Error: {2}").format(volume_id, volume, e.message)
            LOG.error(msg)
            return msg, consts.VOLUME_DISCONNECT_FAILED

        attachments = volume["status"]["attachments"]
        host_name = utils.get_host_name().lower()
        for attachment in attachments:
            if 'host_name' in attachment and attachment['host_name'].lower() == host_name:
                attachment_id = attachment['attachment_id']
                break
        else:
            msg = _LE("Not found attachment to this host! ")
            LOG.error(msg)
            return msg, consts.DETACH_ERROR
        try:
            self.storage_manager_client.disconnect_volume_phy(
                    namespace, attachment_id=attachment_id, volume_id=volume_id)
            LOG.info(_LI("The time out time: {0}").format(time_out))
            volume_monitor = state_monitor.StateMonitor(self.storage_manager_client,
                                                        volume["status"],
                                                        namespace, False, time_out)
            volume_monitor.monitor_detach()
            LOG.info(_LI("Disconnect the volume successfully."))
            return None, consts.DETACH_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Error happened when detach volume {0} {1} from this "
                      "server. Error: {2}").format(volume.name, volume, ex)
            LOG.error(msg)
            return msg, consts.VOLUME_DISCONNECT_FAILED

    def _get_device_link_path(self, volume):
        volume_id = volume["status"]["id"]
        return os.path.join(consts.VOLUME_LINK_DIR, volume_id)

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
            host_name = utils.get_host_name()
            for attachment in attachments:
                if attachment['host_name'] == host_name:
                    return volume_status.ALREADY_ATTACHED_TO_THIS_HOST
            else:
                return volume_status.ALREADY_ATTACHED_TO_OTHER_HOST

        except Exception as ex:
            LOG.exception(ex.message)
            LOG.error(_LE("Error happened while getting volume list information from cinder. Error: {0}").format(ex))
            return None, volume_status.UNKNOWN

    def _is_volume_shareable(self, volume):
        return volume["spec"]["multiattach"]

    def _get_dev_path_by_volume(self, volume):
        link_path = self._get_device_link_path(volume)
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

    def get_wrapped_brick_connector(self, conn_info, volume=None):
        if conn_info is None:
            LOG.error("The conn_info is None!!")
            return None
        conn_info = conn_info['connection_info']
        if 'driver_volume_type' in conn_info:
            LOG.info(_LI("Volume type is {0}".format(conn_info['driver_volume_type'])))
            kwargs = {'conn': conn_info}
            return brickconnector.brick_get_connector(conn_info['driver_volume_type'], **kwargs)
        else:
            LOG.error(_LE("Incorrect conn_info"))
            return None

    def rebuild_link_path_by_volume(self, namespace, link_path, volume):
        volume_id = volume["status"]["id"]
        conn_info = self._get_connection_info(namespace, volume_id)
        dev_path = ""
        try:
            brick_connector = self.get_wrapped_brick_connector(conn_info, volume=volume)
            if not brick_connector:
                msg = "Volume is attached to this machine, but can't get connector info."
                return None, msg, consts.VOLUME_ATTACHED_THIS_NO_DEV

            device_info = brick_connector.connect_volume(conn_info['connection_info']['data'])
            dev_path = os.path.realpath(device_info['path'])
            link_path = os.path.join(consts.VOLUME_LINK_DIR, volume_id)
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
            return None, message, consts.VOLUME_ATTACHED_THIS_NO_DEV

    def getvolumelimitinfo(self):
        return self._get_volumelimitinfo_for_bms()

    def _supports_vbd(self):
        return False