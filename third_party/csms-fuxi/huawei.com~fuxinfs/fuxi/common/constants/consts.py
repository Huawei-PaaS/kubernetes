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

# Connector Type
# NoVA for indirect connect
# CINDER for direct connect
NOVA_CONNECTOR = 'NOVA'
CINDER_CONNECTOR = 'CINDER'

PROTO_DSWARE = "dsware"

# Storage Interface
STORAGEMANAGE_API = 'storagemanager'
OPENSTACK_API = 'openstack'

# Access Mode
AM_RWO = 'ReadWriteOnce'
AM_ROX = 'ReadOnlyMany'
AM_RWX = 'ReadWriteMany'


# If volume_provider is cinder, and if cinder volume is attached to this server
# by Nova, an link file will create under this directory to match attached
# volume. Of course, creating link file will decrease interact time
# with backend providers in some cases.
VOLUME_LINK_DIR = '/dev/disk/by-id/'

# Device scan interval
DEVICE_SCAN_TIME_DELAY = 0.3

# Timeout for scanning device
DEVICE_SCAN_TIMEOUT = 60

# Gigabyte scale relative to byte
G = 1024.0 * 1024.0 * 1024.0

# Timeout for querying meta-data from localhost
CURL_MD_TIMEOUT = 5

# default address to listen
DEFAULT_ADDRESS = '0.0.0.0'

# State code
GET_PARAMS_FAILED = '0001'
ATTACH_OK = '1000'
GET_VOLUME_RECORD_FAILED = '1001'
VOLUME_PATH_EXISTED = '1002'
VOLUME_PATH_NOT_EXISIED = '1003'
CONNECT_VOLUME_FAILED = '1004'
VOLUME_IS_UNSHAREABLE = '1005'
VOLUME_IS_MOUNTED = '1006'
VOLUME_ATTACHED_THIS_NO_DEV = '1007'

MOUNT_OK = '2000'
VOLUME_IS_ATTACHED_TO_OTHERS = '2001'
GET_VOLUME_DEVICE_PATH_FAILED = '2002'
GET_MOUNT_PATH_FAILED = '2003'

UNMOUNT_OK = '3000'

DETACH_OK = '4000'
DM_DEV_IS_NONE = '4001'
GET_VOLUME_BY_ID_FAILED = '4002'
VOLUME_STATE_IS_INCORRECT = '4003'
VOLUME_DISCONNECT_FAILED = '4004'
VOLUME_NO_STATUS = '4200'

CREATE_OK = '5001'
CREATE_ERROR = '5002'
GET_CONNECTOR_FAILED = '5003'
VOLUME_STATE_IS_WRONG = '5004'

DELETE_OK = '6001'
DELETE_ERROR = '6002'

ATTACH_ERROR = '60001'
MOUNT_ERROR = '60002'
UNMOUNT_ERROR = '60003'
DETACH_ERROR = '60004'

EXPAND_OK = '7001'
EXPAND_ERROR = '7002'

INVALID_USAGE = '10001'

VOLUME_NOT_FOUND = '404'

LOG_FILE = '/var/paas/sys/log/fuxi-nfs.log'
LOG_AUDIT_FILE = '/var/paas/sys/log/csms-fuxi/audit-nfs.log'
FUXI_LOGROTATE = '/etc/logrotate.d/fuxi-nfs.logrotate.conf'
MAGIC_CODE = '9a8c-33da-42ec-93d5'
DEFAULT_VOLUME_PROVIDER = {
    'cinder': 'providers.cinder.cinder_provider.CinderProvider',
    'storage_manager': 'providers.storage_manager.storage_manager_provider.StorageManagerProvider'
}

DECRYPT_FILE_NAME = 'temp.key'

