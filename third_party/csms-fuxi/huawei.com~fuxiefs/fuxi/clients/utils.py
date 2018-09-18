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

import urlparse as parse
from oslo_concurrency import processutils
from oslo_log import log as logging
from cinderclient import client as cinder_client
from novaclient import client as nova_client
from keystoneauth1.session import Session
from keystoneclient.auth import get_plugin_class
from common import config

LOG = logging.getLogger(__name__)


def get_root_helper():
    return 'sudo cinder-rootwrap /etc/cinder/rootwrap.conf'


def execute(*cmd, **kwargs):
    if 'run_as_root' in kwargs and 'root_helper' not in kwargs:
        kwargs['root_helper'] = get_root_helper()

    return processutils.execute(*cmd, **kwargs)


def _openstack_auth_from_config(**config):
    if config.get("username") and config.get("password"):
        plugin_class = get_plugin_class('password')
    else:
        plugin_class = get_plugin_class('token')
    plugin_options = plugin_class.get_options()
    plugin_kwargs = {}
    for option in plugin_options:
        if option.dest in config:
            plugin_kwargs[option.dest] = config[option.dest]
    return plugin_class(**plugin_kwargs)


def get_keystone_session():
    cfg = dict()

    cfg['auth_url'] = config.get("CINDER", "auth_url", None)
    cfg['username'] = config.get("CINDER", "username", None)
    cfg['password'] = config.CONF.cinder.password

    if '/v3' in parse.urlparse(config.get("CINDER", "auth_url", None)).path:
        cfg['user_domain_name'] = config.get("CINDER", "user_domain_name", None)
        cfg['project_domain_name'] = config.get("CINDER", "project_domain_name", None)
        cfg['project_name'] = config.get("CINDER", "tenant_name", None)
    else:
        cfg['tenant_name'] = config.get("CINDER", "tenant_name", None)
    return Session(auth=_openstack_auth_from_config(**cfg), verify=False)


def get_nova_client(session=None, region=None):
    if not session:
        session = get_keystone_session()
    if not region and config.get("CINDER", "region", None):
        return nova_client.Client(session=session, region_name=config.get("CINDER", "region", None), version=2)
    return nova_client.Client(session=session, region_name=region, version=2)


def get_cinder_client(session=None, region=None):
    if not session:
        session = get_keystone_session()
    if not region and config.get("CINDER", "region", None):
        return cinder_client.Client(session=session, region_name=config.get("CINDER", "region", None), version=2)
    return cinder_client.Client(session=session, region_name=region, version=2)

