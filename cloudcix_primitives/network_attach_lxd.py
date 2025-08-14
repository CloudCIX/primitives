"""
Module for attaching/reading/detatching a network device to an LXD instance.
"""
# stdlib
from typing import Dict, Tuple
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
    vlan_id: str,
    device_name: str,
    instance_type: str,
    mac_address: str = None,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Attach network devices to an LXD instance.

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
        vlan_id:
            description: The VLAN ID for the network interface.
            type: string
            required: true
        device_name:
            description: The name of the network device.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance, either 'vms' or 'containers'.
            type: string
            required: true
        mac_address:
            description: Optional MAC address for the interface.
            type: string
            required: false
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define the messages
    messages = {
        1000: f'Successfully attached network interface to {instance_type} {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for network or instance operations',
        3022: f'Failed to retrieve networks from {endpoint_url}. Payload exited with status ',
        3023: f'Failed to retrieve instance {instance_name}. Payload exited with status ',
        3024: f'Network br{vlan_id} does not exist on {endpoint_url}.',
        3025: f'Failed to create network device: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        network_interface_name = f'br{vlan_id}'

        # Check if the network exists
        ret = rcc.run(cli='networks.all')
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        networks = ret['payload_message']
        fmt.add_successful('networks.all', ret)

        # Check if our network exists
        network_exists = False
        for network in networks:
            if network.name == network_interface_name:
                network_exists = True

        if not network_exists:
            return False, f"{prefix+4}: {messages[prefix+4]}", fmt.successful_payloads

        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)

        # Check if the device already exists
        devices = instance.devices
        if device_name in devices:
            fmt.add_successful('network_device.check', {device_name: 'already_exists'})
            return True, f"1000: {messages[1000]}", fmt.successful_payloads

        # Create device configuration
        device_config = {
            'type': 'nic',
            'network': network_interface_name,
            'ipv4.address': None,
            'ipv6.address': None,
        }

        # Add the device to the instance
        try:
            instance.devices[device_name] = device_config

            # Add MAC address
            if mac_address:
                instance.config[f'volatile.{device_name}.hwaddr'] = mac_address

            instance.save(wait=True)
            fmt.add_successful('network_device.create', {device_name: 'created'})
        except Exception as e:
            return False, f"{prefix+5}: {messages[prefix+5]}{e}", fmt.successful_payloads

        return True, f'1000: {messages[1000]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg

    return True, msg

def read(
    endpoint_url: str,
    project: str,
    instance_name: str,
    instance_type: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, Dict, str]:
    """
    description:
        Read the configuration of additional network devices attached to an LXD instance.

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
        description: A tuple with a boolean flag indicating success or failure, a dictionary containing the configuration, and a message.
        type: tuple
    """
    # Define the messages
    messages = {
        1200: f'Successfully read network configuration for {instance_type} {instance_name} on {endpoint_url}',
        1201: f'No secondary network interfaces found for {instance_type} {instance_name} on {endpoint_url}',
        3221: f'Failed to connect to {endpoint_url} for instance operations',
        3222: f'Failed to retrieve instance {instance_name}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        result = {}

        # Get the instance
        ret = rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, {}
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, {}

        instance = ret['payload_message']
        fmt.add_successful('instances.get', ret)

        # Get devices from instance
        devices = instance.devices
        config = instance.config

        # Filter for network interfaces (excluding the primary one which is typically 'eth0')
        network_devices = {}
        for name, device in devices.items():
            if device.get('type') == 'nic' and name != 'eth0':
                network_device = device.copy()
                # Check if there's a MAC address in the config using the lxd.py convention
                mac_key = f'volatile.{name}.hwaddr'
                if mac_key in config:
                    network_device['mac_address'] = config[mac_key]
                network_devices[name] = network_device

        if not network_devices:
            # No secondary network interfaces found
            result['network_devices'] = None
            fmt.add_successful('network_devices.read', {'status': 'none_found'})
            return True, f'1201: {messages[1201]}', fmt.successful_payloads, {endpoint_url: result}

        # Return the network devices
        result['network_devices'] = network_devices
        fmt.add_successful('network_devices.read', {'status': 'found', 'count': len(network_devices)})
        return True, f'1200: {messages[1200]}', fmt.successful_payloads, {endpoint_url: result}

    status, msg, successful_payloads, result = run_host(endpoint_url, 3220, {})

    if status is False:
        return False, {}, msg

    return True, result, msg

def scrub(
    endpoint_url: str,
    project: str,
    instance_name: str,
    device_name: str,
    instance_type: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Remove a network device from an LXD instance.

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
        device_name:
            description: The name of the network device to remove.
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
        description: A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define the messages
    messages = {
        1100: f'Successfully removed network interface {device_name} from {instance_type} {instance_name} on {endpoint_url}',
        3121: f'Failed to connect to {endpoint_url} for instance operations',
        3122: f'Failed to retrieve instance {instance_name}. Payload exited with status ',
        3123: f'Failed to remove network interface: ',
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

        # Check if the device exists
        devices = instance.devices

        if device_name not in devices:
            fmt.add_successful('network_device.remove', {device_name: 'not_found'})
            return True, f'1100: {messages[1100]}', fmt.successful_payloads

        # Remove the device from the instance
        try:
            # Remove the device
            del instance.devices[device_name]

            # Also remove any MAC address configuration if present
            mac_key = f'volatile.{device_name}.hwaddr'
            if mac_key in instance.config:
                del instance.config[mac_key]

            instance.save(wait=True)
            fmt.add_successful('network_device.remove', {device_name: 'removed'})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads

        return True, f'1100: {messages[1100]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})

    if status is False:
        return status, msg

    return True, msg