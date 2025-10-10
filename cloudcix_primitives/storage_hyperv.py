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
    hyperv_dictify_vertical,
)

__all__ = [
    'build',
    'read',
    'scrub',
    'update',
]

SUCCESS_CODE = 0
GB_BYTES = 1073741824



def build(
        host: str,
        vm_identifier: str,
        storage_identifier: str,
        size: int,
) -> Tuple[bool, str]:
    """
    description:
        Creates secondary storage volume for HyperV VMs.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is built
            type: string
            required: true
        vm_identifier:
            description: unique identification name for the target HyperV VM on the HyperV host
            type: string
            required: true
        storage_identifier:
            description: unique identification name for the storage drive to be created on the HyperV host
            type: string
            required: true
        size:
            description: The size of the storage volume to be created in gigabytes.
            type: int
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'

    # Define message
    messages = {
        1000: f'Successfully created storage {storage_identifier} at {storage_path}',
        1001: f'Storage {storage_identifier} already exists on Host {host} at {storage_path}',

        3021: f'Failed to connect to host {host} for payload read_storage_file: ',
        3022: f'Failed to connect to host {host} for payload create_storage_file: ',
        3023: f'Failed to run create_storage_file payload on the host {host}. Payload exited with status ',
        3024: f'Failed to connect to host {host} for payload prepare_storage_file: ',
        3025: f'Failed to run prepare_storage_file payload on the host {host}. Payload exited with status ',
        3026: f'Failed to connect to host {host} for payload dismount_storage_file: ',
        3027: f'Failed to run dismount_storage_file payload on host {host}. Payload exited with status ',
        3028: f'Failed to connect to host {host} for payload attach_storage_file: ',
        3029: f'Failed to run attach_storage_file payload on host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {storage_path}',
            'create_storage_file': f'New-VHD -Path {storage_path} -SizeBytes {size}GB -Dynamic',
            'prepare_storage_file': f'$mountedVHD = Mount-VHD -Path {storage_path} -NoDriveLetter -PassThru;'
                                    'Initialize-Disk -Number $mountedVHD.Number -PartitionStyle GPT;'
                                    'Set-Disk -Number $mountedVHD.Number -IsOffline $false;'
                                    '$partition = New-Partition -DiskNumber $mountedVHD.Number -UseMaximumSize -AssignDriveLetter;'
                                    'Format-Volume -DriveLetter $partition.DriveLetter -FileSystem NTFS'
                                    f" -NewFileSystemLabel '{storage_identifier}' -Confirm:$false;",
            'dismount_storage_file': f'Dismount-VHD -Path {storage_path}',
            'attach_storage_file': f'Add-VMHardDiskDrive -VMName {vm_identifier} -Path {storage_path} -ControllerType SCSI'
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create storage drive exists already
            return True, fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        ret = rcc.run(payloads['create_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        fmt.add_successful('create_storage_file', ret)

        ret = rcc.run(payloads['prepare_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        fmt.add_successful('prepare_storage_file', ret)

        ret = rcc.run(payloads['dismount_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix + 6]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix + 7]), fmt.successful_payloads
        fmt.add_successful('dismount_storage_file', ret)

        ret = rcc.run(payloads['attach_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix + 8]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix + 9]), fmt.successful_payloads
        fmt.add_successful('attach_storage_file', ret)

        return True, messages[1000], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})

    return status, msg


def read(
    host: str,
    vm_identifier: str,
    storage_identifier: str,
):
    """
    description:
        Gets the status of the <domain_path><storage> file info on the given Host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is built
            type: string
            required: true
        vm_identifier:
            description: unique identification name for the target HyperV VM on the HyperV host
        storage_identifier:
            description: unique identification name for the storage drive to be queried on the HyperV host
            type: string
            required: true
    return:
        description:
            status:
                description: True if all read operations were successful, False otherwise.
                type: boolean
            messages:
                type: list
                description: list of error messages encountered during read operation. May be empty.
            successful_payloads:
                type: list
                description: list of payloads that ran successfully. May be empty.
            data:
                type: object
                description: storage drive meta data retrieved from host. May be empty if nothing could be retrieved.
    """

    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'

    # Define message
    messages = {
        1300: f'Successfully read storage image {storage_identifier}',

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
            'read_storage_file': f'Get-VHD -Path {storage_path}',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        else:
            data_dict[host] = hyperv_dictify_vertical(ret["payload_message"])
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
    vm_identifier: str,
    storage_identifier: str,
):
    """
    description:
        Removes storage volume <storage_identifier> attached to domain <vm_identifier> host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_hyperv is scrubbed
            type: string
            required: true
        vm_identifier:
            description: unique identification name for the target HyperV VM on the HyperV host
        storage_identifier:
            description: unique identification name for the storage drive to be removed on the HyperV host
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the remove was successful or not and
            the output or error message.
        type: tuple
    """

    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'

    # Define message
    messages = {
        1100: f'Successfully removed storage image {storage_path} from {vm_path} on host {host}.',
        1101: f'Storage file {storage_path} does not exist on host {host}.',

        3121: f'Failed to connect to the Host {host} for the payload read_storage_file: ',
        3122: f'Failed to connect to Host {host} for detach_storage_file payload: ',
        3123: f'Failed to run detach_storage_file payload on Host {host}. Payload exited with status ',
        3124: f'Failed to connect to Host {host} for remove_storage_file payload: ',
        3125: f'Failed to run remove_storage_file payload on Host {host}. Payload exited with status '
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {storage_path}',
            'detach_storage_file': f'Remove-VMHardDiskDrive -VMHardDiskDrive (Get-VMHardDiskDrive -VMName "{vm_identifier}"'
                                   f" | Where-Object {{ $_.Path -EQ '{storage_path}' }}) -Confirm:$false",
            'remove_storage_file': f'Remove-Item -Path {storage_path} -Force -Confirm:$false',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        ret = rcc.run(payloads['detach_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        fmt.add_successful('detach_storage_file', ret)

        ret = rcc.run(payloads['remove_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        fmt.add_successful('remove_storage_file', ret)

        return True, messages[1100], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})

    return status, msg



def update(
    host: str,
    vm_identifier: str,
    storage_identifier: str,
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
        vm_identifier:
            description: The location or directory path where this storage_hyperv is updated
            type: string
            required: true
        storage_identifier:
            description: The name of the storage_hyperv to be updated
            type: string
            required: true
        size:
            description: the size (in GB) to resize the storage file to.
            type: int
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the update was successful or not and
            the output or error message.
        type: tuple
    """

    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'

    # Define message
    messages = {
        1200: f'Successfully updated storage file {storage_path} on host {host} to {size}GB.',
        1202: f'Storage file storage file {storage_path} is already {size}GB, no need to resize.',
        3221: f'Failed to connect to the Host {host} for payload read_storage_file: ',
        3222: f'Storage file {storage_path} does not exist on host {host}',
        3223: f'Volume size {size} is smaller than current volume size (%dGB). Shrinking storage volumes is not supported.',
        3224: f'Failed to connect to the Host {host} for payload resize_storage_file: ',
        3225: f'Failed to run resize_storage_file payload on Host {host}. Payload exited with status '
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_storage_file': f'Get-VHD -Path {storage_path}',
            'resize_storage_file': f'Resize-VHD -Path {storage_path} -SizeBytes {size}GB',
        }

        ret = rcc.run(payloads['read_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+2}: ' + messages[prefix + 2]), fmt.successful_payloads
        fmt.add_successful('read_storage_file', ret)

        data = hyperv_dictify_vertical(ret["payload_message"])
        current_size = int(data['Size']) / GB_BYTES

        if current_size == size:
            return True, f'1202: ' + messages[1202], fmt.successful_payloads
        if size < current_size:
            return False, f'{prefix+3}: ' + messages[prefix+3] % current_size, fmt.successful_payloads

        ret = rcc.run(payloads['resize_storage_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        fmt.add_successful('resize_storage_file', ret)

        return True, messages[1200], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3220, {})
    return status, msg
