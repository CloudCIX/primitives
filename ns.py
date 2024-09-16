"""
Primitive to Build, Read and Scrub a network name space on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
# local


__all__ = [
    'build',
    'scrub',
    'read',
]

SUCCESS_CODE = 0


def build(
        name: str,
        lo_addr='169.254.169.254',
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates a network name space on PodNet HA.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
        config_file:
            description: |
                path to the config.json file. Defaults to /opt/robot/config.json if
                not supplied.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define messages

    messages = {
        1000: f'1000: Successfully created network name space {name} on both PodNet nodes.',
        1001: f'1001: Success: name space {name} exists already',
        2111: f'2011: Config file {config_file} loaded.',
        3011: f'3011: Failed to load config file {config_file}, It does not exist.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for create_namespace_payload: ',
        3023: f'3023: Failed to create name space {name} on the enabled PodNet. Payload exited with status ',
        3024: f'3024: Failed to run enable_forwardv4_payload in name space {name} on the enabled PodNet. Payload exited with status ',
        3025: f'3025: Failed to connect to the enabled PodNet from the config file {config_file} for enable_forwardv4_payload: ',
        3026: f'3026: Failed to create name space {name} on the enabled PodNet. Payload exited with status ',
        3027: f'3027: Failed to create name space {name} on the enabled PodNet. Payload exited with status ',
        3028: f'3028: Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo_payload: ',
        3029: f'3029: Failed to run enable_lo_payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3030: f'3030: Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1_payload: ',
        3031: f'3031: Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1_payload: ',
        3032: f'3032: Failed to run create_lo1_payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3033: f'3033: Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1_payload: ',
        3034: f'3034: Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1_address_payload: ',
        3035: f'3035: Failed to run create_lo1_address_payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3036: f'3036: Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo1_payload: ',
        3037: f'3037: Failed to run enable_lo1_payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3051: f'3051: Successfully created name space {namespace} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for find_namespace_payload: ',
        3052: f'3052: Successfully created name space {namespace} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for create_namespace_payload: ',
        3053: f'3053: Successfully created name space {namespace} on enabled PodNet but failed to create on the disabled PodNet. '
               'Payload exited with status ',
        3054: f'3054: Successfully created name space {namespace} on both PodNet nodes but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for enable_forwardv4_payload: ',
        3055: f'3055: Successfully created name space {namespace} on both PodNet nodes but failed to run enable_forwardv4_payload on '
              f'disabled PodNet. Payload exited with status ',
        3056: f'3056: Successfully created name space {namespace} and enabled IPv4 forwarding on both PodNet nodes but failed to '
              f'connect to the disabled PodNet from the config file {config_file} for enable_forwardv6_payload: ',
        3057: f'3057: Successfully created name space {namespace} both PodNet nodes but failed to run enable_forwardv6_payload on '
              f'disabled PodNet. Payload exited with status ',
        3058: f'3058: Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo_payload: ',
        3059: f'3059: Failed to run enable_lo_payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3060: f'3060: Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1_payload: ',
        3061: f'3061: Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1_payload: ',
        3062: f'3062: Failed to run create_lo1_payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3063: f'3063: Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1_payload: ',
        3064: f'3064: Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1_address_payload: ',
        3065: f'3065: Failed to run create_lo1_address_payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3066: f'3066: Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo1_payload: ',
        3067: f'3067: Failed to run enable_lo1_payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
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

    name_grepsafe = name.replace('.', '\.')
    lo_addr_grepsafe = lo_addr.replace('.', '\.')

    # define payloads
    find_namespace_payload = "ip netns list | grep -w '{name_grepsafe}'"
    create_namespace_payload = "ip netns create {name}"
    enable_forwardv4_payload = "ip netns exec {name} sysctl --write net.ipv4.ip_forward=1"
    enable_forwardv6_payload = "ip netns exec {name} sysctl --write net.ipv6.conf.all.forwarding=1"
    enable_lo_payload = "ip netns exec {name} ip link set dev lo up"
    find_lo1_payload = "ip netns exec {name} ip link show lo1"
    add_lo1_payload = "ip netns exec {name} ip link add lo1 type dummy"
    find_lo1_address_payload = "ip netns exec {name} show dev lo1 | grep -w '{lo_addr_grepsafe}'"
    create_lo1_address_payload = "ip netns exec {name} ip addr add {lo_addr} dev lo1"
    enable_lo1_payload = "ip netns exec {name} ip link set dev lo1 up"

    # call rcc comms_ssh on enabled PodNet to find name space
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3021] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_namespace = True
    if ret["payload_code"] == SUCCESS_CODE:
        # No need to create this name space if it exists already
        create_namespace = False

    if create_namespace:
      # call rcc comms_ssh on enabled PodNet
      ret = comms_ssh(
          host_ip=enabled,
          payload=create_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3022] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3023]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to enable IPv4 forwarding
    ret = comms_ssh(
        host_ip=enabled,
        payload=enable_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3024] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3025]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to enable IPv6 forwarding
    ret = comms_ssh(
        host_ip=enabled,
        payload=enable_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3026] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3027]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to enable lo (no need to check - bringing an interface up is idempotent)
    ret = comms_ssh(
        host_ip=enabled,
        payload=enable_lo_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3028] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3029]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to check for lo1
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_lo1_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3030] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_lo1 = True
    if ret["payload_code"] != SUCCESS_CODE:
        # No need to create lo1 if it exists already
        create_lo1 = False

    if create_lo1:
      # call rcc comms_ssh on enabled PodNet
      ret = comms_ssh(
          host_ip=enabled,
          payload=create_lo1_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3031] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3032]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to check for lo1
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_lo1_address_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3033] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_lo1_address = True
    if ret["payload_code"] != SUCCESS_CODE:
        # No need to assign this address name space if it has been assigned already
        create_lo1_address = False

    if create_lo1_address:
        # call rcc comms_ssh on enabled PodNet
        ret = comms_ssh(
            host_ip=enabled,
            payload=create_lo1_address_payload,
            username='robot',
        )
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, messages[3034] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
        if ret["payload_code"] != SUCCESS_CODE:
            return False, messages[3035]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on enabled PodNet to enable lo1 (no need to check - bringing an interface up is idempotent)
    ret = comms_ssh(
        host_ip=enabled,
        payload=enable_lo1_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3036] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3037]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'


    ############################################################## Disabled PodNet ##############################################################


    # call rcc comms_ssh on disabled PodNet to find name space
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3051] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_namespace = True
    if ret["payload_code"] == SUCCESS_CODE:
        # No need to create this name space if it exists already
        create_namespace = False

    if create_namespace:
      # call rcc comms_ssh on disabled PodNet to create name space
      ret = comms_ssh(
          host_ip=disabled,
          payload=create_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3052] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3053]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to enable IPv4 forwarding
    ret = comms_ssh(
        host_ip=disabled,
        payload=enable_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3054] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3055]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to enable IPv6 forwarding
    ret = comms_ssh(
        host_ip=disabled,
        payload=enable_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3056] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3057]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to enable lo (no need to check - bringing an interface up is idempotent)
    ret = comms_ssh(
        host_ip=disabled,
        payload=enable_lo_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3058] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3059]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to check for lo1
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_lo1_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3060] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_lo1 = True
    if ret["payload_code"] != SUCCESS_CODE:
        # No need to create lo1 if it exists already
        create_lo1 = False

    if create_lo1:
      # call rcc comms_ssh on disabled PodNet
      ret = comms_ssh(
          host_ip=disabled,
          payload=create_lo1_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3061] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3062]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to check for lo1
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_lo1_address_payload ,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3063] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    create_lo1_address = True
    if ret["payload_code"] != SUCCESS_CODE:
        # No need to assign this address name space if it has been assigned already
        create_lo1_address = False

    if create_lo1_address:
        # call rcc comms_ssh on disabled PodNet
        ret = comms_ssh(
            host_ip=disabled,
            payload=create_lo1_address_payload,
            username='robot',
        )
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, messages[3064] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
        if ret["payload_code"] != SUCCESS_CODE:
            return False, messages[3065]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet to enable lo1 (no need to check - bringing an interface up is idempotent)
    ret = comms_ssh(
        host_ip=disabled,
        payload=enable_lo1_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3066] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3067]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    return True, messages[1000]


def scrub(
        name: str,
        lo_addr='169.254.169.254',
        config_file = None,
) -> Tuple[bool, str]:
    """
    description:
        Removes a network name space from PodNet HA.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """

    # Define messages

    messages = {
        1100: f'1100: Successfully removed name space {name} from both PodNet nodes.',
        2111: f'2111: Config file {config_file} loaded.',
        3111: f'3111: Failed to load config file {config_file}, It does not exist.',
        3112: f'3112: Failed to get `ipv6_subnet` from config file {config_file}',
        3113: f'3113: Invalid value for `ipv6_subnet` from config file {config_file}',
        3114: f'3114: Failed to get `podnet_a_enabled` from config file {config_file}',
        3115: f'3115: Failed to get `podnet_b_enabled` from config file {config_file}',
        3116: f'3116: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3117: f'3117: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3118: f'3118: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3122: f'3122: Failed to connect to the enabled PodNet from the config file {config_file} for delete_namespace_payload: ',
        3123: f'3123: Failed to delete name space {name} on the enabled PodNet. Payload exited with status ',
        3131: f'3131: Successfully deleted name space {namespace} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for find_namespace_payload: ',
        3132: f'3132: Successfully deleted name space {namespace} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for delete_namespace_payload: ',
        3133: f'3133: Successfully deleted name space {namespace} on enabled PodNet but failed to delete on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3111]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3112]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3113]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3114]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3115]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3116]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3117]
    else:
        return False, messages[3118]

    name_grepsafe = name.replace('.', '\.')

    # define payloads
    find_namespace_payload = "ip netns list | grep -w '{name_grepsafe}'"
    delete_namespace_payload = "ip netns delete {name}"

    # call rcc comms_ssh on enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3121] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    delete_namespace = False
    if ret["payload_code"] == SUCCESS_CODE:
        # No need to delete this name space if it exists already
        delete_namespace = True

    if delete_namespace:
      # call rcc comms_ssh on enabled PodNet
      ret = comms_ssh(
          host_ip=enabled,
          payload=delete_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3122] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3123]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if channel_code != CHANNEL_SUCCESS:
        return False, messages[3131] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'

    delete_namespace = False
    if ret["payload_code"] == SUCCESS_CODE:
        # Only delete this name space if it exists
        delete_namespace = True

    if delete_namespace:
      # call rcc comms_ssh on disabled PodNet
      ret = comms_ssh(
          host_ip=disabled,
          payload=delete_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3132] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3133]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    return True, messages[1000]


def read(
        name: str,
        lo_addr='169.254.169.254',
        config_file = None,
) -> Tuple[bool, dict, str]:
    """
    description:
        Reads cloud-init user data and meta data files for a virtual machine on
        PodNet HA (if any) and returns them.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successfull, (2) a dict containing the data as read from
            the both machines' current state and (3) the output or success message.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: dict structure holding user data from machine <podnet_ip>
                  type: object
                  entry:
                    description: |
                        the entry of the network name space in the list output by
                        `ip netns list`.
                    type: string
                  forwardv4:
                    description: content of net.ipv4.ip_forward sysctl in network name space
                    type: string
                  forwardv6:
                    description: content of net.ipv6.conf.all.forwarding sysctl in network name space
                    type: string
    """

    # Define messages

    messages = {
        1200: f'1200: Successfully retrieved network name space {name} status from both PodNet nodes.',
        2211: f'2211: Config file {config_file} loaded.',
        3211: f'3211: Failed to load config file {config_file}, It does not exist.',
        3212: f'3212: Failed to get `ipv6_subnet` from config file {config_file}',
        3213: f'3213: Invalid value for `ipv6_subnet` from config file {config_file}',
        3214: f'3214: Failed to get `podnet_a_enabled` from config file {config_file}',
        3215: f'3215: Failed to get `podnet_b_enabled` from config file {config_file}',
        3216: f'3216: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3217: f'3217: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3218: f'3218: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3222: f'3222: Failed to find name space {name} on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for find_forwardv4_payload',
        3224: f'3224: Failed to run find_forwardv4_payload {name} on the enabled PodNet. Payload exited with status ',
        3225: f'3225: Unexpected value for sysctl net.ipv4.ip_forward in name space {name} on the enabled PodNet ',
        3226: f'3226: Failed to connect to the enabled PodNet from the config file {config_file} for find_forwardv6_payload: ',
        3227: f'3227: Failed to run {name} find_forwardv4_payload on the enabled PodNet. Payload exited with status ',
        3228: f'3228: Unexpected value for sysctl net.ipv6.conf.all.forwarding in name space {name} on the enabled PodNet ',
        3231: f'3231: Failed to connect to the disabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3232: f'3232: Failed to find name space {name} on the disabled PodNet. Payload exited with status ',
        3233: f'3233: Failed to connect to the disabled PodNet for find_forwardv4_payload.: ',
        3234: f'3234: Failed to run find_forwardv4_payload on the disabled PodNet. Payload exited with status ',
        3235: f'3235: Value for sysctl net.ipv4.ip_forward on disabled PodNet is unexpected ',
        3236: f'3236: Failed to connect to the disabled PodNet from the config file {config_file} for find_forwardv6_payload: ',
        3237: f'3237: Failed to run find_forwardv6_payload on disabled PodNet. Payload exited with status ',
        3238: f'3238: Value for sysctl net.ipv6.conf.all.forwarding on disabled PodNet is unexpected ',
    }

    retval = True
    data_dict = None
    message_list = ()

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        retval = False
        message_list.append(messages[3211])
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        retval = False
        message_list.append(messages[3212])
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        retval = False
        message_list.append(messages[3213])

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    data_dict = {}

    data_dict[podnet_a] = {
        'entry': None,
    }

    data_dict[podnet_b] = {
        'entry': None,
    }

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3214])
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3215])

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        retval = False
        message_list.append(messages[3216])
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        retval = False
        message_list.append(messages[3217])
    else:
        message_list.append(messages[3218])

    if retval == False:
        return retval, data_dict, message_list

    name_grepsafe = name.replace('.', '\.')

    # define payloads
    find_namespace_payload = "ip netns list | grep -w '{name_grepsafe}'"
    find_forwardv4_payload = "ip netns exec {name} sysctl --write net.ipv4.ip_forward | awk '{print $3}"
    find_forwardv6_payload = "ip netns exec {name} sysctl --write net.ipv6.conf.all.forwarding | awk {print $3}'"

    # call rcc comms_ssh for name space retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_namespace_payload,
        username='robot',
    )

    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3221] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3222] + f'{payload_code}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        data_dict[enabled]['entry'] = ret["payload_message"]

    # call rcc comms_ssh for IPv4 forwarding status retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3223] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3224] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3225] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[enabled]['forwardv4'] = ret["payload_message"]

    # call rcc comms_ssh for IPv6 forwarding status retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3226] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3227] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3228] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[enabled]['forwardv6'] = ret["payload_message"]

    # call rcc comms_ssh for name space retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3231] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3232] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        data_dict[disabled]['entry'] = ret["payload_message"]

    # call rcc comms_ssh for IPv4 forwarding status retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3233] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3234] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3235] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[disabled]['forwardv4'] = ret["payload_message"]

    # call rcc comms_ssh for IPv6 forwarding status retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3236] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {channel_message}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3237] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3238] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[disabled]['forwardv6'] = ret["payload_message"]

    message_list.append(messages[1200])
    return retval, data_dict, message_list