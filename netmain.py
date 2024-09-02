"""
Primitive for Global Network Interface (interface config as Service)
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

BUILD_TEMPLATE = 'netmain/commands/build.sh.j2'
QUIESCE_TEMPLATE = 'netmain/commands/quiesce.sh.j2'
RESTART_TEMPLATE = 'netmain/commands/restart.sh.j2'
LOGGER = 'primitives.netmain'


def build(
        host: str,
        ifname: str,
        config_filepath=None,
        ips=None,
        mac=None,
        routes=None,
        vlans=None,
) -> Tuple[bool, str]:
    """
    description:
        It setups either an ethernet interface with or without VLAN tagged interfaces on Linux server as system service
         that persists against reboots.
        1. Creates UP bash script file
           - /usr/local/bin/netmain-{{ ifname }}-up.sh
        2. Creates DOWN bash script file
           - /usr/local/bin/netmain-{{ ifname }}-down.sh
        3. Creates system service script file
           - /etc/systemd/system/netmain-{{ ifname }}.service
        4. Enables and Starts the service

    parameters:
        host:
            description: IP or DNS name of the host where the interface is created on.
            type: string
            required: True
        ifname:
            description: Name of the interface
            type: string
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            type: string or None
            required: False
        ips:
            description: List of IP addresses defined on ethernet/vlan interface, in string format as `ip/mask`
            type: list or None
            required: False
        mac:
            description: MAC address of the interface
            type: string or None
            required: False
        routes:
            description: List of route objects defined on ethernet interface
            type: list or None
            required: False
            properties:
                to:
                    description: IP addresses to which the traffic is destined
                    type: string
                    required: True
                via:
                    description: IP addresses from which the traffic is directed
                    type: string
                    required: True
        vlans:
            description: List of vlan interface objects
            type: list
            required: False
            properties:
                vlan:
                    description: The number used to tag the ifname interface.
                    type: int
                    required: True
                ips:
                    description: List of IP addresses defined on vlan interface
                    type: list of strings
                    required: False
                routes:
                    description: List of route objects defined on vlan interface
                    type: list of strings
                    required: False
                    properties:
                        to:
                            description: IP addresses to which the traffic is destined
                            type: string
                            required: True
                        via:
                            description: IP addresses from which the traffic is directed
                            type: string
                            required: True

    return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for netmain.build')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    if routes is None:
        routes = []
    if ips is None:
        ips = []
    if vlans is None:
        vlans = []

    # messages
    messages = {
        '000': f'Successfully built interface #{ifname} in the network',
        '300': f'Failed to create UP bash script file /usr/local/bin/net_main-{ifname}-up.sh',
        '301': f'Failed to create DOWN bash script file /usr/local/bin/net_main-{ifname}-down.sh',
        '302': f'Failed to create System Service file /etc/systemd/system/net_main-{ifname}.service',
        '303': f'Failed to enable and start the net_main-{ifname}.service.',
    }

    template_data = {
        'ifname': ifname,
        'ips': ips,
        'mac': mac,
        'messages': messages,
        'routes': routes,
        'vlans': vlans,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate build bash script for Interface #{ifname}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated build bash script for Interface #{ifname}\n{bash_script}')

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
            f'Interface #{ifname} on #{host} build commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{ifname} on #{host} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output


def quiesce(
        host: str,
        ifname: str,
        config_filepath=None,
) -> Tuple[bool, str]:
    """
    description:
        Disables and Stops the service

    parameters:
        host:
            description: IP or dns name of the host where the interface is created on.
            type: string
            required: True
        ifname:
            description: Name of the interface
            type: string
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            type: string
            required: False

    return:
        description: |
            A tuple with a boolean flag stating whether the quiesce was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.quiesce')
    logger.debug('Compiling data for netmain.quiesce')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # messages
    messages = {
        '000': f'Successfully quiesced interface #{ifname} in the network',
        '300': f'Failed to disable and stop the net_main-{ifname}.service.',
    }

    template_data = {
        'ifname': ifname,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(QUIESCE_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate quiesce bash script for Interface #{ifname}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated quiesce bash script for Interface #{ifname}\n{bash_script}')

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
            f'Interface #{ifname} on #{host} quiesce commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{ifname} on #{host} quiesce commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output


def restart(
        host: str,
        ifname: str,
        config_filepath=None,
) -> Tuple[bool, str]:
    """
    description:
        Enables and Starts the service

    parameters:
        host:
            description: IP or dns name of the host where the interface is created on.
            type: string
            required: True
        ifname:
            description: Name of the interface
            type: str
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            type: string

    return:
        description: |
            A tuple with a boolean flag stating whether the restart was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.restart')
    logger.debug('Compiling data for netmain.restart')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # messages
    messages = {
        '000': f'Successfully restarted interface #{ifname} in the network',
        '300': f'Failed to enable and start the net_main-{ifname}.service.',
    }

    template_data = {
        'ifname': ifname,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(RESTART_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate restart bash script for Interface #{ifname}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated restart bash script for Interface #{ifname}\n{bash_script}')

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
            f'Interface #{ifname} on #{host} restart commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{ifname} on #{host} restart commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
