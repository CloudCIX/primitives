"""
Module for connecting an LXD host to a CEPH storage pool.
Assumes the storage pool already exists on the CEPH host.
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
]

def build(
    endpoint_url: str,
    pool_name: str,
    ceph_source: str,
    ceph_user: str,
    ceph_cluster_name: str="ceph",
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description: Connect an LXD host to an existing CEPH storage pool.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        pool_name:
            description: Name to give the storage pool on the LXD host.
            type: string
            required: true
        ceph_source:
            description: Name of the existing storage pool on the CEPH host.
            type: string
            required: true
        ceph_user:
            description: CEPH user with access to the storage pool.
            type: string
            required: true
        ceph_cluster_name:
            description: Name of the CEPH cluster.
            type: string
            required: false
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
        1000: f'Successfully connected LXD host {endpoint_url} to CEPH storage pool {ceph_source} as {pool_name}',
        1001: f'Storage pool {pool_name} already exists on LXD host {endpoint_url}',
        3001: f'Failed to connect to {endpoint_url} for storage pool operations',
        3002: f'Failed to check if storage pool {pool_name} exists on {endpoint_url}',
        3003: f'Failed to create storage pool {pool_name} on {endpoint_url}',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Check if the storage pool already exists
        ret = rcc.run(cli='storage_pools.exists', name=pool_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads        
        pool_exists = ret['payload_message']
        fmt.add_successful('storage_pools.exists', ret)        
        # If the pool already exists, return success with appropriate message
        if pool_exists:
            return True, f"1001: {messages[1001]}", fmt.successful_payloads

        try:
        # Create the storage pool.
            pool_config = {
                "name": pool_name,
                "description": "",
                "driver": "ceph",
                "config": {
                    "source": ceph_source,
                    "ceph.cluster_name": ceph_cluster_name,
                    "ceph.user.name": ceph_user,
                    "ceph.osd.pool_name": ceph_source,
                    "volatile.initial_source": ceph_source,
                    "volatile.pool.pristine": "true",
                    "ceph.osd.pg_num": "32"
                }
            }
            ret = rcc.run(
                cli='storage_pools.create',
                definition=pool_config
            )
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads
            
            fmt.add_successful('storage_pools.create', {'name': pool_name, 'driver': 'ceph'})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {str(e)}", fmt.successful_payloads
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3000, {})
    
    if status is False:
        return status, msg
    if msg.startswith('1001:'):
        return True, msg
    # Otherwise return the success message
    return True, f'1000: {messages[1000]}'


def read(
    endpoint_url: str,
    pool_name: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, Dict, str]:
    """
    description: Read details of a CEPH storage pool connected to an LXD host.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        pool_name:
            description: Name of the storage pool on the LXD host.
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
    # Define messages
    messages = {
        1000: f'Successfully read CEPH storage pool {pool_name} on LXD host {endpoint_url}',
        1001: f'Storage pool {pool_name} not found on LXD host {endpoint_url}',
        3001: f'Failed to connect to {endpoint_url} for storage pool operations',
        3002: f'Failed to check if storage pool {pool_name} exists on {endpoint_url}',
        3003: f'Failed to get storage pool {pool_name} details on {endpoint_url}',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        result = {}
        
        # STEP 1: Check if the storage pool exists
        ret = rcc.run(cli='storage_pools.exists', name=pool_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, {}, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}")
        if ret["payload_code"] != API_SUCCESS:
            return False, {}, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}")
        
        pool_exists = ret['payload_message']
        fmt.add_successful('storage_pools.exists', ret)
        
        # If the pool doesn't exist, return appropriate message
        if not pool_exists:
            return True, {}, f"1001: {messages[1001]}"
        
        # STEP 2: Get storage pool details
        try:
            ret = rcc.run(cli='storage_pools.get', name=pool_name)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, {}, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}")
            if ret["payload_code"] != API_SUCCESS:
                return False, {}, fmt.payload_error(ret, f"{prefix+3}: {messages[prefix+3]}")
            
            # Extract storage pool details 
            pool_obj = ret['payload_message']
            fmt.add_successful('storage_pools.get', ret)
            
            result[endpoint_url] = {
                "name": pool_obj.name,
                "driver": pool_obj.driver,
                "used_by": pool_obj.used_by,
                "config": pool_obj.config,
            }
            
            # Add volumes information if available
            if hasattr(pool_obj, 'volumes') and hasattr(pool_obj.volumes, 'all'):
                try:
                    volumes = [v.name for v in pool_obj.volumes.all()]
                    result[endpoint_url]["volumes"] = volumes
                except:
                    result[endpoint_url]["volumes"] = "Unable to retrieve volumes"
            
            return True, result, f"1000: {messages[1000]}"
            
        except Exception as e:
            return False, {}, f"{prefix+3}: {messages[prefix+3]}: {str(e)}"

    status, result, msg = run_host(endpoint_url, 3000, {})
    
    if status is False:
        return status, {}, msg
   
    return True, result, msg
