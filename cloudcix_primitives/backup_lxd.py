"""
LXD Container Backup Management
"""
# stdlib
import json
import os
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
        backup_id: str,
        backup_dir: str,
) -> Tuple[bool, str]:
    """
    Creates a container backup on the LXD host and exports it to storage.
    
    Parameters:
        host: LXD host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        backup_dir: Directory for backup storage
    """
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

    # Generate backup name and paths
    backup_name = f"{container_name}_{backup_id}"
    backup_filename = f"{backup_name}.tar.gz"
    backup_path = os.path.join(backup_dir, backup_filename)

    # Define messages
    messages = {
        1000: f"Successfully created and exported backup '{backup_name}' for container '{container_name}'",
        3001: f"Failed to check existing backups for container '{container_name}'",
        3002: f"Failed to create backup for container '{container_name}'",
        3003: f"Failed to export backup '{backup_name}' for container '{container_name}'",
        3004: f"Failed to wait for backup operation to complete for container '{container_name}'",
        3005: f"External backup already exists for '{container_name}', no action taken",
        3006: f"Local backup already exists for '{container_name}', possible concurrent operation",
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
            
            # Export backup to storage
            curl_cmd = (f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket "
                        f"lxd/1.0/instances/{container_name}/backups/{backup_name}/export > {backup_path}")
            ret = rcc.run(payload=curl_cmd)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}: SSH connection failed")
            if not _check_file_exists(rcc, fmt, backup_path):
                return False, fmt.payload_error(None, f"{prefix+3}: {messages[prefix+3]}: Failed to verify backup file was created")
            
            # Delete the local backup after successful export
            response = _lxd_api_call(rcc, fmt, "DELETE", f"/1.0/instances/{container_name}/backups/{backup_name}")
            _wait_for_operation(rcc, fmt, response["operation"])
            fmt.add_successful('delete_local_backup', {'backup_name': backup_name})
            
            fmt.add_successful('build_complete', {'backup_path': backup_path})
            return True, f"1000: {messages[1000]} - File saved to: {backup_path}"
            
        except Exception as e:
            return False, fmt.payload_error(None, f"{prefix+2}: {messages[prefix+2]}: {str(e)}")

    status, msg = run_host(host, 3000, {})
    return status, msg

def read(
        host: str,
        username: str,
        container_name: str,
        backup_id: str,
        backup_dir: str,
) -> Tuple[bool, Dict, List[str]]:
    """
    Gets information about a container backup file.
    
    Parameters:
        host: Backup host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        backup_dir: Directory for backup storage
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

    # Generate backup name and filename
    backup_name = f"{container_name}_{backup_id}"
    backup_filename = f"{backup_name}.tar.gz"
    backup_path = os.path.join(backup_dir, backup_filename)

    # Define messages
    messages = {
        1300: f"Successfully read backup information for '{backup_name}' of container '{container_name}'",
        3301: f"Failed to get backup information for container '{container_name}'",
        3302: f"Backup '{backup_name}' does not exist for container '{container_name}'",
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
            # Check backup exists
            backup_exists = _check_file_exists(rcc, fmt, backup_path)
            data_dict['backup_exists'] = backup_exists
            data_dict['backup_path'] = backup_path
            
            # Get backup details if it exists
            if backup_exists:
                backup_details = _get_file_details(rcc, fmt, backup_path)
                if backup_details:
                    data_dict['backup_details'] = backup_details
                    fmt.add_successful('get_backup_info', {'backup_path': backup_path})
                    
                # Basic information
                data_dict.update({
                    'container_name': container_name,
                    'backup_name': backup_name,
                    'backup_id': backup_id
                })
                
                message_list.insert(0, f"1300: {messages[1300]}")
                return True, data_dict, message_list
            else:
                message_list.append(f"{prefix+2}: {messages[prefix+2]}")
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
        backup_id: str,
        backup_dir: str,
) -> Tuple[bool, str]:
    """
    Removes a container backup file.
    
    Parameters:
        host: LXD host IP
        username: SSH username
        container_name: Name of the LXD container
        backup_id: Identifier for the backup
        backup_dir: Directory for backup storage
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

    # Generate backup name and filename
    backup_name = f"{container_name}_{backup_id}"
    backup_filename = f"{backup_name}.tar.gz"
    backup_path = os.path.join(backup_dir, backup_filename)

    # Define messages
    messages = {
        1100: f"Successfully removed backup '{backup_name}' for container '{container_name}'",
        1101: f"Backup '{backup_name}' does not exist for container '{container_name}'",
        3101: f"Failed to check if backup exists for container '{container_name}'",
        3102: f"Failed to delete backup file for '{backup_name}' of container '{container_name}'",
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        try:
            backup_exists = _check_file_exists(rcc, fmt, backup_path)
            
            # If backup doesn't exist, return success with a message
            if not backup_exists:
                return True, f"1101: {messages[1101]}", fmt.successful_payloads
            
            # Delete backup
            success, error_msg = _delete_file(rcc, fmt, backup_path, prefix, messages)
            if success:
                fmt.add_successful('delete_backup', {'backup_path': backup_path})
                return True, f"1100: {messages[1100]} from {backup_path}", fmt.successful_payloads
            else:
                return False, error_msg, fmt.successful_payloads
            
        except Exception as e:
            return False, fmt.payload_error(None, f"{prefix+1}: {messages[prefix+1]}: {str(e)}"), fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3100, {})
    return status, msg
