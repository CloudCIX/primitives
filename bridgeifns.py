# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local


__all__ = [
    'build',
    'scrub',
    'read',
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
        1000: f'1000: Successfully created interface {namespace}.{bridgename} inside namespace {namespace}',
        1001: f'1001: Interface {namespace}.{bridgename} already exists inside namespace {namespace}',
        2111: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to create VETH from Namespace: {namespace} to Bridge: {bridgename}',
        3001: f'3001: Failed to create interface {bridgename}.{namespace}.',
        3002: f'3002: Failed to attach interface {bridgename}.{namespace} to the bridge named {bridgename}',
        3003: f'3003: Failed to isolate {namespace}.{bridgename} to namespace {namespace}',
        3004: f'3004: Failed to bring up interface {namespace}.{bridgename} inside namespace {namespace}',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file}',
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

    # auxiliary payloads
    payload_interface_check = f'ip netns exec {namespace} ip link show {namespace}.{bridgename}'

    # main payloads
    payload_1 = f'ip link add {bridgename}.{namespace} type veth peer name {namespace}.{bridgename}'
    payload_2 = f'ip link set dev {bridgename}.{namespace} master {bridgename}'
    payload_3 = f'ip link set dev {namespace}.{bridgename} netns {namespace}'
    payload_4 = f'ip netns exec {namespace} ip link set dev {namespace}.{bridgename} up'

    #CHECK interface already exists. If there exists the code automatically assume True state then terminate.
    response = comms_ssh(
            host_ip=enabled,
            payload=payload_interface_check,
            username='robot'
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] == SUCCESS_CODE:
        msg = f'{messages[1001]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        return True, msg

    #STEP 1 create VETH
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_1,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3001]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        msg += f'\nPayload Error: {response["payload_error"]}'
        return False, msg
    #STEP 2
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_2,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3002]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        msg += f'\nPayload Error: {response["payload_error"]}'
        return False, msg
    #STEP 3
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_3,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3003]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        msg += f'\nPayload Error: {response["payload_error"]}'
        return False, msg
    #STEP 4
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_4,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3004]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        msg += f'\nPayload Error: {response["payload_error"]}'
        return False, msg

    return True, messages[1000]

def scrub(
    bridgename: str,
    namespace: str,
    config_file=None
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

    # Define message
    messages = {
        1000: f'1000: Successfully removed interface {namespace}.{bridgename} inside namespace {namespace}',
        1001: f'1001: Interface {namespace}.{bridgename} does not exist',
        2111: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to create VETH from Namespace: {namespace} to Bridge: {bridgename}',
        3001: f'3001: Failed to create interface {bridgename}.{namespace}.',
        3002: f'3002: Failed to attach interface {bridgename}.{namespace} to the bridge named {bridgename}',
        3003: f'3003: Failed to isolate {namespace}.{bridgename} to namespace {namespace}',
        3004: f'3004: Failed to bring up interface {namespace}.{bridgename} inside namespace {namespace}',
        3005: f'3005: Failed to delete {namespace}.{bridgename} inside namespace {namespace}.',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file}',
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

    # auxiliary payloads
    payload_interface_check = f'ip netns exec {namespace} ip link show {namespace}.{bridgename}'

    # Define payload
    payload_5 = f'ip netns exec {namespace} ip link del {namespace}.{bridgename}'

    # Check if interface exists returns true if it does not

    response = comms_ssh(
                host_ip=enabled,
                payload=payload_interface_check,
                username='robot')

    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[1001]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        return True, msg

    # Remove interface from namespace
    response = comms_ssh(
        host_ip=enabled,
        payload=payload_5,
        username='robot',
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'{messages[3021]}\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3004]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        msg += f'\nPayload Error: {response["payload_error"]}'
        return False, msg

    return True, messages[1000]

def read(
    bridgename: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        reads a namespace.bridgename interface from namespace.

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
            A tuple with a boolean flag indicating if the interface was successfully read,
            and the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'1000: Successfully read interface {namespace}.{bridgename} inside namespace {namespace}',
        1001: f'1001: Interface {namespace}.{bridgename} does not exist',
        2111: f'2011: Config file {config_file} loaded.',
        3000: f'3000: Failed to read VETH from Namespace: {namespace} to Bridge: {bridgename}',
        3001: f'3001: Failed to create interface {bridgename}.{namespace}.',
        3002: f'3002: Failed to attach interface {bridgename}.{namespace} to the bridge named {bridgename}',
        3003: f'3003: Failed to isolate {namespace}.{bridgename} to namespace {namespace}',
        3004: f'3004: Failed to bring up interface {namespace}.{bridgename} inside namespace {namespace}',
        3005: f'3005: Failed to delete {namespace}.{bridgename} inside namespace {namespace}.',
        3011: f'3011: Failed to load config file {config_file}, It does not exits.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file}',
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
    payload_6 = f'ip netns exec {namespace} ip link show | grep {namespace}.{bridgename}'

    response = comms_ssh(
            host_ip=enabled,
            payload=payload_6,
            username='robot'
    )
    if response['channel_code'] != CHANNEL_SUCCESS:
        msg = f'\nChannel Code: {response["channel_code"]}\nChannel Message: {response["channel_message"]}'
        msg += f'\nChannel Error: {response["channel_error"]}'
        return False, {}, msg
    if response["payload_code"] != SUCCESS_CODE:
        msg = f'{messages[3000]}\nPayload Code: {response["payload_code"]}\nPayload Message: {response["payload_message"]}'
        return False, {}, msg

    dic = {'payloadcode' : response['payload_code'] ,
           'payload_message' : response['payload_message']}

    return True, dic, messages[1000]
