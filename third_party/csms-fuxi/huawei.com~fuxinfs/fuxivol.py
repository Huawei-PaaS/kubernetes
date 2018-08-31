#!/usr/bin/env python

import sys
import subprocess
import json
import base64

APP_PATH = sys.path[0] + '/fuxi/fuxi_cli.py'
MAGIC_CODE = '9a8c-33da-42ec-93d5'
WHITE_SPACE = ' '
COMMA = ','
SPECIAL_SYMBOLS = '&$<>()?'
MOUNT_DEVICE = 'mount_device'


def main(argv):
    if len(argv) < 2:
        error_message = "{\"status\": \"Failed\", \"message\": \"Invalid usage.\"}"
        print(error_message)
        return

    cmd = sys.argv[1]
    args = sys.argv[1:]

    exec_cmd_list = list()
    exec_cmd_list.append('python')
    exec_cmd_list.append(APP_PATH)
    if cmd not in ["create", "delete", "mount", "unmount", "init", "expandvolume"]:
        error_message = "{\"status\": \"Failed\", \"message\": \"Invalid usage.\"}"
        print(error_message)
        return
    else:
        exec_cmd_list.append(cmd)

    ok, request_body = get_request_body(args, cmd, exec_cmd_list)
    if not ok:
        error_message = "{\"status\": \"Failed\", \"message\": \"Invalid usage.\"}"
        print(error_message)
        return

    if request_body:
        exec_cmd_list.append(base64.b64encode('[' + request_body + ']'))

    ok = check_request_parameters(args, cmd)
    if not ok:
        error_message = "{\"status\": \"Failed\", \"message\": \"Illegal input of path.\"}"
        print(error_message)
        return

    exec_cmd = WHITE_SPACE.join(exec_cmd_list)
    p = subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return_code = p.poll()
    line = ''
    while return_code is None:
        return_code = p.poll()
        if return_code == 0:
            line = p.stdout.readline()
            line = line.strip()
        else:
            line += p.stderr.readline()

        if len(line) < 10:
            continue
        try:
            result = json.loads(line)
            if result['magiccode'] == MAGIC_CODE:
                print(line)
                break
        except Exception:
            continue
    if return_code != 0:
        error_message = "{\"status\": \"Failed\", \"message\": \"Parameter error.\"}"
        print(error_message)


def get_request_option(exec_opt_list):
    option_length = len(exec_opt_list)
    if option_length < 1:
        return None

    for x in range(1, option_length + 1):
        opt_string = WHITE_SPACE.join(exec_opt_list[0: x])
        try:
            json.loads(opt_string)
            return opt_string
        except Exception:
            continue

    return None


def check_parameters(args_string):
    index = 0
    for character in args_string:
        try:
            index += 1
            if character in SPECIAL_SYMBOLS:
                if '\\' != args_string[index - 2:index - 1]:
                    return False
        except Exception:
            return False
    return True


def isjson(args_string):
    try:
        json.loads(args_string)
        return True
    except Exception:
        return False


def get_request_body(args, cmd, exec_cmd_list):
    request_body = ''
    if "mount" == cmd:
        if len(args) < 3:
            return False, None
        exec_cmd_list.append(args[1])
        if isjson(get_request_option(args[2:])):
            exec_cmd_list.append(MOUNT_DEVICE)
            request_body = get_request_option(args[2:])
        else:
            exec_cmd_list.append(args[2])
            request_body = get_request_option(args[3:])
    elif "unmount" == cmd:
        if len(args) < 3 or len(args) < 2:
            return False, None
        exec_cmd_list.append(args[1])
        request_body = get_request_option(args[2:])
    elif "create" == cmd:
        if len(args) < 2 or len(args) < 1:
            return False, None
        request_body = get_request_option(args[1:])
    elif "delete" == cmd:
        if len(args) < 3 or len(args) < 2:
            return False, None
        exec_cmd_list.append(args[1])
        request_body = get_request_option(args[2:])
    elif "expandvolume" == cmd:
        if len(args) < 5:
            return False, None
        exec_cmd_list.append(args[3])
        exec_cmd_list.append(args[4])
        request_body = get_request_option(args[1:2])
    elif "init" == cmd:
        pass

    if request_body is None:
        return False, None

    return True, request_body


def check_request_parameters(args, cmd):
    if "mount" == cmd:
        ret = check_parameters("".join(args[1:2]))
        if not ret:
            return False
        return check_parameters("".join(args[2:3]))
    elif "unmount" == cmd:
        return check_parameters("".join(args[1:2]))
    else:
        return True


if __name__ == "__main__":
    main(sys.argv)
