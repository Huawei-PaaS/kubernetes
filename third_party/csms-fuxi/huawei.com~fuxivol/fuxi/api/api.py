#!/usr/bin/env python


from common.config import CONF
from common.constants import consts
from common.constants.consts import DEFAULT_VOLUME_PROVIDER
from common.i18n import _LI
from oslo_log import log as logging
from oslo_utils import importutils
from common.fuxi_exceptions.NotFoundException import VolumeNotFoundException
from request import volume as volume_request
from request.validators import common_validator as common_validator
from request.validators import volume as volume_validator
from response import response
from common import audit_log

LOG = logging.getLogger(__name__, 'fuxi')


class API(object):
    def __init__(self):
        self.AUDIT_LOG = audit_log.LoggerAudit()
        self._init_provider()

    def init(self):
        result = response.create_init_success_response()
        LOG.info(result)
        self.AUDIT_LOG.info("Fuxi init success")
        return result

    def create(self, params):
        LOG.info(_LI("Create parameters: {0}").format(str(params)))
        self.AUDIT_LOG.info("Create volume start")
        ok, result = volume_validator.validate_create_volume_params(params)
        if not ok:
            self.AUDIT_LOG.info("Create volume failed")
            return result

        ok, result = common_validator.validate_manage_namespace(params)
        if not ok:
            self.AUDIT_LOG.info("Create volume failed")
            return result
        namespace = result

        ok, result = volume_validator.validate_access_mode(params)
        if not ok:
            self.AUDIT_LOG.info("Create volume failed")
            return result

        ok, result = volume_validator.validate_passthrough(params)
        if not ok:
            self.AUDIT_LOG.info("Create volume failed")
            return result

        volume_create_params = volume_request.generate_create_params(params)
        try:
            volume_info, message, message_code = self.volume_provider.create(namespace, volume_create_params)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.info("Create volume failed")
            result = response.create_error_response(e.message, consts.CREATE_ERROR)
            return result

        if message_code == consts.CREATE_OK:
            self.AUDIT_LOG.info("Create volume success")
            result = response.create_volume_success_response(volume_info)
        else:
            self.AUDIT_LOG.info("Create volume failed")
            result = response.create_error_response(message, message_code)
        LOG.info(result)
        return result

    def delete(self, volume_id, params):
        LOG.info(_LI("Delete volume {0} with Parameters: {1}").format(volume_id, str(params)))
        self.AUDIT_LOG.critical("Delete volume start")

        ok, result = common_validator.validate_manage_namespace(params)
        if not ok:
            self.AUDIT_LOG.critical("Delete volume failed")
            return result
        namespace = result

        try:
            msg, message_code = self.volume_provider.delete(namespace, volume_id, params)
        except VolumeNotFoundException as ve:
            LOG.exception(ve.message)
            self.AUDIT_LOG.critical("Delete volume failed")
            return response.create_not_found_response(ve.message, consts.VOLUME_NOT_FOUND)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.critical("Delete volume failed")
            return response.create_error_response(e.message, consts.DELETE_ERROR)

        if message_code == consts.DELETE_OK:
            self.AUDIT_LOG.critical("Delete volume success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.critical("Delete volume failed")
            return response.create_error_response(msg, message_code)

    def attach(self, params):
        LOG.info(_LI("Attach Parameters: {0}").format(str(params)))
        self.AUDIT_LOG.warn("Attach volume start")

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Attach volume failed")
            return result
        namespace = result

        ok, result = volume_validator.validate_readwrite_mode(params)
        if not ok:
            self.AUDIT_LOG.warn("Attach volume failed")
            return result

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Attach volume failed")
            return result
        volume_id = result

        ok, result = volume_validator.validate_file_system_type(params)
        if not ok:
            self.AUDIT_LOG.warn("Attach volume failed")
            return result
        fs_type = result

        ok, result = common_validator.validate_time_out(params)
        if not ok:
            self.AUDIT_LOG.warn("Attach volume failed")
            return result
        time_out = result

        LOG.info("fsType: %s" % fs_type)
        volume_params = {"fsType": fs_type, "name": volume_id, "namespace": namespace, "timeout": time_out}

        try:
            dev_path, msg, message_code = self.volume_provider.attach(namespace, volume_id, volume_params)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.warn("Attach volume failed")
            return response.create_error_response(e.message, consts.ATTACH_ERROR)

        if message_code == consts.ATTACH_OK:
            self.AUDIT_LOG.warn("Attach volume success")
            return response.create_volume_attach_success_response(dev_path)
        else:
            self.AUDIT_LOG.warn("Attach volume failed")
            return response.create_error_response(msg, message_code)

    def isattached(self):
        result = response.create_success_response()
        LOG.info(result)
        self.AUDIT_LOG.info("Fuxi isattached success")
        return result

    def waitforattach(self, params):
        return self.attach(params)

    def detach(self, volume_name, node_name, params):
        LOG.info(_LI("Detach parameters:volume_name {0} node_name {1} params {2}").format(volume_name, node_name,
                                                                                          str(params)))
        self.AUDIT_LOG.critical("Detach volume start")
        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.critical("Detach volume failed")
            return result
        namespace = result

        ok, result = common_validator.validate_time_out(params)
        if not ok:
            self.AUDIT_LOG.critical("Detach volume failed")
            return result
        time_out = result

        volume_params = {"timeout": time_out}
        try:
            message, message_code = self.volume_provider.detach(namespace, volume_name, node_name, volume_params)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.critical("Detach volume failed")
            return response.create_error_response(e.message, consts.DELETE_ERROR)

        if message_code == consts.DETACH_OK:
            self.AUDIT_LOG.critical("Detach volume success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.critical("Detach volume failed")
            return response.create_error_response(message, message_code)

    def mount_device(self, mount_path, dm_dev, params):
        LOG.info(_LI("Mount parameters: "
                     "mount_path {0} "
                     "dm_dev {1} "
                     "params {2}")
                 .format(mount_path, dm_dev, str(params)))
        self.AUDIT_LOG.warn("Mount device start")
        ok, result = common_validator.validate_device_path(dm_dev)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result

        LOG.info(_LI("Mount device Path: {0}").format(mount_path))
        LOG.info(_LI("DM Dev: {0}").format(dm_dev))
        LOG.info(_LI("Mount device Parameters: {0}").format(str(params)))

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result
        namespace = result

        ok, result = volume_validator.validate_file_system_type(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result
        fs_type = result

        ok, result = volume_validator.validate_readwrite_mode(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result
        rw_mode = result

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result
        volume_id = result

        LOG.info("fsType: %s" % fs_type)

        try:
            mount_point, message, message_code = \
                self.volume_provider.mount(
                    namespace,
                    volume_id,
                    mount_path,
                    fs_type,
                    rw_mode
                )
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.warn("Mount device failed")
            return response.create_error_response(e.message, consts.MOUNT_ERROR)

        if message_code == consts.MOUNT_OK:
            LOG.info("The mount point: " + mount_point)
            self.AUDIT_LOG.warn("Mount device success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.warn("Mount device failed")
            return response.create_error_response(message, message_code)

    def mount(self, part_dir, mount_path, params):
        LOG.info(_LI("Mount parameters: "
                     "mount_path {0} "
                     "part_dir {1} "
                     "params {2}")
                 .format(mount_path, part_dir, str(params)))
        self.AUDIT_LOG.warn("Mount volume start")
        if mount_path == "mount_device":
            ok, result = common_validator.validate_mount_device(params)
            if not ok:
                self.AUDIT_LOG.warn("Mount volume failed")
                return result
            mount_path = result
        ok, result = common_validator.validate_device_path(mount_path)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        LOG.info(_LI("Mount Path: {0}").format(mount_path))
        LOG.info(_LI("Part Dir: {0}").format(part_dir))
        LOG.info(_LI("Mount Parameters: {0}").format(str(params)))

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result
        namespace = result

        ok, result = volume_validator.validate_file_system_type(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result
        fs_type = result

        ok, result = volume_validator.validate_readwrite_mode(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result
        rw_mode = result

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result
        volume_id = result

        ok, result = common_validator.validate_pod_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        ok, result = volume_validator.validate_volume_pod_uid(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        ok, result = volume_validator.validate_mount_options(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount device failed")
            return result
        option_key_mount_options = result

        LOG.info("fsType: %s" % fs_type)

        try:
            mount_point, message, message_code = \
                self.volume_provider.mount_bind(
                    namespace,
                    volume_id,
                    mount_path,
                    fs_type,
                    rw_mode,
                    part_dir,
                    option_key_mount_options
                )
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.warn("Mount volume failed")
            return response.create_error_response(e.message, consts.MOUNT_ERROR)

        if message_code == consts.MOUNT_OK:
            LOG.info("The mount point: " + mount_point)
            self.AUDIT_LOG.warn("Mount volume success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.warn("Mount volume failed")
            return response.create_error_response(message, message_code)

    def unmount(self, mount_path, params):
        LOG.info(_LI("Unmount Parameters: unmount path {0} params {1}").format(mount_path, str(params)))
        self.AUDIT_LOG.critical("Unmount volume start")
        # TODO: need add check namespace for authority
        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.critical("Unmount volume failed")
            return result
        namespace = result

        ok, result = common_validator.validate_mount_path(mount_path)
        if not ok:
            return result
        mount_path = result

        try:
            self.volume_provider.unmount(namespace, mount_path)
            self.AUDIT_LOG.critical("Unmount volume success")
            return response.create_success_response()
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.critical("Unmount volume failed")
            return response.create_error_response(e.message, consts.UNMOUNT_ERROR)

    def unmountdevice(self, deviceMountPath, params):
        LOG.info(
            _LI("Unmountdevice Parameters: unmountdevice path {0} params {1}").format(deviceMountPath, str(params)))
        self.AUDIT_LOG.critical("Unmountdevice volume start")
        ok, result = common_validator.validate_mount_path(deviceMountPath)
        if not ok:
            return result
        deviceMountPath = result

        try:
            self.volume_provider.unmountdevice(deviceMountPath)
            self.AUDIT_LOG.critical("Unmountdevice volume success")
            return response.create_success_response()
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.critical("Unmountdevice volume failed")
            return response.create_error_response(e.message, consts.UNMOUNT_ERROR)

    def expand(self, new_size, old_size, params):
        LOG.info(_LI("Expand Parameters: {0}").format(str(params)))
        self.AUDIT_LOG.warn("Expand volume start")

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Expand volume failed")
            return result
        namespace = result

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Expand volume failed")
            return result
        volume_id = result

        ok, result = volume_validator.validate_size(new_size)
        if not ok:
            self.AUDIT_LOG.warn("Expand volume failed")
            return result
        new_size = result

        ok, result = volume_validator.validate_size(old_size)
        if not ok:
            self.AUDIT_LOG.warn("Expand volume failed")
            return result
        old_size = result

        LOG.info("oldSize: %s" % old_size)
        LOG.info("newSize: %s" % new_size)

        try:
            msg, message_code = self.volume_provider.expand(namespace, volume_id, new_size)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.warn("Expand volume failed")
            return response.create_error_response(e.message, consts.EXPAND_ERROR)

        if message_code == consts.EXPAND_OK:
            self.AUDIT_LOG.warn("Expand volume success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.warn("Expand volume failed")
            return response.create_error_response(msg, message_code)


    def getvolumelimitkey(self, params):
        ok, result = volume_validator.validate_disk_mode(params)
        if not ok:
            return result
        disk_mode = result
        ok, result = volume_validator.validate_volume_name_for_volumelimit(params)
        if not ok:
            return result
        volume_name = result

        volume_limit_key, err_msg = self.volume_provider.getvolumelimitkey(disk_mode, volume_name)
        if err_msg != None:
            return response.create_error_response(err_msg, consts.VOLUME_LIMIT_KEY_ERROR)

        result = response.create_get_volume_limit_key_successul_response(volume_limit_key)
        LOG.info(result)
        return result


    def getvolumelimitinfo(self):
        volume_limit_result = self.volume_provider.getvolumelimitinfo()
        result = response.create_query_volume_limits_successul_response(volume_limit_result)
        LOG.info(result)
        return result


    def _init_provider(self):

        provider = CONF.provider_type
        LOG.debug("provide: %s" % provider)
        try:
            self.volume_provider = importutils.import_class(DEFAULT_VOLUME_PROVIDER[provider])()
        except Exception as ex:
            LOG.exception(ex.message)
            return response.create_error_response(ex.message, consts.CREATE_ERROR)
