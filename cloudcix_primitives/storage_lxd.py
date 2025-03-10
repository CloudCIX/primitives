"""
Module for updating the root disk size of an LXD container.
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'update',
]

def update(
        endpoint_url: str,
        project: str,
        instance_name: str,
        new_size: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, str, dict]:
    """ Update the root disk size of an LXD container.
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance.
    :param new_size: The new size for the root disk (e.g., '20GB').
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define message
    messages = {
        1000: f'Successfully updated root disk size for containers {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to get containers {instance_name} configuration',
        3023: f'Failed to update root disk size for containers {instance_name}. Error: ',
        3024: f'Root disk not found in containers devices',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get the container
        ret = rcc.run(cli='containers.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        container = ret['payload_message']
        fmt.add_successful('container get', ret)

        # Update the root disk size
        if 'root' not in container.devices:
            return False, f"{prefix+4}: {messages[prefix+4]}", fmt.successful_payloads
        
        try:
            container.devices['root']['size'] = new_size
            container.save(wait=True)
            fmt.add_successful('container.set', {'root.size': new_size})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg, successful_payloads

    return True, f'1000: {messages[1000]}', successful_payloads
