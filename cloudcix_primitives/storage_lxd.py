"""
POC for updating the root disk size of an LXD container.
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

# Explicitly define that this module only supports containers
SUPPORTED_INSTANCES = ['containers']

def update(
        endpoint_url: str,
        project: str,
        instance_name: str,
        new_size: str,
        verify_lxd_certs: bool = True,
        instance_type: str = 'containers'  # Default to 'containers'
) -> Tuple[bool, str, dict]:
    """ Update the root disk size of an LXD container.
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param instance_name: The name of the LXD instance.
    :param new_size: The new size for the root disk (e.g., '20GB').
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :param instance_type: The type of the LXD instance, currently only 'containers' is supported.
    :return: A tuple with a boolean flag indicating success or failure, a message, and a dictionary of successful payloads.
    """
    # Define message
    messages = {
        1000: f'Successfully updated root disk size for {instance_type} {instance_name} on {endpoint_url}',
        3011: f'Invalid instance_type "{instance_type}" sent. Currently only "containers" is supported',
        3021: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3022: f'Failed to get {instance_type} {instance_name} configuration',
        3023: f'Failed to update root disk size for {instance_type} {instance_name}',
        3024: f'Root disk not found in {instance_type} devices',
        3025: f'Failed to save {instance_type} configuration',
        'default': 'An unexpected error occurred. Error code: ',
    }

    # Add validation for instance_type
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3011: {messages[3011]}', {}

    def run_host(endpoint_url, prefix, successful_payloads):
        # Rest of the code remains similar, but use instance_type variable
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get the container - now using the instance_type variable
        ret = rcc.run(cli=f'{instance_type}.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        container = ret['payload_message']
        fmt.add_successful('container get', ret)

        # Update the root disk size
        try:
            devices = container.devices  # Access devices attribute
            if 'root' in devices:
                devices['root']['size'] = new_size
                container.devices = devices  # Update the devices attribute
                try:
                    container.save(wait=True)  # Use the save method to apply changes and wait for completion
                    fmt.add_successful('container config set', {'payload_message': container.config})
                except Exception as save_error:
                    return False, fmt.channel_error(
                        {'channel_code': 500, 'channel_error': str(save_error)}, 
                        f"{prefix+5}: {messages[prefix+5]}: {save_error}"
                    ), fmt.successful_payloads
            else:
                return False, fmt.channel_error(
                    {'channel_code': 400, 'channel_error': "Root disk not found"}, 
                    f"{prefix+4}: {messages[prefix+4]}"
                ), fmt.successful_payloads
        except Exception as e:
            return False, fmt.channel_error(
                {'channel_code': 500, 'channel_error': str(e)}, 
                f"{prefix+3}: {messages[prefix+3]}: {e}"
            ), fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return False, msg, successful_payloads  # Updated to return successful_payloads instead of {}

    return True, f'1000: {messages[1000]}'