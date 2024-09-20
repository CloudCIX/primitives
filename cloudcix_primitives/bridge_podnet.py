"""
Primitive for Public Subnet Bridge on PodNet
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
]

BUILD_TEMPLATE = 'bridge_podnet/commands/build.sh.j2'
HEAD_TEMPLATE = 'bridge_podnet/commands/head.sh.j2'
LOGGER = 'primitives.bridge_podnet'


def head(
        identifier: str,
        config_filepath=None,
) -> Tuple[bool, str]:
    """
    description:
        Verifies if br-{identifier} bridge exists on PodNet's Master Namespace

    parameters:
        identifier:
            description: string to identify the Bridge.
            type: string
        config_filepath:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: False
            type: string

    :return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """
    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.head')
    logger.debug('Compiling data for bridge_podnet.head')

    # hardware data
    if config_filepath is None:
        config_filepath = f'{utils.primitives_directory}/config.json'
    podnets = utils.get_podnets(config_filepath)

    # messages
    messages = {
        '000': f'Bridge #{identifier} exists on PodNet',
        '300': f'Bridge #{identifier} NOT found on PodNet',
    }

    template_data = {
        'identifier': identifier,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = utils.JINJA_ENV.get_template(HEAD_TEMPLATE)
    template_verified, template_error = utils.check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate head bash script for PodNet Bridge #{identifier}.\n{template_error}',
        )
        return False, template_error

    # Prepare public bridge build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated head bash script for PodNet Bridge #{identifier}\n{bash_script}',
    )

    total_success = []
    total_output = ''
    for podnet in podnets:
        host_ip = utils.get_mgmt_ipv6(podnet['mgmt'])
        success, output = False, ''
        # Deploy the bash script to the Host
        try:
            stdout, stderr = deploy_ssh(
                host_ip=host_ip,
                payload=bash_script,
                username='robot',
            )
        except CouldNotConnectException as e:
            # TODO Trigger PodNet failover
            return False, str(e)

        if stdout:
            logger.debug(
                f'PodNet Bridge #{identifier} on #{host_ip} head commands generated stdout.'
                f'\n{stdout}',
            )
            for code, message in messages.items():
                if message in stdout:
                    output += message
                    if int(code) < 100:
                        success = True

        if stderr:
            logger.error(
                f'PodNet Bridge #{identifier} on #{host_ip} head commands generated stderr.'
                f'\n{stderr}',
            )
            output += stderr

        total_success.append(success)
        total_output += total_output
    return any(total_success), total_output


def build(
        address_range: str,
        identifier: str,
        config_filepath=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates br-{identifier} bridge on PodNet's Master Namespace using IP commands.

    parameters:
        address_range:
            description: Public Bridge's address range, eg '91.103.0.1/24'.
            type: string
        identifier:
            description: string to identify the Bridge.
            type: string
        config_filepath:
            description:
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            required: False
            type: string

    return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for bridge_podnet.build')

    # hardware data
    if config_filepath is None:
        config_filepath = f'{utils.primitives_directory}/config.json'
    podnets = utils.get_podnets(config_filepath)

    # messages
    messages = {
        '000': f'Successfully created Bridge #{identifier} on PodNet',
    }

    template_data = {
        'address_range': address_range,
        'identifier': identifier,
        'messages': messages,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = utils.JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = utils.check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate build bash script for PodNet Bridge #{identifier}.\n{template_error}',
        )
        return False, template_error

    # Prepare public bridge build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated build bash script for PodNet Bridge #{identifier}\n{bash_script}',
    )

    total_success = []
    total_output = ''
    for podnet in podnets:
        host_ip = utils.get_mgmt_ipv6(podnet['mgmt'])
        success, output = False, ''
        # Deploy the bash script to the Host
        try:
            stdout, stderr = deploy_ssh(
                host_ip=host_ip,
                payload=bash_script,
                username='robot',
            )
        except CouldNotConnectException as e:
            # TODO Trigger PodNet failover
            return False, str(e)

        if stdout:
            logger.debug(
                f'PodNet Bridge #{identifier} on #{host_ip} build commands generated stdout.'
                f'\n{stdout}',
            )
            for code, message in messages.items():
                if message in stdout:
                    output += message
                    if int(code) < 100:
                        success = True

        if stderr:
            logger.error(
                f'PodNet Bridge #{identifier} on #{host_ip} build commands generated stderr.'
                f'\n{stderr}',
            )
            output += stderr

        total_success.append(success)
        total_output += total_output
    return any(total_success), total_output
