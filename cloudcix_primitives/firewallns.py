"""
Primitive for Domain Nftables of Network Namespace on PodNet HA
"""
# stdlib
import json
from collections import deque
from typing import Any, Deque, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local
from .controllers import FirewallNamespace, FirewallNAT, FirewallSet
from cloudcix_primitives.utils import (
    JINJA_ENV,
    check_template_data,
    load_pod_config,
    SSHCommsWrapper,
    PodnetErrorFormatter,
)

__all__ = [
    'build',
]

SUCCESS_CODE = 0


def complete_rule(rule, iiface, oiface, namespace, table):
    v = '' if str(rule['version']) == '4' else '6'

    # input interface line
    iif = f'iifname {iiface}' if iiface not in [None, 'any'] else ''

    # output interface line
    oif = f'oifname {oiface}' if oiface not in [None, 'any'] else ''

    # sort the `destination` rule format
    if 'any' in rule['destination']:
        daddr = ''
    elif len(rule['destination']) == 1 and '@' in rule['destination'][0]:
        daddr = f'ip{v} daddr {rule["destination"][0]}'
    else:
        daddr = f'ip{v} daddr ' + '{ ' + ', '.join(rule['destination']) + ' }'

    # sort the `source` rule format
    if 'any' in rule['source']:
        saddr = ''
    elif len(rule['source']) == 1 and '@' in rule['source'][0]:
        saddr = f'ip{v} saddr {rule["source"][0]}'
    else:
        saddr = f'ip{v} saddr ' + '{ ' + ', '.join(rule['source']) + ' }'

    # sort the `port` rule format
    if rule['protocol'] == 'any':
        dport = ''
    elif len(rule['port']) == 1 and '@' in rule['port'][0]:
        dport = f'dport {rule["port"][0]}'
    else:
        dport = 'dport ' + '{ ' + ', '.join(rule['port']) + ' }'

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
    log = f'log prefix "Namespace_{namespace}_Table_{table}" level debug' if rule['log'] is True else ''

    return f'{iif} {oif} {saddr} {daddr} {log} {proto_port}', application


def dnat_rule(nat):
    rule_line = f'iifname "{nat["iface"]}" ' if nat['iface'] is not None else ''
    rule_line = f'{rule_line}ip daddr {nat["public"]} dnat to {nat["private"]} '
    return rule_line


def snat_rule(nat):
    rule_line = f'oifname "{nat["iface"]}" ' if nat['iface'] is not None else ''
    rule_line = f'{rule_line}ip saddr {nat["private"]} snat to {nat["public"]} '
    return rule_line


