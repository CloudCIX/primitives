"""
Module for managing RadOS Block Devices via LXD host.
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
    pool_name: str,
    volume_name: str,
    size: int,
    verify_lxd_certs: bool = False,
) -> Tuple[bool, str]:
    """
    description: Build a RadOS Block Device via LXD host.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        pool_name:
            description: Name of the storage pool.
            type: string
            required: true
        volume_name:
            description: Name to give the new volume.
            type: string
            required: true
        size:
            description: Size of the volume in GB.
            type: integer
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure, and a message.
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully built RadOS Block Device {volume_name} in pool {pool_name} on {endpoint_url}',
        3001: f'Failed to connect to {endpoint_url} for storage pool operations',
        3002: f'Failed to get storage pool {pool_name} on {endpoint_url}',
        3003: f'Failed to create RadOS Block Device volume {volume_name} in pool {pool_name}',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # STEP 1: Confirm the Ceph storage pool exists
        ret = rcc.run(cli='storage_pools.get', name=pool_name)
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads
        
        # Get the pool object for further operations
        pool_obj = ret["payload_message"]
        fmt.add_successful('storage_pools.get', ret)

        # STEP 2: Create the volume configuration
        volume_config = {
            "config": {
                "size": f"{size}GiB"
            },
            "name": volume_name,
            "type": "custom"
        }
        
        # STEP 3: Create the volume
        try:
            if hasattr(pool_obj, 'volumes') and hasattr(pool_obj.volumes, 'create'):
                pool_obj.volumes.create(pool_obj.client, volume_config)
                fmt.add_successful('volume.create', {'name': volume_name, 'size': f"{size}GiB"})
            else:
                return False, f"{prefix+3}: {messages[prefix+3]} - Missing required methods on pool object", fmt.successful_payloads
        except AttributeError as e:
            return False, f"{prefix+3}: {messages[prefix+3]} - Invalid pool object structure: {str(e)}", fmt.successful_payloads
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]} - {str(e)}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3000, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def read(
    endpoint_url: str,
    pool_name: str,
    volume_name: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, Dict, str]:
    """
    description: Read a RadOS Block Device via LXD host.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        pool_name:
            description: Name of the storage pool.
            type: string
            required: true
        volume_name:
            description: Name of the volume to read.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure, a data dictionary, and a message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully read RadOS Block Device {volume_name} in pool {pool_name} on {endpoint_url}',
        1001: f'Volume {volume_name} not found in pool {pool_name}',
        3001: f'Failed to connect to {endpoint_url} for storage pool operations',
        3002: f'Failed to get storage pool {pool_name} on {endpoint_url}',
        3003: f'Failed to get volume {volume_name} in pool {pool_name}',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        result = {}
        
        # STEP 1: Confirm the Ceph storage pool exists
        ret = rcc.run(cli='storage_pools.get', name=pool_name)
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, {}, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}")
        if ret["payload_code"] != API_SUCCESS:
            return False, {}, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}")
        
        # Get the pool object
        pool_obj = ret["payload_message"]
        fmt.add_successful('storage_pools.get', ret)
        
        # STEP 2: Get volume info
        if not hasattr(pool_obj, 'volumes') or not hasattr(pool_obj.volumes, 'get'):
            return False, {}, f"{prefix+3}: {messages[prefix+3]} - Missing required methods on pool object"
        
        try:
            volume = pool_obj.volumes.get("custom", volume_name)
            
            if not volume:
                return False, {}, f"{prefix+3}: {messages[prefix+3]} - Volume not found"
                
            # Extract volume details
            result["volume"] = {
                "name": volume.name,
                "type": volume.type,
                "config": volume.config,
            }
            
            # Return success
            return True, {endpoint_url: result}, messages[1000]
        except AttributeError as e:
            return False, {}, f"{prefix+3}: {messages[prefix+3]} - Invalid volume object structure: {str(e)}"
        except Exception as e:
            return False, {}, f"{prefix+3}: {messages[prefix+3]} - {str(e)}"

    status, result, msg = run_host(endpoint_url, 3000, {})
    
    if status is False:
        return status, result, msg

    return True, result, f'1000: {messages[1000]}'


def scrub(
    endpoint_url: str,
    pool_name: str,
    volume_name: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description: Scrub (delete) a RadOS Block Device via LXD host.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        pool_name:
            description: Name of the storage pool.
            type: string
            required: true
        volume_name:
            description: Name of the volume to delete.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure, and a message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully scrubbed RadOS Block Device {volume_name} from pool {pool_name} on {endpoint_url}',
        3001: f'Failed to connect to {endpoint_url} for storage pool operations',
        3002: f'Failed to get storage pool {pool_name} on {endpoint_url}',
        3003: f'Failed to delete volume {volume_name} from pool {pool_name}',
        3004: f'Volume {volume_name} not found in pool {pool_name}',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # STEP 1: Confirm the Ceph storage pool exists
        ret = rcc.run(cli='storage_pools.get', name=pool_name)
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        pool_obj = ret["payload_message"]
        fmt.add_successful('storage_pools.get', ret)
        
        # STEP 2: Check if the pool has the required methods
        if not hasattr(pool_obj, 'volumes') or not hasattr(pool_obj.volumes, 'get'):
            return False, f"{prefix+3}: {messages[prefix+3]} - Missing required methods on pool object", fmt.successful_payloads
        
        # STEP 3: Try to get the volume first to ensure it exists
        try:
            volume = pool_obj.volumes.get("custom", volume_name)
            
            if not volume:
                return False, f"{prefix+4}: {messages[prefix+4]}", fmt.successful_payloads
            
            # STEP 4: Delete the volume
            volume.delete()
            fmt.add_successful('volume.delete', {'name': volume_name})
            
        except AttributeError as e:
            return False, f"{prefix+3}: {messages[prefix+3]} - Invalid volume object structure: {str(e)}", fmt.successful_payloads
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]} - {str(e)}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3000, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
