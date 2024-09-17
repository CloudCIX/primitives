"""
Primitive for Domain Nftables of Network Namespace on PodNet HA
"""
# stdlib
import json
import ipaddress
from pathlib import Path
from collections import deque
from typing import Any, Deque, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local
from .controllers import FirewallNamespace
from utils import JINJA_ENV, check_template_data

__all__ = [
    'build',
]

SUCCESS_CODE = 0


def complete_rule(rule, iiface, oiface, namespace, table):
    v = '' if rule['version'] == '4' else '6'

    # input interface line
    iif = f'iifname {iiface}' if iiface not in [None, 'any'] else ''

    # output interface line
    oif = f'oifname {oiface}' if oiface not in [None, 'any'] else ''

    # sort the `destination` rule format
    if rule['destination'] is None or 'any' in rule['destination']:
        daddr = ''
    else:
        daddr = f'ip{v} daddr ' + '{' + ','.join(rule['destination']) + '}'

    # sort the `source` rule format
    if rule['source'] is None or 'any' in rule['source']:
        saddr = ''
    else:
        saddr = f'ip{v} saddr ' + '{' + ','.join(rule['source']) + '}'

    # sort the `port` rule format
    if rule['port'] is None or rule['protocol'] == 'any':
        dport = ''
    else:
        dport = 'dport ' + '{' + ','.join(rule['port']) + '}'

    # rule protocol and port statement, also gather protocols that require to define chains in config
    application = None
    if rule['protocol'] == 'any':
        proto_port = f'{rule["action"]}'
    elif rule['protocol'] == 'icmp':
        proto_port = f'jump icmp{v}_{rule["action"]}'
        application = f'icmp{v}_{rule["action"]}'
    elif rule['protocol'] == 'dns':
        proto_port = f'jump dns_{rule["action"]}'
        application = f'dns_{rule["action"]}'
    elif rule['protocol'] == 'vpn':
        proto_port = f'jump vpn_{rule["action"]}'
        application = f'vpn_{rule["action"]}'
    else:
        proto_port = f'{rule["protocol"]} {dport} {rule["action"]}'

    # log
    log = f'log prefix "{namespace} Table: {table}" level debug group 0' if rule['log'] is True else ''

    return f'{iif} {oif} {saddr} {daddr} {log} {proto_port}', application


def dnat_rule(nat):
    rule_line = f'iifname "{nat["iiface"]}" ' if nat['iiface'] is not None else ''
    rule_line = f'{rule_line}ip daddr {nat["public"]} dnat to {nat["private"]} '
    return rule_line


def snat_rule(nat):
    rule_line = f'oifname "{nat["oiface"]}" ' if nat['oiface'] is not None else ''
    rule_line = f'{rule_line}ip saddr {nat["private"]} snat to {nat["public"]} '
    return rule_line


