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
        config_file: None,
        host: str,
        username: str,
        password: str = None
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
            description: Path to optional configuration file (not used currently)
            type: string
            required: false
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
        password:
            description: Password for SSH authentication (if provided)
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
        3021: f'Failed to connect to host {host} for payload check_xfrm_interface: ',
        3022: f'Failed to run check_xfrm_interface payload on host {host}: ',
        3023: f'Failed to connect to host {host} for payload remove_existing_routes: ',
        3024: f'Failed to run remove_existing_routes payload on host {host}: ',
        3025: f'Failed to connect to host {host} for payload add_route: ',
        3026: f'Failed to run add_route payload for network {{}} on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username, password)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Check if networks list is empty
        if not networks:
            return True, fmt.payload_error({}, f"1001: " + messages[1001]), fmt.successful_payloads

        # Check if XFRM interface exists
        payloads = {
            'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'remove_existing_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" | xargs -r -I{{}} ip netns exec {namespace} ip route del {{}}'
        }

        ret = rcc.run(payloads['check_xfrm_interface'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" in ret["payload_message"]):
            return False, fmt.payload_error(ret, f"{prefix+2}: XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}"), fmt.successful_payloads
        
        fmt.add_successful('check_xfrm_interface', ret)

        # Remove existing routes
        ret = rcc.run(payloads['remove_existing_routes'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        
        fmt.add_successful('remove_existing_routes', ret)

        # Add new routes for each network
        for network in networks:
            command = f'ip netns exec {namespace} ip route add {network} dev xfrm{vpn_id}'
            ret = rcc.run(command)
            
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5].format(network)), fmt.successful_payloads
            
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6].format(network)), fmt.successful_payloads
            
            fmt.add_successful(f'add_route_{network}', ret)

        return True, messages[1000], fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})

    return status, msg


def read(
    namespace: str,
    vpn_id: int,
    config_file: None,
    host: str,
    username: str,
    password: str = None
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
        config_file:
            description: Path to optional configuration file (not used currently)
            type: string
            required: false
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
        password:
            description: Password for SSH authentication (if provided)
            type: string
            required: false
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
    message_list = []
    data_dict = {
        host: {}
    }

    def run_host(host, prefix, successful_payloads):
        retval = True
        data_dict[host] = {}

        rcc = SSHCommsWrapper(comms_ssh, host, username, password)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'get_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No routes found"'
        }

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
            fmt.store_message(messages[1301])
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
            fmt.store_message(messages[1300])

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    # Use the specified server for testing
    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    return retval, data_dict, message_list


def scrub(
    namespace: str,
    vpn_id: int,
    config_file: None,
    host: str,
    username: str,
    password: str = None
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
            description: Path to optional configuration file (not used currently)
            type: string
            required: false
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
        username:
            description: Username for SSH connection
            type: string
            required: true
        password:
            description: Password for SSH authentication (if provided)
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
        3121: f'Failed to connect to host {host} for payload check_xfrm_interface: ',
        3122: f'Failed to run check_xfrm_interface payload on host {host}: ',
        3123: f'Failed to connect to host {host} for payload get_routes: ',
        3124: f'Failed to run get_routes payload on host {host}: ',
        3125: f'Failed to connect to host {host} for payload remove_routes: ',
        3126: f'Failed to run remove_routes payload on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username, password)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_xfrm_interface': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'get_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" || echo "No routes found"',
            'remove_routes': f'ip netns exec {namespace} ip route show | grep "dev xfrm{vpn_id}" | xargs -r -I{{}} ip netns exec {namespace} ip route del {{}}'
        }

        # Check if XFRM interface exists
        ret = rcc.run(payloads['check_xfrm_interface'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
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

        # Remove routes
        ret = rcc.run(payloads['remove_routes'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6]), fmt.successful_payloads
        
        fmt.add_successful('remove_routes', ret)

        return True, messages[1100], fmt.successful_payloads

    # Use the specified server for testing
    status, msg, successful_payloads = run_host(host, 3120, {})

    return status, msg