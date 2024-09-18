"""
Primitive for Storage image drives (QEMU images) on KVM hosts
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
        cloudimage: str,
) -> Tuple[bool, str]:
    """
    description:
        Copies <cloudimage> to the given <domain_path><storage> and resizes the storage file to <size>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage image will be created
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage image will be created
            type: string
            required: true
        storage:
            description: The unique name of the storage image file to be created
            type: string
            required: true
        size:
            description: The size of the storage image to be created, must be in GB value 
            type: int
            required: true
        cloudimage:
            description: The path to the cloud image file that will be copied to the domain directory.
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created and resized storage image {storage} to {size}GB at {domain_path}{storage} on Host {host}.',
        3021: f'3021: Failed to connect to the Host {host}',
        3022: f'3022: Failed to copy cloud image {cloudimage} to the domain directory {domain_path}{storage} on Host {host}.',
        3023: f'3023: Failed to resize the copied storage image to {size}GB on Host {host}.'
    }
    message_list = {}
    # Define payload
    copy_cloud_image_payload = f'cp {cloudimage} {domain_path}{storage}'
    resize_copied_file = f'qemu-img resize {domain_path}{storage} {size}G'

    # Copy cloud image to domains directory using SSH communication
    response = comms_ssh(
        host_ip=host,
        payload=copy_cloud_image_payload,
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
    if not success:
        return success, message_list

    # Resize the copied file to `size` using SSH communication
    response = comms_ssh(
        host_ip=host,
        payload=resize_copied_file,
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
        msg = f'{messages[3023]}\n ' \
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
        Updates the size of the <domain_path><storage> file on the given Host <host>."

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage image is updated
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage image is located
            type: string
            required: true
        storage:
            description: The name of the storage image to be updated
            type: string
            required: true
        size:
            description: The new size of the storage image in GB.
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
        1000: f'1000: Successfully updated storage image {storage} to {size}GB at {domain_path}{storage} on Host {host}.',
        3021: f'3021: Failed to connect to the Host {host}.',
        3022: f'3022: Failed to update storage image {domain_path}{storage} to {size}GB on Host {host}.'
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
            description: The DNS or IP address of the Host where the storage image is to be removed.
            type: string
            required: true
        domain_path:
            description: The location or directory path where the storage image is located.
            type: string
            required: true
        storage:
            description: The name of the storage image to be removed.
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
        1000: f'1000: Successfully removed storage image {storage} from {domain_path} on Host {host}.',
        3021: f'3021: Failed to connect to the Host {host}',
        3022: f'3022: Failed to remove storage image {domain_path}{storage} from Host {host}.'
    }
    message_list = {}
    # Define payload
    payload = f'rm --force {domain_path}{storage}'

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
            description: The dns or ipadddress of the Host where the storage image is located
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage image is read
            type: string
            required: true
        storage:
            description: The name of the storage image to be read
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
        1000: f'1000: Successfully read storage image {storage}',
        3021: f'3021: Failed to connect to the Host {host}',
        3022: f'3022: Failed to read storage image {domain_path}{storage} on the Host {host}'
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
