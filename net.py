"""
Primitive for Global Network (Netplan interface config) on PodNet
"""
# stdlib
import logging
from typing import Tuple
# lib
from cloudcix.rcc import deploy_lsh, deploy_ssh, CouldNotConnectException
# local
from .utils import JINJA_ENV, check_template_data


__all__ = [
    'build',
]

BUILD_TEMPLATE = 'net/commands/build.sh.j2'
LOGGER = 'primitives.net'


def build(
        host: str,
        identifier: str,
        ips: list,
        config_filepath=None,
        mac=None,
        name=None,
        routes=None,
) -> Tuple[bool, str]:
    """
    description:
        appends the netplan config for the given interface in /etc/netplan/00-installer-config.yaml

    parameters:
        host:
            description: IP or dns name of the host where the interface is created on.
            type: string
            required: True
        identifier:
            description: The interface's logical name on the machine.
            type: string
            required: True
        ips:
            description: List of IPaddresses defined on this interface, in string format
            type: list
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: False
            type: string
        mac:
            description: macaddress of the interface
            type: string
        name:
            description: The interface's custom name on the machine.
            type: string
        routes:
            description: List of route objects defined on this interface
            type: list
            properties:
                to:
                    description: IP addresses to which the traffic is destined
                    type: string
                via:
                    description: IP addresses from which the traffic is directed
    return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for net.build')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # netplan file
    netplan_filepath = '/etc/netplan/00-installer-config.yaml'

    # messages
    messages = {
        '000': f'Successfully added interface #{identifier} to {netplan_filepath}',
        '300': f'Failed to backup {netplan_filepath} to {netplan_filepath}.bak',
        '301': f'Failed to add interface #{identifier} to {netplan_filepath}',
        '302': f'Failed to Generate netplan config.',
        '303': f'Failed to Apply netplan config.',
    }

    template_data = {
        'identifier': identifier,
        'ips': ips,
        'mac': mac,
        'messages': messages,
        'name': name,
        'netplan_filepath': netplan_filepath,
        'routes': routes,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate build bash script for Netplan Interface #{identifier}.\n{template_error}',
        )
        return False, template_error

    # Prepare public bridge build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated build bash script for Netplan Interface #{identifier}\n{bash_script}',
    )

    success, output = False, ''
    # Deploy the bash script to the Host
    try:
        if host in ['127.0.0.1', None, '', 'localhost']:
            stdout, stderr = deploy_lsh(
                payload=bash_script,
            )
        else:
            stdout, stderr = deploy_ssh(
                host_ip=host,
                payload=bash_script,
                username='robot',
            )
    except CouldNotConnectException as e:
        return False, str(e)

    if stdout:
        logger.debug(
            f'Netplan interface #{identifier} on #{host} build commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Netplan interface #{identifier} on #{host} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
