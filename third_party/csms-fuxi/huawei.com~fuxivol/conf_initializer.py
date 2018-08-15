import os
import traceback

from fuxi.common import config


def extract_namespace_from_certificate_by_cmd(certificate_file):
    split_word = '1.1.1.2='
    try:
        if os.path.exists(certificate_file):
            cert_cmd = 'openssl x509 -in ' + certificate_file + ' -text -noout'
            certificate_string = os.popen(cert_cmd).read()
            if len(certificate_string) < 1:
                print "Invalid certificate!"
                return None

            projects_string = certificate_string.split(split_word)
            if len(projects_string) <= 1:
                print "Invalid certificate!"
                return None
            namespace_string = projects_string[1]

            namespace = namespace_string.split(':')
            if len(namespace) < 1:
                print "Invalid certificate!"
                return None
            namespace_certificate = namespace[0]

            print "Extract namespace from certificate successful, namespace: %s" % namespace_certificate
            return namespace_certificate
        else:
            print "Certificate not exist!"
            return None
    except Exception as ex:
        traceback.print_exc()
        print "Failed to extract namespace from certificate! Err: {0}".format(ex.message)
        return None


def main():
    config.init()
    config.enable()
    cluster_mode = os.getenv("cluster_mode", None)
    if cluster_mode == "" or cluster_mode is None:
        certificate_file = config.CONF.storage_manager.ssl_cert
        namespace = extract_namespace_from_certificate_by_cmd(certificate_file)
    else:
        namespace = "default"

    if namespace is None:
        return None
    config.modify("STORAGE_MANAGER", "namespace", namespace)
    return namespace


if __name__ == "__main__":
    main()
