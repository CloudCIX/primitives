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
    namespace: str,
    route: dict = {'destination': '', 'gateway': ''},
    config_file=None
) -> Tuple[bool,str]:
    """
    description:
        Creates an IPv4 or IPv6 route accordingly on a namespace

    parameters:
        namespace:
            description: The VRF network namespace identifier which the route will be created on.
            type: string
            required: true
        route:
            description: A dictionary containing the destination and gateway IP addresses which identifies the route that will be created on a namespace.
            type: dict
            required: true

    return:
        description: |
            A tuple with boolean flag indicating if the route was created or exists
            and the ouput or error message.
        type: tuple
    """
    try:
        #change type to ip_address
        dest = ipaddress.ip_network(route["destination"])
    except:
        return False, f'{route["destination"]} is not a valid IP address.'

    if dest.version == 4:
        v = ''
        version = 4
        metric = 512
    elif dest.version == 6:
        v = '-6'
        version = 6
        metric = 1024
    else:
        return False, f'{route["destination"]} is not a valid IP address.'

    # Define message
    messages = {
        1000: f'1000: Successfully created IPv{version} route: {route["destination"]} through gateway: {route["gateway"]} with metric {metric}',
        1001: f'1001: IPv{version} route: {route["destination"]} through gateway: {route["gateway"]} already exists.',

        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file} for payload routens_show:  ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for payload routens_add:  ',
        3023: f'3023: Failed to run routens_add payload on the enabled PodNet. Payload exited with status ',

        3051: f'3051: Failed to connect to the disabled PodNet from the config file {config_file} for payload routens_show:  ',
        3052: f'3052: Failed to connect to the disabled PodNet from the config file {config_file} for payload routens_add:  ',
        3053: f'3053: Failed to run routens_add payload on the disabled PodNet. Payload exited with status ',
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

    destination_grepsafe = route["destination"].replace('.', '\.')

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
            'routens_show': f'ip netns exec {namespace} ip {v} route | grep --word "{destination_grepsafe}"',
            'routens_add' : f'ip netns exec {namespace} ip {v} route add {route["destination"]} via {route["gateway"]} metric {metric}'
            }

        route_exists = False
        ret = rcc.run(payloads['routens_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            route_exists = True
        fmt.add_successful('routens_show', ret)

        if route_exists:
            #If the interface already exists returns info and true state
            return True, fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads

        ret = rcc.run(payloads['routens_add'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('routens_add', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled,3020,{})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def scrub(
    namespace: str,
    route: dict = {'destination': '', 'gateway': ''},
    config_file=None
) -> Tuple[bool,str]:

    """
    description:
        Deletes an IPv4 or IPv6 route accordingly on a namespace

    parameters:
        namespace:
            description: The VRF network namespace identifier which the route will be deleted from.
            type: string
            required: true
        route:
            description: A dictionary containing the destination and gateway IP addresses which identifies the route that will be deleted from a namespace.
            type: dict
            required: true

    return:
        description: |
            A tuple with boolean flag indicating if the route was deleted or doesn't exist
            and the ouput or error message.
        type: tuple
    """

    try:
        #change type to ip_address
        dest = ipaddress.ip_network(route["destination"])
    except:
        return False, f'{route["destination"]} is not a valid IP address.'

    if dest.version == 4:
        v = ''
        version = 4
        metric = 512
    elif dest.version == 6:
        v = '-6'
        version = 6
        metric = 1024
    else:
        return False, f'{route["destination"]} is not a valid IP address.'

    # Define message

    messages = {
        1100: f'1100: Successfully deleted IPv{version} route: {route["destination"]} through gateway: {route["gateway"]} with metric {metric}',
        1101: f'1101: IPv{version} route: {route["destination"]} through gateway: {route["gateway"]} already does not exist.',

        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for payload routens_show:  ',
        3122: f'3122: Failed to connect to the enabled PodNet from the config file {config_file} for payload routens_del:  ',
        3123: f'3123: Failed to run routens_del payload on the enabled PodNet. Payload exited with status ',

        3151: f'3151: Failed to connect to the disabled PodNet from the config file {config_file} for payload routens_show:  ',
        3152: f'3152: Failed to connect to the disabled PodNet from the config file {config_file} for payload routens_del:  ',
        3153: f'3153: Failed to run routens_del payload on the disabled PodNet. Payload exited with status ',
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

    destination_grepsafe = route["destination"].replace('.', '\.')

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
            'routens_show': f'ip netns exec {namespace} ip {v} route | grep --word "{destination_grepsafe}"',
            'routens_del' : f'ip netns exec {namespace} ip {v} route del {route["destination"]} via {route["gateway"]}'
            }
        route_exists = True

        ret = rcc.run(payloads['routens_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            route_exists = False
        fmt.add_successful('routens_show', ret)

        if not route_exists:
            #If the interface already does not exists returns info and true state
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads

        ret = rcc.run(payloads['routens_del'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('routens_del', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled,3220,{})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3250, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]


def read(
    namespace: str,
    route: dict = {'destination': '', 'gateway': ''},
    config_file=None
) -> Tuple[bool,dict,str]:
    """
    description:
        Reads an IPv4 or IPv6 route from a namespace

    parameters:
        namespace:
            description: The VRF network namespace identifier which the route will be deleted from.
            type: string
            required: true
        route:
            description: A dictionary containing the destination and gateway IP addresses which identifies the route that will be deleted from a namespace.
            type: dict
            required: true

    return:
        description: |
            A tuple with boolean flag indicating if the route was deleted or doesn't exist
            and the ouput or error message.
        type: tuple
    """

    try:
        #change type to ip_address
        dest = ipaddress.ip_network(route["destination"])
    except:
        return False, f'{route["destination"]} is not a valid IP address.'

    if dest.version == 4:
        v = ''
        version = 4
        metric = 512
    elif dest.version == 6:
        v = '-6'
        version = 6
        metric = 1024
    else:
        return False, f'{route["destination"]} is not a valid IP address.'
    # Define message

    messages = {
        1200: f'1200: Successfully read IPv{version} route: {route["destination"]} through gateway: {route["gateway"]} with metric {metric}',

        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for payload routens_show:  ',
        3222: f'3222: Failed to run routens_show payload on the enabled PodNet. Payload exited with status ',

        3251: f'3251: Failed to connect to the disabled PodNet from the config file {config_file} for payload routens_show:  ',
        3252: f'3252: Failed to run routens_show payload on the disabled PodNet. Payload exited with status ',
    }


    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, {}, msg
      else:
          return False, {},msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    destination_grepsafe = route["destination"].replace('.', '\.')
    # Define payload

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
            'routens_show': f'ip netns exec {namespace} ip {v} route | grep --word "{destination_grepsafe}"',
        }

        ret = rcc.run(payloads['routens_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('routens_show', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_a, msg_list, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})

    retval_b, msg_list, successful_payloads, data_dict = run_podnet(disabled, 3250, successful_payloads, data_dict)

    if not (retval_a and retval_b):
        return (retval_a and retval_b), data_dict, msg_list
    else:
       return True, data_dict, (messages[1200])
