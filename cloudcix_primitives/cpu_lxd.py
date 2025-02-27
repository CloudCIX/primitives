'''
POC: CPU limit update for LXD instances.
'''
# stdlib
import sys
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'update',
]

SUPPORTED_INSTANCES = ['virtual_machines', 'containers']

def update(
        endpoint_url: str,
        project: str,
        instance_name: str,
        instance_type: str,
        cpu: int,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    
    """ Update the CPU limit of an LXD instance.
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param name: The name of the LXD instance.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param cpu: The number of CPU cores to set.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define message
    messages = {
        1000: f'Successfully updated the CPU limit for {instance_type} {instance_name} on {endpoint_url}',
        3011: f'Invalid instance_type "{instance_type}" sent. Supported instance types are "containers" and "virtual_machines"',
        3021: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3022: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to set CPU limit for {instance_type} {instance_name}. Error: ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3011: {messages[3011]}', {}

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the instance
        ret = rcc.run(cli=f'{instance_type}.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads
        instance = ret['payload_message']
        fmt.add_successful(f'{instance_type}.get', ret)

        # Update the CPU limit
        try:
            instance.config['limits.cpu'] = str(cpu)
            instance.save(wait=True)
            fmt.add_successful(f'{instance_type}.set', {'limits.cpu': str(cpu)})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads
    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
