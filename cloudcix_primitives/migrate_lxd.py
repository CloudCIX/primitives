"""
Primitive for migrating LXD instances between cluster members.
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'update',
]

def update(
    endpoint_url: str,
    project: str,
    instance_name: str,
    target_cluster_member: str,
    instance_type: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Migrate an LXD instance to another cluster member.

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
            description: The name of the LXD instance to migrate.
            type: string
            required: true
        target_cluster_member:
            description: The destination cluster node for the migration.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD TLS certificates.
            type: boolean
            required: false

    return:
        description: A tuple with a boolean indicating success or failure, and a message.
        type: tuple
    """
    messages = {
        1000: f'Successfully migrated {instance_type} {instance_name} to cluster member {target_cluster_member} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'PyLXD instance not available or missing client on {endpoint_url}.',
        3024: f'Failed to access client from instance for {instance_name} on {endpoint_url}. ',
        3025: f'Failed to submit migration for {instance_name} to {target_cluster_member} on {endpoint_url}. ',
        3026: f'Could not extract operation ID from migration response on {endpoint_url}.',
        3027: f'Failed to parse operation ID from migration response on {endpoint_url}. ',
        3028: f'Failed to wait for migration operation for {instance_name} on {endpoint_url}. ',
        3029: f'Migration operation failed on {endpoint_url}. Error: ',
        3030: f'Failed to check migration operation status for {instance_name} on {endpoint_url}. ',
    }

    rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
    fmt = HostErrorFormatter(
        endpoint_url,
        {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
        {},
    )
    prefix = 3020

    # Check instance exists
    ret = rcc.run(cli='instances.get', name=instance_name)
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
    if ret["payload_code"] != API_SUCCESS:
        return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
    fmt.add_successful('instances.get', ret)

    # Get the PyLXD Instance object from the comms wrapper
    instance = ret.get('payload_message') or ret.get('payload')
    if instance is None or not hasattr(instance, 'client'):
        return False, f"{prefix+3}: " + messages[prefix+3]

    # Submit migration using low-level API: POST /1.0/instances/<name>?target=<member>
    try:
        client = instance.client
    except Exception as e:
        return False, f"{prefix+4}: " + messages[prefix+4] + f" Error accessing client: {str(e)}"

    # Submit the migration request
    try:
        res = client.api.instances[instance_name].post(
            json={'migration': True},
            params={'target': target_cluster_member, 'project': project},
        )
        data = res.json() if hasattr(res, 'json') else res
        fmt.add_successful('instances.migrate.submit', {'target': target_cluster_member, 'response': data})
    except Exception as e:
        return False, f"{prefix+5}: " + messages[prefix+5] + f"Error during migration submission: {str(e)}"
    
    # Extract operation ID from response
    try:
        operation_id = data.get('metadata', {}).get('id')
        if not operation_id:
            return False, f"{prefix+6}: " + messages[prefix+6]
        
        # Remove leading '/1.0/operations/' if present
        operation_id = operation_id.split('/')[-1]
    except Exception as e:
        return False, f"{prefix+7}: " + messages[prefix+7] + f" Error parsing response: {str(e)}"
    
    # Wait for operation to complete using PyLXD client
    try:
        operation = client.operations.get(operation_id)
        operation.wait()
    except Exception as e:
        return False, f"{prefix+8}: " + messages[prefix+8] + f"Error during operation wait: {str(e)}"
    
    # Check operation status
    try:
        # After wait(), check if operation succeeded by checking status_code or lack of error
        if hasattr(operation, 'metadata') and operation.metadata:
            status = operation.metadata.get('status')
            if status == 'Success':
                fmt.add_successful('operations.wait', {'operation_id': operation_id, 'status': 'Success'})
                return True, f'1000: {messages[1000]}'
            else:
                error_msg = operation.metadata.get('err', 'Unknown error')
                return False, f"{prefix+9}: " + messages[prefix+9] + error_msg
        else:
            # If wait() completed without exception, consider it successful
            fmt.add_successful('operations.wait', {'operation_id': operation_id, 'status': 'Completed'})
            return True, f'1000: {messages[1000]}'
    except Exception as e:
        return False, f"{prefix+10}: " + messages[prefix+10] + f"Error checking operation status: {str(e)}"