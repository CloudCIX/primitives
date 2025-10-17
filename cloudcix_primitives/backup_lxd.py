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
        project_name: str,
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
        project_name:
            description: The project name the instance belongs to
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
        3022: f"Failed to execute check_backup payload on {host}. ",
        3023: f"Failed to connect to host {host} for create_backup_dir payload: ",
        3024: f"Failed to create backup directory at {backup_dir}. ",
        3025: f"Failed to connect to host {host} for check_lxd_backup payload: ",
        3026: f"Failed to execute check_lxd_backup payload on {host}. ",
        3027: f"Failed to connect to host {host} for create_backup payload: ",
        3028: f"Failed to execute create_backup payload on {host}. ",
        3029: f"Failed to parse create_backup response on {host} - no payload: ",
        3030: f"Failed to parse create_backup response on {host} - no operation URL: ",
        3031: f"Failed to parse create_backup response on {host} - invalid JSON: ",
        3032: f"Failed to connect to host {host} for wait_backup payload: ",
        3033: f"Failed to execute wait_backup payload on {host}. ",
        3034: f"Failed to connect to host {host} for export_backup payload: ",
        3035: f"Failed to execute export_backup payload on {host}. ",
        3036: f"Export command produced errors on {host}: ",
        3037: f"Failed to connect to host {host} for verify_backup payload: ",
        3038: f"Failed to verify backup file was created at {backup_path}. ",
        3039: f"Failed to connect to host {host} for verify_backup_size payload: ",
        3040: f"Backup file at {backup_path} is empty. ",
        3041: f"Failed to parse backup file size on {host}. ",
        3042: f"Failed to connect to host {host} for cleanup_backup payload (export failed): ",
        3043: f"Failed to execute cleanup_backup payload on {host} (export failed). ",
        3044: f"Failed to connect to host {host} for cleanup_backup payload (final cleanup): ",
        3045: f"Failed to execute cleanup_backup payload on {host} (final cleanup). ",
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
            'verify_backup_size': f"test -s {backup_path} && stat -c%s {backup_path} 2>/dev/null || echo '0'",
            'create_backup_dir': f"mkdir -p {backup_dir}",
            'check_lxd_backup': f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket 'lxd/1.0/instances/{instance_name}/backups/{backup_name}?project={project_name}'",
            'create_backup': (
                f"curl -s -X POST --unix-socket /var/snap/lxd/common/lxd/unix.socket "
                f"'lxd/1.0/instances/{instance_name}/backups?project={project_name}' "
                f"-H 'Content-Type: application/json' "
                f"-d '{json.dumps({'name': backup_name, 'compression_algorithm': 'gzip', 'instance_only': False})}'"
            ),
            'wait_backup': lambda op_url: f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket lxd{op_url}/wait",
            'export_backup': f"curl -s -X GET --unix-socket /var/snap/lxd/common/lxd/unix.socket 'lxd/1.0/instances/{instance_name}/backups/{backup_name}/export?project={project_name}' > {backup_path}",
            'verify_backup': f"[ -f {backup_path} ] && echo 'exists' || echo 'not_found'",
            'cleanup_backup': f"curl -s -X DELETE --unix-socket /var/snap/lxd/common/lxd/unix.socket 'lxd/1.0/instances/{instance_name}/backups/{backup_name}?project={project_name}'",
        }
        
        # Step 1: Check if backup file already exists on filesystem
        ret = rcc.run(payload=payloads['check_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        
        # Accept exit codes 0 (exists) or 1 (doesn't exist), anything else is an error
        if ret.get("payload_code") not in (SUCCESS_CODE, 1):
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        
        # If file exists, verify it's not empty before returning success
        if 'payload_message' in ret and 'exists' in ret['payload_message']:
            size_ret = rcc.run(payload=payloads['verify_backup_size'])
            if size_ret["channel_code"] == CHANNEL_SUCCESS:
                file_size = size_ret.get('payload_message', '0').strip()
                try:
                    if int(file_size) > 0:
                        return True, f"1001: {messages[1001]}", fmt.successful_payloads
                except ValueError:
                    pass  # Invalid size, continue to recreate backup
        
        fmt.add_successful('check_backup', ret)
        
        # Step 2: Create backup directory if it doesn't exist
        ret = rcc.run(payload=payloads['create_backup_dir'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        
        # Check if the mkdir command succeeded
        if ret.get("payload_code") != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        fmt.add_successful('create_backup_dir', ret)
        
        # Step 3: Check if LXD backup exists internally
        ret = rcc.run(payload=payloads['check_lxd_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        
        # Check if the curl command succeeded
        if ret.get("payload_code") != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        
        # Check if response indicates backup exists (not a 404 error)
        response_msg = ret.get('payload_message', '')
        lxd_backup_exists = 'error_code":404' not in response_msg and 'not found' not in response_msg.lower()
        
        fmt.add_successful('check_lxd_backup', ret)
        
        # Step 4: Create the backup (only if it doesn't exist in LXD)
        if not lxd_backup_exists:
            ret = rcc.run(payload=payloads['create_backup'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            
            # Check if the curl command succeeded
            if ret.get("payload_code") != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            
            if 'payload_message' not in ret or not ret['payload_message']:
                return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9] + f"Backup creation command was: {payloads['create_backup']}"), fmt.successful_payloads
            
            try:
                response = json.loads(ret['payload_message'])
                operation_url = response.get("operation")
                if not operation_url:
                    return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10] + f"Invalid response, no operation URL. Response was: {ret['payload_message']}"), fmt.successful_payloads
            except (json.JSONDecodeError, TypeError) as e:
                return False, fmt.payload_error(ret, f"{prefix+11}: " + messages[prefix+11] + f"Invalid JSON response: {e}. Raw response: {ret['payload_message']}"), fmt.successful_payloads
            
            fmt.add_successful('create_backup', ret)
            
            # Step 5: Wait for backup to complete
            wait_command = payloads['wait_backup'](operation_url)
            ret = rcc.run(payload=wait_command)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
            
            # Check if the curl command succeeded
            if ret.get("payload_code") != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+13}: " + messages[prefix+13]), fmt.successful_payloads
            
            fmt.add_successful('wait_backup', ret)
        
        # Step 6: Export the backup
        ret = rcc.run(payload=payloads['export_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            # Don't cleanup if we can't even connect
            return False, fmt.channel_error(ret, f"{prefix+14}: " + messages[prefix+14]), fmt.successful_payloads
        
        # Check if the export command succeeded (curl exit code should be 0)
        export_failed = False
        export_error_msg = ""
        
        if ret.get("payload_code") != SUCCESS_CODE:
            export_failed = True
            export_error_msg = fmt.payload_error(ret, f"{prefix+15}: " + messages[prefix+15])
        
        # Check for any errors in stderr output
        if ret.get("payload_error") and ret["payload_error"].strip():
            export_failed = True
            export_error_msg = fmt.payload_error(ret, f"{prefix+16}: " + messages[prefix+16] + ret['payload_error'])
        
        if not export_failed:
            fmt.add_successful('export_backup', ret)
        
        # Step 7: Verify the file was created AND has content
        ret = rcc.run(payload=payloads['verify_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            # Attempt cleanup before returning error
            rcc.run(payload=payloads['cleanup_backup'])
            return False, fmt.channel_error(ret, f"{prefix+17}: " + messages[prefix+17]), fmt.successful_payloads
        
        if 'payload_message' not in ret or 'exists' not in ret['payload_message']:
            # Attempt cleanup before returning error
            rcc.run(payload=payloads['cleanup_backup'])
            return False, fmt.payload_error(ret, f"{prefix+18}: " + messages[prefix+18]), fmt.successful_payloads
        
        fmt.add_successful('verify_backup', ret)
        
        # Step 7b: Verify the file has content (size > 0)
        size_ret = rcc.run(payload=payloads['verify_backup_size'])
        if size_ret["channel_code"] != CHANNEL_SUCCESS:
            # Attempt cleanup before returning error
            rcc.run(payload=payloads['cleanup_backup'])
            return False, fmt.channel_error(size_ret, f"{prefix+19}: " + messages[prefix+19]), fmt.successful_payloads
        
        file_size = size_ret.get('payload_message', '0').strip()
        try:
            if int(file_size) == 0:
                # Attempt cleanup before returning error
                rcc.run(payload=payloads['cleanup_backup'])
                return False, fmt.payload_error(size_ret, f"{prefix+20}: " + messages[prefix+20]), fmt.successful_payloads
        except ValueError:
            # Attempt cleanup before returning error
            rcc.run(payload=payloads['cleanup_backup'])
            return False, fmt.payload_error(size_ret, f"{prefix+21}: " + messages[prefix+21] + f"Invalid size output: {file_size}"), fmt.successful_payloads
        
        fmt.add_successful('verify_backup_size', size_ret)
        
        # If export failed earlier but file exists and has content, still return the error
        if export_failed:
            # Attempt cleanup before returning error
            cleanup_ret = rcc.run(payload=payloads['cleanup_backup'])
            if cleanup_ret["channel_code"] != CHANNEL_SUCCESS:
                # Add cleanup error to the export error message
                cleanup_error = fmt.channel_error(cleanup_ret, f"{prefix+22}: " + messages[prefix+22])
                export_error_msg += f" Additionally, cleanup failed: {cleanup_error}"
            elif cleanup_ret.get("payload_code") != SUCCESS_CODE:
                cleanup_error = fmt.payload_error(cleanup_ret, f"{prefix+23}: " + messages[prefix+23])
                export_error_msg += f" Additionally, cleanup failed: {cleanup_error}"
            return False, export_error_msg, fmt.successful_payloads
        
        # Step 8: Clean up - Delete the local LXD backup
        ret = rcc.run(payload=payloads['cleanup_backup'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            # Log warning but don't fail the operation since backup file exists and is valid
            warning_msg = fmt.channel_error(ret, f"{prefix+24}: " + messages[prefix+24])
        elif ret.get("payload_code") != SUCCESS_CODE:
            # Log warning but don't fail the operation
            warning_msg = fmt.payload_error(ret, f"{prefix+25}: " + messages[prefix+25])
        else:
            fmt.add_successful('cleanup_backup', ret)
        
        # Success - backup file exists, has content, and is exported
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
        3322: f"Failed to execute check_backup payload on {host}. ",
        3323: f"Backup '{backup_name}' does not exist on host {host}",
        3324: f"Failed to connect to host {host} for get_backup_details payload: ",
        3325: f"Failed to execute get_backup_details payload on {host}. ",
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
        
        # Check if the test command succeeded (should be 0 or 1)
        if ret.get("payload_code") not in (SUCCESS_CODE, 1):
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
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
                fmt.store_channel_error(file_ret, f"{prefix+4}: " + messages[prefix+4])
                return retval, fmt.message_list, fmt.successful_payloads, data_dict
            
            # Check if the commands succeeded
            if file_ret.get("payload_code") != SUCCESS_CODE:
                retval = False
                fmt.store_payload_error(file_ret, f"{prefix+5}: " + messages[prefix+5])
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
            fmt.store_payload_error(ret, f"{prefix+3}: " + messages[prefix+3])
            
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
        3122: f"Failed to connect to host {host} for remove_backup payload (channel error): ",
        3123: f"Failed to execute remove_backup payload on {host} (payload error): ",
        3124: f"Failed to connect to host {host} for verify_removal payload: ",
        3125: f"Backup file '{backup_name}' still exists after deletion attempt",
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
        
        # Check if rm command succeeded
        if delete_ret.get("payload_code") != SUCCESS_CODE:
            return False, fmt.payload_error(delete_ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        
        fmt.add_successful('remove_backup', delete_ret)
        
        # 4. Verify the file was deleted
        ret = rcc.run(payload=payloads['verify_removal'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        # 5. Confirm file is gone
        if 'payload_message' in ret and 'exists' in ret['payload_message']:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        
        fmt.add_successful('verify_removal', ret)
        
        # Success
        return True, f"1100: {messages[1100]}", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    return status, msg
