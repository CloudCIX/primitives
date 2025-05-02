"""
Primitive for VPN routes in a Project namespace on Podnet
"""
# stdlib
from typing import Tuple, Dict, List, Any
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    SSHCommsWrapper,
)

__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
        namespace: str,
        vpn_id: int,
        networks: List[str],
        host: str,
        username: str = "robot",
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
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
            default: "robot"
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
        3021: f'Failed to connect to host {host} for payload check_xfrm_interface: ',
        3022: f'Failed to run check_xfrm_interface payload on host {host}: ',
        3023: f'Failed to connect to host {host} for payload remove_existing_routes: ',
        3024: f'Failed to run remove_existing_routes payload on host {host}: ',
        3025: f'Failed to connect to host {host} for payload add_route: ',
        3026: f'Failed to run add_route payload for network {{}} on host {host}: ',
    }

    # Define all payloads upfront
    payloads = {
        'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
        'check_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No existing routes"'
    }

    # Add dynamic route payloads for each network
    for network in networks:
        payloads[f'add_route_{network}'] = f'ip netns exec {namespace} ip route add {network} dev xfrm{vpn_id}'

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Check if networks list is empty
        if not networks:
            return True, fmt.payload_error({}, f"1001: " + messages[1001]), fmt.successful_payloads

        # Check if XFRM interface exists
        ret = rcc.run(payloads['check_xfrm_interface'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" in ret["payload_message"]):
            return False, fmt.payload_error(ret, f"{prefix+2}: XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}"), fmt.successful_payloads
        
        fmt.add_successful('check_xfrm_interface', ret)

        # First check if there are any routes to remove
        check_route_ret = rcc.run(payloads['check_routes'])
        
        # Handle route removal with improved robustness
        if "No existing routes" in check_route_ret["payload_message"]:
            # No routes to remove, continue
            pass
        else:
            # Parse routes from output and remove them individually
            routes_to_remove = []
            for line in check_route_ret["payload_message"].strip().split('\n'):
                if line and "dev xfrm" in line:
                    parts = line.split()
                    if parts and parts[0]:
                        network = parts[0]
                        routes_to_remove.append(network)
            
            if routes_to_remove:
                for route in routes_to_remove:
                    del_cmd = f'ip netns exec {namespace} ip route del {route}'
                    del_ret = rcc.run(del_cmd)
                    if del_ret["channel_code"] != CHANNEL_SUCCESS or del_ret["payload_code"] != SUCCESS_CODE:
                        # Log warning but continue with other routes
                        pass
        
        fmt.add_successful('remove_existing_routes', {})

        # Add new routes for each network
        success_count = 0
        for network in networks:
            ret = rcc.run(payloads[f'add_route_{network}'])
            
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5].format(network)), fmt.successful_payloads
            
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6].format(network)), fmt.successful_payloads
            
            fmt.add_successful(f'add_route_{network}', ret)
            success_count += 1

        return True, f"{messages[1000]} ({success_count} routes added)", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})

    return status, msg


