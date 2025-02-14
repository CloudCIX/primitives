# stdlib
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import LXDCommsWrapper, HostErrorFormatter

__all__ = [
    'update',
]

SUPPORTED_INSTANCES = ['virtual_machines', 'containers']

def update(endpoint_url: str, project: str, name: str, instance_type: str, cpu: int, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    Update the CPU count of an LXD instance.

    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param name: The name of the LXD instance.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param cpu: The number of CPUs to set.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, and a message.
    """
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'Invalid instance_type "{instance_type}". Supported instance types are "containers" and "virtual_machines".'

    rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
    fmt = HostErrorFormatter(endpoint_url, {'payload_message': 'STDOUT', 'payload_error': 'STDERR'}, {})

    # Update the CPU count using REST API
    ret = rcc.run(cli=f'lxc config set {name} limits.cpu {cpu}')
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, fmt.channel_error(ret, "Failed to update the CPU count.")
    if ret["payload_code"] != API_SUCCESS:
        return False, fmt.payload_error(ret, "Failed to update the CPU count.")


def update() -> Tuple[bool, str]:
    return(False, 'Not Implemented')
    return True, "Successfully updated the CPU count."