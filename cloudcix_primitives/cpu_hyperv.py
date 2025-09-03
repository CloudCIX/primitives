"""
Primitive for modifying virtual machine's CPU count on Windows hypervisor
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
    'update',
    'read',
]

SUCCESS_CODE = 0


def update(
    host: str,
    vm_identifier: str,
    cpu: int,
) -> Tuple[bool, str]:
    """
    description: modifies a HyperV virtual machine's number of CPUs

    parameters:
        host:
            description: The DNS name or IP address of the host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        cpu:
            description: Number of CPUs for the HyperV VM
            type: integer
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Path Variables required by the payloads to build a VM.

    # Define message
    messages = {
        1000: f'Successfully set CPU count for VM {vm_identifier} on Host {host} to {cpu}.',
        # payload execution
        3031: f'Failed to connect to the host {host} for get_state payload.',
        3032: f'Failed to to run get_state payload on host {host}: ',
        3033: f'Unexpected state for VM. Must be `Off` for changing number of CPUs but current state is: ',
        3034: f'Failed to connect to the host {host} for set_cpu payload.',
        3035: f'Failed to to run set_cpu payload on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'administrator')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'get_state':    f'$state = Get-VM -Name "{vm_identifier}"; $state.State',
            'set_cpu':      f'Set-VMProcessor -VMName {vm_identifier} -Count {cpu}',
        }

        ret = rcc.run(payloads['get_state'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('get_state', ret)

        if ret['payload_message'].strip() != "Off":
            return False, f'{prefix + 3}: {messages[prefix + 3]} {ret["payload_message"]}', fmt.successful_payloads

        ret = rcc.run(payloads['set_cpu'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        fmt.add_successful('set_ram', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def read(
    host: str,
    vm_identifier: str,
) -> Tuple[bool, str]:
    """
    description: gets a HyperV virtual machine's number of CPUs

    parameters:
        host:
            description: The DNS name or IP address of the host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Path Variables required by the payloads to build a VM.

    # Define message
    messages = {
        1200: f'Successfully retrieved CPU count for VM {vm_identifier} on Host {host}.',
        # payload execution
        3031: f'Failed to connect to the host {host} for get_cpu payload.',
        3032: f'Failed to to run get_cpu payload on host {host}: ',
        3032: f'Failed to to run get_cpu payload on host {host}: ',
    }

    data_dict = {}
    message_list = []

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'administrator')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'get_cpu':      f'Get-VMProcessor {vm_identifier}',
        }

        ret = rcc.run(payloads['get_cpu'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            fmt.store_channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            fmt.store_payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            fmt.add_successful('get_cpu', ret)
            # CPU count will be under key `Count`
            data_dict[host] = hyperv_dictify(ret["payload_message"])

        return True, fmt.message_list, fmt.successful_payloads, data_dict

    status, msg_list, successful_payloads, data_dict = run_host(host, 3030, {})
    if status is False:
        return status, data_dict, message_list
    else:
        return status, data_dict, [f'1200: {messages[1200]}']
