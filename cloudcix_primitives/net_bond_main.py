"""
Primitive for Global Network (Netplan interface config) on PodNet
"""
# stdlib
import logging
from typing import Tuple
# lib
from cloudcix.rcc import comms_lsh, comms_ssh, CHANNEL_SUCCESS, CONNECTION_ERROR
# local
from cloudcix_primitives.utils import JINJA_ENV, check_template_data


__all__ = [
    'build',
]

BUILD_TEMPLATE = 'net_bond_main/commands/build.sh.j2'
LOGGER = 'primitives.net_bond_main'

SUCCESS_CODE = 0

def build(
        host: str,
        filename: str,
        standard_name: str,
        config_filepath=None,
        routes=None,
        interfaces: list[str] = None,
        parameters: dict = None,
        addresses: list[str] = None,
        dhcp4: bool = False,
        dhcp6: bool = False,
        accept_ra: bool = False,
) -> Tuple[bool, str]:
    """
    description:
        1. Backups if /etc/netplan/<filename>.yaml exists
        2. Creates /etc/netplan/<filename>.yaml
        3. Verifies the changes(netplan generate), if failed then reverts the changes and exits
        4. Applies the changes(netplan apply)
        5. Removes the Backup file
    parameters:
        host:
            description: IP or dns name of the host where the interface is created on.
            type: string
            required: True
        filename:
            description: Name of the file to be created in /etc/netplan/ dir
            type: str
            required: True
        standard_name:
            description: The interface's custom/standard name on the machine.
            type: string
            required: True
        config_filepath:
            description: |
                Path to the configuration file containing network settings.
                If not provided, defaults to '/etc/cloudcix/pod/configs/config.json'.
            type: str
            required: False
        routes:
            description: List of routes to be configured for the interface.
            type: list[str]
            required: False
        interfaces:
            description: List of interfaces to be bonded.
            type: list[str]
            required: True
        parameters:
            description: Dictionary of additional parameters for the bond configuration.
            type: dict
            required: False
        addresses:
            description: List of IP addresses to be assigned to the bond interface.
            type: list[str]
            required: False
        dhcp4:
            description: Whether to enable DHCP for IPv4 on the bond interface.
            type: bool
            required: False
            default: False
        dhcp6:
            description: Whether to enable DHCP for IPv6 on the bond interface.
            type: bool
            required: False
        accept_ra:
            description: Whether to accept Router Advertisements for the bond interface.
            type: bool
            required: False    
    returns:
        Tuple[bool, str]: A tuple containing a success flag and a message.
    raises:
        ValueError: If required parameters are missing or invalid.
        ConnectionError: If there is an issue with the connection to the host.
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for net_bond_main.build')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # netplan file
    netplan_filepath = f'/etc/netplan/{filename}.yaml'

    # messages
    messages = {
        '000': f'Successfully built bonded interface #{standard_name} on {host}',
        '300': f'Failed to backup {netplan_filepath} to {netplan_filepath}.bak',
        '301': f'Failed to build bonded interface #{standard_name} on {host}',
        '302': f'Failed to Generate netplan config.',
        '303': f'Failed to Apply netplan config.',
    }

    template_data = {
        'host': host,
        'standard_name': standard_name,
        'config_filepath': config_filepath,
        'netplan_filepath': netplan_filepath,
        'messages': messages,
        'routes': routes or [],
        'interfaces': interfaces or [],
        'parameters': parameters or {},
        'addresses': addresses or [],
        'dhcp4': dhcp4,
        'dhcp6': dhcp6,
        'accept_ra': accept_ra,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate build bash script for Netplan Interface #{standard_name}.\n{template_error}',
        )
        return False, template_error

    # Prepare public bridge build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated build bash script for Netplan Interface #{standard_name}\n{bash_script}',
    )

    success, output = False, ''
    # Deploy the bash script to the Host
    if host in ['127.0.0.1', None, '', 'localhost']:
        ret = comms_lsh(payload=bash_script)
    else:
        ret = comms_ssh(host_ip=host, payload=bash_script, username='robot')

    if ret['channel_code'] != CHANNEL_SUCCESS:
        return False, f'{ret["channel_message"]}\nError: {ret["channel_error"]}'
    if ret['payload_code'] != SUCCESS_CODE:
        return False, f'{ret["payload_message"]}\nError: {ret["payload_error"]}'

    return True, ret["payload_message"]
