"""
Cloud-init configuration management for LXD containers
Allows updating, reading, and scrubbing user-data, vendor-data, and network-config.
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
    'scrub',
]

def update(
        endpoint_url: str,
        project: str,
        container_name: str,
        cloud_init_config: str,
        config_type: str = 'user-data',
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """ Update cloud-init configuration for an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param cloud_init_config: The cloud-init configuration content. NOTE: /path/to/file.yaml
    :param config_type: Type of cloud-init config ('user-data', 'vendor-data', or 'network-config').
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure and a message.
    """
    # Validate config_type
    valid_types = ('user-data', 'vendor-data', 'network-config')
    if config_type not in valid_types:
        return False, f"Invalid config_type: {config_type}. Must be one of: {', '.join(valid_types)}"
    
    # Define message
    config_key = f"cloud-init.{config_type}"
    messages = {
        1000: f'Successfully updated cloud-init {config_type} for container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to update cloud-init configuration for container {container_name}. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the instance
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
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
        container_name: str,
        config_type: str = 'user-data',
        verify_lxd_certs: bool = True
) -> Tuple[bool, Dict, str]:
    """ Retrieve cloud-init configuration from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param config_type: Type of cloud-init config ('user-data', 'vendor-data', or 'network-config').
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a dictionary containing the configuration, and a message.
    """
    # Validate config_type
    valid_types = ('user-data', 'vendor-data', 'network-config')
    if config_type not in valid_types:
        return False, {}, f"Invalid config_type: {config_type}. Must be one of: {', '.join(valid_types)}"
    
    # Define message
    config_key = f"cloud-init.{config_type}"
    messages = {
        1000: f'Successfully retrieved cloud-init {config_type} from container {container_name} on {endpoint_url}',
        1001: f'No cloud-init {config_type} configuration found for container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
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
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, result
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, result

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
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

def scrub(
        endpoint_url: str,
        project: str,
        container_name: str,
        config_type: str = 'user-data',
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """ Remove cloud-init configuration from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param config_type: Type of cloud-init config ('user-data', 'vendor-data', or 'network-config').
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure and a message.
    """
    # Validate config_type
    valid_types = ('user-data', 'vendor-data', 'network-config')
    if config_type not in valid_types:
        return False, f"Invalid config_type: {config_type}. Must be one of: {', '.join(valid_types)}"
    
    # Define message
    config_key = f"cloud-init.{config_type}"
    messages = {
        1000: f'Successfully removed cloud-init {config_type} configuration from container {container_name} on {endpoint_url}',
        1001: f'No cloud-init {config_type} configuration found to remove for container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to remove cloud-init configuration for container {container_name}. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the instance
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
        # Check if the cloud-init configuration exists
        if config_key not in instance.config:
            fmt.add_successful('cloud_init.scrub', {config_key: 'not_found'})
            return True, f'1001: {messages[1001]}', fmt.successful_payloads
        
        # Remove the cloud-init configuration
        try:
            del instance.config[config_key]
            instance.save(wait=True)
            fmt.add_successful('cloud_init.scrub', {config_key: 'removed'})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, f'1000: {messages[1000]}', fmt.successful_payloads
    
    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, msg
