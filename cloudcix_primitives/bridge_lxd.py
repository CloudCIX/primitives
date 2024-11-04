"""
Primitive for Private Bridge in LXD
"""

# 3rd party modules
import jinja2
# stdlib
import os
from typing import Tuple
# local
from cloudcix_primitives.utils import HostErrorFormatter, PyLXDWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]



def build(
        host: str,
        name: int,
        verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Configures a bridge on the LXD host.

    parameters:
        host:
            description: LXD Host where the service will be created
            type: string
            required: true
        name:
          description: The name of the bridge to create
          type: integer
          required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'Successfully created and started bridge_lxd_{name}.service on tux {host}.',

        3021: f'Failed to connect to the host {host} for network.exists payload',
        3022: f'Failed to run network.exists payload on the host {host}. Payload exited with status ',
    }

    config = {
        'ipv4.address': None,
        'ipv6.address': None,
    }


    def run_host(host, prefix, successful_payloads):
        rcc = PyLXDWrapper(host, verify_lxd_certs)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        ret = rcc.run(object='network', method='exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('network.exists', ret)
        
        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]
