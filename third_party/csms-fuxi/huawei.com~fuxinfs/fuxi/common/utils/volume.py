from common.constants import consts


def is_volume_sharable(multi_attach):
    return multi_attach == consts.AM_ROX or multi_attach == consts.AM_RWX


def is_volume_public(is_public):
    if is_public == "true":
        return True
    return False
