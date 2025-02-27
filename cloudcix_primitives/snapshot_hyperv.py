"""
Primitive for Virtual Machine Snapshot on HyperV hosts
"""
# stdlib
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    hyperv_dictify,
    hyperv_dictify_csv,
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
        vm_identifier: str,
        host: str,
        snapshot_identifier: str,
) -> Tuple[bool, str]:
    """
    1. Crates a HyperV VM Snapshot

    host:
        description: Remote server ip address on which this HyperV VM is created
        type: string
    vm_identifier:
        description: Identification of the HyeprV VM on the Host.
        type: string
    snapshot_identifier:
        description: Identification of the HyperV VM's snapshot on the Host.
        type: string
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # messages
    messages = {
        1000: f'Successfully created snapshot #{snapshot_identifier} for HyperV VM {vm_identifier}',
        1001: f'Skipping creation of snapshot #{snapshot_identifier} for HyperV VM {vm_identifier}: snapshot exists',
        3031: f'Failed to connect to host {host} for read_domain_info payload',
        3032: f'Failed to locate domain {vm_identifier} on host {host}',
        3033: f'Failed to connect to host {host} for read_snapshot payload',
        3034: f'Failed to connect to host {host} for set_check_point_type payload ',
        3035: f'Failed to run set_check_point_type payload for snapshot {snapshot_identifier} of domain {vm_identifier} ',
        3036: f'Failed to connect to host {host} for payload create_snapshot',
        3037: f'Failed to create snapshot {snapshot_identifier} for domain {vm_identifier}',
        3038: f'Failed to connect to host {host} for verify_snapshot payload',
        3039: f'Failed to run verify_snapshot payload on host {host} for snapshot {snapshot_identifier} of domain {vm_identifier}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )
        payloads = {
            # check if vm exists already
            'read_domain_info':  f'Get-VM -Name {vm_identifier} ',
            # check if snapshot exists already
            'read_snapshot':        f'Get-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -ea SilentlyContinue',
            'set_check_point_type': f'Set-VM -Name {vm_identifier} -CheckpointType Standard',
            'create_snapshot':      f'Checkpoint-VM -Name {vm_identifier} -SnapshotName {snapshot_identifier} -ErrorAction Stop',
            # verify snapshot created successfully
            'verify_snapshot':   f'Get-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -ea SilentlyContinue',
        }

        ret = rcc.run(payloads['read_domain_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('read_domain_info', ret)

        ret = rcc.run(payloads['read_snapshot'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        create_snapshot = False
        if ret["payload_code"] != SUCCESS_CODE:
            create_snapshot = True
        fmt.add_successful('read_snapshot', ret)

        if create_snapshot is True:
            ret = rcc.run(payloads['set_check_point_type'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
            fmt.add_successful('set_check_point_type', ret)

            ret = rcc.run(payloads['create_snapshot'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            fmt.add_successful('create_snapshot', ret)

            ret = rcc.run(payloads['verify_snapshot'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
            fmt.add_successful('verify_snapshot', ret)
        else:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads

        return True, f'1000: {messages[1000]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})

    return status, msg


def read(
        vm_identifier: str,
        host: str,
        snapshot_identifier: str,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description: Gets the snapshot information

    parameters:
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        snapshot_identifier:
            description: Identification of the HyperV VM's snapshot on the Host.
            type: string
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successful, (2) a dict containing the data as read from
            the both machine's current state and (3) the list of debug and or error messages.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from Host. May be None if nothing
              could be retrieved.
            properties:
              <host>:
                description: read output data from machine <host>
                  type: string
          messages:
            description: list of errors and debug messages collected before failure occurred
            type: array
            items:
              <message>:
                description: exact message of the step, either debug, info or error type
                type: string
    """
    # Define message
    messages = {
        1200: f'Successfully read metadata of snapshot {snapshot_identifier} for domain {vm_identifier} from host {host}',
        3221: f'Failed to connect to host {host} for payload read_snapshot_info',
        3222: f'Failed to read data of snapshot {snapshot_identifier} for domain {vm_identifier} from host {host}',
    }

    # set the outputs
    data_dict = {}
    message_list = []

    def run_host(host, prefix, successful_payloads):
        retval = True
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_snapshot_info':   f'Get-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -ea SilentlyContinue',
        }

        ret = rcc.run(payloads['read_snapshot_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            # Load the domain info into dict
            data_dict[host] = hyperv_dictify(ret["payload_message"])
            fmt.add_successful('read_snapshot_info', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f'1200: {messages[1200]}']


def scrub(
        vm_identifier: str,
        host: str,
        snapshot_identifier: str,
        remove_subtree: bool,
) -> Tuple[bool, str]:
    """
    description: Removes the Snapshot

    parameters:
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        snapshot:
            description: Identification of the HyperV VM's snapshot on the Host.
            type: string
            required: true
        remove_subtree:
            description: Whether to delete child snapshots of the sent snapshot of the domain or not
            type: boolean
            required: true

    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1100: f'Successfully scrubbed snapshot {snapshot_identifier} of domain {vm_identifier} on host {host}',
        3121: f'Failed to connect to the host {host} for payload read_snapshot_info',
        3122: f'Failed to connect to the host {host} for payload remove_snapshot',
        3123: f'Failed to remove snapshot {snapshot_identifier} of the domain {vm_identifier} from host {host}',
        3124: f'Failed to connect to the host {host} for payload remove_subtree',
        3125: f'Failed to remove subtree of snapshot {snapshot_identifier} of the domain {vm_identifier} from host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_snapshot_info': f'Get-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -ea SilentlyContinue',
            'remove_snapshot':    f'Remove-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} ',
            'remove_subtree':     f'Remove-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -IncludeAllChildSnapshots',

        }

        ret = rcc.run(payloads['read_snapshot_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        scrub_snapshot = True
        if ret["payload_code"] != SUCCESS_CODE:
            scrub_snapshot = False
        fmt.add_successful('read_snapshot_info', ret)

        if scrub_snapshot is True:
            if remove_subtree is False:
                ret = rcc.run(payloads['remove_snapshot'])
                if ret["channel_code"] != CHANNEL_SUCCESS:
                    return (
                        False,
                        fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'),
                        fmt.successful_payloads,
                    )
                if ret["payload_code"] != SUCCESS_CODE:
                    return (
                        False,
                        fmt.payload_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'),
                        fmt.successful_payloads,
                    )
                fmt.add_successful('remove_snapshot', ret)
            else:
                ret = rcc.run(payloads['remove_subtree'])
                if ret["channel_code"] != CHANNEL_SUCCESS:
                    return (
                        False,
                        fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'),
                        fmt.successful_payloads,
                    )
                if ret["payload_code"] != SUCCESS_CODE:
                    return (
                        False,
                        fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'),
                        fmt.successful_payloads,
                    )
                fmt.add_successful('remove_subtree', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'


def update(
        vm_identifier: str,
        host: str,
        snapshot_identifier: str,
) -> Tuple[bool, str]:
    """
    description: Update a Snapshot by restoring it

    parameters:
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        snapshot_identifier:
            description: Identification of the HyperV VM's snapshot on the Host.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag stating the restore was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1300: f'Successfully restored to snapshot {snapshot_identifier} for domain {vm_identifier} on host {host}',
        3321: f'Failed to connect to host {host} for payload read_snapshot_info',
        3322: f'Failed to read data of snapshot {snapshot_identifier} for domain {vm_identifier} from host {host}',
        3323: f'Failed to connect to host {host} for payload restore_snapshot',
        3324: f'Failed to restore snapshot {snapshot_identifier} of domain {vm_identifier} on host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_snapshot_info': f'Get-VMSnapshot -VMName {vm_identifier} -Name {snapshot_identifier} -ea SilentlyContinue',
            'restore_snapshot':   f'Restore-VMCheckpoint -Name {snapshot_identifier} -VMName {vm_identifier} -Confirm:$false',
        }

        ret = rcc.run(payloads['read_snapshot_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('read_snapshot_info', ret)

        ret = rcc.run(payloads['restore_snapshot'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('restore_snapshot', ret)

        return True, f'1300: {messages[1300]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3320, {})
    return status, msg


def list(
        vm_identifier: str,
        host: str,
) -> Tuple[bool, str]:
    """
    description: list all snapshots for a given VM

    parameters:
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag stating the restore was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1400: f'Successfully retrieved snapshot list for domain {vm_identifier} on host {host}',
        3421: f'Failed to connect to host {host} for payload list_snapshots',
    }

    data_dict = {}

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'list_snapshots': f'Get-VMSnapshot -VMName {vm_identifier} '
                              '| Select VMName,Name,SnapshotType,CreationTime,ParentSnapshotName,Path '
                              '| ConvertTo-Csv -NoTypeInformation',
        }

        ret = rcc.run(payloads['list_snapshots'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('list_snapshots', ret)

        data_dict[host] = hyperv_dictify_csv(ret["payload_message"])

        return True, f'1400: {messages[1400]}', fmt.successful_payloads, data_dict

    retval, msg, successful_payloads, data_dict = run_host(host, 3420, {})
    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f'1400: {messages[1400]}']
    return status, data_dict, msg
