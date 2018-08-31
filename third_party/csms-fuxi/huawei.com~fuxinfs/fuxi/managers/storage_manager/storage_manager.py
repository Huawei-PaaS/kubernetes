from managers import manager
from clients.storage_manager import storage_manager_client
from common.fuxi_exceptions.NotFoundException import VolumeNotFoundException
from common.constants import consts
from common.i18n import _, _LE, _LI, _LW
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StorageManager(manager.Manager):
    def __init__(self):
        super(StorageManager, self).__init__()
        self.storage_manager_client = storage_manager_client.StorageManagerClient()

    def create(self, namespace, create_params):
        try:
            volume_type = create_params.get("storage_type", "NFS")
            volume = self.storage_manager_client.create_volume(namespace, create_params)
            volume_response = self._get_volume_from_endpoint(namespace, volume, volume_type)
            return volume_response, None, consts.CREATE_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Failed to create volume storage_manager client. Error: {0}").format(ex)
            LOG.error(msg)
            return None, msg, consts.CREATE_ERROR

    def delete(self, namespace, volume_id, storage_type, params):
        LOG.info(_LI("delete volume {0}, and namespace {1}, and storage_type {2}.")
                 .format(volume_id, namespace, storage_type))
        try:
            created_by = params.get('kubernetes.io/createdby', '').strip()
            if created_by != "" and created_by == "cfe-apiserver":
                LOG.info("target sfs share %s is imported, no need to delete" % volume_id)
            else:
                self.storage_manager_client.delete_volume(namespace, volume_id, storage_type)
            return None, consts.DELETE_OK
        except VolumeNotFoundException as ve:
            LOG.exception(ve.message)
            raise VolumeNotFoundException(ve.message)
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Error happened while deleting volume information from interface. Error: {0}").format(ex)
            LOG.error(msg)
            return msg, consts.DELETE_ERROR

    def expand(self, namespace, volume_id, new_size):
        LOG.info(_LI("expand sfs share {0}, and namespace {1}.").format(volume_id, namespace))
        try:
            volume = self.storage_manager_client.get_volume(namespace, volume_id, "NFS")
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Failed to get volume from the volume_id {0}.Err: {1}").format(volume_id, e)
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_BY_ID_FAILED
        if not volume:
            msg = "Can not get the volume accord to the volume id."
            LOG.error(msg)
            return None, msg, consts.GET_VOLUME_RECORD_FAILED
        old_size = volume["spec"]["size"]
        try:
            self.storage_manager_client.expand_volume(namespace, volume_id, new_size, old_size)
            return None, consts.EXPAND_OK
        except Exception as ex:
            LOG.exception(ex.message)
            msg = _LE("Error happened while expanding sfs share information from interface. Error: {0}").format(ex)
            LOG.error(msg)
            return msg, consts.EXPAND_ERROR

    def _get_volume_from_endpoint(self, namespace, vol_info, volume_type):
        # TODO: rename this method
        LOG.info(str(vol_info))
        volume_id = vol_info["status"]["id"]
        volume = self.storage_manager_client.get_volume(namespace, volume_id, volume_type)
        devicemountpath = volume["status"]["export_location"]
        LOG.error(str(devicemountpath))
        volume = "{\"id\": \"%s\", \"namespace\":\"%s\", \"size\":%s, \"labels\":{}, \"options\":" \
                 "{\"fsType\":\"nfs\", \"deviceMountPath\":\"%s\"}}"\
                 % (vol_info["status"]["id"], namespace, vol_info["spec"]["size"], devicemountpath)

        return volume
