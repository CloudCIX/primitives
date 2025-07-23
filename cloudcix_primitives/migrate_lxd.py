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
    'build',
]

def build(
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
            description: The name of the target cluster member to migrate to.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'containers' or 'virtual-machines'.
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
        1000: f'Successfully migrated {instance_type} {instance_name} to cluster member {target_cluster_member} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to migrate instance {instance_name} to {target_cluster_member}. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get the instance
        ret = project_rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)

        # Migrate the instance
        try:
            instance.migrate(target_cluster_member, wait=True)
            fmt.add_successful('instances.migrate', {'target': target_cluster_member})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{str(e)}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'