'''
CPU limit update for LXD instances.
'''
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
        cpu: int,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    
    """ Update the CPU limit of an LXD instance.
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance.
    :param cpu: The number of CPU cores to set.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define message
    messages = {
        1000: f'Successfully updated the CPU limit for instance {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to set CPU limit for instance {instance_name}. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads
        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)

        # Update the CPU limit
        try:
            instance.config['limits.cpu'] = str(cpu)
            instance.save(wait=True)
            fmt.add_successful('instances.set', {'limits.cpu': str(cpu)})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads
    
    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
