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

import os
import requests
import urlparse as parse
from common.constants import consts
from common.i18n import _LI, _LE, _LW
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import uuidutils
from cinderclient import client as cinder_client
from novaclient import client as nova_client
from keystoneauth1.session import Session
from keystoneclient.auth import get_plugin_class
from common import config

cloud_init_conf = '/var/lib/cloud/instances'
server_conf = '/var/paas/conf/server.conf'
LOG = logging.getLogger(__name__)


def get_host_name():
    if os.path.exists(cloud_init_conf):
        host_name = get_server_id()
        if host_name:
            msg = "Get host name from cloud-init %s" % host_name
            LOG.info(msg)
            return host_name
    try:
        instance_uuid = uuidutils.generate_uuid()
        instance_uuid_dir = cloud_init_conf + "/" + instance_uuid
        os.makedirs(instance_uuid_dir)
        return instance_uuid
    except Exception as e:
        LOG.exception(e.message)
        LOG.error(_LE("Get get_hostname from cloud-init failed."))
        return None


def get_server_id():
    if os.path.exists(server_conf):
        try:
            f = open(server_conf)
            serverid = ''
            for i in f.readlines():
                if len(i.strip()) != 0:
                    serverid = i
                    break
            server_id = serverid.rstrip('\n')
            if uuidutils.is_uuid_like(server_id):
                LOG.info(_LI("instance uuid from server conf is:{0}").format(server_id))
                return server_id
        except Exception as e:
            LOG.exception(e.message)
            LOG.error(_LE("Get instance_uuid from server conf failed.Ex: {0}".format(e.message)))
        finally:
            f.close()
    else:
        LOG.warning(_LW("server conf file not exist ! "))

    LOG.warning(_LW("get server id from server conf {0} failed").format(server_conf))
    try:
        inst_uuid = ''
        inst_uuid_count = 0
        dirs = os.listdir(cloud_init_conf)
        for uuid_dir in dirs:
            if uuidutils.is_uuid_like(uuid_dir):
                LOG.info(_LI("instance uuid :{0}").format(uuid_dir))
                inst_uuid = uuid_dir
                inst_uuid_count += 1
        if inst_uuid_count == 1:
            return inst_uuid

        LOG.warning(_LW("There are not one instance uuids under {0}").format(cloud_init_conf))
    except Exception as e:
        LOG.exception(e.message)
        LOG.error(_LE("Get instance_uuid from cloud-init failed.Ex: {0}".format(e.message)))

    try:
        resp = requests.get('http://169.254.169.254/openstack/',
                            timeout=consts.CURL_MD_TIMEOUT)
        metadata_api_versions = resp.text.split()
        metadata_api_versions.sort(reverse=True)
    except Exception as e:
        LOG.exception(e.message)
        LOG.error(_LE("Get metadata from metadata server failed. Error: {0}").format(e))
        return None

    for api_version in metadata_api_versions:
        metadata_url = ''.join(['http://169.254.169.254/openstack/',
                                api_version,
                                '/meta_data.json'])
        try:
            resp = requests.get(metadata_url,
                                timeout=consts.CURL_MD_TIMEOUT)
            metadata = resp.json()
            if metadata.get('uuid', None):
                return metadata['uuid']
        except Exception as e:
            LOG.exception(e.message)
            msg = _LE("Get instance_uuid from metadata server {} "
                      "failed. Error: {}").format(metadata_url, e)
            LOG.error(msg)
            continue

    return None


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

