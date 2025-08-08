"""
Module for managing secondary LXD storage volumes attached to instances. (Host Storage Voumes / Remote RADOS Block Devices)
"""
# stdlib
from typing import Dict, Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'build',
    'read',
    'scrub',
]

def build(
        endpoint_url: str,
        project: str,
        instance_name: str,
        volume_name: str,
        mount_point: str,
        instance_type: str,
        verify_lxd_certs: bool = True,
        storage_pool: str = "default",
) -> Tuple[bool, str]:
    """
    description:
        Attach a secondary LXD storage volume to an instance.

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
        volume_name:
            description: The name of the LXD storage volume to attach.
            type: string
            required: true
        mount_point:
            description: The mount point for the volume inside the instance.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
        storage_pool:
            description: The storage pool to use for the volume.
            type: string
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully attached volume {volume_name} to {instance_type} {instance_name} on {endpoint_url}',
        1001: f'Volume {volume_name} is already attached to {instance_type} {instance_name}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to get instance {instance_name} configuration',
        3023: f'Failed to attach volume {volume_name} to instance {instance_name}. Error: ',
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

        # Check if the volume is already attached
        if volume_name in instance.devices:
            # Volume already attached
            return True, f'1001: {messages[1001]}', fmt.successful_payloads

        # Create device config
        device_config = {
            "type": "disk",
            "pool": storage_pool,
            "source": volume_name,
            "path": mount_point,
        }

        # Add the device to the instance
        instance.devices[volume_name] = device_config

        # Update the instance configuration
        try:
            instance.save(wait=True)
            fmt.add_successful('instances.save', {'device_added': volume_name})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads
        
        return True, f'1000: {messages[1000]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg
    
    return True, msg


def read(
        endpoint_url: str,
        project: str,
        instance_name: str,
        volume_name: str,
        instance_type: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, str, Dict]:
    """
    description:
        Read the configuration of a secondary LXD storage volume attached to an instance.

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
        volume_name:
            description: The name of the LXD storage volume to read.
            type: string
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
        description: |
            A tuple containing:
            - Boolean indicating success (True) or failure (False)
            - String containing a success message or error message
            - Dict containing the volume configuration if successful, empty dict otherwise
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully read volume {volume_name} from {instance_type} {instance_name} on {endpoint_url}',
        1001: f'Volume {volume_name} not found in {instance_type} {instance_name}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to get instance {instance_name} configuration',
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

        # Read the volume configuration
        if volume_name not in instance.devices:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads
        
        volume_config = instance.devices[volume_name]
        fmt.successful_payloads['volume_config'] = volume_config
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status:
        if 'volume_config' in successful_payloads:
            volume_details = successful_payloads['volume_config']
            return True, f'1000: {messages[1000]}', volume_details
        else:
            return True, f'1001: {messages[1001]}', {}
    else:
        return False, msg, {}
    

def scrub(
        endpoint_url: str,
        project: str,
        instance_name: str,
        volume_name: str,
        instance_type: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Detach a secondary LXD storage volume from an instance.

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
        volume_name:
            description: The name of the LXD storage volume to detach.
            type: string
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
    # Define messages
    messages = {
        1000: f'Successfully detached volume {volume_name} from {instance_type} {instance_name} on {endpoint_url}',
        1001: f'Volume {volume_name} not found in {instance_type} {instance_name}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to get instance {instance_name} configuration',
        3023: f'Failed to detach volume {volume_name} from instance {instance_name}. Error: ',
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

        # Detach the volume from the instance
        if volume_name not in instance.devices:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads      
        try:
            del instance.devices[volume_name]
            instance.save(wait=True)
            fmt.add_successful('instances.save', {'device_removed': volume_name})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads
            
        return True, f'1000: {messages[1000]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg
    
    return True, msg
