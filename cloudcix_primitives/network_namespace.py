"""
Primitive for Namespace Network on PodNet
"""
# stdlib
import logging
from typing import Tuple
# lib
from cloudcix.rcc import deploy_ssh, CouldNotConnectException
# local
import cloudcix_primitives.utils

__all__ = [
    'build',
    'scrub',
]


BUILD_TEMPLATE = 'network_namespace/commands/build.sh.j2'
SCRUB_TEMPLATE = 'network_namespace/commands/scrub.sh.j2'
LOGGER = 'primitives.network_namespace'


def build(
        namespace_identifier: str,
        bridge_podnet_identifier=None,
        bridge6_podnet_identifier=None,
        config_filepath=None,
        ip=None,
        ip6=None,
        namespace_networks=None,
) -> Tuple[bool, str]:
    """
    description:
        Build a Linux Network Namespace from the given data.

    parameters:
        namespace_identifier:
            description: The Identifier of the Network Namespace on the host .
            type: string
        bridge_podnet_identifier:
            description: string to identify the Public Bridge that this namespace is connected to.
            required: False
            type: string
        bridge6_podnet_identifier:
            description: string to identify the IPv6 Bridge that this namespace is connected to.
            required: False
            type: string
        config_filepath:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: False
            type: string
        ip:
            description: |
                Public IPv4 address for the network namespace
                ip = {
                    'addresses': ['91.103.3.36', '91.103.3.39'],
                    'mask': 24,
                    'gateway': '91.103.3.1',
                }
            required: False
            type: object
            properties:
                addresses:
                    description: Public network ipv4 addresses
                    type: list for strings
                mask:
                    description: Public subnet mask
                    type: integer
                gateway:
                    description: Public subnet gateway
                    type: string
        ip6:
            description: |
                IPv6 Link address for the network namespace
                ip6 = {
                    'addresses': ['2a02:2078:9:fff0::2', '2a02:2078:9:fff0::3' ],
                    'mask': 64,
                    'gateway': '2a02:2078:9:fff0::1',
                }
            required: False
            type: object
            properties:
                addresses:
                    description: Public network address
                    type: list for strings
                mask:
                    description: Public subnet mask
                    type: integer
                gateway:
                    description: Public subnet gateway
                    type: string

        namespace_networks:
            description: |
                A list of the Namespace network objects
                namespace_networks = [
                    {
                        'vlan': '1001',
                        'private_address_range': '192.168.0.1/24',
                        'ip6_address_range': '2a02:2078:9:1003::1/64'
                    },
                ]
            type: list of objects
            properties:
                vlan:
                    description: vlan number of the network
                    type: string
                private_address_range:
                    description: ipv4 private subnet_ip/subnet_mask
                    type: integer
                ip6_address_range:
                    description: ipv6 subnet_ip/subnet_mask
                    type: string
            required: False

    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple

    Note: It requires following hardware data from config_file
        podnets = [{
            'mgmt': {'ip': '', 'ifname': '',},
            'private': {'ip': '', 'ifname': '',},
        },]
    """
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for network_namespace.build')

    # hardware data and naming
    if config_filepath is None:
        config_filepath = f'{utils.primitives_directory}/config.json'
    podnets = utils.get_podnets(config_filepath)

    total_success = []
    total_output = ''
    for podnet in podnets:
        host_ip = utils.get_mgmt_ipv6(podnet['mgmt']['ip'])
        success, output = _build(
            host_ip,
            bridge_podnet_identifier,
            bridge6_podnet_identifier,
            ip,
            ip6,
            namespace_identifier,
            namespace_networks,
            podnet['private']['ifname'],
        )
        total_success.append(success)
        total_output += total_output
    return any(total_success), total_output


def _build(
        host_ip,
        bridge_podnet_identifier,
        bridge6_podnet_identifier,
        ip,
        ip6,
        namespace_identifier,
        namespace_networks,
        private_ifname,
):
    output = ''
    success = False
    logger = logging.getLogger(f'{LOGGER}._build')

    messages = {
        '000': f'SUCCESS: Successfully created Namespace #{namespace_identifier}',
    }

    template_data = {
        'bridge_identifier': bridge_podnet_identifier,
        'bridge6_identifier': bridge6_podnet_identifier,
        'ip4': ip,
        'ip6': ip6,
        'messages': messages,
        'namespace_identifier': namespace_identifier,
        'namespace_networks': namespace_networks,
        'private_ifname': private_ifname,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = utils.JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = utils.check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate PodNet Namespace network build template for namespace#{namespace_identifier}.'
            f'\n{template_error}',
        )
        return False, template_error

    # Prepare namespace build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated build bash script for Namespace #{namespace_identifier}\n{bash_script}',
    )

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
            f'Namespace Network for namespace #{namespace_identifier} on #{host_ip} build commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True
    if stderr:
        logger.error(
            f'Namespace Network for namespace #{namespace_identifier} on #{host_ip} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output


def scrub(
        namespace_identifier: str,
        config_filepath=None,
) -> Tuple[bool, str]:
    """
    description:
        Deleting namespace for the given data.

    parameters:
        namespace_identifier:
            description: Resource Identifier on the host .
            type: string
        config_filepath:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
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

    logger = logging.getLogger(f'{LOGGER}.scrub')
    logger.debug('Compiling data for network_namespace.scrub')

    # hardware data and naming
    if config_filepath is None:
        config_filepath = f'{utils.primitives_directory}/config.json'
    podnets = utils.get_podnets(config_filepath)

    total_success = []
    total_output = ''
    for podnet in podnets:
        host_ip = utils.get_mgmt_ipv6(podnet['mgmt']['ip'])
        success, output = _scrub(
            host_ip,
            namespace_identifier,
        )
        total_success.append(success)
        total_output += total_output
    return any(total_success), total_output


def _scrub(
        host_ip,
        namespace_identifier,
):
    output = ''
    success = False
    logger = logging.getLogger(f'{LOGGER}._scrub')

    messages = {
        '000': f'SUCCESS: Successfully deleted Namespace #{namespace_identifier}',
    }

    template_data = {
        'messages': messages,
        'namespace_identifier': namespace_identifier,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = utils.JINJA_ENV.get_template(SCRUB_TEMPLATE)
    template_verified, template_error = utils.check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate PodNet Namespace network Scrub template for namespace#{namespace_identifier}.'
            f'\n{template_error}',
        )
        return False, template_error

    # Prepare namespace delete config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated scrub bash script for Namespace #{namespace_identifier}\n{bash_script}',
    )

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
            f'Namespace Network for namespace #{namespace_identifier} on #{host_ip} scrub commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True
    if stderr:
        logger.error(
            f'Namespace Network for namespace #{namespace_identifier} on #{host_ip} scrub commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
