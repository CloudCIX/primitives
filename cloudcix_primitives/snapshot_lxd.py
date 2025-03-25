"""
LXD Snapshot Management Module
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'build',
    'read',
    'scrub',
    'update',
]

def build(
        endpoint_url: str,
        project: str,
        container_name: str,
        snapshot_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Create a snapshot for an LXD container.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        container_name:
            description: The name of the LXD container to snapshot.
            type: string
            required: true
        snapshot_name:
            description: The name to give the snapshot.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    
    return:
        description: |
            A tuple with a boolean flag indicating success or failure, a message.
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully created snapshot {snapshot_name} for container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to create snapshot for container {container_name}. Error: ',
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
        
        # Create the snapshot
        try:
            instance.snapshots.create(snapshot_name)
            fmt.add_successful('snapshot.create', {'snapshot_name': snapshot_name})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1000: {messages[1000]}'


def read(
        endpoint_url: str,
        project: str,
        container_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Retrieve details for the current snapshot from an LXD container.
        NOTE: Using ZFS filesystem, only one snapshot can exist at a time.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        container_name:
            description: The name of the LXD container containing the snapshot.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    
    return:
        description: |
            A tuple with a boolean flag indicating success or failure, a dictionary containing snapshot data, and a message.
        type: tuple
    """
    # Define message
    messages = {
        1200: f'Successfully read snapshot for container {container_name} on {endpoint_url}',
        1201: f'No snapshots found for container {container_name} on {endpoint_url}',
        3221: f'Failed to connect to {endpoint_url} for containers.get payload',
        3222: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3223: f'Failed to retrieve snapshot information. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        result = {}
        
        # Get container
        ret = rcc.run(cli='containers.get', name=container_name)
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, result
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, result
        
        container = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
        try:
            # Get snapshots
            snapshots = list(container.snapshots.all())
            
            if not snapshots:
                # No snapshots found
                result['snapshot'] = None
                fmt.add_successful('snapshots.list', {'count': 0})
                return True, '', fmt.successful_payloads, result
            
            # Get the first snapshot (ZFS only allows one)
            snapshot = snapshots[0]
            
            # Extract snapshot data into a dictionary
            snapshot_data = {
                'name': snapshot.name,
                'created_at': snapshot.created_at,
            }
            
            # Add config if available
            if hasattr(snapshot, 'config'):
                snapshot_data['config'] = snapshot.config
            
            result['snapshot'] = snapshot_data
            fmt.add_successful('containers.snapshots.get', {'snapshot': snapshot_data})
                
        except Exception as e:
            error_msg = f"{prefix+3}: {messages[prefix+3]}{str(e)}"
            return False, fmt.store_error(str(e), error_msg), fmt.successful_payloads, result

        return True, '', fmt.successful_payloads, result

    # Run the host function and get results
    status, msg, successful_payloads, result = run_host(endpoint_url, 3220, {})

    if not status:
        return False, {}, msg
    
    # Prepare response data
    data = {endpoint_url: result}
    
    # Select appropriate message based on whether a snapshot was found
    if result.get('snapshot') is None:
        return True, data, f'1201: {messages[1201]}'
    
    return True, data, f'1200: {messages[1200]}'


def scrub(
        endpoint_url: str,
        project: str,
        container_name: str,
        snapshot_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """Delete a snapshot from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container containing the snapshot.
    :param snapshot_name: The name of the snapshot to delete.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define messages
    messages = {
        1100: f'Successfully deleted snapshot {snapshot_name} from container {container_name} on {endpoint_url}',
        3121: f'Failed to connect to {endpoint_url} for containers.get payload',
        3122: f'Failed to run containers.get payload on {endpoint_url}',
        3123: f'Failed to find snapshot {snapshot_name} for container {container_name}',
        3124: f'Failed to delete snapshot {snapshot_name}. Error: ',
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
        
        # Find and delete the snapshot
        try:
            # Get the snapshot
            snapshot = instance.snapshots.get(snapshot_name)
            if not snapshot:
                fmt.add_successful('snapshot.not_found', {'snapshot_name': snapshot_name})
                return True, f"1100: {messages[1100]}", fmt.successful_payloads
            
            # Delete the snapshot with wait=True to ensure the operation completes before continuing
            snapshot.delete(wait=True)
            fmt.add_successful('snapshot.delete', {'snapshot_name': snapshot_name})
            
        except Exception as e:
            return False, f"{prefix+4}: {messages[3124]}{e}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1100: {messages[1100]}'


def update(
        endpoint_url: str,
        project: str,
        container_name: str,
        snapshot_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Restore a container from a snapshot.
        NOTE: Since we're using ZFS filesystem, only one snapshot can exist at a time,
        so the snapshot_name parameter is required to identify the snapshot.
    
    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        container_name:
            description: The name of the LXD container containing the snapshot.
            type: string
            required: true
        snapshot_name:
            description: The name of the snapshot to restore from.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    
    return:
        description: |
            A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
        type: tuple
    """
    # Define messages
    messages = {
        1300: f'Successfully restored container {container_name} from snapshot {snapshot_name} on {endpoint_url}',
        3321: f'Failed to connect to {endpoint_url} for containers.get payload',
        3322: f'Failed to run containers.get payload on {endpoint_url}',
        3323: f'No snapshots found for container {container_name}',
        3324: f'Failed to restore from snapshot. Error: ',
        3325: f'Snapshot {snapshot_name} not found for container {container_name}',
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
        
        try:
            # Get the specific snapshot
            snapshot = instance.snapshots.get(snapshot_name)
            if not snapshot:
                return False, f"{prefix+5}: {messages[3325]}", fmt.successful_payloads
                
            # Perform the restore operation with default parameters
            snapshot.restore(wait=True)
            fmt.add_successful('snapshot.restore', {'snapshot_name': snapshot_name})
            
        except Exception as e:
            return False, f"{prefix+4}: {messages[3324]}{e}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3320, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1300: {messages[1300]}'
