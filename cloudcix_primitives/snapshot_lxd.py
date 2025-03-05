"""
POC: LXD Snapshot Management Module

Example usage:
# Create a snapshot with expiry date
python3 snapshot_lxd.py build https://10.254.3.9:8443 default container02 containers snap00 false "2025-04-15T12:00:00Z" true

# Read a snapshot
python3 snapshot_lxd.py read https://10.254.3.9:8443 default container02 containers snap00 false false true

# Read and restore from a snapshot (with stateful restore)
python3 snapshot_lxd.py read https://10.254.3.9:8443 default container02 containers snap00 true true true

# List all snapshots
python3 snapshot_lxd.py read https://10.254.3.9:8443 default container02 containers none false false true

# Delete a snapshot
python3 snapshot_lxd.py scrub https://10.254.3.9:8443 default container02 containers snap00 true

# Rename a snapshot
python3 snapshot_lxd.py update https://10.254.3.9:8443 default container02 containers snap00 new_name none true

# Update a snapshot's expiry date
python3 snapshot_lxd.py update https://10.254.3.9:8443 default container02 containers snap00 none "2026-06-30T00:00:00Z" true

# Update both name and expiry date
python3 snapshot_lxd.py update https://10.254.3.9:8443 default container02 containers snap00 new_name "2026-06-30T00:00:00Z" true
"""
# stdlib
from typing import Tuple, Optional


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

SUPPORTED_INSTANCES = ['containers']


