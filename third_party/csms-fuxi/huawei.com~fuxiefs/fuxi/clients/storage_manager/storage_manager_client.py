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

import json
import os

import abstract_storage_manager_client
import requests
from common.config import CONF
from common.i18n import _LI, _LE, _LW
from common.exceptions import StorageManagerClientException
from common.fuxi_exceptions.NotFoundException import VolumeNotFoundException
from oslo_log import log as logging
from clients.storage_manager import http_client

LOG = logging.getLogger(__name__)


NAMESPACE_DIR = '/api/v1/namespaces/'
HTTP_MODEL = "https://"


class StorageManagerClient(abstract_storage_manager_client.AbstractStorageManageClient):
    def __init__(self):
        super(StorageManagerClient, self).__init__()
        storage_manage_addr = os.getenv("storage_manager_addr", None)
        storage_manage_port = os.getenv("storage_manager_port", None)
        if storage_manage_addr is None or storage_manage_addr == "" or storage_manage_port is None \
                or storage_manage_port == "":
            self.storage_mgr_url = CONF.storage_manager.storage_manager_url
        else:
            self.storage_mgr_url = HTTP_MODEL + storage_manage_addr + ":" + storage_manage_port

    def create_volume(self, namespace, create_opts):
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": create_opts,
        }
        storage_type = create_opts["storage_type"]
        create_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes?storage_type=' + str(storage_type)
        LOG.info(_LI("create_url: {0}.").format(create_url))
        LOG.info(_LI("storage_type:  " + storage_type))
        LOG.info(_LI("payload: {0}.").format(payload))

        ret, rsp = http_client.send_request("POST", create_url, data=json.dumps(payload))
        if not ret:
            LOG.error(rsp)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.accepted:
            volume = rsp.json()
            LOG.info(_LI("create volume {0}").format(volume))
            return volume
        else:
            msg = _LE("Failed to create volume.")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            message = _LI("create volume error with status_code {0}").format(rsp.status_code)
            LOG.error(message)
            raise StorageManagerClientException(detail_msg)

    def delete_volume(self, namespace, volume_id, storage_type):
        delete_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + \
                     '?storage_type=' + str(storage_type)
        LOG.info(_LI("Delete {0}").format(delete_url))
        ret, rsp = http_client.send_request("DELETE", delete_url)
        if not ret:
            msg = _LE("Failed to delete volume.")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.not_found:
            msg = _LW("The deleting volume is not found")
            LOG.warning(msg)
            raise VolumeNotFoundException(msg)

        if rsp.status_code == requests.codes.accepted:
            msg = _LI("delete volume request accepted ")
            LOG.info(msg)
            return None
        else:
            msg = _LE("Failed to delete volume.")
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            message = _LI("Delete volume request return status_code {0}").format(rsp.status_code)
            LOG.error(message)
            raise StorageManagerClientException(detail_msg)

    def get_volume(self, namespace, volume_id, storage_type):
        LOG.info(namespace)
        LOG.info(self.storage_mgr_url)
        LOG.info(volume_id)
        get_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '?storage_type=' + str(
            storage_type)
        LOG.info(_LI("Get {0}").format(get_url))

        ret, rsp = http_client.send_request("GET", get_url)
        if not ret:
            msg = _LE("Failed to get volume.")
            LOG.error(msg)
            return None

        if rsp.status_code == requests.codes.ok:
            volume = rsp.json()
            LOG.info(_LI("get volume information: {0}").format(volume))
            return volume
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("get volume information error with status_code {0}").format(rsp.status_code))
            return None

    def expand_volume(self, namespace, volume_id, new_size, old_size):
        connect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/expandvolume'
        LOG.info(_LI("Post: {0}.").format(connect_url))

        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "storage_type": "EFS",
                "os-extend": {
                    "old_size": int(old_size),
                    "new_size": int(new_size)
                }
            }
        }

        LOG.info(_LI("payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", connect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to expand sfs-turbo.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            LOG.info(_LI("expand sfs-turbo request is ok."))
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            LOG.error(_LI("expand sfs-turbo error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)