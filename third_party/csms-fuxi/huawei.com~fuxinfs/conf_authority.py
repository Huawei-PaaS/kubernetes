import sys
import os
import stat
import ConfigParser


def get_log_path():
    log_path = "/usr/libexec/kubernetes/kubelet-plugins/volume/exec/huawei.com~fuxinfs/etc/fuxi.conf"
    config = ConfigParser.RawConfigParser()
    config.read(log_path)
    log_file = config.get("DEFAULT", "log_file")
    audit_file = config.get("DEFAULT", "log_audit")
    if log_file and audit_file:
        return log_file, audit_file
    return None, None


def authority_config(install_path):
    try:
        ret = authority_dir_file(os.path.dirname(install_path), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        if ret is False:
            print "authority_dir_file: Failed"
            return False

        log_file, audit_file = get_log_path()
        if log_file is None:
            print "Failed to get path of the log_file!!!"
            return False

        if audit_file is None:
            print "Failed to get path of the audit_file!!!"
            return False
        if not os.path.exists(log_file):
            log_path = os.path.dirname(log_file)
            if not os.path.exists(log_path):
                os.mkdir(log_path)
            os.mknod(log_file)

        if not os.path.exists(audit_file):
            log_path = os.path.dirname(audit_file)
            if not os.path.exists(log_path):
                os.mkdir(log_path)
            os.mknod(audit_file)

        audit_path = os.path.dirname(audit_file)
        os.chmod(audit_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        os.chmod(audit_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        os.chmod(log_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        os.chmod('/etc/logrotate.d/fuxi-nfs.logrotate.conf', stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        os.chmod(install_path + '/etc/fuxi.conf', stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        print "Success modified authority of file and path!"
        return True
    except Exception as e:
        print "authority_config: Failed to modified authority of the file! Err: {0}".format(e.message)
        return False


def authority_dir_file(path, status):
    if not os.path.exists(path):
        return False
    try:
        if os.path.isfile(path):
            if not (path.find("lib-dynload") > -1 or path.find("config") > -1 or path.find(
                    "encodings") > -1 or os.path.islink(path)):
                os.chmod(path, status)
            return True
        path_list = os.path.os.listdir(path)
        if len(path_list) == 0:
            return True
        else:
            for temp_list in path_list:
                subdirectory = os.path.join(path, temp_list)
                if (subdirectory.endswith("xml") and os.path.isfile(subdirectory)) or subdirectory.endswith("mkfs") or subdirectory.endswith("unmount") or subdirectory.endswith("mount"):
                    os.chmod(subdirectory, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
                    continue
                elif subdirectory.find("lib-dynload") > -1 or subdirectory.find("config") > -1 or subdirectory.find(
                        "encodings") > -1 or os.path.islink(subdirectory):
                    continue
                else:
                    os.chmod(subdirectory, status)
                ret = authority_dir_file(subdirectory, status)
                if ret is False:
                    return False
    except Exception as e:
        print "authority_dir_file: Failed to modified authority of the file! Err: {0}".format(e.message)
        return False


def main():
    try:
        install_file = sys.path[0]
    except Exception as e:
        print "The path of the modified file is wrong! Err: {0}".format(e.message)
        return False
    ret = authority_config(install_file)
    if ret is False:
        print "conf_authority: Failed to modified authority of the file!!!"
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
