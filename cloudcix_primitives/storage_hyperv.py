"""
Primitive for Storage drives on HyperV hosts
"""
# stdlib
import re
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    SSHCommsWrapper,
)

__all__ = [
    'build',
    'read',
    'scrub',
    'update',
]

SUCCESS_CODE = 0


def build(
        host: str,
        domain_path: str,
        storage: str,
        size: int,
) -> Tuple[bool, str]:
    """
    description:
        Creates <domain_path><storage> file on the given Host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_hyperv is created
            type: string
            required: true
        storage:
            description: The unique name of the storage_hyperv to be created
            type: string
            required: true
        size:
            description: The size of the storage_hyperv to be created, must be in GB value 
            type: int
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully created storage {storage}',
        1001: f'Storage {storage} already exists on Host {host}',

        3021: f'Failed to connect to the host {host} for the payload read_storage_file: ',
        3022: f'Failed to connect to the host {host} for the payload create_storage_file: ',
        3023: f'Failed to run create_storage_file on the host {host}. Payload exited with status ',
        3024: f'Failed to connect to the host {host} for the payload dismount_storage_file: ',
        3025: f'Failed to run dismount_storage_file on the host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {domain_path}{storage}',
            'create_storage_file': f'New-VHD -Path {domain_path}{storage} -Dynamic -SizeBytes {size}GB | Mount-VHD -Passthru | Initialize-Disk -PassThru | ' 
                                    'New-Partition -AssignDriveLetter -UseMaximumSize | Format-Volume -FileSystem NTFS -Confirm:$false -Force',
            'dismount_storage_file': f'Dismount-VHD -Path {domain_path}{storage}',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        create_storage = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create storage drive exists already
            create_storage = False
            return True, fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        if create_storage is True:
            ret = rcc.run(payloads['create_storage_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
            fmt.add_successful('create_storage_file', ret)

            ret = rcc.run(payloads['dismount_storage_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
            fmt.add_successful('dismount_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


def read(
    host: str,
    domain_path: str,
    storage: str,
):
    """
    description:
        Gets the status of the <domain_path><storage> file info on the given Host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_hyperv is read
            type: string
            required: true
        storage:
            description: The name of the storage_hyperv to be read
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
        1300: f'Successfully read storage image {storage}',

        3321: f'Failed to connect to the Host {host} for payload read_storage_file: ',
        3322: f'Failed to run read_storage_file payload on the Host {host}. Payload exited with status '
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
            successful_payloads
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {domain_path}{storage}',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        else:
            data_dict[host] = ret["payload_message"].strip()
            fmt.add_successful('read_storage_file', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1300]]



def scrub(
    host: str,
    domain_path: str,
    storage: str,
):
    """
    description:
        Removes <domain_path><storage> file on the given Host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is scrubbed
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_hyperv is removed
            type: string
            required: true
        storage:
            description: The name of the storage_hyperv to be removed
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the remove was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully removed storage image {storage} from {domain_path} on Host {host}.',
        1101: f'Storage image {storage} from {domain_path} does not exist on Host {host}',

        3121: f'Failed to connect to the Host {host} for the payload read_storage_file: ',
        3122: f'Failed to connect to the Host {host} for the payload remove_storage_file: ',
        3123: f'Failed to run remove_storage_file payload on the Host {host}. Payload exited with status '
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {domain_path}{storage}',
            'remove_storage_file': f'Remove-Item -Path {domain_path}{storage} -Recurse -Force -Confirm:$false',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        ret = rcc.run(payloads['remove_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        fmt.add_successful('remove_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]


def update(
    host: str,
    domain_path: str,
    storage: str,
    size: int,
) -> Tuple[bool, str]:
    """
    description:
        Updates the size of the <domain_path><storage> file on the given host <host>."

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_hyperv is updated
            type: string
            required: true
        storage:
            description: The name of the storage_hyperv to be updated
            type: string
            required: true
        size:
            description: The size of the storage_hyperv to be updated, must be in GB value
            type: int
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the update was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1200: f'Successfully updated storage file {storage} to {size}GB at {domain_path}{storage}'
              f' on Host {host}.',
        1201: f'Storage file {domain_path}{storage} does not exist on Host {host}',

        3221: f'Failed to connect to the Host {host} for payload read_storage_file: ',
        3222: f'Failed to connect to the Host {host} for payload resize_storage_file: ',
        3223: f'Failed to run resize_storage_file payload on Host {host}. Payload exited with status '
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {domain_path}{storage}',
            'resize_storage_file': f'Resize-VHD -Path {domain_path}{storage} -SizeBytes {size}GB',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'1201: ' + messages[1201]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        ret = rcc.run(payloads['resize_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        fmt.add_successful('resize_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3220, {})
    if status is False:
        return status, msg

    return True, messages[1200]
