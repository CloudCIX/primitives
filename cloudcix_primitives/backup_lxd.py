"""
LXD Container Backup Management
"""
# stdlib
import json
import os
import sys
import time
from typing import Dict, List, Tuple

# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import HostErrorFormatter, SSHCommsWrapper

__all__ = [
    'build',
    'read',
    'scrub',
]


def build(
        host: str,
        username: str,
        container_name: str,
        backup_id: str = None,
        primary_dir: str = None,
        secondary_dir: str = None
) -> Tuple[bool, str]:
    """
    Creates a container backup on the LXD host, exports it to primary storage,
    and synchronizes it to secondary storage.
    
    Parameters:
        host: LXD host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        primary_dir: Primary directory for backup storage
        secondary_dir: Secondary directory for backup storage
    """
    # Validate required input
    if not host or not username or not container_name:
        return False, "Host, username and container_name are required."
        
    if not primary_dir:
        return False, "Primary directory is required."
        
    if not secondary_dir:
        return False, "Secondary directory is required."
        
    def _lxd_api_call(rcc, fmt, method, endpoint, data=None):
        """Execute a LXD API call via curl."""
        curl_cmd = f"curl -s -X {method} --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd{endpoint}"
        if data:
            json_data = json.dumps(data).replace('"', '\\"')
            curl_cmd += f" -d \"{json_data}\""
        ret = rcc.run(payload=curl_cmd)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            raise Exception(fmt.channel_error(ret, "API call failed"))
        if 'payload_message' not in ret or not ret['payload_message']:
            raise Exception(fmt.payload_error(ret, "API call returned no data"))
        return json.loads(ret['payload_message'])

    def _wait_for_operation(rcc, fmt, operation_url, timeout=300):
        """Wait for a LXD operation to complete."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = _lxd_api_call(rcc, fmt, "GET", operation_url)
            if response["metadata"]["status"] == "Success":
                return True
            elif response["metadata"]["status"] == "Failure":
                raise Exception(f"Operation failed: {response['metadata'].get('err', 'Unknown error')}")
            time.sleep(2)
        raise Exception("Operation timed out")

    def _check_file_exists(rcc, fmt, file_path):
        """Check if a file exists on the remote host."""
        check_cmd = f"[ -f {file_path} ] && echo 'exists' || echo 'not_found'"
        ret = rcc.run(payload=check_cmd)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            raise Exception(fmt.channel_error(ret, "File check failed"))
        return 'payload_message' in ret and 'exists' in ret['payload_message']

    def _sync_to_secondary(rcc, fmt, primary_path, secondary_path, messages, prefix=3400):
        """Synchronize backup from primary to secondary location."""
        copy_cmd = f"cp {primary_path} {secondary_path}"
        copy_ret = rcc.run(payload=copy_cmd)
        if copy_ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(copy_ret, f"{prefix+2}: {messages[prefix+2]}: Failed to copy backup file")
        if not _check_file_exists(rcc, fmt, secondary_path):
            return False, fmt.payload_error(None, f"{prefix+2}: {messages[prefix+2]}: Failed to verify secondary backup was created")
        fmt.add_successful('sync_to_secondary', {'primary_path': primary_path, 'secondary_path': secondary_path})
        return True, f"{prefix}: {messages[1400]}"

    # Generate backup name and paths
    backup_name = f"{container_name}_{backup_id}" if backup_id else f"{container_name}_backup"
    backup_filename = f"{backup_name}.tar.gz"
    backup_path = os.path.join(primary_dir, backup_filename)
    secondary_path = os.path.join(secondary_dir, backup_filename)

    # Define messages
    messages = {
        1000: f"Successfully created and exported backup '{backup_name}' for container '{container_name}'",
        1400: f"Successfully synchronized backup to secondary location",
        3001: f"Failed to check existing backups for container '{container_name}'",
        3002: f"Failed to create backup for container '{container_name}'",
        3003: f"Failed to export backup '{backup_name}' for container '{container_name}'",
        3004: f"Failed to wait for backup operation to complete for container '{container_name}'",
        3005: f"External backup already exists for '{container_name}', no action taken",
        3006: f"Local backup already exists for '{container_name}', possible concurrent operation",
        3401: f"Failed to create secondary directory",
        3402: f"Failed to synchronize backup to secondary location"
    }

    # Initialize SSH connection
    rcc = SSHCommsWrapper(comms_ssh, host, username)
    fmt = HostErrorFormatter(host, {'payload_message': 'STDOUT', 'payload_error': 'STDERR'}, {})

    def run_host(host, prefix, successful_payloads):
        try:
            # Check if external backup exists
            external_backup_exists = _check_file_exists(rcc, fmt, backup_path)
            fmt.add_successful('external_backup_check', {'exists': external_backup_exists, 'path': backup_path})
            if external_backup_exists:
                return False, fmt.payload_error(None, f"{prefix+5}: {messages[prefix+5]}")
            
            # Check if local LXD backup exists
            existing_backups = _lxd_api_call(rcc, fmt, "GET", f"/1.0/instances/{container_name}/backups")
            local_backup_exists = any(backup.split('/')[-1] == backup_name for backup in existing_backups["metadata"])
            if local_backup_exists:
                return False, fmt.payload_error(None, f"{prefix+6}: {messages[prefix+6]}")
            
            # Create backup
            backup_data = {"name": backup_name, "compression_algorithm": "gzip", "instance_only": False}
            response = _lxd_api_call(rcc, fmt, "POST", f"/1.0/instances/{container_name}/backups", backup_data)
            _wait_for_operation(rcc, fmt, response["operation"])
            fmt.add_successful('create_backup', {'backup_name': backup_name})
            
            # Export backup to primary location
            curl_cmd = (f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket "
                        f"lxd/1.0/instances/{container_name}/backups/{backup_name}/export > {backup_path}")
            ret = rcc.run(payload=curl_cmd)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}: SSH connection failed")
            if not _check_file_exists(rcc, fmt, backup_path):
                return False, fmt.payload_error(None, f"{prefix+3}: {messages[prefix+3]}: Failed to verify backup file was created")
            
            # Sync to secondary storage
            sync_success, sync_msg = _sync_to_secondary(rcc, fmt, backup_path, secondary_path, messages)
            if not sync_success:
                return False, sync_msg
            
            # Delete the local backup after successful export
            response = _lxd_api_call(rcc, fmt, "DELETE", f"/1.0/instances/{container_name}/backups/{backup_name}")
            _wait_for_operation(rcc, fmt, response["operation"])
            fmt.add_successful('delete_local_backup', {'backup_name': backup_name})
            
            fmt.add_successful('build_complete', {'primary_path': backup_path, 'secondary_path': secondary_path})
            return True, f"1000: {messages[1000]} - File saved to: {backup_path} and synced to secondary: {secondary_path}"
            
        except Exception as e:
            return False, fmt.payload_error(None, f"{prefix+2}: {messages[prefix+2]}: {str(e)}")

    status, msg = run_host(host, 3000, {})
    return status, msg

def read(
        host: str,
        username: str,
        container_name: str,
        backup_id: str = None,
        primary_dir: str = None,
        secondary_dir: str = None
) -> Tuple[bool, Dict, List[str]]:
    """
    Gets information about a container backup file from both primary and secondary locations.
    
    Parameters:
        host: Backup host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        primary_dir: Primary directory for backup storage
        secondary_dir: Secondary directory for backup storage (optional)
    """
    def _check_file_exists(rcc, fmt, file_path):
        """Check if a file exists on the remote host."""
        check_cmd = f"[ -f {file_path} ] && echo 'exists' || echo 'not_found'"
        ret = rcc.run(payload=check_cmd)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            raise Exception(fmt.channel_error(ret, "File check failed"))
        return 'payload_message' in ret and 'exists' in ret['payload_message']

    def _get_file_details(rcc, fmt, file_path):
        """Get detailed information about a file."""
        file_cmd = f"ls -la {file_path} && stat --format='%y' {file_path} && du -sh {file_path}"
        file_ret = rcc.run(payload=file_cmd)
        
        if file_ret["channel_code"] != CHANNEL_SUCCESS:
            raise Exception(fmt.channel_error(file_ret, "Failed to get file details"))
        
        if 'payload_message' in file_ret and file_ret['payload_message']:
            file_info = file_ret['payload_message'].strip().split('\n')
            return {
                'file_details': file_info[0] if len(file_info) > 0 else "Unknown",
                'created': file_info[1] if len(file_info) > 1 else "Unknown",
                'size': file_info[2] if len(file_info) > 2 else "Unknown"
            }
        return None

    # Validate input
    if not host or not username or not container_name:
        return False, {}, ["Host, username and container_name are required."]

    if not primary_dir:
        return False, {}, ["Primary directory is required."]

    # Generate backup name and filename
    backup_name = f"{container_name}_{backup_id}" if backup_id else f"{container_name}_backup"
    backup_filename = f"{backup_name}.tar.gz"
    primary_path = os.path.join(primary_dir, backup_filename)
    secondary_path = os.path.join(secondary_dir, backup_filename) if secondary_dir else None

    # Define messages
    messages = {
        1300: f"Successfully read backup information for '{backup_name}' of container '{container_name}'",
        3301: f"Failed to get backup information for container '{container_name}'",
        3302: f"Backup '{backup_name}' does not exist in primary location for container '{container_name}'",
        3303: f"Backup '{backup_name}' does not exist in secondary location for container '{container_name}'"
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        data_dict = {}
        message_list = []
        
        try:
            # Check primary backup
            primary_exists = _check_file_exists(rcc, fmt, primary_path)
            data_dict['primary_exists'] = primary_exists
            data_dict['primary_path'] = primary_path
            
            # Get primary backup details if it exists
            if primary_exists:
                primary_details = _get_file_details(rcc, fmt, primary_path)
                if primary_details:
                    data_dict['primary_details'] = primary_details
                    fmt.add_successful('get_primary_backup_info', {'backup_path': primary_path})
            else:
                message_list.append(f"{prefix+2}: {messages[prefix+2]}")
            
            # Check secondary backup if provided
            if secondary_path:
                secondary_exists = _check_file_exists(rcc, fmt, secondary_path)
                data_dict['secondary_exists'] = secondary_exists
                data_dict['secondary_path'] = secondary_path
                
                # Get secondary backup details if it exists
                if secondary_exists:
                    secondary_details = _get_file_details(rcc, fmt, secondary_path)
                    if secondary_details:
                        data_dict['secondary_details'] = secondary_details
                        fmt.add_successful('get_secondary_backup_info', {'backup_path': secondary_path})
                else:
                    message_list.append(f"{prefix+3}: {messages[prefix+3]}")
            
            # Basic information common to both backups
            data_dict.update({
                'container_name': container_name,
                'backup_name': backup_name,
                'backup_id': backup_id
            })
            
            # Consider success if at least one backup exists
            if primary_exists or (secondary_path and secondary_exists):
                message_list.insert(0, f"1300: {messages[1300]}")
                return True, data_dict, message_list
            
            # If we got here, neither backup exists
            message_list.append(fmt.payload_error(None, f"{prefix+1}: {messages[prefix+1]}: No backup files found"))
            return False, data_dict, message_list
            
        except Exception as e:
            message_list.append(fmt.payload_error(None, f"{prefix+1}: {messages[prefix+1]}: {str(e)}"))
            return False, data_dict, message_list

    status, data, messages_list = run_host(host, 3300, {})
    return status, data, messages_list

def scrub(
        host: str,
        username: str,
        container_name: str,
        backup_id: str = None,
        primary_dir: str = None,
        secondary_dir: str = None
) -> Tuple[bool, str]:
    """
    Removes a container backup file from both primary and secondary locations.
    
    Parameters:
        host: LXD host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        primary_dir: Primary directory for backup storage
        secondary_dir: Secondary directory for backup storage (optional)
    """
    def _check_file_exists(rcc, fmt, file_path):
        """Check if a file exists on the remote host."""
        check_cmd = f"[ -f {file_path} ] && echo 'exists' || echo 'not_found'"
        ret = rcc.run(payload=check_cmd)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            raise Exception(fmt.channel_error(ret, "File check failed"))
        return 'payload_message' in ret and 'exists' in ret['payload_message']
    
    def _delete_file(rcc, fmt, file_path, prefix, messages):
        """Delete a file and verify it was deleted."""
        delete_cmd = f"rm -f {file_path}"
        delete_ret = rcc.run(payload=delete_cmd)
        
        if delete_ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(delete_ret, f"{prefix+2}: {messages[prefix+2]}: SSH connection failed")
        
        # Verify the file is deleted
        if _check_file_exists(rcc, fmt, file_path):
            return False, fmt.payload_error(None, f"{prefix+2}: {messages[prefix+2]}: Failed to delete backup file")
        
        return True, None

    # Validate input
    if not host or not username or not container_name:
        return False, "Host, username and container_name are required."

    if not primary_dir:
        return False, "Primary directory is required."

    # Generate backup name and filename
    backup_name = f"{container_name}_{backup_id}" if backup_id else f"{container_name}_backup"
    backup_filename = f"{backup_name}.tar.gz"
    primary_path = os.path.join(primary_dir, backup_filename)
    secondary_path = os.path.join(secondary_dir, backup_filename) if secondary_dir else None

    # Define messages
    messages = {
        1100: f"Successfully removed backup '{backup_name}' for container '{container_name}'",
        1101: f"Backup '{backup_name}' does not exist for container '{container_name}'",
        1102: f"Backup '{backup_name}' partially scrubbed (deleted from primary only)",
        3101: f"Failed to check if backup exists for container '{container_name}'",
        3102: f"Failed to delete backup file for '{backup_name}' of container '{container_name}'",
        3103: f"Failed to delete secondary backup file for '{backup_name}' of container '{container_name}'",
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        try:
            primary_exists = _check_file_exists(rcc, fmt, primary_path)
            secondary_exists = secondary_path and _check_file_exists(rcc, fmt, secondary_path)
            
            # If neither backup exists, return success with a message
            if not primary_exists and not secondary_exists:
                return True, f"1101: {messages[1101]}", fmt.successful_payloads
            
            # Track which backups were successfully deleted
            primary_deleted = False
            secondary_deleted = False
            
            # Delete primary backup if it exists
            if primary_exists:
                success, error_msg = _delete_file(rcc, fmt, primary_path, prefix, messages)
                if success:
                    fmt.add_successful('delete_primary_backup', {'backup_path': primary_path})
                    primary_deleted = True
                else:
                    return False, error_msg, fmt.successful_payloads
            
            # Delete secondary backup if it exists
            if secondary_exists:
                success, error_msg = _delete_file(rcc, fmt, secondary_path, prefix, messages)
                if success:
                    fmt.add_successful('delete_secondary_backup', {'backup_path': secondary_path})
                    secondary_deleted = True
                else:
                    # If primary was deleted but secondary failed, report partial success
                    if primary_deleted:
                        return True, f"1102: {messages[1102]} - {error_msg}", fmt.successful_payloads
                    return False, error_msg, fmt.successful_payloads
            
            # Create appropriate success message based on what was deleted
            success_parts = []
            if primary_deleted:
                success_parts.append(f"primary ({primary_path})")
            if secondary_deleted:
                success_parts.append(f"secondary ({secondary_path})")
            
            success_msg = f"1100: {messages[1100]} from {' and '.join(success_parts)}"
            return True, success_msg, fmt.successful_payloads
            
        except Exception as e:
            return False, fmt.payload_error(None, f"{prefix+1}: {messages[prefix+1]}: {str(e)}"), fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3100, {})
    return status, msg
