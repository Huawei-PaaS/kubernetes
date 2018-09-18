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


class CinderException(Exception):
    """Default Cinder exception"""


class TimeoutException(CinderException):
    """A timeout on waiting for volume to reach destination end state."""


class UnexpectedStateException(CinderException):
    """Unexpected volume state appeared"""


class LoopExceeded(CinderException):
    """Raised when ``loop_until`` looped too many times."""


class NotFound(CinderException):
    """The resource could not be found"""


class TooManyResources(CinderException):
    """Find too many resources."""


class InvalidInput(CinderException):
    """Request data is invalidate"""


class NotMatchedState(CinderException):
    """Current state not match to expected state"""
    message = "Current state not match to expected state."


class MakeFileSystemException(CinderException):
    """Unexpected error while make file system."""


class MountException(CinderException):
    """Unexpected error while mount device."""


class UnmountException(CinderException):
    """Unexpected error while do umount"""


class FuxiBaseException(Exception):
    """Fuxi base exception"""
    def __init__(self, msg):
        super(FuxiBaseException, self).__init__(msg)
        self.msg = msg


class StorageManagerClientException(FuxiBaseException):
    """Storage Manager base exception"""
