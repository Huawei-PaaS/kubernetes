from common.exceptions import FuxiBaseException


class VolumeNotFoundException(FuxiBaseException):
    """Fuxi VolumeNotFoundException exception"""


class BlockDeviceAppNotFoundException(FuxiBaseException):
    """Fuxi BlockDeviceAppNotFoundException exception"""
