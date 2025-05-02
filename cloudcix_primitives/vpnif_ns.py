"""
Primitive for VPN interfaces in a Project namespace on Podnet
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
        host: str,
        username: str = "robot", 
        device: str = "public0",
) -> Tuple[bool, str]:
    """
    description:
        Creates a XFRM interface in the specified namespace for VPN

    parameters:
        namespace:
            description: The Project namespace where VPN interface should be created
            type: string
            required: true
        vpn_id:
            description: VPN identifier used to create the XFRM interface name
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
        device:
            description: Physical device to use for the XFRM interface
            type: string
            required: false
            default: "public0"
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    
    # Define messages
    messages = {
        1000: f'Successfully created XFRM interface xfrm{vpn_id} in namespace {namespace}',
        1001: f'XFRM interface xfrm{vpn_id} already exists in namespace {namespace}',
        3021: f'Failed to connect to host {host} for payload check_vpnif: ',
        3022: f'Failed to run check_vpnif payload on host {host}: ',
        3023: f'Failed to connect to host {host} for payload create_xfrm_interface: ',
        3024: f'Failed to run create_xfrm_interface payload on host {host}. Payload exited with status ',
        3025: f'Failed to connect to host {host} for payload disable_ipsec_policy: ',
        3026: f'Failed to run disable_ipsec_policy payload on host {host}. Payload exited with status ',
        3027: f'Failed to connect to host {host} for payload move_to_namespace: ',
        3028: f'Failed to run move_to_namespace payload on host {host}. Payload exited with status ',
        3029: f'Failed to connect to host {host} for payload bring_interface_up: ',
        3030: f'Failed to run bring_interface_up payload on host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'check_vpnif': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'create_xfrm_interface': f'ip link add xfrm{vpn_id} type xfrm dev {device} if_id {vpn_id}',
            'disable_ipsec_policy': f'sysctl -w net.ipv4.conf.xfrm{vpn_id}.disable_policy=1',
            'move_to_namespace': f'ip link set xfrm{vpn_id} netns {namespace}',
            'bring_interface_up': f'ip netns exec {namespace} ip link set dev xfrm{vpn_id} up',
        }

        # Check if interface already exists in namespace
        ret = rcc.run(payloads['check_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" not in ret["payload_message"]):
            # Interface already exists
            return True, messages[1001], fmt.successful_payloads
        elif (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" in ret["payload_message"]):
            fmt.add_successful('check_vpnif', ret)
        else:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads

        # Create XFRM interface
        ret = rcc.run(payloads['create_xfrm_interface'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4] + str(ret["payload_code"])), fmt.successful_payloads
        fmt.add_successful('create_xfrm_interface', ret)

        # Disable IPsec policy
        ret = rcc.run(payloads['disable_ipsec_policy'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6] + str(ret["payload_code"])), fmt.successful_payloads
        fmt.add_successful('disable_ipsec_policy', ret)

        # Move to namespace
        ret = rcc.run(payloads['move_to_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix + 7]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix + 8] + str(ret["payload_code"])), fmt.successful_payloads
        fmt.add_successful('move_to_namespace', ret)

        # Bring interface up
        ret = rcc.run(payloads['bring_interface_up'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10] + str(ret["payload_code"])), fmt.successful_payloads
        fmt.add_successful('bring_interface_up', ret)

        return True, messages[1000], fmt.successful_payloads

    # Use the specified server for testing
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
        Checks if the XFRM interface exists in the specified namespace

    parameters:
        namespace:
            description: The Project namespace where VPN interface should be checked
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
                description: interface data retrieved from host. May be empty if nothing could be retrieved.
            messages:
                type: list
                description: list of error messages encountered during read operation. May be empty.
    """
    # Define messages
    messages = {
        1300: f'Successfully checked XFRM interface xfrm{vpn_id} in namespace {namespace}',
        1301: f'XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}',
        3321: f'Failed to connect to host {host} for payload check_vpnif: ',
        3322: f'Failed to run check_vpnif payload on host {host}: ',
    }
    message_list = []
    data_dict = {
        host: {}
    }

    def run_host(host, prefix, successful_payloads):
        retval = True
        data_dict[host] = {}
        message_list = []

        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_vpnif': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
        }

        ret = rcc.run(payloads['check_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            message = fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1])
            message_list.append(message)
        elif (ret["payload_code"] != SUCCESS_CODE):
            retval = False
            message = fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2])
            message_list.append(message)
        elif "Interface does not exist" in ret["payload_message"]:
            retval = True
            data_dict[host]['exists'] = False
            fmt.add_successful('check_vpnif', ret)
            message_list.append(messages[1301])
        else:
            retval = True
            data_dict[host]['exists'] = True
            data_dict[host]['interface_info'] = ret["payload_message"].strip()
            fmt.add_successful('check_vpnif', ret)
            message_list.append(messages[1300])

        return retval, message_list, fmt.successful_payloads, data_dict

    # Use the specified server for testing
    retval, msg_list, successful_payloads, data_dict = run_host(host, 3320, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1300]] if data_dict[host].get('exists', False) else [messages[1301]]


def scrub(
    namespace: str,
    vpn_id: int,
    host: str,
    username: str = "robot",
) -> Tuple[bool, str]:
    """
    description:
        Removes XFRM interface from the specified namespace

    parameters:
        namespace:
            description: The Project namespace where VPN interface should be removed
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the XFRM interface to be removed
            type: integer
            required: true
        host:
            description: The host to connect to for running the commands
            type: string
            required: true
            default: "robot"
        username:
            description: Username for SSH connection
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the remove was successful or not and
            the output or error message.
        type: tuple
    """
    # Define messages
    messages = {
        1100: f'Successfully removed XFRM interface xfrm{vpn_id} from namespace {namespace}',
        1101: f'XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}',
        3121: f'Failed to connect to host {host} for payload check_vpnif: ',
        3122: f'Failed to run check_vpnif payload on host {host}: ',
        3123: f'Failed to connect to host {host} for payload delete_vpnif: ',
        3124: f'Failed to run delete_vpnif payload on host {host}: ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, username)
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_vpnif': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'delete_vpnif': f'ip netns exec {namespace} ip link delete dev xfrm{vpn_id}',
        }

        # Check if interface exists
        ret = rcc.run(payloads['check_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" in ret["payload_message"]):
            # No need to remove interface: it does not exist
            return True, messages[1101], fmt.successful_payloads
        elif (ret["payload_code"] == SUCCESS_CODE) and ("Interface does not exist" not in ret["payload_message"]):
            fmt.add_successful('check_vpnif', ret)
        else:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads

        # Delete interface
        ret = rcc.run(payloads['delete_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('delete_vpnif', ret)

        return True, messages[1100], fmt.successful_payloads

    # Use the specified server for testing
    status, msg, successful_payloads = run_host(host, 3120, {})

    return status, msg
