#!/usr/bin/env python

import socket

import os
import re
from clients import utils
from common.i18n import _LI, _LE
from os_brick.initiator import connector
from oslo_concurrency import lockutils
from oslo_concurrency import processutils as putils
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
synchronized = lockutils.synchronized_with_prefix('os-brick-')


class HuaweiDswareConnector(connector.InitiatorConnector):
    """os_brick Dsware Volume Driver, access huawei Dsware"""

    def __init__(self, root_helper, driver=None,
                 execute=putils.execute, *args, **kwargs):
        """Create back-end to dsware."""
        super(HuaweiDswareConnector, self).__init__(root_helper, driver=driver,
                                                    execute=execute, *args, **kwargs)

    def _create_dev_path(self, source, volume_id):
        # type: (object, object) -> object
        dev_path = "/dev/disk/by-id/dsware-%s" % volume_id
        if os.path.lexists(dev_path):
            cmd_unlink = ['unlink', dev_path]
            utils.execute(*cmd_unlink, run_as_root=True)
        cmd_link = ['ln', '-s', source, dev_path]
        utils.execute(*cmd_link, run_as_root=True)
        return dev_path

    def _remove_dev_path(self, volume_id):
        dev_path = "/dev/disk/by-id/dsware-%s" % volume_id
        if os.path.lexists(dev_path):
            cmd_unlink = ['unlink', dev_path]
            utils.execute(*cmd_unlink, run_as_root=True)

    def _analyse_output(self, out):
        if out is not None:
            analyse_result = {}
            out_temp = out.split('\n')
            for line in out_temp:
                if re.search('^ret_code=', line):
                    analyse_result['ret_code'] = line[9:]
                elif re.search('^ret_desc=', line):
                    analyse_result['ret_desc'] = line[9:]
                elif re.search('^dev_addr=', line):
                    analyse_result['dev_addr'] = line[9:]
            return analyse_result
        else:
            return None

    def _attach_volume(self, volume_name):

        cmd = ['vbs_cli', '-c', 'attach', '-v', volume_name]
        out, err = utils.execute(*cmd, run_as_root=True)
        analyse_result = self._analyse_output(out)
        LOG.info(_LI("_attach_volume out is %s" % analyse_result))
        return analyse_result

    def _detach_volume(self, volume_name):
        cmd = ['vbs_cli', '-c', 'detach', '-v', volume_name]
        out, err = utils.execute(*cmd, run_as_root=True)
        analyse_result = self._analyse_output(out)
        LOG.info(_LI("_detach_volume out is %s" % analyse_result))
        return analyse_result

    @synchronized('connect_volume')
    def connect_volume(self, connection_properties):
        """Connect the volume. Returns path for cinder."""
        LOG.info('connection_properties %s' % connection_properties)
        device_info = {'type': 'block'}

        # check connection_properties params
        volume_name = connection_properties['volume_name']
        volume_id = connection_properties['volume']['id']
        if (volume_name is None) or (volume_id is None):
            msg = "some important infor missing, connect volume failed."
            LOG.error(_LE(msg))
            return None

        # get volume name, 50151401 volume or snapshot has been attached
        out = self._attach_volume(volume_name)
        if (out is not None and int(out['ret_code']) not in (0, 50151401)) or out is None:
            msg = "initialize_connection failed."
            LOG.error(_LE(msg))
            return None

        device_info['path'] = self._create_dev_path(out['dev_addr'], volume_id)
        return device_info

    @synchronized('connect_volume')
    def disconnect_volume(self, connection_properties, device_info):
        """Disconnect the volume."""
        LOG.info('connection_properties %s' % connection_properties)

        # check connection_properties params
        volume_name = connection_properties['volume_name']
        volume_id = connection_properties['volume']['id']
        if (volume_name is None) or (volume_id is None):
            msg = "some important infor missing, disconnect volume failed."
            LOG.error(_LE(msg))
            return False

        # delete the symlink
        self._remove_dev_path(volume_id)
        out = self._detach_volume(volume_name)
        if (out is not None and int(out['ret_code']) not in (0, 50151601)) or out is None:
            msg = "detach volume failed."
            LOG.error(_LE(msg))
            return False
        return True

    def check_valid_device(self, path, run_as_root=True):
        """Test to see if the device path is a real device.

        :param path: The file system path for the device.
        :type path: str
        :param run_as_root: run the tests as root user?
        :type run_as_root: bool
        :returns: bool
        """
        cmd = ('dd', 'if=%(path)s' % {"path": path}, 'of=/dev/null', 'count=1')
        out, info = None, None
        try:
            out, info = self._execute(*cmd, run_as_root=run_as_root,
                                      root_helper=self._root_helper)
        except putils.ProcessExecutionError as e:
            LOG.exception(e.message)
            LOG.error(_LE("Failed to access the device on the path "
                          "%(path)s: %(error)s %(info)s."),
                      {"path": path, "error": e.stderr,
                       "info": info})
            return False
        # If the info is none, the path does not exist.
        if info is None:
            LOG.error(_LE("Info is none due to the path dose not exist."))
            return False
        return True

    @synchronized('extend_volume')
    def extend_volume(self, connection_properties):
        raise NotImplementedError

    def get_volume_paths(self, connection_properties):
        raise NotImplementedError

    def get_search_path(self):
        return '/dev/disk/by-id'

    def get_all_available_volumes(self, connection_properties=None):
        return []

    @staticmethod
    def get_connector_properties(root_helper, my_ip, multipath, enforce_multipath, host=None):
        props = dict()
        props['ip'] = my_ip
        props['host'] = host if host else socket.gethostname()
        return props
