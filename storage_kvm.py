"""
Primitive for Storage drives (QEMU images) on KVM hosts
"""

# stdlib
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
import re


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
        3021: f'3021: Failed to connect to the host {host}',
        3022: f'3022: Failed to create storage_kvm {domain_path}{storage} on the host {host}'
    }

    message_list = {}

    # Define payload
    payload = f'qemu-img create -f qcow2 {domain_path}{storage} {size}G'

    # Create storage using SSH communication
    response = comms_ssh(
        host_ip=host,
        payload=payload,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\n ' \
                f'channel_code: {response["channel_code"]}s.\n' \
                f'channel_message: {response["channel_message"]}\n' \
                f'channel_error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3022]}\n ' \
                f'payload_code: {response["payload_code"]}s.\n' \
                f'payload_message: {response["payload_message"]}\n' \
                f'payload_error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    message_list.append(messages[1000])
    return success, message_list


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
        1000: f'1000: Successfully update storage {storage}',
        3021: f'3021: Failed to connect to the host {host}',
        3022: f'3022: Failed to update storage_kvm {domain_path}{storage}'
    }
    message_list = {}
    # Define payload
    payload = f'qemu-img resize {domain_path}{storage} {size}G'

    # Update storage using SSH communication
    response = comms_ssh(
        host_ip=host,
        payload=payload,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\n ' \
                f'channel_code: {response["channel_code"]}s.\n' \
                f'channel_message: {response["channel_message"]}\n' \
                f'channel_error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3022]}\n ' \
                f'payload_code: {response["payload_code"]}s.\n' \
                f'payload_message: {response["payload_message"]}\n' \
                f'payload_error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    message_list.append(messages[1000])
    return success, message_list


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
        1000: f'1000: Successfully removed storage {storage}',
        3021: f'3021: Failed to connect to the host {host}',
        3022: f'3022: Failed to remove storage_kvm {domain_path}{storage} on the host {host}'
    }
    message_list = {}
    # Define payload
    payload = f'rm -force {domain_path}{storage}'

    # Remove storage using SSH communication
    response = comms_ssh(
        host_ip=host,
        payload=payload,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\n ' \
                f'channel_code: {response["channel_code"]}s.\n' \
                f'channel_message: {response["channel_message"]}\n' \
                f'channel_error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3022]}\n ' \
                f'payload_code: {response["payload_code"]}s.\n' \
                f'payload_message: {response["payload_message"]}\n' \
                f'payload_error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    message_list.append(messages[1000])
    return success, message_list


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
        1000: f'1000: Successfully read storage {storage}',
        3021: f'3021: Failed to connect to the host {host}',
        3022: f'3022: Failed to read storage_kvm {domain_path}{storage} on the host {host}'
    }
    message_list = {}
    data_dict = {
        host: {
            'image': None,
            'size': None,
        }
    }
    # Define payload
    payload = f'qemu-img info {domain_path}{storage}'

    # Read storage using SSH communication
    response = comms_ssh(
                host_ip=host,
                payload=payload,
                username='robot',
        )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\n ' \
              f'channel_code: {response["channel_code"]}s.\n' \
              f'channel_message: {response["channel_message"]}\n' \
              f'channel_error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3022]}\n ' \
              f'payload_code: {response["payload_code"]}s.\n' \
              f'payload_message: {response["payload_message"]}\n' \
              f'payload_error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    if success:
        stdout = response.get('stdout', '')

        # Extract the image path
        image_match = re.search(r'image: (\S+)', stdout)
        image = image_match.group(1) if image_match else None

        # Extract the disk size
        size_match = re.search(r'virtual size: (\S+)', stdout)
        size = size_match.group(1) if size_match else None

        data_dict[host] = {
            'image': image,
            'size': size,
        }

    return success, data_dict, message_list
