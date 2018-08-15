import time

from common import exceptions
from common.i18n import _LE, _LI
from oslo_log import log as logging
from common.config import CONF
from clients import utils

LOG = logging.getLogger(__name__)


class StateMonitor(object):
    def __init__(self, client, expected_obj,
                 namespace=None,
                 desired_device_exists=True,
                 time_limit=CONF.monitor_state_timeout,
                 host_machine_type=CONF.host_machine_type,
                 time_delay=1):
        self.expected_obj = expected_obj
        self.time_limit = time_limit
        self.host_machine_type = host_machine_type
        self.start_time = time.time()
        self.time_delay = time_delay
        self.namespace = namespace
        self.client = client
        self.desired_device_exists = desired_device_exists
        self.provider = CONF.provider_type

    def _check_device_exists(self):
        try:
            utils.execute('udevadm', 'trigger', run_as_root=True)
        except Exception as e:
            LOG.error(_LE("Error happened when udevadm trigger. Error: %s"), e)
        return self.desired_device_exists

    def monitor_detach(self):
        while True:
            elapsed_time = time.time() - self.start_time
            if elapsed_time > self.time_limit:
                msg = _LE("Timed out while waiting for detach volume. "
                          "Expected Volume: {0}, "
                          "Elapsed Time: {1}").format(self.expected_obj,
                                                      elapsed_time)
                LOG.error(msg)
                raise exceptions.TimeoutException(msg)

            try:
                if self.provider == 'storage_manager':
                    volume = self.client.get_volume(self.namespace, self.expected_obj["id"])
                    attachments = volume["status"]["attachments"]
                    shareable = volume["spec"].get("multiattach", False)
                else:
                    volume = self.client.volumes.get(self.expected_obj.id)
                    attachments = volume.attachments
                LOG.info(_LI("get the volume information {0}.").format(volume))
                LOG.info(_LI("The attachments is {0}.").format(attachments))
            except Exception as ex:
                LOG.exception(ex.message)
                LOG.error(_LE("get volume failed.Error: {0}").format(ex))
                time.sleep(self.time_delay)
                continue

            if self.host_machine_type == "vm":
                server_id = utils.get_server_id()
                server_ids = self.get_service_ids(attachments)
            else:
                server_id = utils.get_host_name()
                server_ids = self.get_host_names(attachments)

            LOG.info(_LI("The server_id is {0}.").format(server_id))
            LOG.info(_LI("The server_ids is {0}.").format(server_ids))
            if shareable:
                if server_id not in server_ids:
                    return volume
            else:
                if len(attachments) == 0:
                    return volume

            time.sleep(self.time_delay)

    def monitor_attach(self):
        while True:
            elapsed_time = time.time() - self.start_time
            if elapsed_time > self.time_limit:
                msg = _LE("Timed out while waiting for attach volume. "
                          "Expected Volume: {0}, "
                          "Elapsed Time: {1}").format(self.expected_obj,
                                                      elapsed_time)
                LOG.error(msg)
                raise exceptions.TimeoutException(msg)

            try:
                if self.provider == 'storage_manager':
                    volume = self.client.get_volume(self.namespace, self.expected_obj["id"])
                    volume_id = self.expected_obj["id"]
                    attachments = volume["status"]["attachments"]
                else:
                    volume = self.client.volumes.get(self.expected_obj.id)
                    volume_id = self.expected_obj.id
                    attachments = volume.attachments
                LOG.info(_LI("get volume information {0}.").format(volume))
                LOG.info(_LI("The attachments is {0}.").format(attachments))
            except Exception as ex:
                LOG.exception(ex.message)
                LOG.error(_LE("failed to get volume.Error: {0}").format(ex))
                time.sleep(self.time_delay)
                continue

            if self.host_machine_type == "vm":
                server_id = utils.get_server_id()
                server_ids = self.get_service_ids(attachments)
                LOG.info(_LI("The server_id is {0}.").format(server_id))
                LOG.info(_LI("The server_ids is {0}.").format(server_ids))
                if server_id in server_ids and self._check_device_exists():
                    return volume
            else:
                host_name = utils.get_host_name()
                host_names = self.get_host_names(attachments)
                LOG.info(_LI("The host_name is {0}.").format(host_name))
                LOG.info(_LI("The host_names is {0}.").format(host_names))
                if host_name in host_names:
                    return volume

            time.sleep(self.time_delay)

    def get_service_ids(self, volume_attachments):
        server_ids = []
        for i in range(0, len(volume_attachments)):
            server_ids.append(volume_attachments[i]['server_id'])
        return server_ids

    def get_host_names(self, volume_attachments):
        host_names = []
        for i in range(0, len(volume_attachments)):
            host_names.append(volume_attachments[i]['host_name'])
        return host_names
