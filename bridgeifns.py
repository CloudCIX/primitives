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
    'scrub',
]

SUCCESS_CODE = 0


def build(
    bridgename: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Creates a veth link on the main namespace and connects it to a bridge.
        Then, it moves one end of the link to a VRF network namespace and sets the interface up.

    parameters:
        bridgename:
            description: The name of the bridge on the main namespace.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the veth link creation was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created VETH from Namespace: {namespace} to Bridge: {bridgename}',
        2111: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to create VETH from Namespace: {namespace} to Bridge: {bridgename}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file}',
        ##3022: f'3022: Failed to create directory {path} on the enabled PodNet',
        ##3031: f'3031: Successfully created directory {path} on enabled PodNet but Failed to connect to the disabled PodNet '
        ##    f'from the config file {config_file}',
        ##3032: f'3032: Successfully created directory {path} on enabled PodNet but Failed to create on the disabled PodNet',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

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

    # Define payload

    payload_bridge_exists = f'ip link show {bridgename}'
    payload_namespace_exists = f'ip link show {bridgename}'
    payload_1 = f'ip link add {bridgename}.{namespace} type veth peer name {namespace}.{bridgename}'
    payload_2 = f'ip link set dev {bridgename}.{namespace} master {bridgename}'
    payload_3 = f'ip link set dev {namespace}.{bridgename} netns {namespace}'
    payload_4 = f'ip netns exec {namespace} ip link set dev {namespace}.{bridgename} up'

    #Check if bridgename and namespaces already exists or not
    try:
        #Check if bridgename exists if true it will return 0
        exit_code_bridge, _, _ = comms_ssh(
            host_ip='localhost',
            payload=payload_bridge_exists,
            username='robot',)

        #Check if namespace exists if true it will return 0
        exit_code_namespace, _, _ = comms_ssh(
            host_ip='localhost',
            payload=payload_namespace_exists,
            username='robot',)

        # If there are names then the exit code would be 0 and what we want is both bridge and namespace to give exit code 1
        # which means neither exists.
        if exit_code_namespace and exit_code_bridge:
            already_exists = False
        else:
            already_exists = True

    except CouldNotConnectException:
        already_exists = True

    if already_exists:
        return False, messages[3000]
    else:
        # Step 1: Create veth link
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_1,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3000]

        if exit_code != SUCCESS_CODE:
            return False, messages[3000] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 2: Connect one end to the bridge
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_2,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3000]

        if exit_code != SUCCESS_CODE:
            return False, messages[3000] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 3: Move the other end to the namespace
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_3,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3000]

        if exit_code != SUCCESS_CODE:
            return False, messages[3000] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 4: Set the interface up in the namespace
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_4,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3000]

        if exit_code != SUCCESS_CODE:
            return False, messages[3000] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        return True, messages[1000]

#------------------ IGNORE BELOW -----------------------------------------
def scrub(
    bridgename: str,
    namespace: str,
) -> Tuple[bool, str]:
    """
    description:
        Removes the specified veth interface from the given namespace.

    parameters:
        bridgename:
            description: The name of the bridge associated with the interface.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the interface was successfully deleted,
            and the output or error message.
        type: tuple
    """

    # Define functions
    def InterfaceExists(bridgename):
        try:
            exit_code, _, _ = comms_ssh(
                host_ip='localhost',
                payload=f'ip link show {bridgename}',
                username='robot',)

            if exit_code == 0:
                return True
            else:
                return False

        except CouldNotConnectException:
            return False
    # Define messages
    messages = {
        2000: f'2000: Successfully deleted interface {namespace}.{bridgename} from namespace {namespace}.',
        2001: f'2001: Failed to delete interface {namespace}.{bridgename} from namespace {namespace}.',
    }

    if InterfaceExists(bridgename) or InterfaceExists(namespace):
        message = InterfaceExists(bridgename) *  f'Bridgename: {bridgename} already exists.' + InterfaceExists(namespace) * f'Namespace: {namespace} already exists.'
        return False, message
    else:
        # Remove the interface from the namespace
        payload = f'ip netns exec {namespace} ip link del {namespace}.{bridgename}'

        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[2001]

        if exit_code != SUCCESS_CODE:
            return False, messages[2001] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        return True, messages[2000]

