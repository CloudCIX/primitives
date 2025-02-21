'''
POC: CPU limit update for LXD instances.
'''
# stdlib
import sys
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'update_cpu_lxd',
]

SUPPORTED_INSTANCES = ['virtual_machines', 'containers']

def success(response, payload_number):
    if response['channel_code'] != CHANNEL_SUCCESS:
        return False, f'{payload_number}: {response["channel_message"]}', {}
    elif response['payload_code'] != API_SUCCESS:
        return False, f'{payload_number + 1}: {response["payload_message"]}', {}
    else:
        return True, '', response['payload_message']

def update_cpu_lxd(
        endpoint_url: str,
        project: str,
        name: str,
        instance_type: str,
        cpu: int,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    
    """ Update the CPU limit of an LXD instance.

    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param name: The name of the LXD instance.
    :param instance_type: The type of the LXD instance, either "containers" or "virtual_machines".
    :param cpu: The number of CPU cores to set.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """

    # Define message
    messages = {
        1000: f'Successfully updated the CPU limit for {instance_type} {name} on {endpoint_url}',
        3011: f'Invalid instance_type "{instance_type}" sent. Supported instance types are "containers" and "virtual_machines"',
        3021: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3022: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to update the CPU limit. Error: ',
        3423: f'Failed to quiesce {instance_type} on {endpoint_url}. Instance was found in an unexpected state of ',
        3025: f'Failed to set CPU limit for {instance_type} {name}',
        3523: f'Failed to restart {instance_type} on {endpoint_url}. Instance was found in an unexpected state of ',
        'default': 'An unexpected error occurred. Error code: ',
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
        ret = rcc.run(cli=f'{instance_type}.get', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[3021]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[3022]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful(f'{instance_type}.get', ret)

        # Quiesce the instance (stop the instance)
        state = instance.state()
        if state.status == 'Running':
            instance.stop(force=False, wait=True)
        elif state.status != 'Stopped':
            return False, f"{prefix+3}: {messages[3423]} {state.status}", fmt.successful_payloads
            
        # Update the CPU limit using LXDCommsWrapper
        try:
            instance.config['limits.cpu'] = str(cpu)
            instance.save(wait=True)
            fmt.add_successful(f'{instance_type}.set', {'limits.cpu': str(cpu)})
        except Exception as e:
            return False, f"{prefix+4}: {messages[3025]}: {e}", fmt.successful_payloads

        # Restart the instance
        try:
            state = instance.state()
            if state.status == 'Stopped':
                instance.start(force=False, wait=True)
            elif state.status != 'Running':
                return False, f"{prefix+6}: {messages[3523]} {state.status}", fmt.successful_payloads
        except Exception as e:
            return False, fmt.payload_error(ret, f"{prefix+7}: {messages[3523]}: {e}"), fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return False, msg, {}

    return True, f'1000: {messages[1000]}', {'instance': name}

if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: python3 cpu_lxd.py <endpoint_url> <project> <name> <instance_type> <cpu> <verify_lxd_certs>")
        sys.exit(1)

    endpoint_url = sys.argv[1]
    project = sys.argv[2]
    name = sys.argv[3]
    instance_type = sys.argv[4]
    cpu = int(sys.argv[5])
    verify_lxd_certs = sys.argv[6].lower() == 'true'

    success, message, payload = update_cpu_lxd(endpoint_url, project, name, instance_type, cpu, verify_lxd_certs)
    print(message)