def build(
        endpoint_url: str,
        project: str,
        instance_name: str,
        instance_type: str,
        snapshot_name: str,
        stateful: bool = False,
        expires_at: Optional[str] = None,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    """Create a snapshot for an LXD instance.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance to snapshot.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param snapshot_name: The name to give the snapshot.
    :param stateful: Whether to include the runtime state in the snapshot. NOTE: Stateful Containers require CRIU installation and config migration.stateful = true. 
    :param expires_at: Optional expiry date as ISO 8601 string (e.g. "2025-12-31T23:59:59"), or None for no expiry.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define messages
    messages = {
        1000: f'Successfully created snapshot {snapshot_name} for {instance_type} {instance_name} on {endpoint_url}',
        3011: f'Invalid instance_type "{instance_type}" sent. Supported instance types are {", ".join(SUPPORTED_INSTANCES)}',
        3021: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3022: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to create snapshot for {instance_type} {instance_name}. Error: ',
        3024: f'Failed to set expiry for snapshot {snapshot_name}. Error: ',
        3025: f'Invalid date format for expires_at. Expected ISO 8601 format (e.g. "2025-12-31T23:59:59"). Error: ',
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
        
        # Create the snapshot
        try:
            # Using the pylxd client's snapshot creation method
            instance.snapshots.create(snapshot_name, stateful=stateful)
            fmt.add_successful('snapshot.create', {'snapshot_name': snapshot_name, 'stateful': stateful})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads
        
        # Set expiry if provided
        if expires_at is not None:
            try:
                # Get the newly created snapshot
                snapshot = instance.snapshots.get(snapshot_name)
                
                # If expires_at is already in ISO format, use it directly
                iso_expires = expires_at
                
                # Use PUT request to update the snapshot with expiry
                data = {"expires_at": iso_expires}
                api_path = f"{instance._endpoint}/{instance.name}/snapshots/{snapshot_name}"
                
                response = instance.client.api[api_path].put(json=data)
                
                # Wait for operation to complete
                if response.json().get("type") == "async":
                    operation_id = response.json().get("operation")
                    instance.client.operations.wait_for_operation(operation_id)
                
                fmt.add_successful('snapshot.set_expiry', {
                    'snapshot_name': snapshot_name,
                    'expires_at': expires_at
                })
            except ValueError as e:
                return False, f"{prefix+5}: {messages[3025]}{e}", fmt.successful_payloads
            except Exception as e:
                return False, f"{prefix+4}: {messages[3024]}{e}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1000: {messages[1000]}', successful_payloads


def read(
        endpoint_url: str,
        project: str,
        instance_name: str,
        instance_type: str,
        snapshot_name: str = None,
        restore: bool = False,
        restore_stateful: bool = False,
        verify_lxd_certs: bool = True
) -> Tuple[bool, dict, str]:
    """Retrieve details for a snapshot or list all snapshots from an LXD instance.
    Can also restore from a snapshot if specified.
    
    If snapshot_name is provided, retrieves details for that specific snapshot.
    If snapshot_name is None, lists all snapshots for the instance.
    If restore is True, restores the instance from the specified snapshot.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance containing the snapshot.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param snapshot_name: The name of the snapshot to retrieve, or None to list all snapshots.
    :param restore: Boolean indicating whether to restore the instance from this snapshot. NOTE: zfs snapshots limited to most recent snapshot.
    :param restore_stateful: Boolean to restore the instance with its runtime state if the snapshot was stateful.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    
    :return: A tuple with a boolean flag indicating success or failure, a dictionary containing snapshot data, and a message.
    """
    # Define message
    messages = {
        1200: f'Successfully read snapshot {snapshot_name} for {instance_type} {instance_name} on {endpoint_url}',
        1201: f'Successfully listed all snapshots for {instance_type} {instance_name} on {endpoint_url}',
        1202: f'Successfully restored {instance_type} {instance_name} from snapshot {snapshot_name}',
        3211: f'Invalid instance_type "{instance_type}" sent. Supported instance types are {", ".join(SUPPORTED_INSTANCES)}',
        3221: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3222: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3223: f'Failed to retrieve snapshot information. Error: ',
        3224: f'Snapshot {snapshot_name} not found for {instance_type} {instance_name}',
        3225: f'Failed to list snapshots for {instance_type} {instance_name}. Error: ',
        3226: f'Restore operation requires a snapshot name',
        3227: f'Failed to restore {instance_type} {instance_name} from snapshot {snapshot_name}. Error: ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, {}, f'3211: {messages[3211]}'
    
    # Check if restore is requested but snapshot_name is not provided
    if restore and not snapshot_name:
        return False, {}, f'3226: {messages[3226]}'

    def run_host(endpoint_url, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[endpoint_url] = {}

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # First, get the instance object
        ret = project_rcc.run(cli=f'{instance_type}.get', name=instance_name)
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: {messages[prefix+1]}")
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        elif ret["payload_code"] != API_SUCCESS:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: {messages[prefix+2]}")
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        # Store the instance
        instance = ret['payload_message']
        fmt.add_successful(f'{instance_type}.get', ret)
        
        # Track what operations were performed for the return message
        operations = []
        
        if snapshot_name:
            # Get a specific snapshot
            try:
                snapshot = instance.snapshots.get(snapshot_name)
                if not snapshot:
                    retval = False
                    fmt.store_payload_error(
                        {'payload_code': 404, 'payload_error': f'Snapshot {snapshot_name} not found', 'payload_message': ''}, 
                        f"{prefix+4}: {messages[3224]}"
                    )
                    return retval, fmt.message_list, fmt.successful_payloads, data_dict
                
                # Convert snapshot to dict for return value
                snapshot_data = {
                    'name': snapshot.name,
                    'created_at': snapshot.created_at,
                    'stateful': snapshot.stateful
                }
                
                # If there's config data, add it
                if hasattr(snapshot, 'config'):
                    snapshot_data['config'] = snapshot.config
                
                # Add expires_at if present
                if hasattr(snapshot, 'config') and snapshot.config and 'expires_at' in snapshot.config:
                    snapshot_data['expires_at'] = snapshot.config['expires_at']
                
                data_dict[endpoint_url]['snapshot'] = snapshot_data
                fmt.add_successful(f'{instance_type}.snapshots.get', {'snapshot': snapshot_data})
                operations.append('read')
                
                # Restore from snapshot if requested
                if restore:
                    try:
                        # Setup restore options
                        restore_options = {}
                        if restore_stateful and snapshot.stateful:
                            restore_options['restore'] = True
                        
                        # Perform the restore operation
                        snapshot.restore(wait=True, **restore_options)
                        fmt.add_successful('snapshot.restore', {
                            'snapshot_name': snapshot_name, 
                            'restore_stateful': restore_stateful if snapshot.stateful else False
                        })
                        operations.append('restore')
                    except Exception as e:
                        retval = False
                        fmt.store_payload_error(
                            {'payload_code': 500, 'payload_error': str(e), 'payload_message': ''}, 
                            f"{prefix+7}: {messages[3227]}{str(e)}"
                        )
                        return retval, fmt.message_list, fmt.successful_payloads, data_dict
                
            except Exception as e:
                retval = False
                fmt.store_payload_error(
                    {'payload_code': 500, 'payload_error': str(e), 'payload_message': ''}, 
                    f"{prefix+3}: {messages[3223]}{str(e)}"
                )
                return retval, fmt.message_list, fmt.successful_payloads, data_dict
        else:
            # List all snapshots
            try:
                snapshots_data = {}
                for snapshot in instance.snapshots.all():
                    snapshot_info = {
                        'name': snapshot.name,
                        'created_at': snapshot.created_at,
                        'stateful': snapshot.stateful
                    }
                    
                    # Add expires_at if present
                    if hasattr(snapshot, 'config') and snapshot.config and 'expires_at' in snapshot.config:
                        snapshot_info['expires_at'] = snapshot.config['expires_at']
                        
                    snapshots_data[snapshot.name] = snapshot_info
                    
                data_dict[endpoint_url]['snapshots'] = snapshots_data
                fmt.add_successful('snapshots.list', {'count': len(snapshots_data)})
                operations.append('list')
                
            except Exception as e:
                retval = False
                fmt.store_payload_error(
                    {'payload_code': 500, 'payload_error': str(e), 'payload_message': ''}, 
                    f"{prefix+5}: {messages[3225]}{str(e)}"
                )
                return retval, fmt.message_list, fmt.successful_payloads, data_dict

        # Set the appropriate response message based on the operations performed
        data_dict['operations'] = operations
        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(endpoint_url, 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)

    if not retval:
        return retval, {}, "\n".join(message_list)
    else:
        if 'operations' in data_dict:
            operations = data_dict.pop('operations')
            
            if 'restore' in operations:
                return True, data_dict, f'1202: {messages[1202]}'
            elif snapshot_name and 'read' in operations:
                return True, data_dict, f'1200: {messages[1200]}'
            elif 'list' in operations:
                return True, data_dict, f'1201: {messages[1201]}'
        
        # Default response if operations weren't properly tracked
        if snapshot_name:
            return True, data_dict, f'1200: {messages[1200]}'
        else:
            return True, data_dict, f'1201: {messages[1201]}'


def scrub(
        endpoint_url: str,
        project: str,
        instance_name: str,
        instance_type: str,
        snapshot_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    """Delete a snapshot from an LXD instance.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance containing the snapshot.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param snapshot_name: The name of the snapshot to delete.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define messages
    messages = {
        1100: f'Successfully deleted snapshot {snapshot_name} from {instance_type} {instance_name} on {endpoint_url}',
        3111: f'Invalid instance_type "{instance_type}" sent. Supported instance types are {", ".join(SUPPORTED_INSTANCES)}',
        3121: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3122: f'Failed to run {instance_type}.get payload on {endpoint_url}',
        3123: f'Failed to find snapshot {snapshot_name} for {instance_type} {instance_name}',
        3124: f'Failed to delete snapshot {snapshot_name}. Error: ',
    }

    # Validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3111: {messages[3111]}', {}

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
        
        # Find and delete the snapshot
        try:
            # Get the snapshot
            snapshot = instance.snapshots.get(snapshot_name)
            if not snapshot:
                return False, f"{prefix+3}: {messages[prefix+3]}", fmt.successful_payloads
            
            # Delete the snapshot with wait=True to ensure the operation completes before continuing
            snapshot.delete(wait=True)
            fmt.add_successful('snapshot.delete', {'snapshot_name': snapshot_name})
            
        except Exception as e:
            return False, f"{prefix+4}: {messages[3124]}{e}", fmt.successful_payloads
            
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1100: {messages[1100]}', successful_payloads


def update(
        endpoint_url: str,
        project: str,
        instance_name: str,
        instance_type: str,
       snapshot_name: str,
        new_snapshot_name: str = None,
        expires_at: Optional[str] = None,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    """Update a snapshot for an LXD instance by renaming it or setting an expiry date.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance containing the snapshot.
    :param instance_type: The type of the LXD instance.
    :param snapshot_name: The current name of the snapshot.
    :param new_snapshot_name: Optional new name for the snapshot if renaming.
    :param expires_at: Optional expiry date as ISO 8601 string (e.g. "2025-12-31T23:59:59"), or None to remove expiry.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define messages
    messages = {
        1300: f'Successfully updated snapshot {snapshot_name} for {instance_type} {instance_name}',
        1301: f'Successfully renamed snapshot from {snapshot_name} to {new_snapshot_name}',
        1302: f'Successfully updated expiry date for snapshot {snapshot_name}',
        1303: f'Skipped renaming as new name is the same as current name',
        3311: f'Invalid instance_type "{instance_type}" sent. Supported instance types are {", ".join(SUPPORTED_INSTANCES)}',
        3321: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3322: f'Failed to run {instance_type}.get payload on {endpoint_url}',
        3323: f'Failed to retrieve snapshots for {instance_type} {instance_name}',
        3324: f'Failed to rename snapshot {snapshot_name} to {new_snapshot_name}. Error: ',
        3325: f'Failed to update expiry for snapshot {snapshot_name}. Error: ',
        3326: f'No update operations specified. Provide new_snapshot_name or expires_at',
        3327: f'Invalid date format for expires_at. Expected ISO 8601 format (e.g. "2025-12-31T23:59:59"). Error: ',
    }

    # Validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3311: {messages[3311]}', {}
        
    if new_snapshot_name is None and expires_at is None:
        return False, f'3326: {messages[3326]}', {}

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
        
        success_message = ''
        
        # Rename snapshot if requested and if the new name is different from the current name
        if new_snapshot_name and new_snapshot_name != snapshot_name:
            try:
                # Get the snapshot
                snapshot = instance.snapshots.get(snapshot_name)
                # Use wait=True to ensure the operation completes before continuing
                snapshot.rename(new_snapshot_name, wait=True)
                fmt.add_successful('snapshot.rename', {
                    'snapshot_name': snapshot_name, 
                    'new_snapshot_name': new_snapshot_name
                })
                success_message += f'1301: {messages[1301]}\n'
            except Exception as e:
                return False, f"{prefix+4}: {messages[3324]}{e}", fmt.successful_payloads
        elif new_snapshot_name and new_snapshot_name == snapshot_name:
            # Skip renaming if the names are the same
            fmt.add_successful('snapshot.rename_skipped', {'message': 'Names are identical, skipping rename'})
            success_message += f'1303: {messages[1303]}\n'
        
        # Update expiry if requested
        if expires_at is not None:
            try:
                # Get the snapshot (potentially with the new name if renamed)
                current_name = new_snapshot_name if new_snapshot_name and new_snapshot_name != snapshot_name else snapshot_name
                
                # Get the snapshot
                snapshot = instance.snapshots.get(current_name)
                
                # If expires_at is already in ISO format, use it directly
                iso_expires = expires_at
                
                # Use PUT request to update the snapshot with expiry
                data = {"expires_at": iso_expires}
                api_path = f"{instance._endpoint}/{instance.name}/snapshots/{current_name}"
                
                response = instance.client.api[api_path].put(json=data)
                
                # Wait for operation to complete
                if response.json().get("type") == "async":
                    operation_id = response.json().get("operation")
                    instance.client.operations.wait_for_operation(operation_id)
                
                fmt.add_successful('snapshot.update_expiry', {
                    'snapshot_name': current_name, 
                    'expires_at': expires_at
                })
                success_message += f'1302: {messages[1302]}\n'
                
            except ValueError as e:
                return False, f"{prefix+7}: {messages[3327]}{e}", fmt.successful_payloads
            except Exception as e:
                return False, f"{prefix+5}: {messages[3325]}{e}", fmt.successful_payloads
        
        return True, success_message.strip(), fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg, successful_payloads

    return True, f'1300: {messages[1300]}', successful_payloads

