import os
import signal

import requests
from common.config import CONF
from common.i18n import _LE
from common.utils.certificate_crypt import crypt
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

class RestApiTimeout():
    """ RestApiTimeout for use with the `with` statement. """

    class RestApiTimeoutException(Exception):
        """ Simple Exception to be called on timeouts. """
        pass

    def _handleTimeout(self, signum, frame):
        """ Raise an RestApiTimeoutException.

        This is intended for use as a signal handler.
        The signum and frame arguments passed to this are ignored.

        """
        raise RestApiTimeout.RestApiTimeoutException()

    def __init__(self, timeout=10):
        self.timeout = timeout
        signal.signal(signal.SIGALRM, self._handleTimeout)

    def __enter__(self):
        signal.alarm(self.timeout)

    def __exit__(self, exc_type, exc_value, traceback):
        signal.alarm(0)
        return exc_type is RestApiTimeout.RestApiTimeoutException

def send_request(method, url, data=None, exec_timeout=CONF.exec_timeout):
    if method == "POST":
        return _send_post_request(url, data, exec_timeout)
    elif method == "GET":
        return _send_get_request(url, exec_timeout)
    elif method == "DELETE":
        return _send_delete_request(url, exec_timeout)
    elif method == "PUT":
        return _send_put_method(url, data, exec_timeout)
    else:
        raise Exception("Http method not support!")


def _send_post_request(url, data=None, exec_timeout=None):
    headers, ca_file, cert_file, key_file, verify_state = verification_certificate()

    try:
        if exec_timeout < 5:
            exec_timeout = 5
        with RestApiTimeout(exec_timeout):
            return True, requests.post(url,
                                       headers=headers,
                                       data=data,
                                       verify=ca_file,
                                       cert=(cert_file, key_file),
                                       timeout=(5.0,10.0))  # float values, tcp connect timeout, and read timeout before getting first byte data.
        msg = _LE("Overall execution timeout {0}s for sending post url {1}").format(exec_timeout, url)
        LOG.error(msg)
        return False, msg
    except Exception as e:
        LOG.exception(e.message)
        msg = _LE("Failed to send post request.Err: {0}").format(e.message)
        LOG.error(msg)
        message = _LE("Failed to send post request.")
        return False, message

    finally:
        if verify_state and os.path.isfile(key_file):
            crypt.delete_temp_decrypt_key_path()


def _send_get_request(url, exec_timeout=None):
    headers, ca_file, cert_file, key_file, verify_state = verification_certificate()

    try:
        if exec_timeout < 5:
            exec_timeout = 5
        with RestApiTimeout(exec_timeout):
            return True, requests.get(url,
                                      headers=headers,
                                      verify=ca_file,
                                      cert=(cert_file, key_file),
                                      timeout=(5.0,10.0))  # float values, tcp connect timeout, and read timeout before getting first byte data.
        msg = _LE("Overall execution timeout {0}s for sending get requset, url: {1}").format(exec_timeout, url)
        LOG.error(msg)
        return False, msg
    except Exception as e:
        LOG.exception(e.message)
        msg = _LE("Failed to send get request.Err: {0}").format(e.message)
        LOG.error(msg)
        message = _LE("Failed to send get request.")
        return False, message

    finally:
        if verify_state and os.path.isfile(key_file):
            crypt.delete_temp_decrypt_key_path()


def _send_delete_request(url, exec_timeout=None):
    headers, ca_file, cert_file, key_file, verify_state = verification_certificate()

    try:
        if exec_timeout < 5:
            exec_timeout = 5
        with RestApiTimeout(exec_timeout):
            return True, requests.delete(url,
                                         headers=headers,
                                         verify=ca_file,
                                         cert=(cert_file, key_file),
                                         timeout=(5.0,10.0))  # float values, tcp connect timeout, and read timeout before getting first byte data.
        msg = _LE("Overall execution timeout {0}s for sending delete requst, url: {1}").format(exec_timeout, url)
        LOG.error(msg)
        return False, msg
    except Exception as e:
        LOG.exception(e.message)
        msg = _LE("Failed to send delete request.Err: {0}").format(e.message)
        LOG.error(msg)
        message = _LE("Failed to send delete request.")
        return False, message

    finally:
        if verify_state and os.path.isfile(key_file):
            crypt.delete_temp_decrypt_key_path()


def _send_put_method(url, data=None, exec_timeout=None):
    headers, ca_file, cert_file, key_file, verify_state = verification_certificate()

    try:
        if exec_timeout < 5:
            exec_timeout = 5
        with RestApiTimeout(exec_timeout):
            return True, requests.put(url,
                                      headers=headers,
                                      data=data,
                                      verify=ca_file,
                                      cert=(cert_file, key_file),
                                      timeout=(5.0,10.0))  # float values, tcp connect timeout, and read timeout before getting first byte data.
        msg = _LE("Overall execution timeout {0}s for sending put requst, url: {1}").format(exec_timeout, url)
        LOG.error(msg)
        return False, msg
    except Exception as e:
        LOG.exception(e.message)
        msg = _LE("Failed to send put request.Err: {0}").format(e.message)
        LOG.error(msg)
        message = _LE("Failed to send put request.")
        return False, message

    finally:
        if verify_state and os.path.isfile(key_file):
            crypt.delete_temp_decrypt_key_path()


def verification_certificate():
    headers = {'Content-Type': 'application/json'}
    verify_state = CONF.storage_manager.verify
    if verify_state:
        ca_file = crypt.get_ca_file()
        cert_file = crypt.get_cert_file()
        key_file = crypt.create_temp_decrypt_key_path()
        if key_file is None:
            msg = _LE("Failed to create decrypt key")
            LOG.error(msg)
            return False, None, None, None, verify_state
        else:
            return headers, ca_file, cert_file, key_file, verify_state
    else:
        return False, None, None, None, None
