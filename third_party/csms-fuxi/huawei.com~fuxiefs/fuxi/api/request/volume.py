from common.utils import volume as volume_util
from common.constants.consts import AM_RWO


def generate_create_params(params):
    volume_name = params.get('kubernetes.io/name', None)
    volume_size = params.get('kubernetes.io/size', None)
    description = params.get('kubernetes.io/description', None)
    volume_zone = params.get('kubernetes.io/zone', None)
    volume_type = params.get('kubernetes.io/volumetype', None)
    storage_type = params.get('kubernetes.io/storagetype', None)
    snapshotid = params.get('kubernetes.io/snapshotid', None)
    multiattach = params.get('kubernetes.io/multiattach', True)
    share_type = params.get('kubernetes.io/share_type', None)
    share_proto = params.get('kubernetes.io/share_proto', None)
    access_to = params.get('kubernetes.io/access_to', None)
    access_level = params.get('kubernetes.io/access_level', None)
    vpc_id = params.get('kubernetes.io/vpcid', None)
    security_group_id = params.get('kubernetes.io/securitygroupid', None)
    net_id = params.get('kubernetes.io/netid', None)

    create_params = {"name": volume_name,
                     "size": int(volume_size),
                     "description": description,
                     "availability_zone": volume_zone,
                     "volume_type": volume_type,
                     "vpc_id": vpc_id,
                     "security_group_id": security_group_id,
                     "net_id": net_id,
                     "storage_type": storage_type,
                     "snapshot_id": snapshotid,
                     "multiattach": multiattach,
                     "share_type": share_type,
                     "share_proto": share_proto,
                     "access_to": access_to,
                     "access_level": access_level,
                     }
    return create_params
