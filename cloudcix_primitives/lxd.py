"""
Primitive for managing an LXD instance.
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, comms_lxd, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]


INSTANCE_DEFAULT = {
    "architecture": "x86_64",
    "profiles": ["default"],
    "ephemeral": False,
    "config": {},
    "devices": {},
    "source": {
        "type": "image",
        "mode": "pull",
        "protocol": "simplestreams",
    },
}

def build(
    endpoint_url: str,
    name: int,
    config=None,
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Configures a bridge on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be created
            type: string
            required: true
        name:
            description: The name of the bridge to create
            type: integer
            required: true
        config:
            description: |
                A dictionary for the additional configuration of the LXD bridge network.
                See https://documentation.ubuntu.com/lxd/en/latest/reference/network_bridge/#configuration-options
            type: object
            required: false
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
        1000: f'Successfully created bridge_lxd {name} on {endpoint_url}.',

        3021: f'Failed to connect to {endpoint_url} for networks.exists payload',
        3022: f'Failed to run networks.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for networks.create payload',
        3024: f'Failed to run networks.create payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):

        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        ret = rcc.run(cli='networks.exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads

        bridge_exists = ret['payload_message']
        fmt.add_successful('networks.exists', ret)

        if bridge_exists == False:
            ret = rcc.run(cli='networks.create', name=name, type='bridge', config=config)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]

