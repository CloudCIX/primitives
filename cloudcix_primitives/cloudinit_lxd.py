"""
Cloud-init user-data configuration management for LXD instances
"""
# stdlib
from typing import Dict, Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'update',
    'read',
]

def update(
    endpoint_url: str,
    project: str,
    instance_name: str,
    cloud_init_config: str,
    verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Update cloud-init user-data configuration for an LXD instance.

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
        cloud_init_config:
            description: The cloud-init user-data configuration content.
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
    # Define the config key
    config_key = "cloud-init.user-data"
    messages = {
        1000: f'Successfully updated cloud-init user-data for instance {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to update cloud-init configuration for instance {instance_name}. Error: ',
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
        
        # Update the cloud-init configuration
        try:
            instance.config[config_key] = cloud_init_config
            instance.save(wait=True)
            fmt.add_successful('cloud_init.update', {config_key: 'updated'})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads
    
    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'

def read(
        endpoint_url: str,
        project: str,
        instance_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, Dict, str]:
    """
    description:
        Retrieve cloud-init user-data configuration from an LXD instance.

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
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: A tuple with a boolean flag indicating success or failure, a dictionary containing the configuration, and a message.
        type: tuple
    """
    # Define the config key
    config_key = "cloud-init.user-data"
    messages = {
        1000: f'Successfully retrieved cloud-init user-data from instance {instance_name} on {endpoint_url}',
        1001: f'No cloud-init user-data configuration found for instance {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        result = {}
        
        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, result
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, result

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)
        
        # Get the cloud-init configuration
        cloud_init_config = instance.config.get(config_key, '')
        
        if cloud_init_config:
            result[config_key] = cloud_init_config
            fmt.add_successful('cloud_init.read', {config_key: 'found'})
            message = f'1000: {messages[1000]}'
        else:
            result[config_key] = None
            fmt.add_successful('cloud_init.read', {config_key: 'not_found'})
            message = f'1001: {messages[1001]}'
            
        return True, message, fmt.successful_payloads, result

    status, msg, successful_payloads, result = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return False, {}, msg

    return True, result, msg
