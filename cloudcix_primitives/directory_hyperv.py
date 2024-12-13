"""
Primitive to Build and Delete directories on HyperV
"""

# stdlib
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
import re
# local
from cloudcix_primitives.utils import (
    SSHCommsWrapper,
    HostErrorFormatter,
)

__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
        host: str,
        path: str
) -> Tuple[bool, str]:
    """
    description:
        Creates directory on a HyperV host.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this path is built
            type: string
            required: true
        path:
            description: The path to be created on the HyperV host
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define messages
    messages = {
        1000: f'Successfully created directory {path} on the host {host}.',
        1001: f'Directory {path} already exists on the host {host}.',

        3021: f'Failed to connect to the host {host} for read_path payload: ',
        3022: f'Failed to connect to the host {host} for create_path payload: ',
        3023: f'Failed to run create_path payload on the host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'create_path': f"New-Item -Path {path} -ItemType Directory",
            'read_path': f"Test-Path {path}"
        }

        ret = rcc.run(payloads['read_path'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        create_path = True
        if ret["payload_code"] == SUCCESS_CODE:
            create_path = False
            return True, fmt.payload_error(ret, f"1101: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('read_path', ret)

        if create_path is True:

            ret = rcc.run(payloads['create_path'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            fmt.add_successful('create_path', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


def read(
        host: str,
        path: str
):
    """
    description:
        Reads a directory on a HyperV host.

    parameters:
        host:
            description: The dns or ipadddress of the Host where the path is read
            type: string
            required: true
        path:
            description: The path to be read on the HyperV host
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the read was successful or not and
            the output or error message.
        type: tuple

    """
    # Define message
    messages = {
        1100: f'Successfully read directory {path} on the host {host}.',

        3121: f'Failed to connect to the host {host} for read_path payload: ',
        3122: f'Failed to run read_path payload on the host {host}. Payload exited with status ',
    }

    message_list = []
    data_dict = {
        host: {}
    }

    def run_host(host, prefix, successful_payloads):
        retval = True
        data_dict[host] = {}

        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'read_path': f"Get-Item -Path {path}",
        }

        ret = rcc.run(payloads['read_path'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        else:
            data_dict[host] = ret["payload_message"].strip()
            fmt.add_successful('read_path', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3120, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1100]]


def scrub(
    host: str,
    path: str
):
    """
    description:
        Reads a directory on a HyperV host.

    parameters:
        host:
            description: The dns or ipadddress of the Host where the path is scrubbed
            type: string
            required: true
        path:
            description: The path to be scrubbed on the HyperV host
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple

    """
    # Define message
    messages = {
        1200: f'Successfully scrubbed directory {path} on the host {host}.',
        1201: f'Directory {path} does not exist on the host {host}',

        3221: f'Failed to connect to the host {host} for read_path payload: ',
        3222: f'Failed to run read_path payload on the host {host}. Payload exited with status ',

        3223: f'Failed to connect to the host {host} for remove_path payload: ',
        3224: f'Failed to run remove_path payload on the host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_path': f"Get-Item -Path {path}",
            'remove_path': f"Remove-Item -LiteralPath {path} -Force -Recurse",
        }

        ret = rcc.run(payloads['read_path'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        path_exist = True
        if ret["payload_code"] == SUCCESS_CODE:
            path_exist = False
            return True, fmt.payload_error(ret, f"1201: " + messages[1201]), fmt.successful_payloads
        fmt.add_successful('read_path', ret)

        if path_exist:
           ret = rcc.run(payloads['remove_path'])
           if ret["channel_code"] != CHANNEL_SUCCESS:
               return False, fmt.channel_error(ret, messages[prefix + 3]), fmt.successful_payloads
           if ret["payload_code"] != SUCCESS_CODE:
               return False, fmt.payload_error(ret, messages[prefix + 4]), fmt.successful_payloads
           fmt.add_successful('remove_path', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3220, {})
    if status is False:
        return status, msg

    return True, messages[1200]