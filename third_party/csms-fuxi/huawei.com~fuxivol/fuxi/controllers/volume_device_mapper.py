import os
from clients import utils
from common.constants import consts
from common.i18n import _LI, _LE
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def add_dev_to_volume_mapping(dev_path, volume_id):
    link_path = os.path.join(consts.VOLUME_LINK_DIR, volume_id)
    try:
        if os.path.exists(link_path):
            utils.execute('rm', '-f', link_path, run_as_root=True)
        utils.execute('ln', '-s', dev_path, link_path,
                      run_as_root=True)
        return True
    except Exception as e:
        LOG.exception(e.message)
        LOG.error(_LE("Error happened when create link file for "
                      "block device attached by Nova."))
        return False


def remove_dev_to_volume_mapping(volume_id):
    link_path = consts.VOLUME_LINK_DIR + volume_id
    try:
        LOG.info(_LI("Remove the link_path of {0}.").format(link_path))
        utils.execute('rm', '-f', link_path, run_as_root=True)
    except Exception as e:
        LOG.exception(e.message)
        msg = _LE("Error happened when remove  volume link_path. Error: {0}").format(e)
        LOG.warning(msg)


def get_volume_by_dev(device):
    pass
