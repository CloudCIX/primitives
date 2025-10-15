"""
Primitive for Backups on HyperV hosts
"""
# stdlib
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    SSHCommsWrapper,
    hyperv_dictify,
)

__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0



def build(
        host: str,
        vm_identifier: str,
        backup_identifier: str,
        backup_path: None
) -> Tuple[bool, str]:
    """
    description:
        Creates virtual machine backup on HyperV host

    parameters:
        host:
            description: The DNS host name or IP address of the HyperV host on which the virtual machine runs
            type: string
            required: true
        vm_identifier:
            description: unique identification name for the target HyperV VM on the HyperV host
            type: string
            required: true
        backup_identifier:
            description: unique identification name for the backup to be created on the HyperV host
            type: string
            required: true
        backup_path:
            description: |
                path on the HyperV host where the backup is to be stored (defaults to
                D:\\HyperV\\Backup)
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    if backup_path is None:
        backup_path = 'D:\\HyperV\\Backup'
    backup_destination = '\\'.join([backup_path, backup_identifier])

    # Define message
    messages = {
        1000: f'Successfully created backup {backup_identifier} at {backup_destination}',
        1001: f'Backup {backup_identifier} already exists on host {host} at {backup_destination}',
        3021: f'Failed to connect to host {host} for payload check_backup: ',
        3022: f'Failed to run check_backup payload on host {host}: ',
        3023: f'Failed to connect to host {host} for payload create_backup: ',
        3024: f'Failed to run create_backup payload on host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
           'check_backup': f"Test-Path -Path '{backup_destination}'",
           'create_backup': f"$job = Export-VM -Name '{vm_identifier}' -Path '{backup_destination}'; Wait-Job $job",
        }

        ret = rcc.run(payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if (ret["payload_code"] == SUCCESS_CODE) and (ret["payload_message"].strip() == "True"):
            # No need to create backup: it exists already
            return True, fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        elif (ret["payload_code"] == SUCCESS_CODE) and (ret["payload_message"].strip() == "False"):
            fmt.add_successful('check_backup', ret)
        else:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads

        ret = rcc.run(payloads['create_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        fmt.add_successful('create_backup', ret)

        return True, messages[1000], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})

    return status, msg


def read(
    host: str,
    backup_identifier: str,
    backup_path: None,
):
    """
    description:
        Gets the status of a virtual machine backup on HyperV host

    parameters:
        host:
            description: The DNS host name or IP address of the HyperV host on which the virtual machine runs
            type: string
            required: true
        backup_identifier:
            description: unique identification name for the backup to be created on the HyperV host
            type: string
            required: true
        backup_path:
            description: |
                path on the HyperV host where the backup is to be stored (defaults to
                D:\\HyperV\\Backup)
            type: string
            required: false
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
                description: backup meta data retrieved from host. May be empty if nothing could be retrieved.
                items:
                    Sum:
                        description: total size of backup in bytes
                        type: string
                    Count:
                        description: total number of files in backup destination
                        type: string
    """

    if backup_path is None:
        backup_path = 'D:\\HyperV\\Backup'
    backup_destination = '\\'.join([backup_path, backup_identifier])

    # Define message
    messages = {
        1300: f'Successfully read backup {backup_identifier} at {backup_destination}',

        3321: f'Failed to connect to host {host} for payload check_backup: ',
        3322: f'Backup destination for backup {backup_identifier} ({backup_destination}) does not exist.',
        3323: f'Failed to run payload check_backup on host {host}: ',
        3324: f'Failed to connect to host {host} for payload get_backup_size: ',
        3325: f'Failed to run payload get_backup size on host {host}: ',
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
            'check_backup': f"Test-Path -Path '{backup_destination}'",
            'get_backup_size': f'Get-Item {backup_destination} | Get-ChildItem -Recurse -File | Measure-Object -Sum Length | Select Sum,Count'
        }

        ret = rcc.run(payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if (ret["payload_code"] == SUCCESS_CODE and ret["payload_message"].strip() == "True"):
            fmt.add_successful('check_backup', ret)
        elif (ret["payload_code"] == SUCCESS_CODE and ret["payload_message"].strip() == "False"):
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        else:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
            return retval, fmt.message_list, fmt.successful_payloads, data_dict

        ret = rcc.run(payloads['get_backup_size'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        if (ret["payload_code"] != SUCCESS_CODE):
            retval = False
            fmt.store_payload_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        else:
            fmt.add_successful('get_backup_size', ret)
            data_dict[host] = hyperv_dictify(ret["payload_message"])

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1300]]



def scrub(
    host: str,
    backup_identifier: str,
    backup_path: None
):
    """
    description:
        Removes backup <backup_identifier> from host <host>.

    parameters:
        host:
            description: The DNS host name or IP address of the HyperV host on which the virtual machine runs
            type: string
            required: true
        backup_identifier:
            description: unique identification name for the backup to be removed on the HyperV host
            type: string
            required: true
        backup_path:
            description: |
                path on the HyperV host where the backup is to be stored (defaults to
                D:\\HyperV\\Backup)
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the remove was successful or not and
            the output or error message.
        type: tuple
    """
    if backup_path is None:
        backup_path = 'D:\\HyperV\\Backup'
    backup_destination = '\\'.join([backup_path, backup_identifier])

    # Define message
    messages = {
        1100: f'Successfully removed backup {backup_identifier} from {backup_destination} on host {host}.',
        1101: f'Backup {backup_identifier} does not exist on host {host}.',

        3121: f'Failed to connect to host {host} for payload check_backup: ',
        3122: f'Failed to run payload check_backup on host {host}: ',
        3123: f'Failed to connect to host {host} for payload remove_backup: ',
        3124: f'Failed to run payload remove_backup on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_backup': f"Test-Path -Path '{backup_destination}'",
            'remove_backup': f'Remove-Item -Path {backup_destination} -Recurse -Force -Confirm:$false',
        }

        ret = rcc.run(payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        if (ret["payload_code"] == SUCCESS_CODE) and (ret["payload_message"].strip() == "False"):
            # No need to remove backup: it does not exist
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        elif (ret["payload_code"] == SUCCESS_CODE) and (ret["payload_message"].strip() == "True"):
            fmt.add_successful('check_backup', ret)
        else:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads

        ret = rcc.run(payloads['remove_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        fmt.add_successful('remove_backup', ret)

        return True, messages[1100], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})

    return status, msg
