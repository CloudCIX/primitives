"""
Network-Config management for LXD containers
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
    container_name: str,
    network_config: str,
    verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """ Update cloud-init network-config configuration for an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param network_config: The cloud-init network-config content. NOTE: /path/to/file.yaml
            eth0:
                addresses:
                - 192.168.1.50/24      # primary IP 
                - 192.168.1.51/24      # additional IP etc
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure and a message.
    """
    # Define the config key
    config_key = "cloud-init.network-config"
    messages = {
        1000: f'Successfully updated cloud-init network-config for container {container_name} on {endpoint_url}',
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
        
        # Update the network configuration
        try:
            instance.config[config_key] = network_config
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
        verify_lxd_certs: bool = True
) -> Tuple[bool, Dict, str]:
    """ Retrieve cloud-init 'network-config' configuration from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a dictionary containing the configuration, and a message.
    """
    # Define the config key
    config_key = "cloud-init.network-config"
    messages = {
        1000: f'Successfully retrieved cloud-init network-config from container {container_name} on {endpoint_url}',
        1001: f'No cloud-init network-config configuration found for container {container_name} on {endpoint_url}',
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
        
        # Get the Network-Config
        network_config = instance.config.get(config_key, '')
        
        if network_config:
            result[config_key] = network_config
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