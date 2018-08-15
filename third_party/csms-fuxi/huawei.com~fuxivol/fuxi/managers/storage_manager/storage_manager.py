from managers import manager
from clients.storage_manager import storage_manager_client
from common.fuxi_exceptions.NotFoundException import VolumeNotFoundException
from common.constants import consts
from common.i18n import _LE, _LI
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StorageManager(manager.Manager):
    def __init__(self):
        super(StorageManager, self).__init__()
        self.storage_manager_client = storage_manager_client.StorageManagerClient()

    def create(self, namespace, create_params):
        try:
            volume = self.storage_manager_client.create_volume(namespace, create_params)
            pass_through = create_params["passthrough"]
            if pass_through == "false":
                disk_mode = "VBD"
            else:
                disk_mode = "SCSI"

            volume_response = self._get_volume_from_endpoint(namespace, volume, disk_mode)
            return volume_response, None, consts.CREATE_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Failed to create volume storage_manager client. Error: {0}").format(ex)
            LOG.error(msg)
            return None, msg, consts.CREATE_ERROR

    def delete(self, namespace, volume_id, params):
        LOG.info(_LI("delete volume {0}, and namespace {1}")
                 .format(volume_id, namespace))
        try:
            created_by = params.get('kubernetes.io/createdby', '').strip()
            if created_by != "" and created_by == "cfe-apiserver":
                LOG.info("target disk volume %s is imported, no need to delete, try to delete metadata" % volume_id)
                volume = self.storage_manager_client.get_volume(namespace, volume_id)
                if not volume:
                    LOG.info("target disk volume %s does not exist, no need to delete metadata" % volume_id)
                else:
                    status = volume["status"]["status"]
                    if status != 'Available':
                        msg = _LE("status of volume %s is %s, only disk in 'Available' status can be deleted metadata."
                                  % (volume_id, status))
                        LOG.error(msg)
                        return msg, consts.DELETE_ERROR
                    self.storage_manager_client.delete_metadata(namespace, volume_id)
            else:
                self.storage_manager_client.delete_volume(namespace, volume_id)
            return None, consts.DELETE_OK
        except VolumeNotFoundException as ve:
            LOG.exception(ve.message)
            raise VolumeNotFoundException(ve.message)
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Error happened while deleting volume {0} information from interface. Error: {1}")\
                .format(volume_id, ex)
            LOG.error(msg)
            return msg, consts.DELETE_ERROR

    def expand(self, namespace, volume_id, new_size):
        LOG.info(_LI("expand volume {0}, and namespace {1}.").format(volume_id, namespace))
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id)
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Failed to get volume from the volume_id {0}.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED
        az = volume["spec"]["availability_zone"]
        old_size = volume["spec"]["size"]
        volume_type = volume["spec"]["volume_type"]
        try:
            self.storage_manager_client.expand_volume(namespace, volume_id, new_size, old_size, az, volume_type)
            return None, consts.EXPAND_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Error happened while expanding volume information from interface. Error: {0}").format(ex)
            LOG.error(msg)
            return msg, consts.EXPAND_ERROR

    @staticmethod
    def _get_volume_from_endpoint(namespace, vol_info, disk_mode):
        # TODO: rename this method
        volume = "{\"id\": \"%s\", \"namespace\":\"%s\", \"size\":%s, " \
                 " \"options\":{\"fsType\":\"ext4\", \"disk-mode\":\"%s\"}}" % (
                     vol_info["status"]["id"], namespace, vol_info["spec"]["size"], disk_mode)

        return volume
