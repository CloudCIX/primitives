"""
GPU Management for LXD Containers
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper

__all__ = [
    'build',
    'read',
    'scrub',
]

def build(
        endpoint_url: str,
        project: str,
        container_name: str,
        device_identifier: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """Attach a GPU to an LXD container.
    NOTE: Each unique GPU can only be attached once to a container to prevent duplicate references.

    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param device_identifier: The ID of the GPU to attach (PCI address like "0000:01:00.0").
                              This will also be used as the device name.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, and a message.
    """
    
    # Use the device identifier directly as the device name
    device_name = device_identifier
    
    messages = {
        1000: f'Successfully attached GPU {device_identifier} to container {container_name} on {endpoint_url}',
        1001: f'GPU {device_identifier} is already attached to container {container_name}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to attach GPU to container {container_name}. Error: ',
    }

    # Validate input
    if not device_identifier or not isinstance(device_identifier, str):
        return False, f"Invalid device identifier: {device_identifier}"
        
    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the container
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
        # Check if the GPU ID is already attached in any device
        for dev_name, config in instance.devices.items():
            # Only check gpu type devices
            if config.get('type') != 'gpu':
                continue
                
            # For PCI GPUs, check if the ID matches
            if config.get('pci') == device_identifier:
                # GPU already attached - correctly return code and existing device name
                return True, f'1001: {messages[1001]}', {
                    'already_attached': True,
                    'device_name': dev_name,
                    'gpu_id': device_identifier
                }
        
        # Create a GPU configuration for PCI passthrough
        gpu_config = {
            'type': 'gpu',
            'pci': device_identifier,
        }
                      
        # Add the GPU device to the instance
        try:
            instance.devices[device_name] = gpu_config
            instance.save(wait=True)
            fmt.add_successful('containers.device_add', {'device': device_name, 'config': gpu_config})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg
    
    return True, f'1000: {messages[1000]}'


def read(
        endpoint_url: str,
        project: str,
        container_name: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """Read information about attached GPUs from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure and a message with GPU information.
    """
    # Define messages for different statuses
    messages = {
        1000: f'Successfully read GPU information from container {container_name} on {endpoint_url}',
        1001: f'No GPU devices found attached to container {container_name}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the container
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
        # Find all GPU devices attached to the instance
        gpu_devices = {}
        for device_name, config in instance.devices.items():
            # Look for devices of type 'gpu' with PCI configuration
            if config.get('type') == 'gpu' and 'pci' in config:
                # Add device to our list
                gpu_devices[device_name] = {
                    'id': config['pci'],
                    'raw_config': config
                }
        
        # If no GPU devices were found
        if not gpu_devices:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads
        
        # Add the list of GPU devices to the successful payloads
        fmt.successful_payloads['gpu_devices'] = gpu_devices
        
        # Create detailed GPU information message
        gpu_info = []
        for name, device in gpu_devices.items():
            gpu_info.append(f"{name} (PCI: {device['id']})")
        
        gpu_list = ', '.join(gpu_info)
        detailed_message = f'1000: {messages[1000]} - Found: {gpu_list}'
        
        return True, detailed_message, fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return False, msg
        
    return True, msg


def scrub(
        endpoint_url: str,
        project: str,
        container_name: str,
        device_identifier: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """Detach a GPU from an LXD container.
    
    :param endpoint_url: The endpoint URL for the LXD Host.
    :param project: The LXD project name.
    :param container_name: The name of the LXD container.
    :param device_identifier: The identifier of the specific GPU to detach.
                             This can be either a PCI ID or device name (which are now identical).
    :param verify_lxd_certs: Boolean to verify LXD certs.
    :return: A tuple with a boolean flag indicating success or failure, and a message.
    """
    # Define messages for different statuses
    messages = {
        1000: f'Successfully detached GPU from container {container_name} on {endpoint_url}',
        1001: f'No GPU device matching {device_identifier} found in container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for containers.get payload',
        3022: f'Failed to run containers.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to detach GPU from container {container_name}. Error: ',
    }

    # Validate input
    if not device_identifier or not isinstance(device_identifier, str):
        return False, f"Invalid device identifier: {device_identifier}"

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the container
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)
        
        # Check if there are any GPU devices attached
        gpu_devices = []
        for dev_name, config in instance.devices.items():
            # Look for devices of type 'gpu'
            if config.get('type') != 'gpu':
                continue
            
            # Check if it matches either the PCI ID or device name
            if config.get('pci') == device_identifier or dev_name == device_identifier:
                gpu_devices.append(dev_name)
                break
                
        # If no GPU devices were found
        if not gpu_devices:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads
        
        # Remove the GPU devices
        detached_devices = []
        try:
            for dev_name in gpu_devices:
                del instance.devices[dev_name]
                detached_devices.append(dev_name)
            
            # Save the instance configuration
            instance.save(wait=True)
            fmt.add_successful('containers.device_remove', {'devices': detached_devices})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
