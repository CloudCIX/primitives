"""
Primitive for managing VPN routes in a Project namespace
"""
# stdlib
from typing import List, Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper

__all__ = [
    'build',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    namespace: str,
    vpn_id: int,
    networks: List[str],
    config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Adds routes for specified networks through the VPN XFRM interface in the specified namespace

    parameters:
        namespace:
            description: The Project namespace where routes should be added
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the XFRM interface
            type: integer
            required: true
        networks:
            description: List of network CIDRs to route through the VPN
            type: array
            required: true
        config_file:
            description: Path to the PodNet configuration file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully added routes for networks through xfrm{vpn_id} in namespace {namespace}',
        1001: f'No networks provided to add routes for',
        3023: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload remove_existing_routes: ',
        3024: f'Failed to run remove_existing_routes payload on the enabled PodNet. Payload exited with status ',
        3025: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload add_route: ',
        3026: f'Failed to run add_route payload for network %(network)s on the enabled PodNet. Payload exited with status ',
        3053: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload remove_existing_routes: ',
        3054: f'Failed to run remove_existing_routes payload on the disabled PodNet. Payload exited with status ',
        3055: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload add_route: ',
        3056: f'Failed to run add_route payload for network %(network)s on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Check if networks list is empty
    if not networks:
        return False, messages[1001]

    # Load PodNet configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        return False, msg

    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Define all payloads
        payloads = {
            'check_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" 2>/dev/null || echo "Interface does not exist"',  
            'add_route': f'ip netns exec {namespace} ip route add %(network)s dev xfrm{vpn_id}',
            'del_route': f'ip netns exec {namespace} ip route del %(route)s',
        }

        # Remove existing routes first
        check_routes_ret = rcc.run(payloads['check_routes'])
        
        if check_routes_ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(check_routes_ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        
        if check_routes_ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(check_routes_ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
            
        # Remove existing routes if any
        if "Interface does not exist" not in check_routes_ret["payload_message"]:
            routes = []
            for line in check_routes_ret["payload_message"].strip().split('\n'):
                if line and f"dev xfrm{vpn_id}" in line:
                    parts = line.split()
                    if parts and parts[0]:
                        routes.append(parts[0])
            
            for route in routes:
                payload = payloads['del_route'] % {'route': route}
                ret = rcc.run(payload)
                
                fmt.add_successful(f'remove_existing_route_{route}', {})

        # Add routes for each network
        success_count = 0
        for network in networks:
            payload = payloads['add_route'] % {'network': network}
            ret = rcc.run(payload)
            
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5] % {'network': network}), fmt.successful_payloads
            
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6] % {'network': network}), fmt.successful_payloads
            
            fmt.add_successful(f'add_route_{network}', ret)
            success_count += 1

        return True, f"{messages[1000]} ({success_count} routes added)", fmt.successful_payloads

    # Run on enabled PodNet
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3020, {})
    if not status:
        return status, msg_enabled

    # Run on disabled PodNet
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1000]


def scrub(
    namespace: str,
    vpn_id: int,
    config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Removes all routes configured for the VPN XFRM interface in the specified namespace

    parameters:
        namespace:
            description: The Project namespace to remove routes from
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the XFRM interface
            type: integer
            required: true
        config_file:
            description: Path to the PodNet configuration file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the removal was successful or not and
            the output or error message.
        type: tuple
    """
    # Define messages
    messages = {
        1100: f'Successfully removed all routes for xfrm{vpn_id} in namespace {namespace}',
        1101: f'No routes found for xfrm{vpn_id} in namespace {namespace}',
        3121: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload check_routes: ',
        3122: f'Failed to run check_routes payload on the enabled PodNet. Payload exited with status ',
        3123: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload del_route: ',
        3124: f'Failed to run del_route payload on the enabled PodNet. Payload exited with status ',        
        3151: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload check_routes: ',
        3152: f'Failed to run check_routes payload on the disabled PodNet. Payload exited with status ',
        3153: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload del_route: ',
        3154: f'Failed to run del_route payload on the disabled PodNet. Payload exited with status ',
    }
    
    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'
    
    # Load PodNet configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        return False, msg
        
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        # Define all payloads upfront with consistent formatting
        payloads = {
            'check_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" 2>/dev/null || echo "No routes found"',
            'del_route': f'ip netns exec {namespace} ip route del %(route)s',
        }

        # Check for existing routes
        ret = rcc.run(payloads['check_routes'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        
        fmt.add_successful('check_routes', ret)
        
        if "No routes found" in ret["payload_message"]:
            return True, messages[1101], fmt.successful_payloads

        # Parse routes and remove them
        routes_to_remove = []
        for line in ret["payload_message"].strip().split('\n'):
            if line and "dev xfrm" in line:
                parts = line.split()
                if parts and parts[0]:
                    routes_to_remove.append(parts[0])
        
        if not routes_to_remove:
            return True, messages[1101], fmt.successful_payloads
        
        # Remove each route individually
        removed_count = 0
        for route in routes_to_remove:
            payload = payloads['del_route'] % {'route': route}
            ret = rcc.run(payload)
            
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
            
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
            
            fmt.add_successful(f'del_route_{route}', ret)
            removed_count += 1

        return True, f"{messages[1100]} ({removed_count} routes removed)", fmt.successful_payloads

    # Run on enabled PodNet
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3120, {})
    if not status:
        return status, msg_enabled

    # Run on disabled PodNet
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1100]
