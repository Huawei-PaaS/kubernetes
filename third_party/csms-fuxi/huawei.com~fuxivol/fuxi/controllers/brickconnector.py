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

from clients import utils
from clients.dsware import dsware_client
from common.constants import consts
from common.i18n import _LI, _LE
from os_brick.initiator import connector
from oslo_log import log as logging
from hw_brick.initiator import connector as hwconnector

LOG = logging.getLogger(__name__)


def brick_get_connector_properties(my_ip, multipath=False, enforce_multipath=False):
    """Wrapper to automatically set root_helper in brick calls.

    :param my_ip : host's ip address
    :param multipath: A boolean indicating whether the connector can
                      support multipath.
    :param enforce_multipath: If True, it raises exception when multipath=True
                              is specified but multipathd is not running.
                              If False, it falls back to multipath=False
                              when multipathd is not running.
    """

    root_helper = utils.get_root_helper()
    return connector.get_connector_properties(root_helper,
                                              my_ip,
                                              multipath,
                                              enforce_multipath)


def brick_get_connector(protocol, driver=None,
                        use_multi_path=False,
                        device_scan_attempts=3,
                        *args, **kwargs):
    """Wrapper to get a brick connector object.

    This automatically populates the required protocol as well
    as the root_helper needed to execute commands.
    """

    root_helper = utils.get_root_helper()
    LOG.info(_LI("Volume connector protocol {0}".format(protocol)))
    if consts.PROTO_DSWARE == protocol:
        return dsware_client.HuaweiDswareConnector(root_helper=root_helper,
                                                     driver=driver,
                                                     *args, **kwargs)
    else:
        return hwconnector.Hw_InitiatorConnector.factory(
                protocol, root_helper,
                driver=driver,
                use_multipath=use_multi_path,
                device_scan_attempts=device_scan_attempts,
                *args, **kwargs)


