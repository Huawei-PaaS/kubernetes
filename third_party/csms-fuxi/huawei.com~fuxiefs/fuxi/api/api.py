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

        ok, result = volume_validator.validate_volume_size(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_availability_zone(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_volume_type(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_storage_type(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_vpcid(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_securitygroupid(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
            return result

        ok, result = volume_validator.validate_netid(params)
        if not ok:
            self.AUDIT_LOG.critical("Create volume failed")
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
        ok, result = volume_validator.validate_storage_type(params)
        if not ok:
            self.AUDIT_LOG.critical("Delete volume failed")
            return result
        storage_type = result

        try:
            msg, message_code = self.volume_provider.delete(namespace, volume_id, storage_type, params)
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

    def mount(self, mount_path, dm_dev, params):
        LOG.info(_LI("Mount parameters: "
                     "mount_path {0} "
                     "dm_dev {1} "
                     "params {2}")
                 .format(mount_path, dm_dev, str(params)))
        self.AUDIT_LOG.warn("Mount volume start")

        LOG.info(_LI("Mount Path: {0}").format(mount_path))
        LOG.info(_LI("DM Dev: {0}").format(dm_dev))
        LOG.info(_LI("Mount Parameters: {0}").format(str(params)))

        if mount_path == "mount_device":
            ok, result = common_validator.validate_mount_device(params)
            if not ok:
                self.AUDIT_LOG.warn("Mount volume failed")
                return result
            mount_path = result

        ok, result = common_validator.validate_mount(mount_path)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume success")
            return result
        mount_path = result

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        ok, result = volume_validator.validate_file_system_type(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result
        fs_type = result

        ok, result = volume_validator.validate_readwrite_mode(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        share_proto = params.get('share_proto', None)

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Mount volume failed")
            return result

        LOG.info("fsType: %s" % fs_type)

        dm_dev = params.get("deviceMountPath", None)
        if dm_dev is None:
            return response.create_error_response("deviceMountPath is None", consts.MOUNT_ERROR)
        try:
            mount_point, message, message_code = \
                self.volume_provider.mount(
                    mount_path,
                    dm_dev,
                    share_proto
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

        try:
            self.volume_provider.unmount(mount_path)
            self.AUDIT_LOG.critical("Unmount volume success")
            return response.create_success_response()
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.critical("Unmount volume failed")
            return response.create_error_response(e.message, consts.UNMOUNT_ERROR)

    def expand(self, new_size, old_size, params):
        LOG.info(_LI("Expand Parameters: {0}").format(str(params)))
        self.AUDIT_LOG.warn("Expand sfs-turbo start")

        ok, result = common_validator.validate_namespace(params)
        if not ok:
            self.AUDIT_LOG.warn("Expand sfs-turbo failed, due to validate namesapce failed")
            return result
        namesapce = result

        ok, result = volume_validator.validate_volume_id(params)
        if not ok:
            self.AUDIT_LOG.warn("Expand sfs-turbo failed, due to validate volume id failed")
            return result
        volume_id = result

        ok, result = volume_validator.validate_size(new_size)
        if not ok:
            self.AUDIT_LOG.warn("Expand sfs-turbo failed, due to validate volume new size failed")
            return result
        new_size = result

        ok, result = volume_validator.validate_size(old_size)
        if not ok:
            self.AUDIT_LOG.warn("Expand sfs-turbo failed, due to validate volume old size failed")
            return result
        old_size = result

        LOG.info("oldSize: %s" % old_size)
        LOG.info("newSize: %s" % new_size)

        try:
            msg, message_code = self.volume_provider.expand(namesapce, volume_id, new_size)
        except Exception as e:
            LOG.exception(e.message)
            self.AUDIT_LOG.warn("Expand sfs-turbo failed")
            return response.create_error_response(e.message, consts.EXPAND_ERROR)

        if message_code == consts.EXPAND_OK:
            self.AUDIT_LOG.warn("Expand sfs-turbo success")
            return response.create_success_response()
        else:
            self.AUDIT_LOG.warn("Expand sfs-turbo failed")
            return response.create_error_response(msg, message_code)

    def _init_provider(self):

        provider = CONF.provider_type
        LOG.debug("provide: %s" % provider)
        try:
            self.volume_provider = importutils.import_class(DEFAULT_VOLUME_PROVIDER[provider])()
        except Exception as ex:
            LOG.exception(ex.message)
            return response.create_error_response(ex.message, consts.CREATE_ERROR)
