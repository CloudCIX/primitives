"""
Primitive for Storage drives (QEMU images) on KVM hosts
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
            description: The dns or ipadddress of the Host on which this storage_kvm is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_kvm is created
            type: string
            required: true
        storage:
            description: The unique name of the storage_kvm to be created
            type: string
            required: true
        size:
            description: The size of the storage_kvm to be created, must be in GB value 
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
        1000: f'1000: Successfully created storage {storage}',
        3001: f'3001: Already a storage {storage} of different size than requested size {size}GBs '
              f'file exists at {domain_path}',
        3021: f'3021: Failed to connect to the host {host} for the payload read_storage_file',
        3022: f'3022: Failed to connect to the host {host} for the payload create_storage_file',
        3023: f'3023: Failed to create storage_kvm {domain_path}{storage} on the host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'read_storage_file': f'qemu-img info {domain_path}{storage}',
            'create_storage_file': f'qemu-img create -f qcow2 {domain_path}{storage} {size}G',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        create_storage = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create storage drive exists already
            create_storage = False
            # storage already exists, extract the size of the file
            size_match = re.search(r'virtual size: (\S+)', ret["payload_message"].strip())
            checked_size = size_match.group(1) if size_match else 0
            if int(checked_size) != int(size):
                return False, messages[3001], fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        if create_storage is True:
            ret = rcc.run(payloads['create_storage_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix + 2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, messages[prefix + 3]), fmt.successful_payloads
            fmt.add_successful('create_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


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
            description: The dns or ipadddress of the Host on which this storage_kvm is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_kvm is updated
            type: string
            required: true
        storage:
            description: The name of the storage_kvm to be updated
            type: string
            required: true
        size:
            description: The size of the storage_kvm to be updated, must be in GB value
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
        1300: f'1300: Successfully updated storage image {storage} to {size}GB at {domain_path}{storage}'
              f' on Host {host}.',
        3321: f'3321: Failed to connect to the Host {host} for payload resize_storage_file.',
        3322: f'3322: Failed to update storage image {domain_path}{storage} to {size}GB on Host {host}.'
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'resize_storage_file': f'qemu-img resize {domain_path}{storage} {size}G',
        }

        ret = rcc.run(payloads['resize_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        fmt.add_successful('resize_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3320, {})
    if status is False:
        return status, msg

    return True, messages[1300]


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
            description: The dns or ipadddress of the Host on which this storage_kvm is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_kvm is removed
            type: string
            required: true
        storage:
            description: The name of the storage_kvm to be removed
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
        1100: f'1100: Successfully removed storage image {storage} from {domain_path} on Host {host}.',
        3121: f'3121: Failed to connect to the Host {host} for the payload remove_storage_file',
        3122: f'3122: Failed to remove storage image {domain_path}{storage} from Host {host}.'
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'remove_storage_file': f'rm --force {domain_path}{storage}',
        }

        ret = rcc.run(payloads['remove_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        fmt.add_successful('remove_storage_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]


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
            description: The dns or ipadddress of the Host on which this storage_kvm is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_kvm is read
            type: string
            required: true
        storage:
            description: The name of the storage_kvm to be read
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
        1200: f'1200: Successfully read storage image {storage}',
        3221: f'3221: Failed to connect to the Host {host} for the payload read_storage_file',
        3222: f'3222: Failed to read storage image {domain_path}{storage} on the Host {host}'
    }
    message_list = []
    data_dict = {
        host: {
            'image': None,
            'size': None,
        }
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
            'read_storage_file': f'qemu-img info {domain_path}{storage}',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        else:
            # Extract the image path
            image_match = re.search(r'image: (\S+)', ret["payload_message"].strip())
            image = image_match.group(1) if image_match else None

            # Extract the disk size
            size_match = re.search(r'virtual size: (\S+)', ret["payload_message"].strip())
            size = size_match.group(1) if size_match else None

            data_dict[host] = {
                'image': image,
                'size': size,
            }

            fmt.add_successful('read_storage_file', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1200]]
