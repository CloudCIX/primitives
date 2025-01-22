# stdlib
import ipaddress
import json
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    address_range: str,
    device: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Add IP address range to an interface inside a namespace

    parameters:
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true
        address_range:
            description: IP address range to be added
            type: string
            required: true
        device:
            description: Device to assign the IP address range to.
            type: string
            required: true


    return:
        description: |
            A tuple with a boolean flag indicating if the IP address range assignment was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully added {address_range} to {device} inside namespace {namespace} ',
        1001: f'Address range {address_range} already exists inside namespace {namespace} ',

        3021: f'Failed to connect to the enabled PodNet for find_address_range payload:  ',
        3022: f'Failed to connect to the enabled PodNet for address_range_add payload:  ',
        3023: f'Failed to run address_range_add payload on the enabled PodNet. Payload exited with status ',

        3051: f'Failed to connect to the disabled PodNet for find_address_range payload:  ',
        3052: f'Failed to connect to the disabled PodNet for address_range_add payload:  ',
        3053: f'Failed to run address_range_add payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

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


    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )


        ip_ver = ipaddress.ip_interface(address_range)
        if ip_ver.version == 4:
          version = ''
        else:
          version = '-6'

        address_range_grepsafe = address_range.replace('.', '\.')
   
        payloads = {
            'find_address_range' : f'ip netns exec {namespace} ip address show | grep {address_range_grepsafe}',
            'address_range_add' : f'ip netns exec {namespace} ip {version} addr add {address_range} dev {device}',
        }

        ret = rcc.run(payloads['find_address_range'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            #If the address_range already exists returns info and true state
            return True, fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('find_address_range', ret)

        ret = rcc.run(payloads['address_range_add'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('address_range_add', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled,3020,{})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def read(
    address_range: str,
    device: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        Checks for an IP address range in a VRF namespace on the PodNet node.

    parameters:
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true
        address_range:
            description: IP address range to be removed
            type: string
            required: true
        device:
            description: Device to remove the IP address range from.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              process status and file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: structure holding process status/config file contents from machine <podnet_ip>
                type: object
                  process_status:
                  type: string
                    description: |
                      The contents of the dnsmasq.hosts file for this namespace.
                      May be None upon any read errors.
                    type: string
                  config_file:
                    type: string
                    description: |
                      The contents of the nginx configuration file. May be
                      None upon any read errors.
                  config_file:
                    type: string
                    description: |
                      The contents of the nginx hosts file. May be
                      None upon any read errors.
          errors:
            type: array
            description: List of success/error messages produced while reading state
            items:
              type: string
    """

    # Define message
    messages = {
        1200: f'Address range interface is present on both PodNet nodes.',

        3221: f'Failed to connect to the enabled PodNet for read_address_range payload: ',
        3222: f'Failed to run read_address_range payload on the enabled PodNet. Payload exited with status ',

        3251: f'Failed to connect to the disabled PodNet for read_address_range payload: ',
        3252: f'Failed to run read_address_range payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

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

        address_range_grepsafe = address_range.replace('.', '\.')

        # define payloads

        payloads = {
          'read_address_range': f'ip netns exec {namespace} ip address show {device} | grep -A 1 {address_range_grepsafe}'
        }

        ret = rcc.run(payloads['read_address_range'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
        else:
            data_dict[podnet_node]['config'] = ret["payload_message"].strip()
            fmt.add_successful('read_address_range', ret)

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


def scrub(
    address_range: str,
    device: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Remove IP address range from an interface inside a namespace

    parameters:
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true
        address_range:
            description: IP address range to be removed
            type: string
            required: true
        device:
            description: Device to remove the IP address range from.
            type: string
            required: true


    return:
        description: |
            A tuple with a boolean flag indicating if the IP address range removal was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully removed address_range {address_range} inside namespace {namespace} ',
        1101: f'Address range {address_range} does not exist ',

        3121: f'Failed to connect to the enabled PodNet for find_address_range payload:  ',
        3122: f'Failed to connect to the enabled PodNet for address_range_del payload:  ',
        3123: f'Failed to run address_range_del payload on the enabled PodNet. Payload exited with status ',

        3151: f'Failed to connect to the disabled PodNet for find_address_range payload:  ',
        3152: f'Failed to connect to the disabled PodNet for address_range_del payload:  ',
        3153: f'Failed to run address_range_del payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

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

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'stdout', 'payload_error': 'stderr'},
            successful_payloads
        )

        ip_ver = ipaddress.ip_interface(address_range)
        if ip_ver.version == 4:
          version = ''
        else:
          version = '-6'

        address_range_grepsafe = address_range.replace('.', '\.')

        payloads = {
                'find_address_range': f'ip netns exec {namespace} ip address show | grep {address_range_grepsafe}',
                'address_range_del':  f'ip netns exec {namespace} ip {version} addr del {address_range} dev {device}'
        }


        ret = rcc.run(payloads['find_address_range'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            #If the address_range already does NOT exists returns info and true state
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('find_address_range', ret)

        ret = rcc.run(payloads['address_range_del'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('address_range_del', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]
