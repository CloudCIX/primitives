"""
Primitive for Backups on LXD hosts
"""
# stdlib
import json
import os
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

SUCCESS_CODE = 0


def build(
        host: str,
        instance_name: str,
        backup_id: str,
        backup_dir: str,
        instance_type: str,
        username: str = 'robot',
) -> Tuple[bool, str]:
    """
    description:
        Creates instance backup on LXD host and exports it to storage.

    parameters:
        host:
            description: The IP address of the LXD host on which the instance runs
            type: string
            required: true
        instance_name:
            description: unique identification name for the target LXD instance in format '{project_id}-{contra_resource_id}'
            type: string
            required: true
        backup_id:
            description: unique identification name for the backup to be created
            type: string
            required: true
        backup_dir:
            description: path on the host where the backup is to be stored
            type: string
            required: true
        instance_type:
            description: type of LXD instance, either 'vms' or 'containers'
            type: string
            required: true
        username:
            description: SSH username for connecting to the host, will default to robot
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Generate backup name and path
    backup_name = f"{instance_name}_{backup_id}"
    backup_path = os.path.join(backup_dir, f"{backup_name}.tar.gz")

    # Define messages
    messages = {
        # Success messages
        1000: f"Successfully created backup '{backup_name}' for {instance_type} '{instance_name}' at {backup_path}",
        1001: f"Backup '{backup_name}' for {instance_type} '{instance_name}' already exists on host {host} at {backup_path}",
        
        # Error messages
        3021: f"Failed to connect to host {host} for check_backup payload: ",
        3022: f"Failed to connect to host {host} for create_backup payload: ",
        3023: f"Failed to run create_backup payload on {host}. ",
        3024: f"Failed to connect to host {host} for wait_backup payload: ",
        3025: f"Failed to connect to host {host} for export_backup payload: ",
        3026: f"Failed to connect to host {host} for verify_backup payload: ",
        3027: f"Failed to verify backup file was created at {backup_path}. ",
        3028: f"Failed to connect to host {host} for cleanup_backup payload: ",
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        payloads = {
            'check_backup': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
            'create_backup': f"curl -s -X POST --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd/1.0/instances/{instance_name}/backups -d \"{{\\\"name\\\": \\\"{backup_name}\\\", \\\"compression_algorithm\\\": \\\"gzip\\\", \\\"instance_only\\\": false}}\"",
            'wait_backup': lambda op_url: f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd{op_url}/wait",
            'export_backup': f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd/1.0/instances/{instance_name}/backups/{backup_name}/export > {backup_path}",
            'verify_backup': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
            'cleanup_backup': f"curl -s -X DELETE --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd/1.0/instances/{instance_name}/backups/{backup_name}",
        }
        
        # 1. Check if backup already exists
        ret = rcc.run(payload=payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        
        if 'payload_message' in ret and 'exists' in ret['payload_message']:
            # No need to create backup: it exists already
            return True, f"1001: {messages[1001]}", fmt.successful_payloads
        
        fmt.add_successful('check_backup', ret)
        
        # 2. Create the backup 
        ret = rcc.run(payload=payloads['create_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if 'payload_message' not in ret or not ret['payload_message']:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        
        try:
            response = json.loads(ret['payload_message'])
            operation_url = response.get("operation")
            if not operation_url:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3] + "Invalid response, no operation URL"), fmt.successful_payloads
        except (json.JSONDecodeError, TypeError):
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3] + "Invalid JSON response"), fmt.successful_payloads
        
        fmt.add_successful('create_backup', ret)
        
        # 3. Wait for backup to complete
        ret = rcc.run(payload=payloads['wait_backup'](operation_url))
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        fmt.add_successful('wait_backup', ret)
        
        # 4. Export the backup
        ret = rcc.run(payload=payloads['export_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        
        fmt.add_successful('export_backup', ret)
        
        # 5. Verify the file was created
        ret = rcc.run(payload=payloads['verify_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        if 'payload_message' not in ret or 'exists' not in ret['payload_message']:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        
        fmt.add_successful('verify_backup', ret)
        
        # 6. Clean up - Delete the local LXD backup
        ret = rcc.run(payload=payloads['cleanup_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            # This is not critical - log but don't fail
            fmt.add_successful('cleanup_warning', {'message': f"{prefix+8}: " + messages[prefix+8] + "Non-critical error"})
        else:
            fmt.add_successful('cleanup_backup', ret)
        
        # Success
        return True, f"1000: {messages[1000]}", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    return status, msg


def read(
        host: str,
        instance_name: str,
        backup_id: str,
        backup_dir: str,
        instance_type: str,
        username: str = 'robot',
) -> Tuple[bool, Dict, List[str]]:
    """
    description:
        Gets information about an instance backup file.
    
    parameters:
        host:
            description: The IP address of the LXD host
            type: string
            required: true
        instance_name:
            description: unique identification name for the target LXD instance in format '{project_id}-{contra_resource_id}'
            type: string
            required: true
        backup_id:
            description: Identifier for the backup
            type: string
            required: true
        backup_dir:
            description: Directory for backup storage
            type: string
            required: true
        instance_type:
            description: type of LXD instance, either 'vms' or 'containers'
            type: string
            required: true
         username:
            description: SSH username for connecting to the host, will default to robot
            type: string
            required: false
    return:
        description:
            status:
                description: True if all read operations were successful, False otherwise.
                type: boolean
            data:
                type: object
                description: backup meta data retrieved from host. May be empty if nothing could be retrieved.
                properties:
                    backup_exists:
                        description: whether the backup file exists
                        type: boolean
                    backup_path:
                        description: full path to the backup file
                        type: string
                    backup_details:
                        description: file details if backup exists
                        type: object
            messages:
                type: list
                description: list of error messages encountered during read operation. May be empty.
    """
    # Generate backup name and filename
    backup_name = f"{instance_name}_{backup_id}"
    backup_path = os.path.join(backup_dir, f"{backup_name}.tar.gz")

    # Define messages
    messages = {
        # Success messages
        1300: f"Successfully read backup information for {instance_type} '{instance_name}' backup '{backup_name}' at {backup_path}",
        
        # Error messages
        3321: f"Failed to connect to host {host} for check_backup payload: ",
        3322: f"Backup '{backup_name}' does not exist on host {host}",
        3323: f"Failed to connect to host {host} for get_backup_details payload: ",
    }

    data_dict = {host: {}}  # Initialize with host key
    message_list = []

    def run_host(host, prefix, successful_payloads):
        retval = True
        
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        payloads = {
            'check_backup': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
            'get_backup_details': f"ls -la {backup_path} && stat --format='%y' {backup_path} && du -sh {backup_path}",
        }
        
        # 1. Check if backup file exists
        ret = rcc.run(payload=payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        backup_exists = 'payload_message' in ret and 'exists' in ret['payload_message']
        
        # 2. Add basic information to response
        data_dict[host] = {
            'backup_exists': backup_exists,
            'backup_path': backup_path,
            'instance_name': instance_name,
            'backup_name': backup_name,
            'backup_id': backup_id,
            'instance_type': instance_type,
        }
        
        # 3. Get detailed backup info if it exists
        if backup_exists:
            fmt.add_successful('check_backup', ret)
            
            # Get file details
            file_ret = rcc.run(payload=payloads['get_backup_details'])
            
            if file_ret["channel_code"] != CHANNEL_SUCCESS:
                retval = False
                fmt.store_channel_error(file_ret, f"{prefix+3}: " + messages[prefix+3])
                return retval, fmt.message_list, fmt.successful_payloads, data_dict
            
            # Parse file details
            if 'payload_message' in file_ret and file_ret['payload_message']:
                file_info = file_ret['payload_message'].strip().split('\n')
                backup_details = {
                    'file_details': file_info[0] if len(file_info) > 0 else "Unknown",
                    'created': file_info[1] if len(file_info) > 1 else "Unknown",
                    'size': file_info[2] if len(file_info) > 2 else "Unknown"
                }
                data_dict[host]['backup_details'] = backup_details
                fmt.add_successful('get_backup_details', file_ret)
        else:
            # Backup doesn't exist
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
            
        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    # Return results
    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f"1300: {messages[1300]}"]


def scrub(
        host: str,
        instance_name: str,
        backup_id: str,
        backup_dir: str,
        instance_type: str,
        username: str = 'robot',
) -> Tuple[bool, str]:
    """
    description:
        Removes an instance backup file.
    
    parameters:
        host:
            description: The IP address of the LXD host
            type: string
            required: true
        instance_name:
            description: unique identification name for the target LXD instance in format '{project_id}-{contra_resource_id}'
            type: string
            required: true
        backup_id:
            description: Identifier for the backup
            type: string
            required: true
        backup_dir:
            description: Directory for backup storage
            type: string
            required: true
        instance_type:
            description: type of LXD instance, either 'vms' or 'containers'
            type: string
            required: true
         username:
            description: SSH username for connecting to the host, will default to robot
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Generate backup name and filename
    backup_name = f"{instance_name}_{backup_id}"
    backup_path = os.path.join(backup_dir, f"{backup_name}.tar.gz")

    # Define messages
    messages = {
        # Success messages
        1100: f"Successfully removed {instance_type} '{instance_name}' backup '{backup_name}' from {backup_path} on host {host}",
        1101: f"Backup '{backup_name}' for {instance_type} '{instance_name}' does not exist on host {host}",
        
        # Error messages
        3121: f"Failed to connect to host {host} for check_backup payload: ",
        3122: f"Failed to connect to host {host} for remove_backup payload: ",
        3123: f"Failed to connect to host {host} for verify_removal payload: ",
        3124: f"Backup file '{backup_name}' still exists after deletion attempt",
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        payloads = {
            'check_backup': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
            'remove_backup': f"rm -f {backup_path}",
            'verify_removal': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
        }
        
        # 1. Check if backup file exists
        ret = rcc.run(payload=payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        
        backup_exists = 'payload_message' in ret and 'exists' in ret['payload_message']
        
        # 2. If backup doesn't exist, return success (nothing to do)
        if not backup_exists:
            return True, f"1101: {messages[1101]}", fmt.successful_payloads
        
        fmt.add_successful('check_backup', ret)
        
        # 3. Delete backup file
        delete_ret = rcc.run(payload=payloads['remove_backup'])
        
        if delete_ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(delete_ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        
        fmt.add_successful('remove_backup', delete_ret)
        
        # 4. Verify the file was deleted
        ret = rcc.run(payload=payloads['verify_removal'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        
        # 5. Confirm file is gone
        if 'payload_message' in ret and 'exists' in ret['payload_message']:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        fmt.add_successful('verify_removal', ret)
        
        # Success
        return True, f"1100: {messages[1100]}", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    return status, msg
