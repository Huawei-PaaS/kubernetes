# -*- encoding:utf-8 -*-
import os
import stat

from common.constants import consts

MOUNT_DEVICE_SEQNUM_MAP_IDE = {
    '/dev/sda': 1, '/dev/vda': 1, '/dev/xvda': 1,
    '/dev/sdb': 1001, '/dev/vdb': 1001, '/dev/xvdb': 1001,
    '/dev/sdc': 1002, '/dev/vdc': 1002, '/dev/xvdc': 1002,
    '/dev/sdd': 1003, '/dev/vdd': 1003, '/dev/xvdd': 1003,
    '/dev/sde': 2, '/dev/vde': 2, '/dev/xvde': 2,
    '/dev/sdf': 3, '/dev/vdf': 3, '/dev/xvdf': 3,
    '/dev/sdg': 4, '/dev/vdg': 4, '/dev/xvdg': 4,
    '/dev/sdh': 5, '/dev/vdh': 5, '/dev/xvdh': 5,
    '/dev/sdi': 6, '/dev/vdi': 6, '/dev/xvdi': 6,
    '/dev/sdj': 7, '/dev/vdj': 7, '/dev/xvdj': 7,
    '/dev/sdk': 8, '/dev/vdk': 8, '/dev/xvdk': 8,
    '/dev/sdl': 9, '/dev/vdl': 9, '/dev/xvdl': 9,
    '/dev/sdm': 10, '/dev/vdm': 10, '/dev/xvdm': 10,
    '/dev/sdn': 11, '/dev/vdn': 11, '/dev/xvdn': 11,
    '/dev/sdo': 12, '/dev/vdo': 12, '/dev/xvdo': 12,
    '/dev/sdp': 13, '/dev/vdp': 13, '/dev/xvdp': 13,
    '/dev/sdq': 14, '/dev/vdq': 14, '/dev/xvdq': 14,
    '/dev/sdr': 15, '/dev/vdr': 15, '/dev/xvdr': 15,
    '/dev/sds': 16, '/dev/vds': 16, '/dev/xvds': 16,
    '/dev/sdt': 17, '/dev/vdt': 17, '/dev/xvdt': 17,
    '/dev/sdu': 18, '/dev/vdu': 18, '/dev/xvdu': 18,
    '/dev/sdv': 19, '/dev/vdv': 19, '/dev/xvdv': 19,
    '/dev/sdw': 20, '/dev/vdw': 20, '/dev/xvdw': 20,
    '/dev/sdx': 21, '/dev/vdx': 21, '/dev/xvdx': 21,
    '/dev/sdy': 22, '/dev/vdy': 22, '/dev/xvdy': 22,
    '/dev/sdz': 1004, '/dev/vdz': 1004, '/dev/xvdz': 1004,
    '/dev/sdaa': 23, '/dev/vdaa': 23, '/dev/xvdaa': 23,
    '/dev/sdab': 24, '/dev/vdab': 24, '/dev/xvdab': 24,
    '/dev/sdac': 25, '/dev/vdac': 25, '/dev/xvdac': 25,
    '/dev/sdad': 26, '/dev/vdad': 26, '/dev/xvdad': 26,
    '/dev/sdae': 27, '/dev/vdae': 27, '/dev/xvdae': 27,
    '/dev/sdaf': 28, '/dev/vdaf': 28, '/dev/xvdaf': 28,
    '/dev/sdag': 29, '/dev/vdag': 29, '/dev/xvdag': 29,
    '/dev/sdah': 30, '/dev/vdah': 30, '/dev/xvdah': 30,
    '/dev/sdai': 31, '/dev/vdai': 31, '/dev/xvdai': 31,
    '/dev/sdaj': 32, '/dev/vdaj': 32, '/dev/xvdaj': 32,
    '/dev/sdak': 33, '/dev/vdak': 33, '/dev/xvdak': 33,
    '/dev/sdal': 34, '/dev/vdal': 34, '/dev/xvdal': 34,
    '/dev/sdam': 35, '/dev/vdam': 35, '/dev/xvdam': 35,
    '/dev/sdan': 36, '/dev/vdan': 36, '/dev/xvdan': 36,
    '/dev/sdao': 37, '/dev/vdao': 37, '/dev/xvdao': 37,
    '/dev/sdap': 38, '/dev/vdap': 38, '/dev/xvdap': 38,
    '/dev/sdaq': 39, '/dev/vdaq': 39, '/dev/xvdaq': 39,
    '/dev/sdar': 40, '/dev/vdar': 40, '/dev/xvdar': 40,
    '/dev/sdas': 41, '/dev/vdas': 41, '/dev/xvdas': 41,
    '/dev/sdat': 42, '/dev/vdat': 42, '/dev/xvdat': 42,
    '/dev/sdau': 43, '/dev/vdau': 43, '/dev/xvdau': 43,
    '/dev/sdav': 44, '/dev/vdav': 44, '/dev/xvdav': 44,
    '/dev/sdaw': 45, '/dev/vdaw': 45, '/dev/xvdaw': 45,
    '/dev/sdax': 46, '/dev/vdax': 46, '/dev/xvdax': 46,
    '/dev/sday': 47, '/dev/vday': 47, '/dev/xvday': 47,
    '/dev/sdaz': 48, '/dev/vdaz': 48, '/dev/xvdaz': 48,
    '/dev/sdba': 49, '/dev/vdba': 49, '/dev/xvdba': 49,
    '/dev/sdbb': 50, '/dev/vdbb': 50, '/dev/xvdbb': 50,
    '/dev/sdbc': 51, '/dev/vdbc': 51, '/dev/xvdbc': 51,
    '/dev/sdbd': 52, '/dev/vdbd': 52, '/dev/xvdbd': 52,
    '/dev/sdbe': 53, '/dev/vdbe': 53, '/dev/xvdbe': 53,
    '/dev/sdbf': 54, '/dev/vdbf': 54, '/dev/xvdbf': 54,
    '/dev/sdbg': 55, '/dev/vdbg': 55, '/dev/xvdbg': 55,
    '/dev/sdbh': 56, '/dev/vdbh': 56, '/dev/xvdbh': 56,
    '/dev/sdbi': 57, '/dev/vdbi': 57, '/dev/xvdbi': 57,
    '/dev/sdbj': 58, '/dev/vdbj': 58, '/dev/xvdbj': 58,
    '/dev/sdbk': 59, '/dev/vdbk': 59, '/dev/xvdbk': 59,
    '/dev/sdbl': 60, '/dev/vdbl': 60, '/dev/xvdbl': 60,
    '/dev/sdbm': 61, '/dev/vdbm': 61, '/dev/xvdbm': 61
}


