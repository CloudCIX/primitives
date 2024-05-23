"""
Primitive for Namespace NFtable Firewall on PodNet
"""
# stdlib
import logging
from collections import deque
from typing import Deque, List, Tuple
# lib
from cloudcix.rcc import deploy_ssh, CouldNotConnectException
# local
import exceptions
import utils

__all__ = [
    'build_overwrite',
]

BUILD_TEMPLATE = 'firewall_namespace/commands/build.sh.j2'
LOGGER = 'primitives.firewall_namespace'


def dnat_rule(nat, ifname):
    rule_line = f'iifname "{ifname}" ' if ifname is not None else ''
    rule_line = f'{rule_line}ip daddr { {nat["daddr"]} } dnat to {nat["dnat"]} '
    return rule_line


def snat_rule(nat, ifname):
    rule_line = f'oifname "{ifname}" ' if ifname is not None else ''
    rule_line = f'{rule_line}ip saddr { {nat["saddr"]} } snat to {nat["snat"]} '
    return rule_line


def icmp():
    return f'icmp type {{ destination-unreachable, echo-reply, echo-request, time-exceeded }} '


def icmp6():
    return f'icmpv6 type {{ echo-request, mld-listener-query, nd-router-solicit, nd-router-advert, ' \
           f'nd-neighbor-solicit, nd-neighbor-advert }} '


def protocol_line(rule, version):
    if rule['protocol'] == 'any':
        rule_line = ''
    elif rule['protocol'] == 'icmp':
        rule_line = f'{icmp()}' if version == '4' else f'{icmp6()}'
    else:
        rule_line = f'{rule["protocol"]} dport { {",".join(rule["port"])} }'
    return rule_line


def complete_rule(rule, ifname, ifname6, log):
    io = 'i' if 'inbound' in rule['type'] else 'o'
    rule_line = ''
    if rule['version'] == '4':
        # interface line
        rule_line += f'{io}ifname "{ifname}" ' if ifname is not None else ''
        # source and destination
        rule_line += f'ip saddr { {",".join(rule["source"])} } ip daddr { {",".join(rule["destination"])} } '
        # protocal and port
        rule_line += f'{protocol_line(rule["protocol"], "4")} '
        # log
        rule_line += f'log group {log["group"]} ' if rule['log'] else ''
        # action
        rule_line += f'{rule["action"]}'
    else:
        # interface line
        rule_line += f'{io}ifname "{ifname6}" ' if ifname6 is not None else ''
        # source and destination
        rule_line += f'ip6 saddr { {",".join(rule["source"])} } ip6 daddr { {",".join(rule["destination"])} } '
        # protocal and port
        rule_line += f'{protocol_line(rule["protocol"], "6")} '
        # log
        rule_line += f'log group {log["group"]}' if rule['log'] else ''
        # action
        rule_line += f'{rule["action"]}'
    return rule_line


