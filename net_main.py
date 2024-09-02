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

BUILD_TEMPLATE = 'net_main/commands/build.sh.j2'
LOGGER = 'primitives.net_main'


def build(
        host: str,
        ifname: str,
        config_filepath=None,
        ips=None,
        mac=None,
        routes=None,
        vlan=None,
) -> Tuple[bool, str]:
    """
    description:
        It setups either an ethernet interface or a VLAN interface on Linux server as system service that
        persists against reboots.
        1. Creates UP bash script file
           - /usr/local/bin/net_main-{{ ifname }}-up.sh for ethernet interface
           - /usr/local/bin/net_main-{{ ifname }}{{ vlan }}-up.sh for vlan interface
        2. Creates DOWN bash script file
           - /usr/local/bin/net_main-{{ ifname }}-down.sh for ethernet interface
           - /usr/local/bin/net_main-{{ ifname }}{{ vlan }}-down.sh for vlan interface
        3. Creates system service script file
           - /etc/systemd/system/net_main-{{ ifname }}.service for ethernet interface
           - /etc/systemd/system/net_main-{{ ifname }}{{ vlan }}.service for vlan interface
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
            type: string
        ips:
            description: List of IP addresses defined on ethernet/vlan interface, in string format as `ip/mask`
            type: list
        mac:
            description: MAC address of the interface
            type: string
        routes:
            description: List of route objects defined on ethernet interface
            type: list
            properties:
                to:
                    description: IP addresses to which the traffic is destined
                    type: string
                via:
                    description: IP addresses from which the traffic is directed
                    type: string
        vlan:
            description: The number used to tag the VLAN interface from ifname interface.
            type: int

    return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for net_main.build')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # messages
    interface_name = f'{ifname}{vlan}'
    messages = {
        '000': f'Successfully built interface #{interface_name} in the network',
        '300': f'Failed to create UP bash script file /usr/local/bin/net_main-{interface_name}-up.sh',
        '301': f'Failed to create DOWN bash script file /usr/local/bin/net_main-{interface_name}-down.sh',
        '302': f'Failed to create System Service file /etc/systemd/system/net_main-{interface_name}.service',
        '303': f'Failed to enable and start the net_main-{interface_name}.service.',
    }

    template_data = {
        'ifname': ifname,
        'ips': ips,
        'mac': mac,
        'messages': messages,
        'routes': routes,
        'vlan': vlan,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate build bash script for Interface #{interface_name}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated build bash script for Interface #{interface_name}\n{bash_script}')

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
            f'Interface #{interface_name} on #{host} build commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{interface_name} on #{host} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output


def quiesce(
        host: str,
        ifname: str,
        config_filepath=None,
        vlan=None,
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
            type: str
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            type: string
        vlan:
            description: The number used to tag the vlan interface from ifname interface.
            type: int

    return:
        description: |
            A tuple with a boolean flag stating whether the quiesce was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.quiesce')
    logger.debug('Compiling data for net_main.quiesce')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # messages
    interface_name = f'{ifname}{vlan}'
    messages = {
        '000': f'Successfully quiesced interface #{interface_name} in the network',
        '300': f'Failed to disable the net_main-{interface_name}.service.',
        '301': f'Failed to stop the net_main-{interface_name}.service.',
    }

    template_data = {
        'interface_name': interface_name,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate quiesce bash script for Interface #{interface_name}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated quiesce bash script for Interface #{interface_name}\n{bash_script}')

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
            f'Interface #{interface_name} on #{host} quiesce commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{interface_name} on #{host} quiesce commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output


def restart(
        host: str,
        ifname: str,
        config_filepath=None,
        vlan=None,
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
        vlan:
            description: The number used to tag the vlan interface from ifname interface.
            type: int

    return:
        description: |
            A tuple with a boolean flag stating whether the restart was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.restart')
    logger.debug('Compiling data for net_main.restart')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # messages
    interface_name = f'{ifname}{vlan}'
    messages = {
        '000': f'Successfully restarted interface #{interface_name} in the network',
        '300': f'Failed to enable the net_main-{interface_name}.service.',
        '301': f'Failed to start the net_main-{interface_name}.service.',
    }

    template_data = {
        'interface_name': interface_name,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(f'Failed to generate restart bash script for Interface #{interface_name}.\n{template_error}')
        return False, template_error

    # Prepare build config
    bash_script = template.render(**template_data)
    logger.debug(f'Generated restart bash script for Interface #{interface_name}\n{bash_script}')

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
            f'Interface #{interface_name} on #{host} restart commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Interface #{interface_name} on #{host} restart commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
