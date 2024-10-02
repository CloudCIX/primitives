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
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter
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

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        # Enabled Podnet
        1000: f'Successfully created network name space {name} on both PodNet nodes.',
        3021: f'Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace payload: ',
        3022: f'Failed to connect to the enabled PodNet from the config file {config_file} for create_namespace payload: ',
        3023: f'Failed to run create_namespace payload on the enabled PodNet. Payload exited with status ',
        3024: f'Failed to run enable_forwardv4 payload in name space {name} on the enabled PodNet. Payload exited with status ',
        3025: f'Failed to run enable_forwardv4 payload on enabled PodNet. Payload exited with status ',
        3026: f'Failed to connect to the enabled PodNet from the config file {config_file} for enable_forwardv6 payload: ',
        3027: f'Failed to run enable_forwardv6 payload on the enabled PodNet. Payload exited with status ',
        3028: f'Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo payload: ',
        3029: f'Failed to run enable_lo payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3030: f'Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3031: f'Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1 payload: ',
        3032: f'Failed to run create_lo1 payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3033: f'Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3034: f'Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1_address payload: ',
        3035: f'Failed to run create_lo1_address payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3036: f'Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo1 payload: ',
        3037: f'Failed to run enable_lo1 payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',

        # Disabled Podnet
        3051: f'Failed to connect to the disabled PodNet from the config file {config_file} for find_namespace payload: ',
        3052: f'Failed to connect to the disabled PodNet from the config file {config_file} for create_namespace payload: ',
        3053: f'Failed to run create_namespace payload on the disabled PodNet. Payload exited with status ',
        3054: f'Failed to connect to the disabled PodNet from the config file {config_file} for enable_forwardv4 payload: ',
        3055: f'Failed to run enable_forwardv4 payload on disabled PodNet. Payload exited with status ',
        3056: f'Failed to connect to the disabled PodNet from the config file {config_file} for enable_forwardv6 payload: ',
        3057: f'Failed to run enable_forwardv6 payload on disabled PodNet. Payload exited with status ',
        3058: f'Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo payload: ',
        3059: f'Failed to run enable_lo payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3060: f'Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3061: f'Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1 payload: ',
        3062: f'Failed to run create_lo1 payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3063: f'Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3064: f'Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1_address payload: ',
        3065: f'Failed to run create_lo1_address payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3066: f'Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo1 payload: ',
        3067: f'Failed to run enable_lo1 payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
    }

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    name_grepsafe = name.replace('.', '\.')
    lo_addr_grepsafe = lo_addr.replace('.', '\.')

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'find_namespace':     f"ip netns list | grep -w '{name_grepsafe}'",
            'create_namespace':   f"ip netns add {name}",
            'enable_forwardv4':   f"ip netns exec {name} sysctl --write net.ipv4.ip_forward=1",
            'enable_forwardv6':   f"ip netns exec {name} sysctl --write net.ipv6.conf.all.forwarding=1",
            'enable_lo':          f"ip netns exec {name} ip link set dev lo up",
            'find_lo1':           f"ip netns exec {name} ip link show lo1",
            'create_lo1':         f"ip netns exec {name} ip link add lo1 type dummy",
            'find_lo1_address':   f"ip netns exec {name} ip addr show lo1 | grep -w '{lo_addr_grepsafe}'",
            'create_lo1_address': f"ip netns exec {name} ip addr add {lo_addr} dev lo1",
            'enable_lo1':         f"ip netns exec {name} ip link set dev lo1 up",
        }

        ret = rcc.run(payloads['find_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        create_namespace = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create this name space if it exists already
            create_namespace = False
        fmt.add_successful('find_namespace', ret)

        if create_namespace:
            # call rcc comms_ssh on enabled PodNet
            ret = rcc.run(payloads['create_namespace'])

            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('create_namespace', ret)

        ret = rcc.run(payloads['enable_forwardv4'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        fmt.add_successful('enable_forwardv4', ret)

        ret = rcc.run(payloads['enable_forwardv6'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        fmt.add_successful('enable_forwardv6', ret)

        ret = rcc.run(payloads['enable_lo'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        fmt.add_successful('enable_lo', ret)

        ret = rcc.run(payloads['find_lo1'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
        create_lo1 = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create lo1 if it exists already
            create_lo1 = False
        fmt.add_successful('find_lo1', ret)

        if create_lo1:
            ret = rcc.run(payloads['create_lo1'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
            fmt.add_successful('create_lo1', ret)

        ret = rcc.run(payloads['find_lo1_address'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+13}: " + messages[prefix+13]), fmt.successful_payloads
        create_lo1_address = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to assign this address to lo1 if it has been assigned already
            create_lo1_address = False
        fmt.add_successful('find_lo1_address', ret)

        if create_lo1_address:
            ret = rcc.run(payloads['create_lo1_address'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+14}: " + messages[prefix+14]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+15}: " + messages[prefix+15]), fmt.successful_payloads
            fmt.add_successful('create_lo1_address', ret)

        ret = rcc.run(payloads['enable_lo1'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+16}: " + messages[prefix+16]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+17}: " + messages[prefix+17]), fmt.successful_payloads
        fmt.add_successful('enable_lo1', ret)

        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]



def scrub(
        name: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Removes a network name space from PodNet HA.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
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

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        1100: f'Successfully removed name space {name} from both PodNet nodes.',
        3121: f'Failed to connect to the enabled PodNet for find_namespace payload: ',
        3122: f'Failed to connect to the enabled PodNet for delete_namespace_payload: ',
        3123: f'Failed to run delete_namespace payload on the enabled PodNet. Payload exited with status ',

        3131: f'Failed to connect to the disabled PodNet for find_namespace_payload: ',
        3132: f'Failed to connect to the disabled PodNet for delete_namespace_payload: ',
        3133: f'Failed to run delete_namespace payload on the disabled PodNet. Payload exited with status ',
    }

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    name_grepsafe = name.replace('.', '\.')

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'find_namespace':     f"ip netns list | grep -w '{name_grepsafe}'",
            'delete_namespace':   f"ip netns delete {name}",
        }

        ret = rcc.run(payloads['find_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, prefix+1), fmt.successful_payloads
        delete_namespace = True
        if ret["payload_code"] != SUCCESS_CODE:
            # No need to delete this name space if it is gone already
            delete_namespace = False
        fmt.add_successful('find_namespace', ret)

        if delete_namespace:
            # call rcc comms_ssh on enabled PodNet
            ret = rcc.run(payloads['delete_namespace'])

            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('delete_namespace', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3130, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]


def read(
        name: str,
        lo_addr='169.254.169.254',
        config_file=None,
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
            both machines' current state and (3) the output or success message.
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
                  lo_status:
                    description: link status of lo interface
                    type: string
                  lo1_status:
                    description: link status of lo1 interface
                    type: string
                  lo1_address:
                    description: ip addr output for lo1 interface (filtered for lo_addr)
                    type: string
          message:
            description: a status or error message, depending on whether the operation succeeded or not.
            type: string
    """

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        1200: f'1200: Successfully retrieved network name space {name} status from both PodNet nodes.',
        3221: f'Failed to connect to the enabled PodNet for find_namespace_payload: ',
        3222: f'Failed to run find_namespace payload on the enabled PodNet. Payload exited with status ',
        3223: f'Failed to connect to the enabled PodNet for find_forwardv4_payload',
        3224: f'Failed to run find_forwardv4 payload on the enabled PodNet. Payload exited with status ',
        3225: f'Unexpected value for sysctl net.ipv4.ip_forward in name space {name} on the enabled PodNet: ',
        3226: f'Failed to connect to the enabled PodNet for find_forwardv6_payload: ',
        3227: f'Failed to run find_forwardv6_payload on the enabled PodNet. Payload exited with status ',
        3228: f'Unexpected value for sysctl net.ipv6.conf.all.forwarding on enabled PodNet: ',
        3229: f'Failed to connect to the enabled PodNet for find_lo_status payload: ',
        3230: f'Failed to run payload find_lo_status. Payload exited with status ',
        3231: f'Failed to connect to the enabled PodNet for find_lo1 payload: ',
        3232: f'Failed to run payload find_lo1. Payload exited with status ',
        3233: f'Failed to connect to the enabled PodNet for find_lo1_status payload: ',
        3234: f'Failed to run payload find_lo1_status. Payload exited with status ',
        3235: f'Failed to connect to the enabled PodNet for find_lo1_address payload: ',
        3236: f'Failed to run payload find_lo1_address. Payload exited with status ',

        3251: f'Failed to connect to the disabled PodNet for find_namespace_payload: ',
        3252: f'Failed to find_namespace payload on the disabled PodNet. Payload exited with status ',
        3253: f'Failed to connect to the disabled PodNet for find_forwardv4_payload.: ',
        3254: f'Failed to run find_forwardv4_payload on the disabled PodNet. Payload exited with status ',
        3255: f'Unexpected value for sysctl net.ipv4.ip_forward on disabled PodNet: ',
        3256: f'Failed to connect to the disabled PodNet for find_forwardv6_payload: ',
        3257: f'Failed to run find_forwardv6 payload on disabled PodNet. Payload exited with status ',
        3258: f'Unexpected value for sysctl net.ipv6.conf.all.forwarding on disabled PodNet: ',
        3259: f'Failed to connect to the disabled PodNet for find_lo_status payload: ',
        3260: f'Failed to run payload find_lo_status. Payload exited with status ',
        3261: f'Failed to connect to the disabled PodNet for find_lo1 payload: ',
        3262: f'Failed to run payload find_lo1. Payload exited with status ',
        3263: f'Failed to connect to the disabled PodNet for find_lo1_status payload: ',
        3264: f'Failed to run payload find_lo1_status. Payload exited with status ',
        3265: f'Failed to connect to the disabled PodNet for find_lok_address payload: ',
        3266: f'Failed to run payload find_lo1_address. Payload exited with status ',
    }


    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, None, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    name_grepsafe = name.replace('.', '\.')
    lo_addr_grepsafe = lo_addr.replace('.', '\.')

    def run_podnet(podnet_node, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[podnet_node] = {}

        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'find_namespace':     f"ip netns list | grep -w '{name_grepsafe}'",
            'find_forwardv4':     f"ip netns exec {name} sysctl -n net.ipv4.ip_forward",
            'find_forwardv6':     f"ip netns exec {name} sysctl -n net.ipv6.conf.all.forwarding",
            'find_lo_status':     f"ip netns exec {name} ip link show lo | grep UP,LOWER_UP",
            'find_lo1':           f"ip netns exec {name} ip link show lo1",
            'find_lo1_status':    f"ip netns exec {name} ip link show lo | grep UP,LOWER_UP",
            'find_lo1_address':   f"ip netns exec {name} ip addr show lo1 | grep -w '{lo_addr_grepsafe}'",
        }

        ret = rcc.run(payloads['find_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('find_namespace', ret)

        ret = rcc.run(payloads['find_forwardv4'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3} : " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4}: " + messages[prefix+4])
        else:
            data_dict[podnet_node]['forwardv4'] = ret["payload_message"].strip()
            fmt.add_successful('find_forwardv4', ret)
            if ret["payload_message"].strip() != "1":
                retval = False
                fmt.store_payload_error(ret, f"{prefix+5}: "
                    + messages[prefix+5]
                    + f'`{ret["payload_message"].strip()}`. Payload exit status: ')

        ret = rcc.run(payloads['find_forwardv6'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+6}: " + messages[prefix+6])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+7}: " + messages[prefix+7])
        else:
            data_dict[podnet_node]['forwardv6'] = ret["payload_message"].strip()
            fmt.add_successful('find_forwardv6', ret)
            if ret["payload_message"].strip() != "1":
                retval = False
                fmt.store_payload_error(ret, f"{prefix+8}: "
                    + messages[prefix+8]
                    + f'`{ret["payload_message"].strip()}`. Payload exit status: ')

        ret = rcc.run(payloads['find_lo_status'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+9}: " + messages[prefix+9])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+10}: " + messages[prefix+10])
        else:
            fmt.add_successful('find_lo_status', ret)
            data_dict[podnet_node]['lo_status'] = ret["payload_message"].strip()

        ret = rcc.run(payloads['find_lo1'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+11}: " + messages[prefix+11])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+12}: " + messages[prefix+12])
        else:
            fmt.add_successful('find_lo1', ret)

        ret = rcc.run(payloads['find_lo1_status'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+13}: " + messages[prefix+13])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+14}: " + messages[prefix+14])
        else:
            fmt.add_successful('find_lo1_status', ret)
            data_dict[podnet_node]['lo1_status'] = ret["payload_message"].strip()

        ret = rcc.run(payloads['find_lo1_address'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+15}: " + messages[prefix+15])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+16}: " + messages[prefix+16])
        else:
            fmt.add_successful('find_lo1_address', ret)
            data_dict[podnet_node]['lo1_address'] = ret["payload_message"].strip()

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_enabled, msg_list_enabled, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})

    retval_disabled, msg_list_disabled, successful_payloads, data_dict = run_podnet(disabled, 3250, successful_payloads, data_dict)

    msg_list = list()
    msg_list.extend(msg_list_enabled)
    msg_list.extend(msg_list_disabled)

    if not (retval_enabled and retval_disabled):
        return False, data_dict, msg_list
    else:
       return True, data_dict, (messages[1200])