def build_overwrite(
        namespace_identifier: str,
        config_filepath=None,
        firewall_rules=None,
        log=None,
        nat=None,
        namespace_pubif=None,
        namespace_pubif6=None,
) -> Tuple[bool, str]:
    """
    description:
        - Creates a /tmp/<namespace_identifier>.conf file with new config
        - Validates the nft file `sudo nft -c -f /tmp/<namespace_identifier>.conf`
        - If any errors then exits with errors
        - Config is applied `sudo ip netns exec <namespace_identifier> --file /tmp/<namespace_identifier>.conf`
        - Temp file is removed from /tmp/

    parameters:
        namespace_identifier:
            description: Resource Identifier on the host .
            type: string
        config_filepath:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: False
            type: string
        firewall_rules:
            description: |
                containing firewall rules in the following format
                rule = {
                    'version': '4',
                    'source': [],
                    'destination': [],
                    'protocol': 'tcp',
                    'port': ['22'],
                    'action': 'accept',
                    'log': False,
                    'type': 'inbound'
                }
            type: object
            properties:
                version:
                    description: version of IP ie 4 or 6
                    type: string
                source:
                    description: list of source ipaddresses (all must be either private or public but not mixed)
                    type: list of strings
                destination:
                    description: list of destination ipaddresses (all must be either private or public but not mixed)
                    type: list of strings
                protocol:
                    description: name of the protocol, e.g `tcp`, `udp`, `icmp` or `any`
                    type: string
                port:
                    description: list of ports, a port is a number in range [0, 65535] and `*`(any)
                    type: string
                action:
                    description: can take either `accept` or `drop`
                    type: string
                log:
                    description: to log the rule, this has to be True otherwise False
                    type: boolean
                type:
                    description: class of rule such as 'inbound', 'outbound', 'inbound_forward' and 'outbound_forward'
                    type: string
            required: False
        log:
            description: |
                logging setup
                log = {
                    'prefix': 'Region #1123 Project #234:',
                    'level': 1,
                    'group: 1,
                }
            type: object
            properties:
                prefix:
                    description: Name of the log identifier
                    type: string
                level:
                    description: logging levels, such as debug(1), info(3), notice(5), error(7) or fatal(8) (default 5)
                    type: int
                group:
                    description: helps identify the netlink group to which the log messages are sent
                    type: int
            required: False
        nat:
            description: |
                List of NATs object with Private IP and its Public IP or defaulted to None
                nat = {
                    'dnats': [{'daddr': '91.103.3.36', 'dnat': '192.168.0.2'},]
                    'snats': [{'saddr': '192.168.0.1/24', 'snat': '91.103.3.1'},]
                }
            required: False
            type: optional, List of strings or None
            properties:
                dnats:
                    description: list of dnat pairs
                    type: list of objects
                    properties:
                        daddr:
                            description: destination address, it should be a Public IP
                            type: string
                        dnat:
                            description: destination nat address, it should be a Private IP
                            type: string
                snats:
                    description: list of snat pairs
                    type: list of objects
                    properties:
                        saddr:
                            description: source address, it should be a Private address or address range
                            type: string
                        snat:
                            description: destination nat address, it should be a Public IP
                            type: string
        namespace_pubif:
            description: |
                string to identify the Namespace interface connected to IPv4 Public Bridge.
                e.g `P123.B345`
            required: False
            type: string
        namespace_pubif6:
            description: |
                string to identify the Namespace interface connected to IPv6 Public Bridge.
                e.g `P123.B345`
            required: False
            type: string

    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple

    Note: It requires following hardware data from config_file
        podnets = [{
            'mgmt': {'ip': '', 'ifname': '',},
        },]
    """
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for firewall_namespace.build_overwrite')

    # hardware data
    if config_filepath is None:
        config_filepath = f'{utils.primitives_directory}/config.json'
    podnets = utils.get_podnets(config_filepath)

    # nat rules
    dnat_rules: List[str] = []
    snat_rules: List[str] = []
    if nat is not None:
        dnats = nat.get('dnats', [])
        snats = nat.get('snats', [])
        for obj in dnats:
            dnat_rules.append(dnat_rule(obj, namespace_pubif))
        for obj in snats:
            snat_rules.append(snat_rule(obj, namespace_pubif))

    # rule log setup
    log = {'prefix': 'Rule:', 'level': 1, 'group': 1} if log is None else log

    # messages
    fail_start = f'Failed to apply Firewall config for namespace {namespace_identifier}.'
    messages = {
        '000': f'Successfully applied Firewall config for namespace {namespace_identifier}',
        '100': f'Configuration file /tmp/{namespace_identifier}.nft is valid. Applying the Firewall',
        '300': f'{fail_start} Configuration file /tmp/{namespace_identifier}.nft Not found.',
        '301': f'{fail_start} Configuration file /tmp/{namespace_identifier}.nft syntax is invalid. Exiting.',
        '302': f'{fail_start} Unexpected error occurred while applying the Firewall.',
    }

    # Firewall rules
    inbound_rules: Deque[str] = deque()
    outbound_rules: Deque[str] = deque()
    inbound_forward_rules: Deque[str] = deque()
    outbound_forward_rules: Deque[str] = deque()
    for rule in sorted(firewall_rules, key=lambda fw: fw['order']):
        # type sorting
        if rule['type'] == 'inbound':
            inbound_rules.append(complete_rule(rule, namespace_pubif, namespace_pubif6, log))
        elif rule['type'] == 'outbound':
            outbound_rules.append(complete_rule(rule, namespace_pubif, namespace_pubif6, log))
        elif rule['type'] == 'inbound_forward':
            inbound_forward_rules.append(complete_rule(rule, namespace_pubif, namespace_pubif6, log))
        elif rule['type'] == 'outbound_forward':
            outbound_forward_rules.append(complete_rule(rule, namespace_pubif, namespace_pubif6, log))
        else:
            raise exceptions.InvalidFirewallRuleType

    # template data
    template_data = {
        'log': log,
        'dnat_rules': dnat_rules,
        'snat_rules': snat_rules,
        'inbound_rules': inbound_rules,
        'inbound_forward_rules': inbound_forward_rules,
        'outbound_forward_rules': outbound_forward_rules,
        'outbound_rules': outbound_rules,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = utils.JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = utils.check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate PodNet Namespace Firewall build template. {template_error}')
        return False, template_error

    # Generate Firewall build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated Firewall build bash script for Namespace #{namespace_identifier}\n{bash_script}',
    )

    total_success = []
    total_output = ''
    for podnet in podnets:
        host_ip = utils.get_mgmt_ipv6(podnet['mgmt'])
        success, output = _build(
            host_ip,
            bash_script,
            messages,
            namespace_identifier,
        )
        total_success.append(success)
        total_output += total_output
    return any(total_success), total_output


def _build(
        host_ip,
        bash_script,
        messages,
        namespace_identifier,
):
    output = ''
    success = False
    logger = logging.getLogger(f'{LOGGER}._build')

    # Deploy the bash script to the Host
    try:
        stdout, stderr = deploy_ssh(
            host_ip=host_ip,
            payload=bash_script,
            username='robot',
        )
    except CouldNotConnectException as e:
        return False, str(e)

    if stdout:
        logger.debug(
            f'PodNet Firewall rules for Namespace #{namespace_identifier} on #{host_ip} '
            f'build commands generated stdout.\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True
    if stderr:
        logger.error(
            f'Firewall rules for Namespace #{namespace_identifier} on #{host_ip} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