# get the key that it has the same value
def search_dir(pardir):
    res_lst = []
    if pardir in MOUNT_DEVICE_SEQNUM_MAP_IDE.keys():
        parkey = MOUNT_DEVICE_SEQNUM_MAP_IDE[pardir]
        for key, value in MOUNT_DEVICE_SEQNUM_MAP_IDE.items():
            if value == parkey:
                res_lst.append(key)
            else:
                continue
        res_lst.remove(pardir)

    return res_lst


# get the device
def get_device(volume, server_id):
    res_lst = []
    device_lst = volume.get("status", {}).get("attachments", [])
    if len(device_lst) > 0:
        for item in device_lst:
            if item.get("server_id", None) == server_id:
                res_lst.append(item["device"])
            else:
                continue
    return res_lst


# judge attach point dir exists on the platform system
def check_dir_exists(pardir):
    if pardir:
        if os.path.exists(pardir):
            return True
        else:
            return False
    else:
        return False


# get the real path that exists on the platform system
def get_real_path(path_lst):
    if len(path_lst) > 0:
        for item in path_lst:
            if check_dir_exists(item):
                return item
            else:
                continue
    return None


def get_vbd_device(pci_address):
    virtios = os.listdir(consts.PCI_ADDRESS + pci_address)
    device = ''
    for virtio in virtios:
        if virtio.find("virtio") > -1:
            device = os.path.join(consts.DEV_PATH,
                                  (os.listdir(consts.PCI_ADDRESS + pci_address + '/' + virtio + consts.PCI_BLOCK)[0]))
            return device
        else:
            continue

    return device


def get_scsi_device(wwn):
    device_path = os.path.realpath(consts.VM_SCSI_DEVICE_PATH + wwn)
    if check_block_device(device_path):
        return device_path
    else:
        device_path = os.path.realpath(consts.BMS_SCSI_DEVICE_PATH + wwn)
        if check_block_device(device_path):
            return device_path
        else:
            return None


def check_block_device(device_path):
    return os.path.exists(device_path) and stat.S_ISBLK(os.stat(device_path)[stat.ST_MODE])
