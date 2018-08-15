import commands

# Execute the given shell cmd with an optional timeout,
# and just return outputs(string|None) and potential error(None|string):
# * status == 0: the raw outputs and None
# * status != 0: None and the formated string with raw status and outputs
#
# Be aware this method just ignores the status code, so it can call
# exec_shell_cmd_with_raw_resp() and use raw status & outputs for more
# accurate custom defined handle.
#
def exec_shell_cmd(cmd, timeout=0):
    targetCmd = cmd
    if timeout > 0:
        targetCmd = "timeout %d %s" % (timeout, cmd)
    status, outputs = commands.getstatusoutput(targetCmd)
    if status == 0:
        return outputs, None
    return None, "Status: {0}, Error: {1}".format(status, outputs)

# Execute the given shell cmd with an optional timeout,
# and return raw status (int|None) and outputs(string).
# The caller can do custom defined handle accordingly.
#
def exec_shell_cmd_with_raw_resp(cmd, timeout=0):
    targetCmd = cmd
    if timeout > 0:
        targetCmd = "timeout %d %s" % (timeout, cmd)
    return commands.getstatusoutput(targetCmd)
