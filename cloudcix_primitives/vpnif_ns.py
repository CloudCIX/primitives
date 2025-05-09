"""
Primitive for VPN interfaces in a Project namespace on Podnet
"""
# stdlib
from typing import Tuple, Dict, List, Any
import json
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper

__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
        namespace: str,
        vpn_id: int,
        config_file=None,
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
        config_file:
            description: Path to the PodNet configuration file
            type: string
            required: false
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
        3021: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload check_vpnif_inside: ',
        3022: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload check_vpnif_outside: ',
        3023: f'Failed to run check_vpnif_inside payload on the enabled PodNet. Payload exited with status ',
        3024: f'Failed to run check_vpnif_outside payload on the enabled PodNet. Payload exited with status ',
        3025: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload delete_vpnif_outside: ',
        3026: f'Failed to run delete_vpnif_outside payload on the enabled PodNet. Payload exited with status ',
        3027: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload delete_vpnif_inside: ',
        3028: f'Failed to run delete_vpnif_inside payload on the enabled PodNet. Payload exited with status ',
        3029: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload create_xfrm_interface: ',
        3030: f'Failed to run create_xfrm_interface payload on the enabled PodNet. Payload exited with status ',
        3031: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload disable_ipsec_policy: ',
        3032: f'Failed to run disable_ipsec_policy payload on the enabled PodNet. Payload exited with status ',
        3033: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload move_to_namespace: ',
        3034: f'Failed to run move_to_namespace payload on the enabled PodNet. Payload exited with status ',
        3035: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload bring_interface_up: ',
        3036: f'Failed to run bring_interface_up payload on the enabled PodNet. Payload exited with status ',
        
        3051: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload check_vpnif_inside: ',
        3052: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload check_vpnif_outside: ',
        3053: f'Failed to run check_vpnif_inside payload on the disabled PodNet. Payload exited with status ',
        3054: f'Failed to run check_vpnif_outside payload on the disabled PodNet. Payload exited with status ',
        3055: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload delete_vpnif_outside: ',
        3056: f'Failed to run delete_vpnif_outside payload on the disabled PodNet. Payload exited with status ',
        3057: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload delete_vpnif_inside: ',
        3058: f'Failed to run delete_vpnif_inside payload on the disabled PodNet. Payload exited with status ',
        3059: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload create_xfrm_interface: ',
        3060: f'Failed to run create_xfrm_interface payload on the disabled PodNet. Payload exited with status ',
        3061: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload disable_ipsec_policy: ',
        3062: f'Failed to run disable_ipsec_policy payload on the disabled PodNet. Payload exited with status ',
        3063: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload move_to_namespace: ',
        3064: f'Failed to run move_to_namespace payload on the disabled PodNet. Payload exited with status ',
        3065: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload bring_interface_up: ',
        3066: f'Failed to run bring_interface_up payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'
    
    # Load PodNet configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
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

        payloads = {
            'check_vpnif_inside': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null',
            'check_vpnif_outside': f'ip link show xfrm{vpn_id} 2>/dev/null',
            'delete_vpnif_outside': f'ip link del xfrm{vpn_id}',
            'delete_vpnif_inside': f'ip netns exec {namespace} ip link del xfrm{vpn_id}',
            'create_xfrm_interface': f'ip link add xfrm{vpn_id} type xfrm dev {device} if_id {vpn_id}',
            'disable_ipsec_policy': f'sysctl -w net.ipv4.conf.xfrm{vpn_id}.disable_policy=1',
            'move_to_namespace': f'ip link set xfrm{vpn_id} netns {namespace}',
            'bring_interface_up': f'ip netns exec {namespace} ip link set dev xfrm{vpn_id} up',
        }

        interface_present_inside = False
        interface_present_outside = False
        
        # Check if interface exists in the project namespace
        ret = rcc.run(payloads['check_vpnif_inside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            interface_present_inside = True
        fmt.add_successful('check_vpnif_inside', ret)
        
        # Check if interface exists in the main namespace
        ret = rcc.run(payloads['check_vpnif_outside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            interface_present_outside = True
        fmt.add_successful('check_vpnif_outside', ret)

        # Handle edge cases
        if interface_present_outside and (not interface_present_inside):
            # Interface exists in main namespace but not in project namespace
            # Delete the stale interface from main namespace
            ret = rcc.run(payloads['delete_vpnif_outside'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('delete_vpnif_outside', ret)
            
        if (not interface_present_outside) and interface_present_inside:
            # Interface exists in project namespace but not in main namespace
            # Delete the stale interface from project namespace
            ret = rcc.run(payloads['delete_vpnif_inside'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            fmt.add_successful('delete_vpnif_inside', ret)

        # Check if interface exists in both namespaces
        if interface_present_inside and interface_present_outside:
            # Interface already exists in both places
            return True, messages[1001], fmt.successful_payloads
        
        # At this point, interface doesn't exist correctly, create it
        if not (interface_present_inside and interface_present_outside):
            # Create XFRM interface
            ret = rcc.run(payloads['create_xfrm_interface'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
            fmt.add_successful('create_xfrm_interface', ret)

            # Disable IPsec policy
            ret = rcc.run(payloads['disable_ipsec_policy'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
            fmt.add_successful('disable_ipsec_policy', ret)

            # Move to namespace
            ret = rcc.run(payloads['move_to_namespace'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+13}: " + messages[prefix+13]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+14}: " + messages[prefix+14]), fmt.successful_payloads
            fmt.add_successful('move_to_namespace', ret)

        # Always bring interface up
        ret = rcc.run(payloads['bring_interface_up'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+15}: " + messages[prefix+15]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+16}: " + messages[prefix+16]), fmt.successful_payloads
        fmt.add_successful('bring_interface_up', ret)

        return True, messages[1000], fmt.successful_payloads

    # Run on enabled PodNet
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3020, {})
    if not status:
        return status, msg_enabled

    # Run on disabled PodNet
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1000]


def read(
    namespace: str,
    vpn_id: int,
    config_file=None,
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
        config_file:
            description: Path to the PodNet configuration file
            type: string
            required: false
    return:
        description:
            status:
                description: True if all read operations were successful, False otherwise.
                type: boolean
            data:
                type: object
                description: interface data retrieved from PodNets. May be empty if nothing could be retrieved.
            messages:
                type: list
                description: list of error messages encountered during read operation. May be empty.
    """
    # Define messages
    messages = {
        1300: f'Successfully checked XFRM interface xfrm{vpn_id} in namespace {namespace}',
        1301: f'XFRM interface xfrm{vpn_id} does not exist in namespace {namespace}',
        3321: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload check_vpnif: ',
        3322: f'Failed to run check_vpnif payload on the enabled PodNet. Payload exited with status ',
        
        3351: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload check_vpnif: ',
        3352: f'Failed to run check_vpnif payload on the disabled PodNet. Payload exited with status ',
    }
    
    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'
    
    # Load PodNet configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, {}, [msg]
        else:
            return False, {}, [msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)]
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']
    
    message_list = []
    data_dict = {
        'enabled': {},
        'disabled': {}
    }

    def run_podnet(podnet_node, prefix, successful_payloads):
        retval = True
        node_type = 'enabled' if podnet_node == enabled else 'disabled'
        data_dict[node_type] = {}
        local_message_list = []  # Use a local list for messages

        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'check_vpnif': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
        }

        ret = rcc.run(payloads['check_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            local_message_list.append(f"{prefix+1}: " + messages[prefix + 1])
            return retval, local_message_list, fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            local_message_list.append(f"{prefix+2}: " + messages[prefix + 2])
            return retval, local_message_list, fmt.successful_payloads
        
        fmt.add_successful('check_vpnif', ret)
        
        if "Interface does not exist" in ret["payload_message"]:
            data_dict[node_type]['exists'] = False
            local_message_list.append(messages[1301])
        else:
            data_dict[node_type]['exists'] = True
            data_dict[node_type]['interface_info'] = ret["payload_message"].strip()
            local_message_list.append(messages[1300])

        return retval, local_message_list, fmt.successful_payloads

    # Run on enabled PodNet
    retval_enabled, msg_list_enabled, successful_payloads = run_podnet(enabled, 3320, {})
    message_list.extend(msg_list_enabled)

    # Run on disabled PodNet
    retval_disabled, msg_list_disabled, successful_payloads = run_podnet(disabled, 3350, successful_payloads)
    message_list.extend(msg_list_disabled)

    # Overall success if both operations were successful
    overall_success = retval_enabled and retval_disabled

    return overall_success, data_dict, message_list


def scrub(
    namespace: str,
    vpn_id: int,
    config_file=None,
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
        config_file:
            description: Path to the PodNet configuration file
            type: string
            required: false
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
        3121: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload check_vpnif: ',
        3122: f'Failed to run check_vpnif payload on the enabled PodNet. Payload exited with status ',
        3123: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload delete_vpnif: ',
        3124: f'Failed to run delete_vpnif payload on the enabled PodNet. Payload exited with status ',
        
        3151: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload check_vpnif: ',
        3152: f'Failed to run check_vpnif payload on the disabled PodNet. Payload exited with status ',
        3153: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload delete_vpnif: ',
        3154: f'Failed to run delete_vpnif payload on the disabled PodNet. Payload exited with status ',
    }
    
    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'
    
    # Load PodNet configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
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

        payloads = {
            'check_vpnif': f'ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo "Interface does not exist"',
            'delete_vpnif': f'ip netns exec {namespace} ip link delete dev xfrm{vpn_id}',
        }

        # Check if interface exists
        ret = rcc.run(payloads['check_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        
        fmt.add_successful('check_vpnif', ret)
        
        if "Interface does not exist" in ret["payload_message"]:
            # No need to remove interface: it does not exist
            return True, messages[1101], fmt.successful_payloads

        # Delete interface
        ret = rcc.run(payloads['delete_vpnif'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('delete_vpnif', ret)

        return True, messages[1100], fmt.successful_payloads

    # Run on enabled PodNet
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3120, {})
    if not status:
        return status, msg_enabled

    # Run on disabled PodNet
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1100]