def build(
        namespace: str,
        table: str,
        priority: int,
        config_file=None,
        rules=None,
        nats=None,
) -> Tuple[bool, str]:
    """
    description: |
        1. Creates a /tmp/firewallns_<namespace>_<table>.conf file with nftable table config
        2. Validates the nft file
           `ip netns exec <namespace> nft --check --file /tmp/firewallns_<namespace>_<table>.conf`
        3. Flushes already existing nftables table in namespace if any
           `ip netns exec <namespace> nft flush table inet <table>`
        4. Config is applied `ip netns exec <namespace> --file /tmp/firewallns_<namespace>_<table>.conf`

    parameters:
        namespace:
            description: Network Namespace Identifier on the PodNet HA on which the table is applied.
            type: string
            required: true
        table:
            description: Name of the table in nftables, a table per domains like firewall, nats, vpns2s and vpndyn
            type: string
            required: true
        priority:
            description: |
                The priority in an nftables chain definition determines the order in which chains are processed
                by the packet filter when multiple chains are attached to the same hook (e.g., input, output, forward).
                It helps specify the execution order of the rules in different chains,
                allowing some rules to be evaluated before others.
                Lower values: Higher priority (processed first).
                Higher values: Lower priority (processed later).
            type: integer
            required: true
        config_file:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: false
            type: string
        rules:
            description: |
                containing list of firewall rules in the following format
                rule = {
                    'version': '4',
                    'source': ['91.103.3.36'],
                    'destination': ['10.0.0.2'],
                    'protocol': 'tcp',
                    'port': ['22'],
                    'action': 'accept',
                    'log': True,
                    'iiface': 'VRF123.BM45',
                    'oiface': 'private0.1000',
                    'order': 0,
                }
            type: array
            items:
                type: dict
                properties:
                    version:
                        description: version of IP ie 4 or 6
                        type: string
                        required: true
                    source:
                        description: list of source ipaddresses (all must be either private or public but not mixed)
                        type: array
                        items:
                            type: string
                        required: true
                    destination:
                        description: |
                            list of destination ipaddresses (all must be either private or public but not mixed)
                        type: array
                        items:
                            type: string
                        required: true
                    protocol:
                        description: name of the protocol, e.g `tcp`, `udp`, `icmp` or `any`
                        type: string
                        required: true
                    port:
                        description: list of ports, a port is a number in range [0, 65535] and `*`(any)
                        type: array
                        items:
                            type: string
                        required: true
                    action:
                        description: can take either `accept` or `drop`
                        type: string
                        required: true
                    log:
                        description: to log the rule, this has to be True otherwise False
                        type: boolean
                        required: true
                    iiface:
                        description: |
                            the input interface, entry point of a traffic in the network namespace
                            e.g 'VRF123.BM90', 'private0.1004', 'none'
                        type: string
                        required: true
                    oiface:
                        description: |
                            the output interface, exit point of a traffic from the network namespace
                            e.g 'VRF123.BM90', 'private0.1004', 'none'
                        type: string
                        required: true
            required: false
        nats:
            description: |
                    NAT object with dnats and snats Private IP and its Public IP or defaulted to None
                nats = {
                    'dnats': [
                        {
                            'public': '91.103.3.36',
                            'private': '192.168.0.2',
                            'iiface': 'VRF123.BM45'
                        },
                    ]
                    'snats': [
                        {
                            'public': '91.103.3.1',
                            'private': '192.168.0.1/24',
                            'oiface': 'VRF123.BM45'
                        },
                    ]
                }
            required: false
            type: array
            items:
                type: object
                properties:
                    dnats:
                        description: list of dnat pairs
                        type: array
                        items:
                            type: dict
                            properties:
                                public:
                                    description: destination address, it should be a Public IP
                                    type: string
                                    required: true
                                private:
                                    description: destination nat address, it should be a Private IP
                                    type: string
                                    required: true
                                iiface:
                                    description: |
                                        the input interface, entry point of a traffic in the network namespace
                                        e.g 'VRF123.BM90'
                                    type: string
                                    required: true
                        required: false
                    snats:
                        description: list of snat pairs
                        type: array
                        items:
                            type: dict
                            properties:
                                public:
                                    description: source nat address, it should be a Public IP
                                    type: string
                                    required: true
                                private:
                                    description: source address, it should be a Private address or address range
                                    type: string
                                    required: true
                                oiface:
                                    description: |
                                        the output interface, exit point of a traffic from the network namespace
                                        e.g 'VRF123.BM90'
                                    type: string
                                    required: true
                        required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define variables
    nftables_file = f'/tmp/firewallns_{namespace}_{table}.conf'

    # Define message
    messages = {
        1000: f'1000: Successfully created nftables {table} in namespace {namespace}',
        2011: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to create nftables {table} in namespace {namespace}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3020: f'3020: Failed to Verify rules. One or more rules have invalid values',
        3030: f'3030: One of the rule is Invalid, Both `iiface` and `oiface` cannot be None in a rule object',
        3040: f'3040: Failed to verify nftables.conf.j2 template data, One or more template fields are None',
        3050: f'3050: Failed to connect to the enabled PodNet from the config file {config_file}',
        3051: f'3051: Failed to create nftables file {nftables_file} on the enabled PodNet',
        3060: f'3060: Failed to connect to the enabled PodNet from the config file {config_file}',
        3061: f'3061: Failed to validate nftables file {nftables_file} on the enabled PodNet',
        3070: f'3070: Failed to connect to the enabled PodNet from the config file {config_file}',
        3071: f'3071: Failed to flush table {table} on the enabled PodNet',
        3080: f'3080: Failed to connect to the enabled PodNet from the config file {config_file}',
        3081: f'3081: Failed to apply nftables file {nftables_file} on the enabled PodNet',
        3090: f'3090: Failed to connect to the disabled PodNet from the config file {config_file}',
        3091: f'3091: Failed to create nftables file {nftables_file} on the disabled PodNet',
        3100: f'3100: Failed to connect to the disabled PodNet from the config file {config_file}',
        3101: f'3101: Failed to create nftables file {nftables_file} on the disabled PodNet',
        3110: f'3110: Failed to connect to the disabled PodNet from the config file {config_file}',
        3111: f'3111: Failed to validate nftables file {nftables_file} on the disabled PodNet',
        3120: f'3120: Failed to connect to the disabled PodNet from the config file {config_file}',
        3121: f'3121: Failed to flush table {table} on the disabled PodNet',
        3130: f'3130: Failed to connect to the disabled PodNet from the config file {config_file}',
        3131: f'3131: Failed to apply nftables file {nftables_file} on the disabled PodNet',
    }

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3011]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3012]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3013]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3014]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3015]

    # Find out enabled and disabled PodNets
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3016]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3017]
    else:
        return False, messages[3018]

    # Block 02: Validate rules
    proceed, errors = True, []
    for rule in rules:
        validated = FirewallNamespace(rule)
        success, errs = validated()
        if success is False:
            proceed = False
            errors.extend(errs)

    if proceed is False:
        return False, messages[3020]

    # Block 03: Prepare Firewall rules
    # DNAT and SNAT rules
    prerouting_rules: List[str] = []
    postrouting_rules: List[str] = []
    if nats is not None:
        dnats = nats.get('dnats', [])
        snats = nats.get('snats', [])
        for dnat in dnats:
            prerouting_rules.append(dnat_rule(dnat))
        for snat in snats:
            postrouting_rules.append(snat_rule(snat))

    # applications
    applications: List[str] = []
    # input_rules
    input_rules: Deque[str] = deque()
    # forward_rules
    forward_rules: Deque[str] = deque()
    # output_rules
    output_rules: Deque[str] = deque()

    for rule in sorted(rules, key=lambda fw: fw['order']):
        # sort traffic direction ie inbound, outbound and forward
        iiface = rule['iiface'] if rule['iiface'] not in [None, '', 'none'] else None
        oiface = rule['oiface'] if rule['oiface'] not in [None, '', 'none'] else None
        if iiface is not None and oiface is None:
            input_rule, application = complete_rule(rule, iiface, None, namespace, table)
            input_rules.append(input_rule)
            applications.append(application)
        elif iiface is None and oiface is not None:
            output_rule, application = complete_rule(rule, None, oiface, namespace, table)
            output_rules.append(output_rule)
            applications.append(application)
        elif iiface is not None and oiface is not None:
            forward_rule, application = complete_rule(rule, iiface, oiface, namespace, table)
            forward_rules.append(forward_rule)
            applications.append(application)
        else:
            return False, messages[3030]

    # remove the duplicates in applications
    applications = list(set(applications))

    # Block 04: Prepare nftables.conf template
    # template data
    template_data = {
        'applications': applications,
        'forward_rules': forward_rules,
        'input_rules': input_rules,
        'output_rules': output_rules,
        'postrouting_rules': postrouting_rules,
        'prerouting_rules': prerouting_rules,
        'priority': priority,
        'table': table,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template('firewallns/nftables.conf.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, messages[3040]

    # Generate Firewall build config
    nftables_config = template.render(**template_data)

    # Define Payloads
    payload_create_nftables_file = f'echo "{nftables_config}" > {nftables_file}'
    payload_validate_nftables_file = f'ip netns exec {namespace} nft --check --file {nftables_file}'
    payload_flush_table = f'if ip netns exec {namespace} nft list tables | grep -q "inet {table}"; then' \
                          f' ip netns exec {namespace} nft flush table inet {table}; fi'
    payload_apply_nftables_file = f'ip netns exec {namespace} nft --file {nftables_file}'
    payload_remvoe_nftables_file = f'rm {nftables_file}'

    # Block 05: Create temp nftables.conf file on Enabled PodNet
    # call rcc comms_ssh on enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_create_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3050]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3051]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 06: Validate temp nftables.conf file on Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_validate_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3060]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3061]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 07: Flush the table if exists already on Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_flush_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3070]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3071]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 08: Apply the nftables.conf file to the namespace on Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_apply_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3080]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3081]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 09: Remove the temp nftables.conf file on Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_remvoe_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3090]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3091]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 10: Create temp nftables.conf file on Disabled PodNet
    # call rcc comms_ssh on enabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_create_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3100]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3101]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 11: Validate temp nftables.conf file on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_validate_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3110]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3111]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 12: Flush the table if exists already on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_flush_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3120]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3121]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 13: Apply the nftables.conf file to the namespace on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_apply_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3130]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3131]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 14: Remove the temp nftables.conf file on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_remvoe_nftables_file,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3140]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3141]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    return True, messages[1000]


def scrub(
        namespace: str,
        table: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description: Flushes already existing nftables <table> in <namespace>
    parameters:
        namespace:
            description: Network Namespace Identifier on the PodNet HA on which the table is applied.
            type: string
            required: true
        table:
            description: Name of the table in nftables, a table per domains like firewall, nats, vpns2s and vpndyn
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully removed nftables {table} in namespace {namespace}',
        2011: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to remove nftables {table} in namespace {namespace}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3020: f'3020: Failed to connect to the Enabled PodNet from the config file {config_file}',
        3021: f'3021: Failed to flush table {table} on the Enabled PodNet',
        3030: f'3030: Failed to connect to the Disabled PodNet from the config file {config_file}',
        3031: f'3031: Failed to flush table {table} on the Disabled PodNet',
    }

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3011]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3012]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3013]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3014]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3015]

    # Find out enabled and disabled PodNets
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3016]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3017]
    else:
        return False, messages[3018]

    # Define payload
    payload_flush_table = f'if ip netns exec {namespace} nft list tables | grep -q "inet {table}"; then' \
                          f' ip netns exec {namespace} nft flush table inet {table}; fi'

    # Block 02: Flush the table if exists already on Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_flush_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3020]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3021]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    # Block 03: Flush the table if exists already on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_flush_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3030]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3031]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        return False, msg

    return True, messages[1000]


def read(
        namespace: str,
        table: str,
        config_file=None,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description: Gets the entire rules of nftables <table> in <namespace>
    parameters:
        namespace:
            description: Network Namespace Identifier on the PodNet HA on which the table is applied.
            type: string
            required: true
        table:
            description: Name of the table in nftables, a table per domains like firewall, nats, vpns2s and vpndyn
            type: string
            required: true
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successful, (2) a dict containing the data as read from
            the both machine's current state and (3) the list of debug and or error messages.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: read output data from machine <podnet_ip>
                  type: string
          messages:
            description: list of errors and debug messages collected before failure occurred
            type: array
            items:
              <message>:
                description: exact message of the step, either debug, info or error type
                type: string
    """
    # Define message
    messages = {
        1000: f'1000: Successfully read nftables {table} in namespace {namespace}',
        2011: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to read nftables {table} in namespace {namespace}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3020: f'3020: Failed to connect to the Enabled PodNet from the config file {config_file}',
        3021: f'3021: Failed to read table {table} from the Enabled PodNet',
        3030: f'3030: Failed to connect to the Disabled PodNet from the config file {config_file}',
        3031: f'3031: Failed to read table {table} from the Disabled PodNet',
    }

    # set the outputs
    success = True
    data_dict = {}
    message_list = []

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        success = False
        message_list.append(messages[3011])
        return success, data_dict, message_list
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        success = False
        message_list.append(messages[3012])
        return success, data_dict, message_list
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        success = False
        message_list.append(messages[3013])
        return success, data_dict, message_list

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    data_dict = {
        podnet_a: None,
        podnet_b: None,
    }

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        success = False
        message_list.append(messages[3014])
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        success = False
        message_list.append(messages[3015])

    # Find out enabled and disabled podnets
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        success = False
        message_list.append(messages[3016])
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        success = False
        message_list.append(messages[3017])
    else:
        success = False
        message_list.append(messages[3018])

    # return if success is False at this stage
    if success is False:
        return success, data_dict, message_list

    # Define payload
    payload_read_table = f'if ip netns exec {namespace} nft list table inet {table}'

    # Block 02: Read the table from Enabled PodNet
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_read_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3020]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3021]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    data_dict[enabled] = response['payload_message']

    # Block 03: Flush the table if exists already on Disabled PodNet
    response = comms_ssh(
        host_ip=disabled,
        payload=payload_read_table,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3030]}\nChannel Code: {response["channel_code"]}s.\n'
        msg += f'Channel Message: {response["channel_message"]}\nChannel Error: {response["channel_error"]}'
        message_list.append(msg)
        success = False
    if response['payload_code'] != SUCCESS_CODE:
        msg = f'{messages[3031]}\nPayload Code: {response["payload_code"]}s.\n'
        msg += f'Payload Message: {response["payload_message"]}\nPayload Error: {response["payload_error"]}'
        message_list.append(msg)
        success = False

    data_dict[disabled] = response['payload_message']

    return success, data_dict, message_list
