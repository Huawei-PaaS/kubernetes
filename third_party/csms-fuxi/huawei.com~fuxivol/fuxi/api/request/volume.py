from common.utils import volume as volume_util
from common.constants.consts import AM_RWO


def generate_create_params(params):
    volume_name = params.get('kubernetes.io/name', None)
    volume_size = params.get('kubernetes.io/size', None)
    volume_zone = params.get('kubernetes.io/zone', None)
    volume_desc = params.get('kubernetes.io/description', None)
    volume_type = params.get('kubernetes.io/volumetype', None)
    snapshot_id = params.get('kubernetes.io/snapshot', None)
    multi_attach = params.get('kubernetes.io/accessmode', AM_RWO)
    shareable = volume_util.is_volume_sharable(multi_attach)
    volume_paasthrough = params.get('kubernetes.io/hw:passthrough', 'false')
    crypt_key_id = params.get('paas.storage.io/cryptKeyId', '')

    create_params = {"name": volume_name,
                     "size": int(volume_size),
                     "zone": volume_zone,
                     "type": volume_type,
                     "desc": volume_desc,
                     "shareable": shareable,
                     "snapshot": snapshot_id,
                     "passthrough": volume_paasthrough,
                     "cryptKeyId": crypt_key_id
                     }
    return create_params
