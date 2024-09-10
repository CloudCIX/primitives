"""
Primitive to Build and Delete directories on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CouldNotConnectException
# local


__all__ = [
    'build',
]

SUCCESS_CODE = 0


def build(
        path: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates directory on PodNet HA.

    parameters:
        path:
            description: The path to be created on the PodNet
            type: string
            required: true
        config_file:
            description: The path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created directory {path}',
        2111: f'2011: Config file {path} loaded.',
        3000: f'3000: Failed to create directory {path}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file}',
        3022: f'3022: Failed to create directory {path} on the enabled PodNet'
        3031: f'3031: Successfully created directory {path} on enabled PodNet but Failed to connect to the disabled PodNet '
              f'from the config file {config_file}',
        3032: f'3032: Successfully created directory {path} on enabled PodNet but Failed to create on the disabled PodNet',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

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

    # First run on enabled PodNet
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

    # define payload
    payload = f'mkdir --parents {path}'

    # call rcc comms_ssh on enabled PodNet
    try:
        create_dir, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3021]

    if create_dir.exit_code != SUCCESS_CODE:
        return False, messages[3022]

    # call rcc comms_ssh on disabled PodNet
    try:
        create_dir, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3031]

    if create_dir.exit_code != SUCCESS_CODE:
        return False, messages[3032]

    return True, messages[1000]
