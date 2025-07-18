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
    new_size: int,
    instance_type: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Update the root disk size of an LXD instance.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        project:
            description: The LXD project name.
            type: string
            required: true
        instance_name:
            description: The name of the LXD instance.
            type: string
            required: true
        new_size:
            description: The new size for the root disk in GB.
            type: integer
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully updated root disk size for instance {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to get instance {instance_name} configuration',
        3023: f'Failed to update root disk size for instance {instance_name}. Error: ',
        3024: f'Root disk not found in instance devices',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get the container
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        container = ret['payload_message']
        fmt.add_successful('instances.get', ret)

        # Update the root disk size
        if 'root' not in container.devices:
            return False, f"{prefix+4}: {messages[prefix+4]}", fmt.successful_payloads
        
        try:
            container.devices['root']['size'] = f'{new_size}GB'
            container.save(wait=True)
            fmt.add_successful('instances.set', {'root.size': f'{new_size}GB'})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
