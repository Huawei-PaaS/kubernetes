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
    storage_type = params.get('kubernetes.io/storagetype', None)
    share_proto = params.get('kubernetes.io/shareproto', None)
    ispublic = params.get('kubernetes.io/ispublic', False)
    is_public = volume_util.is_volume_public(ispublic)
    access_to = params.get('kubernetes.io/accessto', None)
    access_level = params.get('kubernetes.io/accesslevel', None)
    crypt_key_id = params.get('paas.storage.io/cryptKeyId', '')
    crypt_domain_id = params.get('paas.storage.io/cryptDomainId', '')
    crypt_alias = params.get('paas.storage.io/cryptAlias', '')

    create_params = {"name": volume_name,
                     "size": int(volume_size),
                     "zone": volume_zone,
                     "type": volume_type,
                     "desc": volume_desc,
                     "shareable": shareable,
                     "snapshot": snapshot_id,
                     "storage_type": storage_type,
                     "share_proto": share_proto,
                     "is_public": is_public,
                     "access_to": access_to,
                     "access_level": access_level,
                     "cryptKeyId": crypt_key_id,
                     "cryptDomainId": crypt_domain_id,
                     "cryptAlias": crypt_alias
                     }
    return create_params
