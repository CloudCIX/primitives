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
    """
    messages = {
        1000: f'Successfully migrated {instance_type} {instance_name} to cluster member {target_cluster_member} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to submit migration for {instance_name} to {target_cluster_member} on {endpoint_url}.',
        3024: f'Failed to connect to {endpoint_url} for operations.wait.get payload',
        3025: f'Migration operation failed on {endpoint_url}. Error: ',
        3026: f'Could not extract operation ID from migration response on {endpoint_url}.',
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
        return False, f"{prefix+3}: " + messages[prefix+3] + "PyLXD instance not available or missing client()."

    # Submit migration using low-level API: POST /1.0/instances/<name>?target=<member>
    try:
        client = instance.client
        res = client.api.instances[instance_name].post(
            json={'migration': True},
            params={'target': target_cluster_member, 'project': project},
        )
        data = res.json() if hasattr(res, 'json') else res
        fmt.add_successful('instances.migrate.submit', {'target': target_cluster_member, 'response': data})
    except Exception as e:
        # HostErrorFormatter has no .error(); return a plain message
        return False, f"{prefix+5}: " + messages[prefix+5] + str(e)

    return True, f'1000: {messages[1000]}'