def read(
    namespace: str,
    vpn_id: int,
    host: str,
    username: str = "robot",
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description:
        Reads the current routes configured for the VPN XFRM interface in the specified namespace

    parameters:
        namespace:
            description: The Project namespace to check routes in
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the XFRM interface
            type: integer
            required: true
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
            default: "robot"
    return:
        description:
            status:
                description: True if all read operations were successful, False otherwise.
                type: boolean
            data:
                type: object
                description: Route data retrieved from host. May be empty if nothing could be retrieved.
            messages:
                type: list
                description: list of error messages encountered during read operation. May be empty.
    """
    # Define messages
    messages = {
        1300: f'Successfully retrieved routes for xfrm{vpn_id} in namespace {namespace}',
        1301: f'No routes found for xfrm{vpn_id} in namespace {namespace}',
        3321: f'Failed to connect to host {host} for payload check_xfrm_interface: ',
        3322: f'Failed to run check_xfrm_interface payload on host {host}: ',
        3323: f'Failed to connect to host {host} for payload get_routes: ',
        3324: f'Failed to run get_routes payload on host {host}: ',
    }
    
    # Define all payloads upfront
    payloads = {
        'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
        'get_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No routes found"'
    }
    
    message_list = []
    data_dict = {
        host: {}
    }

    def run_host(host, prefix, successful_payloads):
        retval = True
        data_dict[host] = {}
        local_message_list = []  # Use a local list for messages

        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        # Check if XFRM interface exists
        ret = rcc.run(payloads['check_xfrm_interface'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix + 1])
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        if (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" in ret["payload_message"]):
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}")
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        fmt.add_successful('check_xfrm_interface', ret)
        
        # Record interface info
        data_dict[host]['interface_exists'] = True
        data_dict[host]['interface_info'] = ret["payload_message"].strip()

        # Get current routes
        ret = rcc.run(payloads['get_routes'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3}: " + messages[prefix + 3])
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4}: " + messages[prefix + 4])
            return retval, fmt.message_list, fmt.successful_payloads, data_dict
        
        fmt.add_successful('get_routes', ret)
        
        if "No routes found" in ret["payload_message"]:
            data_dict[host]['routes'] = []
            # Replace fmt.store_message with adding to local message list
            local_message_list.append(messages[1301])
        else:
            # Parse routes from output
            routes = []
            for line in ret["payload_message"].strip().split('\n'):
                if line.strip():
                    # Extract network part from route line
                    parts = line.split()
                    if parts and parts[0]:
                        network = parts[0]
                        routes.append(network)
            
            data_dict[host]['routes'] = routes
            # Replace fmt.store_message with adding to local message list
            local_message_list.append(messages[1300])

        # Return the local message list instead of expecting fmt to have one
        return retval, local_message_list, fmt.successful_payloads, data_dict

    # Use the specified server for testing
    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    return retval, data_dict, message_list


def scrub(
    namespace: str,
    vpn_id: int,
    host: str,
    username: str = "robot",
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
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
            default: "robot"
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
        3121: f'Failed to connect to host {host} for payload check_xfrm_interface: ',
        3122: f'Failed to run check_xfrm_interface payload on host {host}: ',
        3123: f'Failed to connect to host {host} for payload get_routes: ',
        3124: f'Failed to run get_routes payload on host {host}: ',
        3125: f'Failed to connect to host {host} for payload remove_routes: ',
        3126: f'Failed to run remove_routes payload on host {host}: ',
    }
    
    # Define all payloads upfront
    payloads = {
        'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
        'get_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No routes found"',
        'verify_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No routes found"'
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        # Check if XFRM interface exists
        ret = rcc.run(payloads['check_xfrm_interface'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if (ret["payload_code"] != SUCCESS_CODE) or ("Interface does not exist" in ret["payload_message"]):
            return False, fmt.payload_error(ret, f"Interface xfrm{vpn_id} does not exist in namespace {namespace}"), fmt.successful_payloads
        
        fmt.add_successful('check_xfrm_interface', ret)

        # Check if there are any routes to remove
        ret = rcc.run(payloads['get_routes'])
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        
        fmt.add_successful('get_routes', ret)
        
        if "No routes found" in ret["payload_message"]:
            return True, messages[1101], fmt.successful_payloads

        # Parse routes from output and remove them individually
        routes_to_remove = []
        for line in ret["payload_message"].strip().split('\n'):
            if line and "dev xfrm" in line:
                parts = line.split()
                if parts and parts[0]:
                    network = parts[0]
                    routes_to_remove.append(network)
        
        if not routes_to_remove:
            return True, messages[1101], fmt.successful_payloads
        
        # Add route removal payloads dynamically
        for route in routes_to_remove:
            payloads[f'remove_route_{route}'] = f'ip netns exec {namespace} ip route del {route}'
        
        # Remove each route individually for better error handling
        failed_routes = []
        for route in routes_to_remove:
            del_ret = rcc.run(payloads[f'remove_route_{route}'])
            if del_ret["channel_code"] != CHANNEL_SUCCESS or del_ret["payload_code"] != SUCCESS_CODE:
                failed_routes.append(route)
            else:
                fmt.add_successful(f'remove_route_{route}', del_ret)
        
        if failed_routes:
            return False, fmt.payload_error({}, f"Failed to remove some routes: {failed_routes}"), fmt.successful_payloads
        
        fmt.add_successful('remove_routes', {})

        # Verify all routes were removed
        verify_ret = rcc.run(payloads['verify_routes'])
        
        if "No routes found" in verify_ret["payload_message"]:
            return True, f"{messages[1100]} ({len(routes_to_remove)} routes removed)", fmt.successful_payloads
        else:
            remaining_routes = []
            for line in verify_ret["payload_message"].strip().split('\n'):
                if line and "dev xfrm" in line:
                    parts = line.split()
                    if parts and parts[0]:
                        remaining_routes.append(parts[0])
            
            if remaining_routes:
                return False, fmt.payload_error({}, f"Some routes still remain after removal attempt: {remaining_routes}"), fmt.successful_payloads
            else:
                return True, f"{messages[1100]} ({len(routes_to_remove)} routes removed)", fmt.successful_payloads

    # Use the specified server for testing
    status, msg, successful_payloads = run_host(host, 3120, {})

    return status, msg
