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
from common.fuxi_exceptions.NotFoundException import VolumeNotFoundException, BlockDeviceAppNotFoundException
from oslo_log import log as logging
from clients.storage_manager import http_client

LOG = logging.getLogger(__name__)

NAMESPACE_DIR = '/api/v1/namespaces/'
HTTP_MODEL = "https://"
PERSISTENT_VOLUME_DIR = '/api/v1/'


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
        create_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes'
        LOG.info(_LI("Post {0}").format(create_url))
        if create_opts["cryptKeyId"] == "" or create_opts["cryptKeyId"] is None:
            metadata = {"labels": {"hw:passthrough": create_opts["passthrough"]}
                        }
        else:
            metadata = {"labels": {"hw:passthrough": create_opts["passthrough"],
                                   "__system__cmkid": create_opts["cryptKeyId"]}
                        }
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "metadata": metadata,
            "spec": {
                "name": create_opts["name"],
                "size": create_opts["size"],
                "availability_zone": create_opts["zone"],
                "description": create_opts["desc"],
                "multiattach": create_opts["shareable"],
                "snapshot_id": create_opts["snapshot"],
                "volume_type": create_opts["type"]
            }
        }
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
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            message = _LI("create volume error with status_code {0}").format(rsp.status_code)
            LOG.error(message)
            raise StorageManagerClientException(detail_msg)

    def delete_volume(self, namespace, volume_id):
        delete_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id
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
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            message = _LI("Delete volume request return status_code {0}").format(rsp.status_code)
            LOG.error(message)
            raise StorageManagerClientException(detail_msg)

    def delete_metadata(self, namespace, volume_id):
        delete_metadata_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/metadata'
        LOG.info(_LI("Delete {0}").format(delete_metadata_url))
        ret, rsp = http_client.send_request("DELETE", delete_metadata_url)
        if not ret:
            msg = _LE("Failed to delete metadata for disk volume %s." % volume_id)
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.ok:
            msg = _LI("delete metadata for disk volume %s request successfully" % volume_id)
            LOG.info(msg)
            return None
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            message = _LI("Delete metadata for disk volume {0} request return status_code {1}")\
                .format(volume_id, rsp.status_code)
            LOG.error(message)
            raise StorageManagerClientException(detail_msg)

    def get_volume(self, namespace, volume_id):
        LOG.info(namespace)
        LOG.info(self.storage_mgr_url)
        LOG.info(volume_id)
        get_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id
        LOG.info(_LI("Get {0}").format(get_url))

        ret, rsp = http_client.send_request("GET", get_url)
        if not ret:
            msg = _LE("Failed to get volume.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            volume = rsp.json()
            LOG.info(_LI("get volume information: {0}").format(volume))
            return volume
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("get volume information error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def get_volume_id_from_volume_name(self, namespace, volume_name):
        LOG.info(namespace)
        LOG.info(self.storage_mgr_url)
        LOG.info(volume_name)
        get_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes?name=' + str(volume_name)
        LOG.info(_LI("Get {0}").format(get_url))

        ret, rsp = http_client.send_request("GET", get_url)
        if not ret:
            msg = _LE("Failed to get volume accord the volume_name.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.accepted:
            volume = rsp.json()
            LOG.info(_LI("get volume information: {0}").format(volume))
            items = volume['items']
            if len(items) > 0:
                for item in items:
                    if item['spec']['name'].strip() == volume_name:
                        volume_id = item['status']['id']
                        return volume_id
                    else:
                        continue
            else:
                return None
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("get volume information error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def connect_volume_vir(self, namespace, server_id, volume_id):
        connect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/attach'
        LOG.info(_LI("Post: {0}.").format(connect_url))

        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-attach": {
                    "server_id": server_id
                }
            }
        }

        LOG.info(_LI("In the vir model payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", connect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to connect volume in the vir model.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.accepted:
            attachment = rsp.json()
            LOG.info(_LI("Attachment body {0}").format(attachment))
            return attachment
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            LOG.error(_LI("Connect volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def disconnect_volume_vir(self, namespace, server_id, volume_id):

        disconnect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/detach'
        LOG.info(_LI("Post: {0}").format(disconnect_url))
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-detach": {
                    "server_id": server_id
                }
            }
        }

        LOG.info(_LI("In the vir model payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", disconnect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to disconnect volume in the vir model")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.accepted:
            LOG.info(_LI("detach volume request is accept "))
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            LOG.error(_LI("Disconnect volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def connect_volume_phy(self, namespace, host_name, volume_id, device):
        connect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/attach'
        LOG.info(_LI("Post: {0}.").format(connect_url))

        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-attach": {
                    "host_name": host_name,
                    "device": device
                }
            }
        }

        LOG.info(_LI("In the phy model payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", connect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to connect volume in the phy model")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.accepted:
            return None
        else:
            msg = _LE("Failed to connect volume in the phy model")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("get volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(msg)

    def disconnect_volume_phy(self, namespace, attachment_id, volume_id):
        disconnect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/detach'
        LOG.info(_LI("Post: {0}").format(disconnect_url))
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-detach": {
                    "attachment_id": attachment_id
                }
            }
        }

        LOG.info(_LI("In the phy model payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", disconnect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to disconnect volume in the phy model")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.accepted:
            LOG.info(_LI("detach volume request is accept "))
            return None
        else:
            msg = _LE("Failed to disconnect volume in the phy model")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("detach volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(msg)

    def reserve_volume(self, namespace, volume_id):
        reserve_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/reserve'
        LOG.info(_LI("Post: {0}").format(reserve_url))
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-reserve": {}
            }
        }

        LOG.info(_LI("payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", reserve_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to reserve volume.")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.accepted:
            LOG.info(_LI("reserve volume request is accept "))
        else:
            msg = _LE("Failed to reserve volume.")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("reserve volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(msg)

    def unreserve_volume(self, namespace, volume_id):
        unreserve_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/unreserve'
        LOG.info(_LI("Post: {0}").format(unreserve_url))
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-unreserve": {}
            }
        }

        LOG.info(_LI("payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", unreserve_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to unreserve volume.")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.accepted:
            LOG.info(_LI("unreserve volume request is accept "))
        else:
            msg = _LE("Failed to unreserve volume.")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("unreserve volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(msg)

    def initialize_connection(self, namespace, volume_id, connector_properties):
        initconn_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/initconn'
        LOG.info(_LI("Post: {0}").format(initconn_url))
        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
            "spec": {
                "os-initialize_connection": {
                    "connector": connector_properties
                }
            }
        }

        LOG.info(_LI("payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", initconn_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to initialize connection.")
            LOG.error(msg)
            raise StorageManagerClientException(msg)

        if rsp.status_code == requests.codes.ok:
            connection = rsp.json()
            return connection
        else:
            msg = _LE("Failed to initialize connection.")
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("Initialize connection error with status_code {0}").format(rsp.status_code))
            LOG.error(msg)
            raise StorageManagerClientException(msg)

    def get_volume_id_from_pv(self, pvname):
        LOG.info(pvname)
        get_url = CONF.kube_apiserver_url + PERSISTENT_VOLUME_DIR + 'persistentvolumes/' + str(pvname)
        LOG.info(_LI("Get {0}").format(get_url))

        ret, rsp = http_client.send_request("GET", get_url)
        if not ret:
            msg = _LE("Failed to get persistent_volume.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            LOG.info(_LI("The request for getting the persistent_volumes is accepted."))
            persistent_volume = rsp.json()
            LOG.info(_LI("the persistent volume information: {0}").format(persistent_volume))

            if persistent_volume['spec']['flexVolume']:
                volume_id = persistent_volume['spec']['flexVolume']['options']['volumeID']
                return volume_id
            else:
                return None

        else:
            detail_msg = rsp.json()
            LOG.error(_LE("error info: {0}").format(detail_msg))
            LOG.error(_LE("get persistent_volume information error with status_code {0}").format(rsp.status_code))
            message = _LE("Failed to get persistent volume")
            raise StorageManagerClientException(message)

    def expand_volume(self, namespace, volume_id, new_size, old_size, az, volume_type):
        connect_url = self.storage_mgr_url + NAMESPACE_DIR + namespace + '/volumes/' + volume_id + '/expandvolume'
        LOG.info(_LI("Post: {0}.").format(connect_url))

        payload = {
            "apiVersion": "paas/v1beta1",
            "kind": "Volume",
             "metadata": {
                 "region": az
             },
            "spec": {
                "storage_type": volume_type.upper(),
                "os-extend": {
                    "old_size": int(old_size),
                    "new_size": int(new_size)
                }
            }
        }

        LOG.info(_LI("payload: {0}.").format(payload))
        ret, rsp = http_client.send_request("POST", connect_url, data=json.dumps(payload))
        if not ret:
            msg = _LE("Failed to expand volume.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            LOG.info(_LI("expand volume request is ok "))
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("Error info: {0}").format(detail_msg))
            LOG.error(_LI("expand volume error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def get_volume_attachment(self, server_id, volume_id):
        LOG.info(server_id)
        LOG.info(self.storage_mgr_url)
        LOG.info(volume_id)
        get_url = self.storage_mgr_url + PERSISTENT_VOLUME_DIR + 'servers/' + server_id + '/block_device/' + volume_id
        LOG.info(_LI("Get {0}").format(get_url))

        ret, rsp = http_client.send_request("GET", get_url)
        if not ret:
            msg = _LE("Failed to get device path.")
            LOG.error(msg)
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            volume_attachment = rsp.json()
            LOG.info(_LI("get device path: {0}").format(volume_attachment))
            return volume_attachment
        elif rsp.status_code == requests.codes.not_found:
            msg = _LW("The find block device app is not found")
            LOG.warning(msg)
            raise BlockDeviceAppNotFoundException(msg)
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("get volume information error with status_code {0}").format(rsp.status_code))
            raise StorageManagerClientException(detail_msg)

    def get_attached_volume_spec_from_host(self, server_id, host_src):
        get_url = self.storage_mgr_url + PERSISTENT_VOLUME_DIR + 'servers/' + server_id + '/block_device?host_src=' + host_src
        LOG.info(_LI("Get {0}").format(get_url))
        ret, rsp = http_client.send_request("GET", get_url, 5)
        if not ret:
            LOG.error(_LE("Failed to get attached volume spec for host {0}: {1}".format(server_id, rsp)))
            raise StorageManagerClientException(rsp)

        if rsp.status_code == requests.codes.ok:
            host_attached_volume_spec = rsp.json()
            LOG.info(_LI("Get attached volume spec for host {0}: {1}").format(server_id, host_attached_volume_spec))
            return host_attached_volume_spec
        elif rsp.status_code == requests.codes.not_found:
            msg = _LW("The block device api is not found")
            LOG.warning(msg)
            raise BlockDeviceAppNotFoundException(msg)
        else:
            detail_msg = rsp.json()
            LOG.info(_LI("error info: {0}").format(detail_msg))
            LOG.error(_LI("Get attached volume spec for host {0} error with status_code {1}").format(server_id, rsp.status_code))
            raise StorageManagerClientException(detail_msg)
