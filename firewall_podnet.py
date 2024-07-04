"""
Primitive of Nftable based Main Firewall for PodNet
"""
# stdlib
import logging
from collections import deque
from typing import Tuple
# lib
from cloudcix.rcc import deploy_lsh, CouldNotExecuteException
# local
from .controllers import FirewallPodNet
from .utils import JINJA_ENV, check_template_data

__all__ = [
    'build',
]

BUILD_TEMPLATE = 'firewall_podnet/commands/build.sh.j2'
LOGGER = 'primitives.firewall_podnet'


def complete_rule(rule, iiface, oiface, log_setup):
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

    # rule protocol and port statement
    if rule['protocol'] == 'any':
        proto_port = f'{rule["action"]}'
    elif rule['protocol'] == 'icmp':
        proto_port = f'jump icmp{v}_{rule["action"]}'
    elif rule['protocol'] == 'dns':
        proto_port = f'jump dns_{rule["action"]}'
    elif rule['protocol'] == 'vpn':
        proto_port = f'jump vpn_{rule["action"]}'
    else:
        proto_port = f'{rule["protocol"]} {dport} {rule["action"]}'

    # log
    log = f'log prefix "{str(log_setup["prefix"])}" group {str(log_setup["group"])}' if rule['log'] is True else ''

    return f'{iif} {oif} {saddr} {daddr} {log} {proto_port}'


def build(
        firewall_rules=None,
        log_setup=None,
) -> Tuple[bool, str]:
    """
    description:
        - Creates a /tmp/nftables.conf file with new config
        - Validates the nft file `sudo nft -c -f /tmp/nftables.conf`
        - If any errors then exits with errors
        - Move the file to /etc/nftables/nftables.conf

    parameters:
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
                    'iiface': 'public0',
                    'oiface': 'mgmt0',
                    'order': 0,
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
                iiface:
                    description: the input interface, entry point of a traffic in the network host
                    type: string
                oiface:
                    description: the output interface, exit point of a traffic in the network host
                    type: string
            required: False
        log_setup:
            description: |
                logging setup and location
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
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    output = ''
    success = False

    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for firewall_podnet.build')

    # rule log setup
    log_setup = {'prefix': 'Rule', 'level': 1, 'group': 1} if log_setup is None else log_setup

    # messages
    fail_start = f'Failed to apply Firewall config for PodNet.'
    messages = {
        '000': f'Successfully applied Firewall config for PodNet',
        '100': f'Configuration file /tmp/nftables.conf is valid. Applying the Firewall',
        '300': f'{fail_start} Configuration file /tmp/nftables.nft Not found.',
        '301': f'{fail_start} Configuration file /tmp/nftables.nft syntax is invalid. Exiting.',
        '302': f'{fail_start} Unexpected error occurred while applying the Firewall.',
        '303': f'Failed to replace /etc/nftables.conf with /tmp/nftables.conf.',
    }

    # validate the rules
    proceed, errors = True, []
    for rule in firewall_rules:
        validated = FirewallPodNet(rule)
        success, errs = validated()
        if success is False:
            proceed = False
            errors.extend(errs)

    if proceed is False:
        return False, f'Errors: {"; ".join(errors)}'

    # Prepare Firewall rules
    inbound_rules = deque()
    outbound_rules = deque()
    forward_rules = deque()
    for rule in sorted(firewall_rules, key=lambda fw: fw['order']):
        # sort traffic direction ie inbound, outbound and forward
        iiface = rule['iiface'] if rule['iiface'] not in [None, '', 'none'] else None
        oiface = rule['oiface'] if rule['oiface'] not in [None, '', 'none'] else None
        if iiface is not None and oiface is None:
            inbound_rules.append(complete_rule(rule, iiface, None, log_setup))
        elif iiface is None and oiface is not None:
            outbound_rules.append(complete_rule(rule, None, oiface, log_setup))
        elif iiface is not None and oiface is not None:
            forward_rules.append(complete_rule(rule, iiface, oiface, log_setup))

    # template data
    template_data = {
        'log_setup': log_setup,
        'inbound_rules': inbound_rules,
        'forward_rules': forward_rules,
        'outbound_rules': outbound_rules,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate PodNet Firewall build template. {template_error}')
        return False, template_error

    # Generate Firewall build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated PodNet Firewall build bash script#\n{bash_script}')

    # Deploy the bash script to the Host
    try:
        stdout, stderr = deploy_lsh(
            payload=bash_script,
        )
    except CouldNotExecuteException as e:
        return False, str(e)

    if stdout:
        logger.debug(f'Firewall rules for PodNet build commands generated stdout.\n{stdout}')
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True
    if stderr:
        logger.error(f'Firewall rules for PodNet build commands generated stderr.\n{stderr}')
        output += stderr

    return success, output
