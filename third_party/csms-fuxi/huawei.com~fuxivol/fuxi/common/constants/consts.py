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
VOLUME_MOUNT_DEVICE_FAILED = '4005'

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

VOLUME_LIMIT_KEY_OK = '8001'
VOLUME_LIMIT_KEY_ERROR = '8002'

INVALID_USAGE = '10001'

VOLUME_NOT_FOUND = '404'

LOG_FILE = '/var/paas/sys/log/fuxi.log'
LOG_AUDIT_FILE = '/var/paas/sys/log/csms-fuxi/audit.log'
FUXI_LOGROTATE = '/etc/logrotate.d/fuxi.logrotate.conf'
MAGIC_CODE = '9a8c-33da-42ec-93d5'
DEFAULT_VOLUME_PROVIDER = {
    'cinder': 'providers.cinder.cinder_provider.CinderProvider',
    'storage_manager': 'providers.storage_manager.storage_manager_provider.StorageManagerProvider'
}

DECRYPT_FILE_NAME = 'temp.key'

DEV_PATH = '/dev/'
PCI_ADDRESS = '/sys/bus/pci/devices/'
PCI_BLOCK = '/block'
VM_SCSI_DEVICE_PATH = '/dev/disk/by-id/scsi-3'
BMS_SCSI_DEVICE_PATH = 'wwn-0x'

HC_ALL_MODE_DISK_VOLUME_LIMIT_KEY = "attachable-volumes-hc-all-mode-disk"
HC_VBD_MODE_DISK_VOLUME_LIMIT_KEY = "attachable-volumes-hc-vbd-mode-disk"
HC_SCSI_MODE_DISK_VOLUME_LIMIT_KEY = "attachable-volumes-hc-scsi-mode-disk"

OS_DOCKER_USED_HC_DISK_NUM = 2

# The following maximum values are just in the view of ECS, not CCE
DEFAULT_MAX_TOTAL_DISK_NUM_OF_ECS_VM = 24
DEFAULT_MAX_VBD_DISK_NUM_OF_ECS_VM = 24
DEFAULT_MAX_SCSI_DISK_NUM_OF_ECS_VM = 23

# The following maximum values are just in the view of BMS, not CCE
DEFAULT_MAX_TOTAL_DISK_NUM_OF_BMS_PM = 60
DEFAULT_ZERO_DISK_OF_BMS_PM = 0
DEFAULT_MAX_SCSI_DISK_NUM_OF_BMS_PM = 60

VBD_DISK_DEVICE_NAME_PREFIX = "/dev/vd"
VBD_DISK_DEVICE_NAME_PREFIX_IN_XEN = "/dev/xvd"
SCSI_DISK_DEVICE_NAME_PREFIX = "/dev/sd"
VBD_DISK_BUS_NAME = "virtio"
SCSI_DISK_BUS_NAME = "scsi"
HOST_SOURCE_ECS = "ecs"
HOST_SOURCE_BMS = "bms"
HC_DISK_MODE_VBD = "VBD"
HC_DISK_MODE_SCSI = "SCSI"

HOST_TYPE_VM = 'VirtualMachine'
HOST_TYPE_PM = 'BareMetal'
