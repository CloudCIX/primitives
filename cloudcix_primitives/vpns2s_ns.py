"""
Primitive for Strongswan Site-2-Site VPN tunnels in a Project namespace on Podnet
"""
# stdlib
import json
from typing import Tuple, Dict, List
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    PodnetErrorFormatter,
    SSHCommsWrapper,
    load_pod_config,
    JINJA_ENV,
    check_template_data,
)

__all__ = [
    'build',
    'scrub',
]

SUCCESS_CODE = 0


def build(
        namespace: str,
        vpn_id: int,
        stif_number: int,
        ike_version: str,
        ike_pre_shared_key: str,
        ike_local_identifier: str,
        ike_remote_identifier: str,
        ike_authentication: str,
        ike_dh_groups: str,
        ike_encryption: str,
        ike_lifetime: str,
        ike_gateway_value: str,
        ipsec_authentication: str,
        ipsec_encryption: str,
        ipsec_establish_time: str,
        ipsec_groups: str,
        ipsec_lifetime: str,
        child_sas: List[Dict[str, str]],
        config_file: str = None,
) -> Tuple[bool, str]:
    """
    description:
        Creates and configures a Strongswan Site-2-Site VPN tunnel in the specified namespace

    parameters:
        namespace:
            description: The Project namespace where VPN tunnel should be configured
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the tunnel
            type: integer
            required: true
        stif_number:
            description: STIF interface number
            type: integer
            required: true
        ike_version:
            description: IKE version to use ('1' or '2')
            type: string
            required: true
        ike_pre_shared_key:
            description: Pre-shared key for IKE authentication
            type: string
            required: true
        ike_local_identifier:
            description: Local identifier for IKE
            type: string
            required: true
        ike_remote_identifier:
            description: Remote identifier for IKE
            type: string
            required: true
        ike_authentication:
            description: IKE authentication algorithm
            type: string
            required: true
        ike_dh_groups:
            description: IKE Diffie-Hellman groups
            type: string
            required: true
        ike_encryption:
            description: IKE encryption algorithm
            type: string
            required: true
        ike_lifetime:
            description: IKE lifetime in seconds
            type: string
            required: true
        ike_gateway_value:
            description: IKE gateway address
            type: string
            required: true
        ipsec_authentication:
            description: IPsec authentication algorithm
            type: string
            required: true
        ipsec_encryption:
            description: IPsec encryption algorithm
            type: string
            required: true
        ipsec_establish_time:
            description: When to establish the IPsec tunnel ('on-demand' or 'on-traffic')
            type: string
            required: true
        ipsec_groups:
            description: IPsec groups
            type: string
            required: true
        ipsec_lifetime:
            description: IPsec lifetime in seconds
            type: string
            required: true
        child_sas:
            description: List of child SAs with local and remote traffic selectors
            type: array
            required: true
        config_file:
            description: Path to optional configuration file (JSON format)
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
        1000: f'Successfully configured Site-to-Site VPN tunnel {namespace}-{vpn_id}',
        
        # For enabled PodNet
        3021: f'Failed to connect to the enabled PodNet for payload write_config: ',
        3022: f'Failed to run write_config payload on the enabled PodNet: ',
        3023: f'Failed to connect to the enabled PodNet for payload terminate_vpn: ',
        3024: f'Failed to run terminate_vpn payload on the enabled PodNet: ',
        3025: f'Failed to connect to the enabled PodNet for payload load_vpn: ',
        3026: f'Failed to run load_vpn payload on the enabled PodNet: ',
        3027: f'Failed to connect to the enabled PodNet for payload initiate_vpn: ',
        3028: f'Failed to run initiate_vpn payload on the enabled PodNet: ',
        
        # For disabled PodNet
        3051: f'Failed to connect to the disabled PodNet for payload write_config: ',
        3052: f'Failed to run write_config payload on the disabled PodNet: ',
        3053: f'Failed to connect to the disabled PodNet for payload terminate_vpn: ',
        3054: f'Failed to run terminate_vpn payload on the disabled PodNet: ',
        3055: f'Failed to connect to the disabled PodNet for payload load_vpn: ',
        3056: f'Failed to run load_vpn payload on the disabled PodNet: ',
        3057: f'Failed to connect to the disabled PodNet for payload initiate_vpn: ',
        3058: f'Failed to run initiate_vpn payload on the disabled PodNet: ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Load pod configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
    
    # Use the processed configuration
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']
    # Get podnet_cpe from config.json
    podnet_cpe = config_data['processed'].get('ipv4_link_cpe', '')
    
    # Get SSH username from config (default to 'robot' if not specified)
    username = config_data.get('ssh', {}).get('username', 'robot')

    # Prepare template data
    template_data = {
        'namespace': namespace,
        'vpn_id': vpn_id,
        'ike_version': ike_version,
        'ike_encryption': ike_encryption,
        'ike_authentication': ike_authentication,
        'ike_dh_groups': ike_dh_groups,
        'ike_lifetime': ike_lifetime,
        'podnet_cpe': podnet_cpe,
        'ike_gateway_value': ike_gateway_value,
        'stif_number': stif_number,
        'ike_local_identifier': ike_local_identifier,
        'ike_remote_identifier': ike_remote_identifier,
        'child_sas': child_sas,
        'ipsec_lifetime': ipsec_lifetime,
        'ipsec_encryption': ipsec_encryption,
        'ipsec_authentication': ipsec_authentication,
        'ipsec_groups': ipsec_groups,
        'ipsec_establish_time': ipsec_establish_time,
        'ike_pre_shared_key': ike_pre_shared_key,
    }

    # Load the template
    template = JINJA_ENV.get_template('vpns2s_ns/s2s.conf.j2')
    
    # Validate template data
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f"Template validation error: {template_error}"
    
    # Render configuration template
    conf_template = template.render(**template_data)

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, username)
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        # Prepare the payloads
        conf_filepath = f'/etc/swanctl/conf.d/{namespace}_{vpn_id}.conf'
        payloads = {
            'write_config': '\n'.join([f'tee {conf_filepath} <<EOF', conf_template, 'EOF']),
            'terminate_vpn': f'swanctl --terminate --force --ike {namespace}-{vpn_id} 2>/dev/null || true',
            'load_vpn': 'swanctl --load-all',
            'initiate_vpn': f'swanctl --initiate --ike {namespace}-{vpn_id}'
        }

        # Write configuration file
        ret = rcc.run(payloads['write_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix + 2]), fmt.successful_payloads
        
        fmt.add_successful('write_config', ret)

        # Terminate existing VPN connection if running (allow to fail silently)
        ret = rcc.run(payloads['terminate_vpn'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        
        fmt.add_successful('terminate_vpn', ret)

        # Load all VPN configurations
        ret = rcc.run(payloads['load_vpn'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6]), fmt.successful_payloads
        
        fmt.add_successful('load_vpn', ret)

        # Initiate VPN connection
        ret = rcc.run(payloads['initiate_vpn'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix + 7]), fmt.successful_payloads
        
        fmt.add_successful('initiate_vpn', ret)

        return True, "", fmt.successful_payloads

    # Run commands on enabled PodNet node
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3020, {})
    if not status:
        return status, msg_enabled

    # Run commands on disabled PodNet node
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1000]


def scrub(
    namespace: str,
    vpn_id: int,
    config_file: str = None,
) -> Tuple[bool, str]:
    """
    description:
        Removes Strongswan Site-2-Site VPN tunnel from the specified namespace

    parameters:
        namespace:
            description: The Project namespace where VPN tunnel should be removed
            type: string
            required: true
        vpn_id:
            description: VPN identifier for the tunnel to be removed
            type: integer
            required: true
        config_file:
            description: Path to optional configuration file
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
        1100: f'Successfully removed VPN tunnel {namespace}-{vpn_id}',
        1101: f'VPN tunnel {namespace}-{vpn_id} does not exist',
        
        # For enabled PodNet
        3121: f'Failed to connect to the enabled PodNet for payload terminate_vpn: ',
        3122: f'Failed to run terminate_vpn payload on the enabled PodNet: ',
        3123: f'Failed to connect to the enabled PodNet for payload remove_config: ',
        3124: f'Failed to run remove_config payload on the enabled PodNet: ',
        3125: f'Failed to connect to the enabled PodNet for payload reload_vpn: ',
        3126: f'Failed to run reload_vpn payload on the enabled PodNet: ',
        
        # For disabled PodNet
        3151: f'Failed to connect to the disabled PodNet for payload terminate_vpn: ',
        3152: f'Failed to run terminate_vpn payload on the disabled PodNet: ',
        3153: f'Failed to connect to the disabled PodNet for payload remove_config: ',
        3154: f'Failed to run remove_config payload on the disabled PodNet: ',
        3155: f'Failed to connect to the disabled PodNet for payload reload_vpn: ',
        3156: f'Failed to run reload_vpn payload on the disabled PodNet: ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Load pod configuration
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
    
    # Use the processed configuration
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    # Get SSH username from config (default to 'robot' if not specified)
    username = config_data.get('ssh', {}).get('username', 'robot')

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, username)
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        conf_filepath = f'/etc/swanctl/conf.d/{namespace}_{vpn_id}.conf'
        payloads = {
            'terminate_vpn': f'swanctl --terminate --force --ike {namespace}-{vpn_id}',
            'remove_config': f'rm -f {conf_filepath}',
            'reload_vpn': 'swanctl --load-all'
        }
        
        # Terminate VPN connection
        ret = rcc.run(payloads['terminate_vpn'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix + 1]), fmt.successful_payloads
        
        fmt.add_successful('terminate_vpn', ret)

        # Remove conf file
        ret = rcc.run(payloads['remove_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix + 3]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix + 4]), fmt.successful_payloads
        
        fmt.add_successful('remove_config', ret)

        # Reload all VPNs
        ret = rcc.run(payloads['reload_vpn'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix + 5]), fmt.successful_payloads
        
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix + 6]), fmt.successful_payloads
        
        fmt.add_successful('reload_vpn', ret)
        
        return True, "", fmt.successful_payloads

    # Run commands on enabled PodNet node
    status, msg_enabled, successful_payloads = run_podnet(enabled, 3120, {})
    if not status:
        return status, msg_enabled

    # Run commands on disabled PodNet node
    status, msg_disabled, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if not status:
        return status, msg_disabled

    return True, messages[1100]
