"""
Primitive for modifying virtual machine RAM on Windows hypervisor
"""
# stdlib
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_lsh, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    SSHCommsWrapper,
)

__all__ = [
    'build',
]

SUCCESS_CODE = 0


def build(
    host: str,
    vm_identifier: str,
    ram: int,
) -> Tuple[bool, str]:
    """
    description: modifies a HyperV virtual machine's RAM

    parameters:
        host:
            description: The DNS name or IP address of the host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        ram:
            description: Number of RAM, in GBs, for the HyperV VM
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
        1000: f'Successfully set RAM for VM {vm_identifier} on Host {host} to {ram}.',
        # payload execution
        3031: f'Failed to connect to the host {host} for set_ram payload.',
        3032: f'Failed to to run set_ram payload on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'administrator')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'set_ram':                  f'Set-VMMemory {vm_identifier} -DynamicMemoryEnabled $false -StartupBytes {ram}GB',
        }

        ret = rcc.run(payloads['set_ram'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('set_ram', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'