def build(
        namespace: str,
        table: str,
        priority: int,
        config_file=None,
        nats=None,
        rules=None,
        sets=None,
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
                        description: |
                            - list of ipaddresses (all must be either private or public but not mixed)
                               OR
                            - set can be used but only one set in source list is allowed and a set should start with `@`
                              sign before the set name ie for set['name'] = 'us_ipv4' then the source = ['@us_ipv4'],
                              if a set is used in source or destination of a rule then a set for
                              the same name must be supplied in sets.
                              OR
                            - `any` can be used to mention for all the IPAddresses
                               if used then only `any` should be in the list ie source = ['any'].
                        type: array
                        items:
                            type: string
                        required: true
                    destination:
                        description: |
                            - list of ipaddresses (all must be either private or public but not mixed)
                               OR
                            - a set can be used but only one set in destination list is allowed and a set should start
                              with `@` sign before the set name ie for set['name'] = 'us_ipv4' then the
                              destination = ['@us_ipv4'], if a set is used in source or destination of a rule then
                              a set for the same name must be supplied in sets.
                              OR
                            - `any` can be used to mention for all the IPAddresses
                               if used then only `any` should be in the list ie source = ['any'].
                        type: array
                        items:
                            type: string
                        required: true
                    protocol:
                        description: name of the protocol, e.g `tcp`, `udp`, `icmp` or `any`
                        type: string
                        required: true
                    port:
                        description: |
                            - list of ports, a port is a number in range [0, 65535], should be mentioned in
                              string format ie port = ['3', '22', '45-600']
                              OR
                            - `*` can be used to specify any port ie port = ['*']
                              OR
                            - An empty list can be used when protocol is `any` ie port = [] if protocol = 'any'
                              OR
                            - a set can be used but only one set in port list is allowed and a set should start
                              with `@` sign before the set name ie for set['name'] = 'myports' then the
                              port = ['@myports'], if a set is used in port of a rule then
                              a set for the same name must be supplied in sets.
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
                            'iface': 'VRF123.BM45'
                        },
                    ]
                    'snats': [
                        {
                            'public': '91.103.3.1',
                            'private': '192.168.0.1/24',
                            'iface': 'VRF123.BM45'
                        },
                    ]
                }
            required: false
            type: array
            items:
                type: dict
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
                                iface:
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
                                iface:
                                    description: |
                                        the output interface, exit point of a traffic from the network namespace
                                        e.g 'VRF123.BM90'
                                    type: string
                                    required: true
                        required: false
        sets:
            description: |
                List of objects, each defined for a collection of elements
                (such as IP addresses, network ranges, ports, or other data types)
                that can be used to group similar items together for easier management within rules.
                sets = [
                    {
                        'name': 'ie_ipv4',
                        'type': 'ipv4_addr',
                        'elements': ['91.103.0.1/24',],
                    },
                ]
            required: false
            type: array
            items:
                type: dict
                properties:
                    name:
                        description: unique name within the table to identify the set and to call the set in rules
                        required: true
                        type: string
                    type:
                        description: |
                            To define the nature of the set elements
                             - `ipv4_addr`: IP addresses and or IP address ranges of version 4
                             - `ipv6_addr`: IP addresses and or IP address ranges of version 6
                             - `inet_service`: Port Numbers
                             - `ether_addr` : Mac Addresses
                        required: true
                        type: string
                    elements:
                        description: The list of items of the same type
                        required: true
                        type: array
                        items:
                            type: string
                            required: true

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
        3000: f'3000: Failed to create nftables {table} in namespace {namespace}',
        # Validating params
        2020: f'2020: All the supplied parameters are validated.',
        3020: f'3020: Errors occurred in validating supplied parameters.',
        3021: f'3021: Failed to validate Sets. One or more sets have same names. Name must be unique in the Sets',
        3022: f'3022: Failed to validate Sets. Errors occurred while validating sets. Errors: ',
        3023: f'3023: Failed to validate Rules. One or more rules have invalid values. Errors: ',
        3024: f'3024: Failed to validate Rules. Sets used in rules are not found in supplied Sets. Errors: ',
        3025: f'3025: Failed to validate NATs. One or more NATs are invalid. Errors: ',
        3030: f'3030: One of the rule is Invalid, Both `iiface` and `oiface` cannot be None in a rule object',
        3040: f'3040: Failed to verify nftables.conf.j2 template data, One or more template fields are None',
        # Enabled PodNet
        3051: f'3051: Failed to connect to the Enabled PodNet for payload create_nftables_file',
        3052: f'3052: Failed to create nftables file {nftables_file} on the Enabled PodNet',
        3053: f'3053: Failed to connect to the Enabled PodNet for payload validate_nftables_file',
        3054: f'3054: Failed to validate nftables file {nftables_file} on the Enabled PodNet',
        3055: f'3055: Failed to connect to the Enabled PodNet for payload read_table',
        3056: f'3056: Failed to read table {table} on the Enabled PodNet',
        3057: f'3057: Failed to connect to the Enabled PodNet for payload flush_table',
        3058: f'3058: Failed to flush table {table} on the Enabled PodNet',
        3059: f'3059: Failed to connect to the Enabled PodNet for payload apply_nftables_file',
        3060: f'3060: Failed to apply nftables file {nftables_file} on the Enabled PodNet',
        3061: f'3061: Failed to connect to the Enabled PodNet for payload remove_nftables_file',
        3062: f'3062: Failed to remove nftables file {nftables_file} on the Enabled PodNet',
        # Disable PodNet
        3071: f'3071: Failed to connect to the Disabled PodNet for payload create_nftables_file',
        3072: f'3072: Failed to create nftables file {nftables_file} on the Disabled PodNet',
        3073: f'3073: Failed to connect to the Disabled PodNet for payload validate_nftables_file',
        3074: f'3074: Failed to validate nftables file {nftables_file} on the Disabled PodNet',
        3075: f'3075: Failed to connect to the Disabled PodNet for payload read_table',
        3076: f'3076: Failed to read table {table} on the Disabled PodNet',
        3077: f'3077: Failed to connect to the Disabled PodNet for payload flush_table',
        3078: f'3078: Failed to flush table {table} on the Disabled PodNet',
        3079: f'3079: Failed to connect to the Disabled PodNet for payload apply_nftables_file',
        3080: f'3080: Failed to apply nftables file {nftables_file} on the Disabled PodNet',
        3081: f'3081: Failed to connect to the Disabled PodNet for payload remove_nftables_file',
        3082: f'3082: Failed to apply nftables file {nftables_file} on the Disabled PodNet',
    }

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            msg += "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'], indent=2, sort_keys=True)
            return False, msg
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    # Block 02: Validate sets and rules
    validated = True
    messages_list = []
    set_names = []
    # validate sets
    # 1. Same Set names are not allowed
    # 2. Validate fields of Set object
    if sets:
        valid_sets = True
        # first make sure set names are unique in the list
        set_names.extend([obj['name'] for obj in sets])
        if len(sets) != len(list(set(set_names))):
            valid_sets = False
            messages_list.append(messages[3021])
        errors = []
        for obj in sets:
            controller = FirewallSet(obj)
            success, errs = controller()
            if success is False:
                valid_sets = False
                errors.extend(errs)
        if valid_sets is False:
            validated = False
            messages_list.append(f'{messages[3022]} {";".join(errors)}')

    # validate rules
    if rules:
        errors = []
        valid_rules = True
        for rule in rules:
            controller = FirewallNamespace(rule)
            success, errs = controller()
            if success is False:
                valid_rules = False
                errors.extend(errs)
        if valid_rules is False:
            validated = False
            messages_list.append(f'{messages[3023]} {";".join(errors)}')

        # check if the rule has any sets in source, destination or ports,
        # if so then check that set is defined in sets
        errors = []
        valid_set_elements = True
        for rule in rules:
            rule_sets = []
            # collect the sets from the rules that starts with `@`
            if type(rule['source']) is list:
                rule_sets.extend([item.strip('@') for item in rule['source'] if '@' in item])
            if type(rule['destination']) is list:
                rule_sets.extend([item.strip('@') for item in rule['destination'] if '@' in item])
            if type(rule['port']) is list:
                rule_sets.extend([item.strip('@') for item in rule['port'] if '@' in item])
            # now check if each rule_set is supplied in sets(set_names)
            for rule_set in rule_sets:
                if rule_set not in set_names:
                    valid_set_elements = False
                    errors.append(f'{rule_set} not found in the supplied sets')
        if valid_set_elements is False:
            validated = False
            messages_list.append(f'{messages[3024]} {";".join(errors)}')

    # validate nats
    if nats:
        errors = []
        valid_nats = True
        nats_list = nats['dnats'] + nats['snats']
        for nat in nats_list:
            controller = FirewallNAT(nat)
            success, errs = controller()
            if success is False:
                valid_nats = False
                errors.extend(errs)
        if valid_nats is False:
            validated = False
            messages_list.append(f'{messages[3025]} {";".join(errors)}')

    if validated is False:
        return False, f'{messages[3020]} {"; ".join(messages_list)}'

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
        'sets': sets,
        'table': table,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template('firewallns/nftables.conf.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, messages[3040]

    # Generate Firewall build config
    nftables_config = template.render(**template_data)

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        table_grepsafe = table.replace('.', '\\.')
        payloads = {
            'create_nftables_file': f'echo "{nftables_config}" > {nftables_file}',
            'validate_nftables_file': f'ip netns exec {namespace} nft --check --file {nftables_file}',
            'read_table': f'ip netns exec {namespace} nft list tables | grep --word "inet {table_grepsafe} "',
            'flush_table': f'ip netns exec {namespace} nft delete table inet {table} ',
            'apply_nftables_file': f'ip netns exec {namespace} nft --file {nftables_file}',
            'remove_nftables_file': f'rm --force {nftables_file}',
        }

        ret = rcc.run(payloads['create_nftables_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        fmt.add_successful('create_nftables_file', ret)

        ret = rcc.run(payloads['validate_nftables_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 4]), fmt.successful_payloads
        fmt.add_successful('validate_nftables_file', ret)

        ret = rcc.run(payloads['read_table'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 5]), fmt.successful_payloads
        flush_table = False
        if ret["payload_code"] == SUCCESS_CODE:
            # Need to delete this table if it exists already
            flush_table = True
        fmt.add_successful('read_table', ret)

        if flush_table:
            ret = rcc.run(payloads['flush_table'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix + 7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, messages[prefix + 8]), fmt.successful_payloads
            fmt.add_successful('flush_table', ret)

        ret = rcc.run(payloads['apply_nftables_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 9]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 10]), fmt.successful_payloads
        fmt.add_successful('apply_nftables_file', ret)

        ret = rcc.run(payloads['remove_nftables_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 11]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 12]), fmt.successful_payloads
        fmt.add_successful('remove_nftables_file', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3050, {})
    if status is False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3060, successful_payloads)
    if status is False:
        return status, msg

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
        1100: f'1100: Successfully removed nftables {table} in namespace {namespace}',
        3100: f'3100: Failed to remove nftables table {table} in namespace {namespace}',
        3121: f'3121: Failed to connect to the Enabled PodNet for payload read_table',
        3122: f'3122: Failed to read table {table} on the Enabled PodNet',
        3123: f'3123: Failed to connect to the Enabled PodNet for payload flush_table',
        3124: f'3124: Failed to flush table {table} on the Enabled PodNet',
        3131: f'3131: Failed to connect to the Disabled PodNet for payload read_table',
        3132: f'3132: Failed to read table {table} on the Disabled PodNet',
        3133: f'3133: Failed to connect to the Disabled PodNet for payload flush_table',
        3134: f'3134: Failed to flush table {table} on the Disabled PodNet',
    }

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            msg += "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'], indent=2, sort_keys=True)
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

        table_grepsafe = table.replace('.', '\\.')
        payloads = {
            'read_table': f'ip netns exec {namespace} nft list tables | grep --word "inet {table_grepsafe}"',
            'flush_table': f'ip netns exec {namespace} nft delete table inet {table} ',
        }

        ret = rcc.run(payloads['read_table'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        flush_table = False
        if ret["payload_code"] == SUCCESS_CODE:
            # Need to delete this table if it exists already
            flush_table = True
        fmt.add_successful('read_table', ret)

        if flush_table:
            ret = rcc.run(payloads['flush_table'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
            fmt.add_successful('flush_table', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status is False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3130, successful_payloads)
    if status is False:
        return status, msg

    return True, messages[1100]


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
        1200: f'1200: Successfully read nftables {table} in namespace {namespace}',
        3200: f'3200: Failed to read nftables {table} in namespace {namespace}',
        3221: f'3221: Failed to connect to the Enabled PodNet for payload read_table',
        3222: f'3222: Failed to read table {table} from the Enabled PodNet',
        3231: f'3231: Failed to connect to the Disabled PodNet for payload read_table',
        3232: f'3232: Failed to read table {table} from the Disabled PodNet',
    }

    # set the outputs
    data_dict = {}
    message_list = []

    # Block 01: Get the PodNets IPs
    # set default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    status, config_data, msg = load_pod_config(config_file)
    message_list.append(msg)
    if not status:
        if config_data['raw'] is None:
            return False, data_dict, message_list
        else:
            msg += "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'], indent=2, sort_keys=True)
            message_list.append(msg)
            return False, data_dict, message_list
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[podnet_node] = {}

        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_table': f'ip netns exec {namespace} nft list table inet {table} ',
        }

        ret = rcc.run(payloads['read_table'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        else:
            data_dict[podnet_node]['read_table'] = ret["payload_message"].strip()
            fmt.add_successful('read_table', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_a, msg_list, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})
    message_list.extend(msg_list)

    retval_b, msg_list, successful_payloads, data_dict = run_podnet(disabled, 3230, successful_payloads, data_dict)
    message_list.extend(msg_list)

    if not (retval_a and retval_b):
        return (retval_a and retval_b), data_dict, message_list
    else:
        return True, data_dict, [messages[1200]]
