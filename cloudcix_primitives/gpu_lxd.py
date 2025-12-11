"""
GPU Management for LXD Instances
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
        instance_name: str,
        device_identifier: str,
        device_name: str,
        instance_type: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Attach a GPU to an LXD instance.

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
            description: The name of the LXD instance.
            type: string
            required: true
        device_identifier:
            description: The ID of the GPU to attach (PCI address like "0000:01:00.0").
            type: string
            required: true
        gpu_name:
            description: The name to use for the GPU device in LXD.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure, and a message.
        type: tuple
    """
    
    # Use the gpu_name parameter as the device name
    device_name = gpu_name
    
    messages = {
        1000: f'Successfully attached GPU {device_identifier} as {gpu_name} to {instance_type} {instance_name} on {endpoint_url}',
        1001: f'GPU {device_identifier} is already attached to {instance_type} {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to attach GPU to instance {instance_name}. Error: ',
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
        
        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)
        
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
            fmt.add_successful('instances.device_add', {'device': device_name, 'config': gpu_config})
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
        instance_name: str,
        instance_type: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str, dict]:
    """
    description:
        Read information about attached GPUs from an LXD instance.

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
            description: The name of the LXD instance.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: |
            A tuple with a boolean flag indicating success or failure, a message with GPU information,
            and a dictionary containing detailed GPU device information.
        type: tuple
    """
    # Define messages for different statuses
    messages = {
        1000: f'Successfully read GPU information from {instance_type} {instance_name} on {endpoint_url}',
        1001: f'No GPU devices found attached to {instance_type} {instance_name}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        
        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)
        
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
    
    if status:
        if 'gpu_devices' in successful_payloads:
            gpu_details = successful_payloads['gpu_devices']
            # Format the output to match repository standards
            devices_info = [f"{name} (PCI: {details['id']})" for name, details in gpu_details.items()]
            devices_str = ", ".join(devices_info) if devices_info else "None"
            
            return True, f'1000: {messages[1000]} - Devices: {devices_str}', gpu_details
        else:
            return True, f'1001: {messages[1001]}', {}
    else:
        return False, msg, {}


def scrub(
        endpoint_url: str,
        project: str,
        instance_name: str,
        device_identifier: str,
        gpu_name: str,
        instance_type: str,
        verify_lxd_certs: bool = True
) -> Tuple[bool, str]:
    """
    description:
        Detach a GPU from an LXD instance.

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
            description: The name of the LXD instance.
            type: string
            required: true
        device_identifier:
            description: The ID of the GPU to detach (PCI address like "0000:01:00.0").
            type: string
            required: true
        gpu_name:
            description: The name of the GPU device in LXD to detach.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
            
    return:
        description: A tuple with a boolean flag indicating success or failure, and a message.
        type: tuple
    """
    # Define messages for different statuses
    messages = {
        1000: f'Successfully detached GPU {gpu_name} from {instance_type} {instance_name} on {endpoint_url}',
        1001: f'No GPU device matching {gpu_name} or {device_identifier} found in {instance_type} {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for instances.get payload',
        3022: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to detach GPU from instance {instance_name}. Error: ',
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
        
        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)
        
        # Check if there are any GPU devices attached
        gpu_devices = []
        for dev_name, config in instance.devices.items():
            # Look for GPU device matching by name
            if config.get('type') == 'gpu' and dev_name == gpu_name:
                gpu_devices.append(dev_name)
                
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
            fmt.add_successful('instances.device_remove', {'devices': detached_devices})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}: {e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'
