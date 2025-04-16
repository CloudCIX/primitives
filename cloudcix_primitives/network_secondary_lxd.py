"""
Module for Secondary Network Device management in LXD containers.
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
    container_name: str,
    vlan_id: str,
    device_name: str,
    mac_address: str = None,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    Attach a secondary network interface to an LXD container.
    """
    # Define the messages
    messages = {
        1000: f'Successfully attached network interface to container {container_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for network or container operations',
        3022: f'Failed to retrieve networks from {endpoint_url}. Payload exited with status ',
        3023: f'Failed to retrieve container {container_name}. Payload exited with status ',
        3024: f'Network device {device_name} already exists on container {container_name}.',
        3025: f'Network br{vlan_id} does not exist on {endpoint_url}.',
        3026: f'Failed to create network device: ',
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
            return False, f"{prefix+5}: {messages[prefix+5]}", fmt.successful_payloads

        # Get the container
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads

        instance = ret['payload_message']
        fmt.add_successful('containers.get', ret)

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

        # Add the device to the container
        try:
            instance.devices[device_name] = device_config

            # Add MAC address
            if mac_address:
                instance.config[f'volatile.{device_name}.hwaddr'] = mac_address

            instance.save(wait=True)
            fmt.add_successful('network_device.create', {device_name: 'created'})
        except Exception as e:
            return False, f"{prefix+6}: {messages[prefix+6]}{e}", fmt.successful_payloads

        return True, f'1000: {messages[1000]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})

    if status is False:
        return status, msg

    return True, msg

def read(
    endpoint_url: str,
    project: str,
    container_name: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, Dict, str]:
    """
    Read the secondary network configuration of an LXD container.
    """
    # Define the messages
    messages = {
        1200: f'Successfully read network configuration for container {container_name} on {endpoint_url}',
        1201: f'No secondary network interfaces found for container {container_name} on {endpoint_url}',
        3221: f'Failed to connect to {endpoint_url} for container operations',
        3222: f'Failed to retrieve container {container_name}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        result = {}

        # Get the container
        ret = rcc.run(cli='containers.get', name=container_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, {}
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, {}

        container = ret['payload_message']
        fmt.add_successful('containers.get', ret)

        # Get devices from container
        devices = container.devices
        config = container.config

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
    container_name: str,
    device_name: str,
    verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    Remove a secondary network interface from an LXD container.
    """
    # Define the messages
    messages = {
        1100: f'Successfully removed network interface {device_name} from container {container_name} on {endpoint_url}',
        3121: f'Failed to connect to {endpoint_url} for container operations',
        3122: f'Failed to retrieve container {container_name}. Payload exited with status ',
        3124: f'Network interface {device_name} does not exist on container {container_name}.',
        3125: f'Failed to remove network interface: ',
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

        # Check if the device exists
        devices = instance.devices

        if device_name not in devices:
            fmt.add_successful('network_device.remove', {device_name: 'not_found'})
            return True, f'1100: {messages[1100]}', fmt.successful_payloads

        # Remove the device from the container
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
            return False, f"{prefix+5}: {messages[prefix+5]}{e}", fmt.successful_payloads

        return True, f'1100: {messages[1100]}', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})

    if status is False:
        return status, msg

    return True, msg