"""
Primitive to update config values on an LXD instance using pylxd.
"""
# stdlib
from typing import Dict, Tuple
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
    instance_type: str,
    config: Dict[str, str],
    verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Update config values on an LXD instance.

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
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        config:
            description: Dictionary of config key-value pairs to update on the instance.
            type: object
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    return:
        description: A tuple with a boolean flag indicating success or failure, and a message.
        type: tuple
    """
    messages = {
        1000: f'Successfully updated config for {instance_type} {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to update config for instance {instance_name}. Error: ',
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

        # Apply config updates
        try:
            instance.config.update(config)
            instance.save(wait=True)
            fmt.add_successful('instances.config_update', {'config': config})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg
    return True, f'1000: {messages[1000]}'
