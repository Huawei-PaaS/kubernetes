import os
import sys
import traceback
from fuxi.common import config


def initialize_file_lock(lock_path, filelock):
    try:
        lock_file = os.path.join(lock_path, filelock)
        if not os.path.exists(lock_file):
            lock_file_handler = open(lock_file, "w")
            lock_file_handler.close()
            print "Success to create lock file"
        return True
    except Exception:
        print "Failed to create lock file!"
        return False


def main():
    try:
        root_path = sys.path[0]
        lock_path = root_path + '/lock/'
        if not os.path.exists(lock_path):
            os.makedirs(lock_path)
    except Exception as ex:
        traceback.print_exc()
        print "Failed to create lock path! Err: {0}".format(ex.message)
        sys.exit(1)

    filelocks = ['.mount', '.unmount', '.mkfs']
    for filelock in filelocks:
        ret = initialize_file_lock(lock_path, filelock)
        if ret is False:
            sys.exit(1)

    ret = config.modify("STORAGE_MANAGER", "lock_path", lock_path)
    if ret:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
